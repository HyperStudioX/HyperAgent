"""Sandbox File Operations Tool.

Provides a LangChain tool for file operations within E2B sandboxes,
using session-based sandbox management for sharing with code execution.
"""

import base64
import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.sandbox.execution_sandbox_manager import get_execution_sandbox_manager
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SandboxFileInput(BaseModel):
    """Input schema for sandbox file operations."""

    operation: Literal["read", "write", "list", "delete", "exists"] = Field(
        ...,
        description="File operation to perform",
    )
    path: str = Field(
        ...,
        description="File or directory path in the sandbox",
    )
    content: str | None = Field(
        default=None,
        description="Content to write (for 'write' operation). Use base64 encoding for binary files.",
    )
    is_binary: bool = Field(
        default=False,
        description="Whether the content is base64-encoded binary data",
    )
    # Context fields (injected by agent, not provided by LLM)
    # These are excluded from the JSON schema so the LLM doesn't see them
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )


@tool(args_schema=SandboxFileInput)
async def sandbox_file(
    operation: Literal["read", "write", "list", "delete", "exists"],
    path: str,
    content: str | None = None,
    is_binary: bool = False,
    # Session context (injected by agent, not provided by LLM)
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Perform file operations in an E2B sandbox.

    Supports reading, writing, listing, deleting files and checking existence.
    Uses the same sandbox session as execute_code for consistency.

    Operations:
    - read: Read file content (returns base64 for binary files)
    - write: Write content to file (accepts base64 for binary)
    - list: List directory contents with metadata
    - delete: Remove file or directory
    - exists: Check if path exists

    Args:
        operation: The file operation to perform
        path: File or directory path in the sandbox
        content: Content to write (for 'write' operation)
        is_binary: Whether content is base64-encoded binary
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with operation results including:
        - success: Whether operation completed successfully
        - operation: The operation performed
        - path: The path operated on
        - content: File content (for 'read')
        - is_binary: Whether content is base64-encoded
        - entries: Directory entries (for 'list')
        - exists: Whether path exists (for 'exists')
        - bytes_written: Number of bytes written (for 'write')
        - error: Error message if operation failed
    """
    # Check for E2B API key
    if not settings.e2b_api_key:
        logger.warning("e2b_api_key_not_configured")
        return json.dumps({
            "success": False,
            "operation": operation,
            "path": path,
            "error": "E2B API key not configured. Set E2B_API_KEY environment variable.",
        })

    try:
        # Get or create sandbox session
        sandbox_manager = get_execution_sandbox_manager()
        session = await sandbox_manager.get_or_create_sandbox(
            user_id=user_id,
            task_id=task_id,
        )
        executor = session.executor

        if not executor.sandbox:
            return json.dumps({
                "success": False,
                "operation": operation,
                "path": path,
                "error": "Sandbox not available",
            })

        sandbox = executor.sandbox

        # Dispatch to operation handler
        operation_handlers = {
            "read": lambda: _read_file(sandbox, path),
            "write": lambda: _write_file(sandbox, path, content, is_binary),
            "list": lambda: _list_directory(sandbox, path),
            "delete": lambda: _delete_path(sandbox, path),
            "exists": lambda: _check_exists(sandbox, path),
        }

        handler = operation_handlers.get(operation)
        if handler:
            return await handler()

        return json.dumps({
            "success": False,
            "operation": operation,
            "path": path,
            "error": f"Unknown operation: {operation}",
        })

    except Exception as e:
        logger.error("sandbox_file_error", operation=operation, path=path, error=str(e))
        return json.dumps({
            "success": False,
            "operation": operation,
            "path": path,
            "error": str(e),
        })


async def _read_file(sandbox, path: str) -> str:
    """Read a file from the sandbox."""
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

        return json.dumps({
            "success": True,
            "operation": "read",
            "path": path,
            "content": text_content,
            "is_binary": is_binary,
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "operation": "read",
            "path": path,
            "error": str(e),
        })


async def _write_file(sandbox, path: str, content: str | None, is_binary: bool) -> str:
    """Write content to a file in the sandbox."""
    if content is None:
        return json.dumps({
            "success": False,
            "operation": "write",
            "path": path,
            "error": "No content provided for write operation",
        })

    try:
        if is_binary:
            # Decode base64 content
            file_content = base64.b64decode(content)
        else:
            # Text content
            file_content = content.encode("utf-8") if isinstance(content, str) else content

        await sandbox.files.write(path, file_content)

        logger.info("sandbox_file_written", path=path, bytes=len(file_content), is_binary=is_binary)

        return json.dumps({
            "success": True,
            "operation": "write",
            "path": path,
            "bytes_written": len(file_content),
            "is_binary": is_binary,
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "operation": "write",
            "path": path,
            "error": str(e),
        })


async def _list_directory(sandbox, path: str) -> str:
    """List contents of a directory in the sandbox."""
    try:
        # Use sandbox command to list directory
        result = await sandbox.commands.run(f"ls -la {path}", timeout=30)

        if result.exit_code != 0:
            return json.dumps({
                "success": False,
                "operation": "list",
                "path": path,
                "error": result.stderr or "Failed to list directory",
            })

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

        return json.dumps({
            "success": True,
            "operation": "list",
            "path": path,
            "entries": entries,
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "operation": "list",
            "path": path,
            "error": str(e),
        })


async def _delete_path(sandbox, path: str) -> str:
    """Delete a file or directory from the sandbox."""
    try:
        # Use rm -rf to handle both files and directories
        result = await sandbox.commands.run(f"rm -rf {path}", timeout=30)

        if result.exit_code != 0:
            return json.dumps({
                "success": False,
                "operation": "delete",
                "path": path,
                "error": result.stderr or "Failed to delete path",
            })

        logger.info("sandbox_path_deleted", path=path)

        return json.dumps({
            "success": True,
            "operation": "delete",
            "path": path,
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "operation": "delete",
            "path": path,
            "error": str(e),
        })


async def _check_exists(sandbox, path: str) -> str:
    """Check if a path exists in the sandbox."""
    try:
        result = await sandbox.commands.run(f"test -e {path} && echo 'exists'", timeout=10)

        exists = result.exit_code == 0 and "exists" in (result.stdout or "")

        logger.debug("sandbox_path_checked", path=path, exists=exists)

        return json.dumps({
            "success": True,
            "operation": "exists",
            "path": path,
            "exists": exists,
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "operation": "exists",
            "path": path,
            "error": str(e),
        })


async def sandbox_file_with_context(
    operation: Literal["read", "write", "list", "delete", "exists"],
    path: str,
    content: str | None = None,
    is_binary: bool = False,
    user_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Perform file operations and return parsed result dict.

    Convenience wrapper that returns a dict instead of JSON string.

    Args:
        operation: File operation to perform
        path: File or directory path
        content: Content to write (for 'write' operation)
        is_binary: Whether content is base64-encoded binary
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        Dict with operation results
    """
    result_json = await sandbox_file.ainvoke({
        "operation": operation,
        "path": path,
        "content": content,
        "is_binary": is_binary,
        "user_id": user_id,
        "task_id": task_id,
    })
    return json.loads(result_json)
