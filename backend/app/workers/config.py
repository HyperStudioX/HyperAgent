"""ARQ Worker configuration."""

from datetime import timedelta
from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.config import settings


def get_redis_settings() -> RedisSettings:
    """Parse Redis URL into ARQ RedisSettings."""
    parsed = urlparse(settings.redis_url)

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0) if parsed.path else 0,
    )


class WorkerConfig:
    """ARQ Worker configuration settings."""

    # Redis connection
    redis_settings = get_redis_settings()

    # Queue settings
    queue_name = "hyperagent:tasks"
    max_jobs = 10  # Concurrent jobs per worker
    job_timeout = timedelta(minutes=30)  # Max time per job
    keep_result = timedelta(hours=24)  # Result retention

    # Retry settings
    max_tries = 3
    retry_delay = timedelta(seconds=30)

    # Health check
    health_check_interval = timedelta(seconds=15)
