"""File Management Tools for Sandbox.

Provides LangChain tools for file reading, writing, searching, and editing
within sandboxes, using session-based sandbox management for sharing with
code execution.
"""

import json
import shlex

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sandbox import file_operations
from app.sandbox.execution_sandbox_manager import get_execution_sandbox_manager

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class FileReadInput(BaseModel):
    """Input schema for file_read tool."""

    path: str = Field(
        ...,
        description="File path in the sandbox to read",
    )
    offset: int | None = Field(
        default=None,
        description="Line number to start reading from (1-based). Useful for large files.",
    )
    limit: int | None = Field(
        default=None,
        description="Maximum number of lines to read. Useful for large files.",
    )
    # Context fields (injected by agent, not provided by LLM)
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


class FileWriteInput(BaseModel):
    """Input schema for file_write tool."""

    path: str = Field(
        ...,
        description="File path in the sandbox to write to",
    )
    content: str = Field(
        ...,
        description="Content to write to the file",
    )
    mode: str = Field(
        default="overwrite",
        description="Write mode: 'overwrite' (default) replaces file content, 'append' adds to end",
    )
    # Context fields
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


class FileStrReplaceInput(BaseModel):
    """Input schema for file_str_replace tool."""

    path: str = Field(
        ...,
        description="File path in the sandbox to edit",
    )
    old_str: str = Field(
        ...,
        description="The exact string to find and replace (must appear exactly once in the file)",
    )
    new_str: str = Field(
        ...,
        description="The replacement string",
    )
    # Context fields
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


class FileFindByNameInput(BaseModel):
    """Input schema for file_find_by_name tool."""

    pattern: str = Field(
        ...,
        description="File name or glob pattern to search for (e.g., '*.py', 'config.json')",
    )
    path: str = Field(
        default="/",
        description="Directory to search in (default: root '/')",
    )
    # Context fields
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


class FileFindInContentInput(BaseModel):
    """Input schema for file_find_in_content tool."""

    pattern: str = Field(
        ...,
        description="Text or regex pattern to search for in file contents",
    )
    path: str = Field(
        default="/",
        description="Directory to search in (default: root '/')",
    )
    include: str | None = Field(
        default=None,
        description="File pattern filter (e.g., '*.py', '*.js') to limit search scope",
    )
    # Context fields
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_sandbox_runtime(user_id: str | None, task_id: str | None):
    """Get the sandbox runtime for file operations.

    Returns:
        Tuple of (runtime, sandbox_id) or raises on failure.
    """
    from app.sandbox.provider import is_provider_available

    available, issue = is_provider_available("execution")
    if not available:
        raise RuntimeError(issue)

    sandbox_manager = get_execution_sandbox_manager()
    session = await sandbox_manager.get_or_create_sandbox(
        user_id=user_id,
        task_id=task_id,
    )
    executor = session.executor

    if not executor.sandbox_id:
        raise RuntimeError("Sandbox not available")

    return executor.get_runtime(), session.sandbox_id


def _error_result(**kwargs) -> str:
    """Create a JSON error response."""
    return json.dumps({"success": False, **kwargs})


