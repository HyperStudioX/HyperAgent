"""Router for project management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.models.schemas import (
    AssignItemRequest,
    CreateProjectRequest,
    ProjectListResponse,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.repository import project_repository

logger = get_logger(__name__)

router = APIRouter(prefix="/projects")


@router.get("/", response_model=list[ProjectListResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all projects for the current user."""
    try:
        projects = await project_repository.list_for_user(db, current_user.id)
        return [ProjectListResponse(**p) for p in projects]
    except Exception as e:
        logger.error("list_projects_error", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Failed to list projects")


@router.post("/", response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new project."""
    try:
        project = await project_repository.create(
            db,
            name=request.name,
            user_id=current_user.id,
            description=request.description,
            color=request.color,
        )
        return ProjectResponse(**project.to_dict())
    except Exception as e:
        await db.rollback()
        logger.error("create_project_error", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a project with its conversations and research tasks."""
    try:
        project = await project_repository.get_with_items(db, project_id, current_user.id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        data = project.to_dict()
        data["conversations"] = [
            conv.to_dict(include_messages=False) for conv in project.conversations
        ]
        data["research_tasks"] = [
            task.to_dict() for task in project.research_tasks
        ]
        return ProjectResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_project_error",
            error=str(e),
            project_id=project_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to get project")


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a project's name, description, or color."""
    try:
        updated = await project_repository.update(
            db,
            project_id,
            current_user.id,
            name=request.name,
            description=request.description,
            color=request.color,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Project not found")
        return ProjectResponse(**updated.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "update_project_error",
            error=str(e),
            project_id=project_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to update project")


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a project. Items are unlinked but not deleted."""
    try:
        deleted = await project_repository.delete(db, project_id, current_user.id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "deleted", "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "delete_project_error",
            error=str(e),
            project_id=project_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to delete project")


@router.post("/{project_id}/items")
async def assign_items(
    project_id: str,
    request: AssignItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Assign conversations and/or research tasks to a project."""
    try:
        success = await project_repository.assign_items(
            db,
            project_id,
            current_user.id,
            conversation_ids=request.conversation_ids or None,
            task_ids=request.research_task_ids or None,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "assigned", "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "assign_items_error",
            error=str(e),
            project_id=project_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to assign items")


@router.delete("/{project_id}/items")
async def remove_items(
    project_id: str,
    request: AssignItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove conversations and/or research tasks from a project."""
    try:
        success = await project_repository.remove_items(
            db,
            project_id,
            current_user.id,
            conversation_ids=request.conversation_ids or None,
            task_ids=request.research_task_ids or None,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "removed", "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "remove_items_error",
            error=str(e),
            project_id=project_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to remove items")
