"""Project repository for project persistence and item assignment."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import (
    Conversation,
    Project,
    ResearchTask,
)

logger = get_logger(__name__)


class ProjectRepository:
    """Repository for persisting projects and managing item assignments."""

    async def list_for_user(
        self, db: AsyncSession, user_id: str
    ) -> list[dict]:
        """List all projects for a user with conversation/task counts."""
        # Get projects with counts via subqueries
        conv_count = (
            select(func.count(Conversation.id))
            .where(Conversation.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        task_count = (
            select(func.count(ResearchTask.id))
            .where(ResearchTask.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )

        result = await db.execute(
            select(
                Project,
                conv_count.label("conversation_count"),
                task_count.label("research_task_count"),
            )
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
        )
        rows = result.all()
        return [
            {
                **row[0].to_dict(),
                "conversation_count": row[1] or 0,
                "research_task_count": row[2] or 0,
            }
            for row in rows
        ]

    async def create(
        self,
        db: AsyncSession,
        name: str,
        user_id: str,
        description: str | None = None,
        color: str | None = None,
    ) -> Project:
        """Create a new project."""
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            user_id=user_id,
            description=description,
            color=color,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    async def get_for_user(
        self, db: AsyncSession, project_id: str, user_id: str
    ) -> Project | None:
        """Get a project verifying ownership."""
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_items(
        self, db: AsyncSession, project_id: str, user_id: str
    ) -> Project | None:
        """Get a project with all conversations and research tasks."""
        result = await db.execute(
            select(Project)
            .options(
                selectinload(Project.conversations),
                selectinload(Project.research_tasks),
            )
            .where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        project_id: str,
        user_id: str,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> Project | None:
        """Partial update of a project. Returns updated project or None."""
        project = await self.get_for_user(db, project_id, user_id)
        if not project:
            return None
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if color is not None:
            project.color = color
        await db.commit()
        await db.refresh(project)
        return project

    async def delete(
        self, db: AsyncSession, project_id: str, user_id: str
    ) -> bool:
        """Delete a project. Items are SET NULL. Returns True if deleted."""
        project = await self.get_for_user(db, project_id, user_id)
        if not project:
            return False
        await db.delete(project)
        await db.commit()
        return True

    async def assign_items(
        self,
        db: AsyncSession,
        project_id: str,
        user_id: str,
        conversation_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> bool:
        """Assign conversations/tasks to a project. Returns False if project not found."""
        project = await self.get_for_user(db, project_id, user_id)
        if not project:
            return False

        if conversation_ids:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id.in_(conversation_ids),
                    Conversation.user_id == user_id,
                )
            )
            for conv in result.scalars().all():
                conv.project_id = project_id

        if task_ids:
            result = await db.execute(
                select(ResearchTask).where(
                    ResearchTask.id.in_(task_ids),
                    ResearchTask.user_id == user_id,
                )
            )
            for task in result.scalars().all():
                task.project_id = project_id

        await db.commit()
        return True

    async def remove_items(
        self,
        db: AsyncSession,
        project_id: str,
        user_id: str,
        conversation_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> bool:
        """Remove conversations/tasks from a project (set project_id = NULL)."""
        project = await self.get_for_user(db, project_id, user_id)
        if not project:
            return False

        if conversation_ids:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id.in_(conversation_ids),
                    Conversation.user_id == user_id,
                    Conversation.project_id == project_id,
                )
            )
            for conv in result.scalars().all():
                conv.project_id = None

        if task_ids:
            result = await db.execute(
                select(ResearchTask).where(
                    ResearchTask.id.in_(task_ids),
                    ResearchTask.user_id == user_id,
                    ResearchTask.project_id == project_id,
                )
            )
            for task in result.scalars().all():
                task.project_id = None

        await db.commit()
        return True


# Module-level singleton
project_repository = ProjectRepository()