def _success_result(**kwargs) -> str:
    """Create a JSON success response."""
    return json.dumps({"success": True, **kwargs})


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(args_schema=FileReadInput)
async def file_read(
    path: str,
    offset: int | None = None,
    limit: int | None = None,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Read file contents from the sandbox.

    Reads a file and returns its contents. For large files, use offset and
    limit to read specific line ranges.

    Args:
        path: File path in the sandbox
        offset: Line number to start reading from (1-based)
        limit: Maximum number of lines to read
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with file contents or error message
    """
    try:
        runtime, sandbox_id = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        return _error_result(operation="read", path=path, error=str(e))

    try:
        result = await file_operations.read_file(runtime, path)

        if not result["success"]:
            return json.dumps(result)

        content = result["content"]

        # Apply offset/limit for line-based slicing
        if offset is not None or limit is not None:
            lines = content.split("\n")
            start = (offset - 1) if offset and offset > 0 else 0
            end = (start + limit) if limit else None
            content = "\n".join(lines[start:end])
            result["content"] = content
            result["lines_shown"] = len(lines[start:end])
            result["total_lines"] = len(lines)

        result["sandbox_id"] = sandbox_id

        logger.info(
            "file_read_completed",
            path=path,
            sandbox_id=sandbox_id,
            offset=offset,
            limit=limit,
        )

        return json.dumps(result)

    except Exception as e:
        logger.error("file_read_error", path=path, error=str(e))
        return _error_result(operation="read", path=path, error=str(e))


@tool(args_schema=FileWriteInput)
async def file_write(
    path: str,
    content: str,
    mode: str = "overwrite",
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Create or write files in the sandbox.

    Writes content to a file. Supports overwrite (replace) and append modes.
    Creates parent directories automatically if they don't exist.

    Args:
        path: File path in the sandbox
        content: Content to write
        mode: Write mode - 'overwrite' (default) or 'append'
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with success/error message
    """
    if mode not in ("overwrite", "append"):
        return _error_result(
            operation="write",
            path=path,
            error=f"Invalid mode: {mode}. Use 'overwrite' or 'append'.",
        )

    try:
        runtime, sandbox_id = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        return _error_result(operation="write", path=path, error=str(e))

    try:
        if mode == "append":
            # Read existing content first, then append
            existing = await file_operations.read_file(runtime, path)
            if existing["success"]:
                content = existing["content"] + content
            # If file doesn't exist, just write the new content

        result = await file_operations.write_file(runtime, path, content)
        result["sandbox_id"] = sandbox_id
        result["mode"] = mode

        logger.info(
            "file_write_completed",
            path=path,
            sandbox_id=sandbox_id,
            mode=mode,
            bytes_written=result.get("bytes_written"),
        )

        return json.dumps(result)

    except Exception as e:
        logger.error("file_write_error", path=path, error=str(e))
        return _error_result(operation="write", path=path, error=str(e))


@tool(args_schema=FileStrReplaceInput)
async def file_str_replace(
    path: str,
    old_str: str,
    new_str: str,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Perform targeted string replacement in a file.

    Reads the file, verifies that old_str appears exactly once, replaces it
    with new_str, and writes the file back. This is an atomic edit operation
    preferred over rewriting entire files for small changes.

    Args:
        path: File path in the sandbox
        old_str: The exact string to find (must appear exactly once)
        new_str: The replacement string
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with success/error message
    """
    try:
        runtime, sandbox_id = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        return _error_result(operation="str_replace", path=path, error=str(e))

    try:
        # Read the file
        read_result = await file_operations.read_file(runtime, path)
        if not read_result["success"]:
            return _error_result(
                operation="str_replace",
                path=path,
                error=read_result.get("error", "Failed to read file"),
            )

        content = read_result["content"]
        occurrences = content.count(old_str)

        if occurrences == 0:
            return _error_result(
                operation="str_replace",
                path=path,
                error="old_str not found in file. Make sure the string matches exactly.",
            )

        if occurrences > 1:
            return _error_result(
                operation="str_replace",
                path=path,
                error=(
                    f"old_str found {occurrences} times in file. "
                    f"It must appear exactly once for safe replacement."
                ),
            )

        # Perform the replacement
        new_content = content.replace(old_str, new_str, 1)
        write_result = await file_operations.write_file(runtime, path, new_content)

        if not write_result["success"]:
            return _error_result(
                operation="str_replace",
                path=path,
                error=write_result.get("error", "Failed to write file"),
            )

        logger.info(
            "file_str_replace_completed",
            path=path,
            sandbox_id=sandbox_id,
        )

        return _success_result(
            operation="str_replace",
            path=path,
            sandbox_id=sandbox_id,
            message="String replaced successfully.",
        )

    except Exception as e:
        logger.error("file_str_replace_error", path=path, error=str(e))
        return _error_result(operation="str_replace", path=path, error=str(e))


@tool(args_schema=FileFindByNameInput)
async def file_find_by_name(
    pattern: str,
    path: str = "/",
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Find files matching a name or glob pattern in the sandbox.

    Searches for files whose names match the given pattern using the
    find command. Useful for locating files by name or extension.

    Args:
        pattern: File name or glob pattern (e.g., '*.py', 'config.json')
        path: Directory to search in (default: '/')
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with list of matching file paths
    """
    try:
        runtime, sandbox_id = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        return _error_result(operation="find_by_name", pattern=pattern, error=str(e))

    try:
        cmd = (
            f"find {shlex.quote(path)} -name {shlex.quote(pattern)} "
            f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
            f"2>/dev/null | head -100"
        )
        result = await runtime.run_command(cmd, timeout=30)

        files = [
            line.strip()
            for line in (result.stdout or "").strip().split("\n")
            if line.strip()
        ]

        logger.info(
            "file_find_by_name_completed",
            pattern=pattern,
            path=path,
            sandbox_id=sandbox_id,
            count=len(files),
        )

        return _success_result(
            operation="find_by_name",
            pattern=pattern,
            path=path,
            files=files,
            count=len(files),
            sandbox_id=sandbox_id,
        )

    except Exception as e:
        logger.error("file_find_by_name_error", pattern=pattern, error=str(e))
        return _error_result(operation="find_by_name", pattern=pattern, error=str(e))


@tool(args_schema=FileFindInContentInput)
async def file_find_in_content(
    pattern: str,
    path: str = "/",
    include: str | None = None,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Search file contents for a text or regex pattern in the sandbox.

    Uses grep to search for a pattern across files. Returns matching lines
    with file paths and line numbers. Useful for finding code references,
    configuration values, or any text within files.

    Args:
        pattern: Text or regex pattern to search for
        path: Directory to search in (default: '/')
        include: File pattern filter (e.g., '*.py') to limit search scope
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with matching lines, file paths, and line numbers
    """
    try:
        runtime, sandbox_id = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        return _error_result(operation="find_in_content", pattern=pattern, error=str(e))

    try:
        cmd = f"grep -rn {shlex.quote(pattern)} {shlex.quote(path)}"

        if include:
            cmd += f" --include={shlex.quote(include)}"

        # Exclude common noise directories and limit output
        cmd += (
            " --exclude-dir=node_modules --exclude-dir=.git"
            " --exclude-dir=__pycache__ --exclude-dir=.venv"
            " 2>/dev/null | head -100"
        )

        result = await runtime.run_command(cmd, timeout=30)

        matches = [
            line.strip()
            for line in (result.stdout or "").strip().split("\n")
            if line.strip()
        ]

        logger.info(
            "file_find_in_content_completed",
            pattern=pattern,
            path=path,
            include=include,
            sandbox_id=sandbox_id,
            count=len(matches),
        )

        return _success_result(
            operation="find_in_content",
            pattern=pattern,
            path=path,
            matches=matches,
            count=len(matches),
            sandbox_id=sandbox_id,
        )

    except Exception as e:
        logger.error("file_find_in_content_error", pattern=pattern, error=str(e))
        return _error_result(operation="find_in_content", pattern=pattern, error=str(e))
