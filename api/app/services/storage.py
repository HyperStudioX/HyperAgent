"""Storage service for research task persistence."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import ResearchSource, ResearchStep, ResearchTask

logger = get_logger(__name__)


class StorageService:
    """Service for persisting research tasks to PostgreSQL."""

    async def create_task(
        self,
        db: AsyncSession,
        task_id: str,
        query: str,
        depth: str,
        scenario: str,
        user_id: str,
    ) -> ResearchTask:
        """Create a new research task.

        Args:
            db: Database session
            task_id: Unique task identifier
            query: Research query
            depth: Research depth level
            scenario: Research scenario type
            user_id: User identifier (required)

        Returns:
            Created ResearchTask instance
        """
        task = ResearchTask(
            id=task_id,
            query=query,
            depth=depth,
            scenario=scenario,
            status="pending",
            user_id=user_id,
        )
        db.add(task)
        await db.flush()
        logger.info("task_created", task_id=task_id, query=query[:50])
        return task

    async def get_task(self, db: AsyncSession, task_id: str) -> ResearchTask | None:
        """Get a research task by ID with all related data.

        Args:
            db: Database session
            task_id: Task identifier

        Returns:
            ResearchTask if found, None otherwise
        """
        result = await db.execute(
            select(ResearchTask)
            .where(ResearchTask.id == task_id)
            .options(selectinload(ResearchTask.steps), selectinload(ResearchTask.sources))
        )
        return result.scalar_one_or_none()

    async def update_task_status(
        self,
        db: AsyncSession,
        task_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update task status.

        Args:
            db: Database session
            task_id: Task identifier
            status: New status
            error: Optional error message
        """
        task = await self.get_task(db, task_id)
        if task:
            task.status = status
            if error:
                task.error = error
            if status == "completed" or status == "failed":
                task.completed_at = datetime.utcnow()
            await db.flush()
            logger.info("task_status_updated", task_id=task_id, status=status)

    async def update_task_report(
        self,
        db: AsyncSession,
        task_id: str,
        report: str,
    ) -> None:
        """Update task report content.

        Args:
            db: Database session
            task_id: Task identifier
            report: Report content
        """
        task = await self.get_task(db, task_id)
        if task:
            task.report = report
            await db.flush()

    async def add_step(
        self,
        db: AsyncSession,
        task_id: str,
        step_id: str,
        step_type: str,
        description: str,
        status: str,
        output: str | None = None,
    ) -> ResearchStep:
        """Add a research step.

        Args:
            db: Database session
            task_id: Parent task identifier
            step_id: Step identifier
            step_type: Type of step (search, analyze, synthesize, write)
            description: Step description
            status: Step status
            output: Optional step output

        Returns:
            Created ResearchStep instance
        """
        step = ResearchStep(
            id=step_id,
            task_id=task_id,
            type=step_type,
            description=description,
            status=status,
            output=output,
        )
        db.add(step)
        await db.flush()
        return step

    async def update_step_status(
        self,
        db: AsyncSession,
        step_id: str,
        status: str,
        output: str | None = None,
    ) -> None:
        """Update step status.

        Args:
            db: Database session
            step_id: Step identifier
            status: New status
            output: Optional output content
        """
        result = await db.execute(select(ResearchStep).where(ResearchStep.id == step_id))
        step = result.scalar_one_or_none()
        if step:
            step.status = status
            if output:
                step.output = output
            await db.flush()

    async def add_source(
        self,
        db: AsyncSession,
        task_id: str,
        source_id: str,
        title: str,
        url: str,
        snippet: str | None = None,
        content: str | None = None,
        relevance_score: float | None = None,
    ) -> ResearchSource:
        """Add a research source.

        Args:
            db: Database session
            task_id: Parent task identifier
            source_id: Source identifier
            title: Source title
            url: Source URL
            snippet: Source snippet/summary
            content: Full source content
            relevance_score: Relevance score (0-1)

        Returns:
            Created ResearchSource instance
        """
        source = ResearchSource(
            id=source_id,
            task_id=task_id,
            title=title,
            url=url,
            snippet=snippet,
            content=content,
            relevance_score=relevance_score,
        )
        db.add(source)
        await db.flush()
        return source

    async def get_task_dict(self, db: AsyncSession, task_id: str) -> dict[str, Any] | None:
        """Get task as dictionary for API response.

        Args:
            db: Database session
            task_id: Task identifier

        Returns:
            Task data as dictionary or None
        """
        task = await self.get_task(db, task_id)
        if task:
            return task.to_dict()
        return None

    async def update_task_worker_info(
        self,
        db: AsyncSession,
        task_id: str,
        worker_job_id: str,
        worker_name: str | None = None,
    ) -> None:
        """Update task with worker tracking information.

        Args:
            db: Database session
            task_id: Task identifier
            worker_job_id: ARQ job ID
            worker_name: Name of the worker processing the task
        """
        await db.execute(
            update(ResearchTask)
            .where(ResearchTask.id == task_id)
            .values(
                worker_job_id=worker_job_id,
                worker_name=worker_name,
                started_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()
        logger.info(
            "task_worker_info_updated",
            task_id=task_id,
            worker_job_id=worker_job_id,
        )

    async def update_task_progress(
        self,
        db: AsyncSession,
        task_id: str,
        progress: int,
    ) -> None:
        """Update task progress percentage.

        Args:
            db: Database session
            task_id: Task identifier
            progress: Progress percentage (0-100)
        """
        await db.execute(
            update(ResearchTask)
            .where(ResearchTask.id == task_id)
            .values(progress=progress)
        )
        await db.flush()

    async def increment_task_retry(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> int:
        """Increment task retry count and return new value.

        Args:
            db: Database session
            task_id: Task identifier

        Returns:
            New retry count
        """
        task = await self.get_task(db, task_id)
        if task:
            task.retry_count += 1
            await db.flush()
            return task.retry_count
        return 0


# Global instance
storage_service = StorageService()
