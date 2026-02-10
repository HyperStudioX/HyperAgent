"""Sandbox File Operations Tool.

Provides a LangChain tool for file operations within sandboxes,
using session-based sandbox management for sharing with code execution.
"""

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sandbox import file_operations
from app.sandbox.execution_sandbox_manager import get_execution_sandbox_manager

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
    """Perform file operations in a sandbox.

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
    from app.sandbox.provider import is_provider_available

    available, issue = is_provider_available("execution")
    if not available:
        logger.warning("sandbox_not_available", issue=issue)
        return json.dumps(
            {
                "success": False,
                "operation": operation,
                "path": path,
                "error": issue,
            }
        )

    try:
        # Get or create sandbox session
        sandbox_manager = get_execution_sandbox_manager()
        session = await sandbox_manager.get_or_create_sandbox(
            user_id=user_id,
            task_id=task_id,
        )
        executor = session.executor

        if not executor.sandbox_id:
            return json.dumps(
                {
                    "success": False,
                    "operation": operation,
                    "path": path,
                    "error": "Sandbox not available",
                }
            )

        runtime = executor.get_runtime()

        # Dispatch to operation handler using shared file_operations
        if operation == "read":
            result = await file_operations.read_file(runtime, path)
        elif operation == "write":
            result = await file_operations.write_file(runtime, path, content or "", is_binary)
        elif operation == "list":
            result = await file_operations.list_directory(runtime, path)
        elif operation == "delete":
            result = await file_operations.delete_path(runtime, path)
        elif operation == "exists":
            result = await file_operations.check_exists(runtime, path)
        else:
            result = {
                "success": False,
                "operation": operation,
                "path": path,
                "error": f"Unknown operation: {operation}",
            }

        return json.dumps(result)

    except Exception as e:
        logger.error("sandbox_file_error", operation=operation, path=path, error=str(e))
        return json.dumps(
            {
                "success": False,
                "operation": operation,
                "path": path,
                "error": str(e),
            }
        )


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
    result_json = await sandbox_file.ainvoke(
        {
            "operation": operation,
            "path": path,
            "content": content,
            "is_binary": is_binary,
            "user_id": user_id,
            "task_id": task_id,
        }
    )
    return json.loads(result_json)
