"""Sandbox Files API.

Provides REST endpoints for listing and reading files from sandboxes.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.sandbox import get_execution_sandbox_manager
from app.sandbox.app_sandbox_manager import get_app_sandbox_manager
from app.sandbox.file_operations import list_directory, read_file

logger = get_logger(__name__)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


def _get_sandbox_runtime(session):
    """Get the SandboxRuntime from a session, handling both session types.

    ExecutionSandboxSession has .executor (BaseCodeExecutor) with .get_runtime()
    AppSandboxSession has .sandbox (SandboxRuntime) directly
    """
    if hasattr(session, "executor"):
        return session.executor.get_runtime()
    return session.sandbox


@router.get("/files")
async def list_sandbox_files(
    sandbox_type: Literal["execution", "app"] = Query(
        ..., description="Type of sandbox (execution or app)"
    ),
    task_id: str = Query(..., description="Task/conversation ID for session lookup"),
    path: str = Query("/home/user", description="Directory path to list"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List files in a sandbox directory.

    Requires authentication. The user_id is derived from the authenticated session.

    Args:
        sandbox_type: Type of sandbox (execution for code, app for web apps)
        task_id: Task or conversation ID to identify the sandbox session
        path: Directory path to list (default: /home/user)
        current_user: Authenticated user (from session)

    Returns:
        Dict with success status and file entries
    """
    # Use authenticated user's ID for session lookup
    user_id = current_user.id

    logger.info(
        "list_sandbox_files",
        sandbox_type=sandbox_type,
        task_id=task_id,
        path=path,
        user_id=user_id,
    )

    # Validate path to prevent traversal
    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    try:
        # Get the appropriate sandbox manager
        if sandbox_type == "execution":
            manager = get_execution_sandbox_manager()
        else:
            manager = get_app_sandbox_manager()

        # Get the existing session
        session = await manager.get_session(user_id=user_id, task_id=task_id)
        if not session:
            return {
                "success": False,
                "error": f"No active {sandbox_type} sandbox session found",
                "entries": [],
            }

        # Get the runtime abstraction
        runtime = _get_sandbox_runtime(session)

        # List the directory
        result = await list_directory(runtime, path)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to list directory"),
                "entries": [],
            }

        # Transform entries to frontend format
        entries = []
        for entry in result.get("entries", []):
            # Skip hidden files and special entries
            name = entry.get("name", "")
            if name.startswith(".") or name in (".", ".."):
                continue

            full_path = f"{path.rstrip('/')}/{name}"
            entry_data: dict = {
                "name": name,
                "path": full_path,
                "type": "directory" if entry.get("is_directory") else "file",
                "size": entry.get("size", 0),
            }
            if "modified_at" in entry:
                entry_data["modified_at"] = entry["modified_at"]
            entries.append(entry_data)

        return {
            "success": True,
            "path": path,
            "entries": entries,
            "sandbox_id": session.sandbox_id,
        }

    except Exception as e:
        logger.error("list_sandbox_files_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list sandbox files")


@router.get("/files/content")
async def read_sandbox_file(
    sandbox_type: Literal["execution", "app"] = Query(
        ..., description="Type of sandbox (execution or app)"
    ),
    task_id: str = Query(..., description="Task/conversation ID for session lookup"),
    path: str = Query(..., description="File path to read"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Read file content from a sandbox.

    Requires authentication. The user_id is derived from the authenticated session.

    Args:
        sandbox_type: Type of sandbox (execution for code, app for web apps)
        task_id: Task or conversation ID to identify the sandbox session
        path: File path to read
        current_user: Authenticated user (from session)

    Returns:
        Dict with success status, file content, and metadata
    """
    # Use authenticated user's ID for session lookup
    user_id = current_user.id

    logger.info(
        "read_sandbox_file",
        sandbox_type=sandbox_type,
        task_id=task_id,
        path=path,
        user_id=user_id,
    )

    # Validate path to prevent traversal
    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    try:
        # Get the appropriate sandbox manager
        if sandbox_type == "execution":
            manager = get_execution_sandbox_manager()
        else:
            manager = get_app_sandbox_manager()

        # Get the existing session
        session = await manager.get_session(user_id=user_id, task_id=task_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"No active {sandbox_type} sandbox session found",
            )

        # Get the runtime abstraction
        runtime = _get_sandbox_runtime(session)

        # Read the file
        result = await read_file(runtime, path)

        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Failed to read file"),
            )

        response: dict = {
            "success": True,
            "path": path,
            "content": result.get("content", ""),
            "is_binary": result.get("is_binary", False),
            "size": result.get("size", 0),
            "sandbox_id": session.sandbox_id,
        }
        if result.get("content_type"):
            response["content_type"] = result["content_type"]
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("read_sandbox_file_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to read sandbox file")
