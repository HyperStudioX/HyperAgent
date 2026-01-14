"""Research task handler for background worker."""

import uuid
from typing import Any

from redis.asyncio import Redis

from app.agents import agent_supervisor
from app.core.logging import get_logger
from app.db.base import async_session_maker
from app.models.schemas import ResearchDepth, ResearchScenario
from app.services.storage import storage_service
from app.workers.progress import ProgressReporter

logger = get_logger(__name__)

# Progress percentages for each step
STEP_PROGRESS = {
    "search": 25,
    "analyze": 50,
    "synthesize": 75,
    "write": 90,
}


async def run_research_task(
    ctx: dict,
    task_id: str,
    query: str,
    depth: str,
    scenario: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Execute a research task in the background worker.

    This is the main task handler that replaces the inline SSE processing.
    It runs the research agent and updates the database with progress and results.

    Args:
        ctx: ARQ context (contains redis connection, job info)
        task_id: Unique task identifier
        query: Research query string
        depth: Research depth (quick, standard, deep)
        scenario: Research scenario (academic, market, technical, news)
        user_id: User ID for task ownership (required)

    Returns:
        Result dictionary with task_id and status
    """
    redis: Redis = ctx["redis"]
    job_id = ctx["job_id"]
    worker_name = ctx.get("worker_name")

    logger.info(
        "research_task_started",
        task_id=task_id,
        job_id=job_id,
        query=query[:50],
        depth=depth,
        scenario=scenario,
    )

    # Initialize progress reporter for real-time updates
    progress = ProgressReporter(redis, task_id)

    async with async_session_maker() as db:
        try:
            # Update task status to running
            await storage_service.update_task_status(db, task_id, "running")
            await storage_service.update_task_worker_info(db, task_id, job_id, worker_name)
            await db.commit()

            # Emit progress: starting
            await progress.emit("task_started", {"task_id": task_id})

            report_content: list[str] = []
            step_ids: dict[str, str] = {}
            token_buffer: list[str] = []

            # Run the research agent via supervisor
            async for event in agent_supervisor.run(
                query=query,
                mode="research",
                depth=ResearchDepth(depth),
                scenario=ResearchScenario(scenario),
            ):
                if event["type"] == "step":
                    step_type = event["step_type"]

                    if event["status"] == "running":
                        # Create new step in database
                        step_id = str(uuid.uuid4())
                        await storage_service.add_step(
                            db=db,
                            task_id=task_id,
                            step_id=step_id,
                            step_type=step_type,
                            description=event["description"],
                            status="running",
                        )
                        step_ids[step_type] = step_id

                        # Emit progress event
                        await progress.emit_step(
                            step_type=step_type,
                            description=event["description"],
                            status="running",
                            step_id=step_id,
                        )
                    else:
                        # Update existing step status
                        if step_type in step_ids:
                            await storage_service.update_step_status(
                                db, step_ids[step_type], event["status"]
                            )
                            await progress.emit_step(
                                step_type=step_type,
                                description=event["description"],
                                status=event["status"],
                                step_id=step_ids[step_type],
                            )

                    # Update progress percentage based on step
                    if step_type in STEP_PROGRESS:
                        await storage_service.update_task_progress(
                            db, task_id, STEP_PROGRESS[step_type]
                        )
                        await progress.emit_progress(STEP_PROGRESS[step_type], step_type)

                    await db.commit()

                elif event["type"] == "source":
                    # Create source in database
                    source_id = str(uuid.uuid4())
                    await storage_service.add_source(
                        db=db,
                        task_id=task_id,
                        source_id=source_id,
                        title=event["title"],
                        url=event["url"],
                        snippet=event.get("snippet"),
                        relevance_score=event.get("relevance_score"),
                    )
                    await db.commit()

                    # Emit source event
                    await progress.emit_source(
                        source_id=source_id,
                        title=event["title"],
                        url=event["url"],
                        snippet=event.get("snippet"),
                    )

                elif event["type"] == "token":
                    report_content.append(event["content"])
                    token_buffer.append(event["content"])

                    # Batch token updates to reduce Redis calls (every 10 tokens)
                    if len(token_buffer) >= 10:
                        await progress.emit_token_batch("".join(token_buffer))
                        token_buffer.clear()

            # Flush remaining tokens
            if token_buffer:
                await progress.emit_token_batch("".join(token_buffer))

            # Save final report
            full_report = "".join(report_content)
            await storage_service.update_task_report(db, task_id, full_report)
            await storage_service.update_task_status(db, task_id, "completed")
            await storage_service.update_task_progress(db, task_id, 100)
            await db.commit()

            await progress.emit_complete()

            logger.info(
                "research_task_completed",
                task_id=task_id,
                job_id=job_id,
                report_length=len(full_report),
            )

            return {
                "task_id": task_id,
                "status": "completed",
                "report_length": len(full_report),
            }

        except Exception as e:
            logger.error(
                "research_task_failed",
                task_id=task_id,
                job_id=job_id,
                error=str(e),
            )

            await storage_service.update_task_status(
                db, task_id, "failed", error=str(e)
            )
            await db.commit()

            await progress.emit_error(str(e))

            # Re-raise for ARQ retry mechanism
            raise
