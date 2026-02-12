"""Redis-backed rate limiting middleware."""

from typing import Callable

from fastapi import HTTPException, Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis for distributed state."""

    def __init__(
        self,
        app,
        redis_url: str,
        requests_per_minute: int = 30,
        enabled: bool = True,
        exclude_paths: list[str] | None = None,
    ):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            redis_url: Redis connection URL
            requests_per_minute: Maximum requests allowed per minute per IP
            enabled: Whether rate limiting is enabled
            exclude_paths: Paths to exclude from rate limiting (e.g., ["/health"])
        """
        super().__init__(app)
        self.redis_url = redis_url
        self.rpm = requests_per_minute
        self.enabled = enabled
        self.exclude_paths = exclude_paths or ["/api/v1/health"]
        self._redis: Redis | None = None

        if self.enabled:
            logger.warning(
                "rate_limit_proxy_trust_notice",
                detail="Rate limiting relies on X-Forwarded-For/X-Real-IP headers for client identification. "
                "Ensure a trusted reverse proxy is configured to set these headers in production, "
                "otherwise clients can spoof their IP to bypass rate limits.",
            )

    async def _get_redis(self) -> Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip if disabled or excluded path
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)
        rate_limit_key = f"rate_limit:{client_ip}"

        try:
            redis = await self._get_redis()

            # Increment counter
            current_count = await redis.incr(rate_limit_key)

            # Set expiry on first request in window
            if current_count == 1:
                await redis.expire(rate_limit_key, 60)

            # Get TTL for response headers
            ttl = await redis.ttl(rate_limit_key)

            # Check if over limit
            if current_count > self.rpm:
                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    count=current_count,
                    limit=self.rpm,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
                    headers={
                        "X-RateLimit-Limit": str(self.rpm),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(ttl),
                        "Retry-After": str(ttl),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(self.rpm)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.rpm - current_count))
            response.headers["X-RateLimit-Reset"] = str(ttl)

            return response

        except HTTPException:
            raise
        except Exception as e:
            # If Redis fails, allow request but log warning
            logger.warning("rate_limit_redis_error", error=str(e))
            return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies.

        WARNING: X-Forwarded-For and X-Real-IP headers are trivially spoofable
        by clients when no trusted reverse proxy (e.g., nginx, CloudFront, ALB)
        is configured to strip/overwrite these headers. Without a trusted proxy,
        an attacker can set arbitrary IPs to bypass rate limiting. In production,
        configure a trusted proxy layer and only trust headers set by that proxy.
        """
        # Check X-Forwarded-For header (for requests behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
