"""HyperAgent API application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, files, health, hitl, query, sandbox, sandbox_proxy, skills, tasks
from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.base import close_db, init_db
from app.middleware.rate_limit import RateLimitMiddleware

# Initialize logging first
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("application_starting", app_name=settings.app_name)

    # Initialize database
    # In development, auto-create tables. In production, use migrations.
    try:
        await init_db(create_tables=(settings.environment == "development"))
        logger.info("database_ready")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        # Continue without database in development
        if settings.environment == "production":
            raise

    # Initialize task queue connection
    from app.workers.task_queue import task_queue

    try:
        await task_queue.get_pool()
        logger.info("task_queue_ready")
    except Exception as e:
        logger.error("task_queue_init_failed", error=str(e))
        # Continue without queue in development

    # Initialize skill registry
    from app.db.base import get_db_session
    from app.services.skill_registry import skill_registry

    try:
        async with get_db_session() as db:
            await skill_registry.initialize(db)
            logger.info("skill_registry_ready")
    except Exception as e:
        logger.error("skill_registry_init_failed", error=str(e))
        # Continue without skills in development

    # Initialize guardrails (lazy init on first use, but log config)
    if settings.guardrails_enabled:
        logger.info(
            "guardrails_enabled",
            input=settings.guardrails_input_enabled,
            output=settings.guardrails_output_enabled,
            tool=settings.guardrails_tool_enabled,
            action=settings.guardrails_violation_action,
        )
        if settings.guardrails_violation_action != "block":
            logger.warning(
                "guardrails_non_blocking",
                action=settings.guardrails_violation_action,
                detail="Guardrails violation action is not set to 'block'. Violations will not be prevented.",
            )
    else:
        logger.warning(
            "guardrails_disabled_warning",
            detail="Safety guardrails are disabled. This is not recommended for production.",
        )

    if not settings.auth_enabled:
        logger.warning(
            "auth_disabled_warning",
            detail="Authentication is disabled. All endpoints are publicly accessible.",
        )

    yield

    # Shutdown
    logger.info("application_shutting_down")

    # Close task queue
    try:
        await task_queue.close()
    except Exception as e:
        logger.error("task_queue_close_failed", error=str(e))

    # Close database connections
    try:
        await close_db()
    except Exception as e:
        logger.error("database_close_failed", error=str(e))

    # Close rate limiter Redis connection
    for middleware in app.user_middleware:
        if hasattr(middleware, "cls") and middleware.cls == RateLimitMiddleware:
            # Note: The middleware instance is created by Starlette, not accessible here
            pass

    logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting middleware (must be added before CORS)
# Disabled in development environment
rate_limit_enabled = (
    settings.rate_limit_enabled and settings.environment != "development"
)
app.add_middleware(
    RateLimitMiddleware,
    redis_url=settings.redis_url,
    requests_per_minute=settings.rate_limit_rpm,
    enabled=rate_limit_enabled,
    exclude_paths=["/api/v1/health", "/docs", "/openapi.json"],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(query.router, prefix=settings.api_prefix, tags=["query"])
app.include_router(tasks.router, prefix=settings.api_prefix, tags=["tasks"])
app.include_router(conversations.router, prefix=settings.api_prefix, tags=["conversations"])
app.include_router(files.router, prefix=settings.api_prefix, tags=["files"])
app.include_router(skills.router, prefix=settings.api_prefix, tags=["skills"])
app.include_router(hitl.router, prefix=settings.api_prefix, tags=["hitl"])
app.include_router(sandbox.router, prefix=settings.api_prefix, tags=["sandbox"])
app.include_router(sandbox_proxy.router, prefix=settings.api_prefix, tags=["sandbox-proxy"])
