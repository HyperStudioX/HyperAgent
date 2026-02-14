"""Centralized Redis connection management.

Provides a shared Redis connection pool used by all modules that need Redis
(query streaming, rate limiting, etc.). All modules should use get_redis()
instead of creating their own connections. Call close_redis_pool() during
application shutdown.
"""

from redis.asyncio import Redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    """Get the shared Redis client, creating it on first call.

    Returns:
        Shared Redis client instance
    """
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
        logger.info("redis_pool_created")
    return _redis


async def close_redis_pool() -> None:
    """Close the shared Redis connection pool. Call during app shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("redis_pool_closed")
