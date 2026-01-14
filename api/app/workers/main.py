"""
Worker entry point for ARQ background job processing.

Run with: python -m app.workers.main
Or: arq app.workers.main.WorkerSettings
"""

from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.workers.config import get_redis_settings
from app.workers.tasks.research import run_research_task

# Initialize logging
setup_logging(log_level=settings.log_level, log_format=settings.log_format)
logger = get_logger(__name__)


async def startup(ctx: dict) -> None:
    """Worker startup hook - initialize resources."""
    # Note: worker_name is None during startup - ARQ sets it after initialization
    logger.info("worker_initializing")

    # Initialize database connection pool
    from app.db.base import init_db

    await init_db(create_tables=False)

    logger.info("worker_ready", max_jobs=ctx.get("max_jobs", 10))


async def shutdown(ctx: dict) -> None:
    """Worker shutdown hook - cleanup resources."""
    logger.info("worker_shutting_down")

    # Close database connections
    from app.db.base import close_db

    await close_db()

    logger.info("worker_stopped")


class WorkerSettings:
    """ARQ Worker Settings - loaded by arq CLI."""

    # Redis connection
    redis_settings = get_redis_settings()

    # Task functions to register
    functions = [
        run_research_task,
    ]

    # Scheduled/cron jobs (uncomment when needed)
    # cron_jobs = [
    #     cron(cleanup_stale_tasks, hour=3, minute=0),
    # ]

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Worker settings
    max_jobs = 10
    job_timeout = 1800  # 30 minutes
    keep_result = 86400  # 24 hours
    poll_delay = 0.5  # Seconds between queue polls

    # Worker name (for identification in logs and monitoring)
    name = "hyperagent-worker"  # Set to custom name like "hyperagent-worker-1" if running multiple workers

    # Retry settings
    max_tries = 3
    retry_delay = 30  # Seconds

    # Logging
    log_results = True


if __name__ == "__main__":
    import asyncio

    from arq import run_worker

    asyncio.run(run_worker(WorkerSettings))
