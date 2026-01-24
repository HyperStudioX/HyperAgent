"""Shared file operation utilities for E2B sandboxes.

Provides common file operation implementations that can be used by both
execution sandboxes and app development sandboxes.
"""

import base64
from typing import Any

from e2b import AsyncSandbox

from app.core.logging import get_logger

logger = get_logger(__name__)


async def read_file(sandbox: AsyncSandbox, path: str) -> dict[str, Any]:
    """Read a file from the sandbox.

    Args:
        sandbox: E2B sandbox instance
        path: File path in the sandbox

    Returns:
        Dict with success status, content, and metadata
    """
    try:
        content = await sandbox.files.read(path)

        # Try to decode as text
        try:
            if isinstance(content, bytes):
                text_content = content.decode("utf-8")
                is_binary = False
            else:
                text_content = content
                is_binary = False
        except UnicodeDecodeError:
            # Binary file - encode as base64
            text_content = base64.b64encode(content).decode("utf-8")
            is_binary = True

        logger.info("sandbox_file_read", path=path, size=len(content), is_binary=is_binary)

        return {
            "success": True,
            "operation": "read",
            "path": path,
            "content": text_content,
            "is_binary": is_binary,
            "size": len(content),
        }

    except Exception as e:
        logger.error("sandbox_file_read_error", path=path, error=str(e))
        return {
            "success": False,
            "operation": "read",
            "path": path,
            "error": str(e),
        }


async def write_file(
    sandbox: AsyncSandbox,
    path: str,
    content: str,
    is_binary: bool = False,
) -> dict[str, Any]:
    """Write content to a file in the sandbox.

    Args:
        sandbox: E2B sandbox instance
        path: File path in the sandbox
        content: Content to write (base64 for binary files)
        is_binary: Whether content is base64-encoded binary

    Returns:
        Dict with success status and metadata
    """
    if content is None:
        return {
            "success": False,
            "operation": "write",
            "path": path,
            "error": "No content provided for write operation",
        }

    try:
        if is_binary:
            # Decode base64 content
            file_content = base64.b64decode(content)
        else:
            # Text content
            file_content = content.encode("utf-8") if isinstance(content, str) else content

        # Ensure parent directory exists
        parent_dir = "/".join(path.split("/")[:-1])
        if parent_dir:
            await sandbox.commands.run(f"mkdir -p {parent_dir}", timeout=10)

        await sandbox.files.write(path, file_content)

        logger.info("sandbox_file_written", path=path, bytes=len(file_content), is_binary=is_binary)

        return {
            "success": True,
            "operation": "write",
            "path": path,
            "bytes_written": len(file_content),
            "size": len(file_content),
            "is_binary": is_binary,
        }

    except Exception as e:
        logger.error("sandbox_file_write_error", path=path, error=str(e))
        return {
            "success": False,
            "operation": "write",
            "path": path,
            "error": str(e),
        }


async def list_directory(sandbox: AsyncSandbox, path: str) -> dict[str, Any]:
    """List contents of a directory in the sandbox.

    Args:
        sandbox: E2B sandbox instance
        path: Directory path in the sandbox

    Returns:
        Dict with success status and directory entries
    """
    try:
        # Use sandbox command to list directory
        result = await sandbox.commands.run(f"ls -la {path}", timeout=30)

        if result.exit_code != 0:
            return {
                "success": False,
                "operation": "list",
                "path": path,
                "error": result.stderr or "Failed to list directory",
            }

        # Parse ls output
        entries = []
        lines = (result.stdout or "").strip().split("\n")
        for line in lines[1:]:  # Skip the "total" line
            parts = line.split()
            if len(parts) >= 9:
                entry = {
                    "permissions": parts[0],
                    "links": parts[1],
                    "owner": parts[2],
                    "group": parts[3],
                    "size": int(parts[4]) if parts[4].isdigit() else 0,
                    "date": " ".join(parts[5:8]),
                    "name": " ".join(parts[8:]),
                    "is_directory": parts[0].startswith("d"),
                }
                entries.append(entry)

        logger.info("sandbox_directory_listed", path=path, count=len(entries))

        return {
            "success": True,
            "operation": "list",
            "path": path,
            "entries": entries,
            "output": result.stdout,
        }

    except Exception as e:
        logger.error("sandbox_directory_list_error", path=path, error=str(e))
        return {
            "success": False,
            "operation": "list",
            "path": path,
            "error": str(e),
        }


async def delete_path(sandbox: AsyncSandbox, path: str) -> dict[str, Any]:
    """Delete a file or directory from the sandbox.

    Args:
        sandbox: E2B sandbox instance
        path: Path to delete

    Returns:
        Dict with success status
    """
    try:
        # Use rm -rf to handle both files and directories
        result = await sandbox.commands.run(f"rm -rf {path}", timeout=30)

        if result.exit_code != 0:
            return {
                "success": False,
                "operation": "delete",
                "path": path,
                "error": result.stderr or "Failed to delete path",
            }

        logger.info("sandbox_path_deleted", path=path)

        return {
            "success": True,
            "operation": "delete",
            "path": path,
        }

    except Exception as e:
        logger.error("sandbox_path_delete_error", path=path, error=str(e))
        return {
            "success": False,
            "operation": "delete",
            "path": path,
            "error": str(e),
        }


async def check_exists(sandbox: AsyncSandbox, path: str) -> dict[str, Any]:
    """Check if a path exists in the sandbox.

    Args:
        sandbox: E2B sandbox instance
        path: Path to check

    Returns:
        Dict with success status and existence flag
    """
    try:
        result = await sandbox.commands.run(f"test -e {path} && echo 'exists'", timeout=10)

        exists = result.exit_code == 0 and "exists" in (result.stdout or "")

        logger.debug("sandbox_path_checked", path=path, exists=exists)

        return {
            "success": True,
            "operation": "exists",
            "path": path,
            "exists": exists,
        }

    except Exception as e:
        logger.error("sandbox_path_exists_error", path=path, error=str(e))
        return {
            "success": False,
            "operation": "exists",
            "path": path,
            "error": str(e),
        }
