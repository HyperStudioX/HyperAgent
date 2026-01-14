"""HyperAgent API application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.base import close_db, init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import health, query

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

    yield

    # Shutdown
    logger.info("application_shutting_down")

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
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        redis_url=settings.redis_url,
        requests_per_minute=settings.rate_limit_rpm,
        enabled=settings.rate_limit_enabled,
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
