"""Shared file operation utilities for sandboxes.

Provides common file operation implementations that can be used by both
execution sandboxes and app development sandboxes. Uses the SandboxRuntime
protocol so this module works with any provider (E2B, BoxLite, etc.).
"""

import base64
import shlex
from typing import Any

from app.core.logging import get_logger
from app.sandbox.runtime import SandboxRuntime

logger = get_logger(__name__)


async def read_file(sandbox: SandboxRuntime, path: str) -> dict[str, Any]:
    """Read a file from the sandbox.

    Args:
        sandbox: Sandbox runtime instance
        path: File path in the sandbox

    Returns:
        Dict with success status, content, and metadata
    """
    try:
        content = await sandbox.read_file(path)

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
    sandbox: SandboxRuntime,
    path: str,
    content: str,
    is_binary: bool = False,
) -> dict[str, Any]:
    """Write content to a file in the sandbox.

    Args:
        sandbox: Sandbox runtime instance
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
            await sandbox.run_command(f"mkdir -p {shlex.quote(parent_dir)}", timeout=10)

        await sandbox.write_file(path, file_content)

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


async def list_directory(sandbox: SandboxRuntime, path: str) -> dict[str, Any]:
    """List contents of a directory in the sandbox.

    Args:
        sandbox: Sandbox runtime instance
        path: Directory path in the sandbox

    Returns:
        Dict with success status and directory entries
    """
    try:
        result = await sandbox.run_command(f"ls -la {shlex.quote(path)}", timeout=30)

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
            parts = line.split(None, 8)
            if len(parts) >= 9:
                entry = {
                    "permissions": parts[0],
                    "links": parts[1],
                    "owner": parts[2],
                    "group": parts[3],
                    "size": int(parts[4]) if parts[4].isdigit() else 0,
                    "date": " ".join(parts[5:8]),
                    "name": parts[8],
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


async def delete_path(sandbox: SandboxRuntime, path: str) -> dict[str, Any]:
    """Delete a file or directory from the sandbox.

    Args:
        sandbox: Sandbox runtime instance
        path: Path to delete

    Returns:
        Dict with success status
    """
    # Safety check: refuse to delete root-level directories
    protected_paths = {"/", "/home", "/root", "/etc", "/usr", "/var", "/tmp",
                       "/bin", "/sbin", "/lib", "/opt", "/dev", "/proc", "/sys"}
    normalized = path.rstrip("/") or "/"
    if normalized in protected_paths:
        logger.warning("sandbox_delete_refused_protected_path", path=path)
        return {
            "success": False,
            "operation": "delete",
            "path": path,
            "error": f"Refusing to delete protected path: {path}",
        }

    try:
        result = await sandbox.run_command(f"rm -rf {shlex.quote(path)}", timeout=30)

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


async def check_exists(sandbox: SandboxRuntime, path: str) -> dict[str, Any]:
    """Check if a path exists in the sandbox.

    Args:
        sandbox: Sandbox runtime instance
        path: Path to check

    Returns:
        Dict with success status and existence flag
    """
    try:
        cmd = f"test -e {shlex.quote(path)} && echo 'exists'"
        result = await sandbox.run_command(cmd, timeout=10)

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
