"""Circuit Breaker Pattern for External API Resilience.

Implements a circuit breaker to prevent cascade failures when external services
(Tavily, Gemini, E2B) become unavailable. The circuit breaker has three states:

- CLOSED: Normal operation, requests pass through
- OPEN: Service is unavailable, requests fail fast without calling the service
- HALF_OPEN: Testing if service has recovered, allows one request through

Usage:
    # As decorator
    @circuit_breaker("tavily")
    async def search(query: str):
        return await tavily_client.search(query)

    # As context manager
    async with CircuitBreaker.get("gemini").call():
        result = await gemini_client.generate(prompt)

    # Manual check
    breaker = CircuitBreaker.get("e2b")
    if breaker.is_available():
        try:
            result = await e2b_client.run(code)
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise
"""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance."""

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: float = 30.0  # Seconds before trying recovery
    success_threshold: int = 2  # Successes in half-open before closing
    half_open_max_calls: int = 1  # Max concurrent calls in half-open state


@dataclass
class CircuitBreakerState:
    """Internal state tracking for a circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    half_open_calls: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker for '{service_name}' is open. "
            f"Retry after {retry_after:.1f} seconds."
        )


class CircuitBreaker:
    """Circuit breaker for external service calls.

    Thread-safe implementation that can be used across async contexts.
    """

    # Global registry of circuit breakers by service name
    _instances: dict[str, "CircuitBreaker"] = {}
    _registry_lock: asyncio.Lock | None = None

    def __init__(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker.

        Args:
            service_name: Unique identifier for the service
            config: Configuration (uses defaults if not provided)
        """
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()

    @classmethod
    def get(cls, service_name: str, config: CircuitBreakerConfig | None = None) -> "CircuitBreaker":
        """Get or create a circuit breaker for a service.

        Args:
            service_name: Unique identifier for the service
            config: Configuration (only used if creating new instance)

        Returns:
            Circuit breaker instance for the service
        """
        if service_name not in cls._instances:
            cls._instances[service_name] = cls(service_name, config)
            logger.info(
                "circuit_breaker_created",
                service=service_name,
                failure_threshold=cls._instances[service_name].config.failure_threshold,
                recovery_timeout=cls._instances[service_name].config.recovery_timeout,
            )
        return cls._instances[service_name]

    @classmethod
    def reset_all(cls) -> None:
        """Reset all circuit breakers (for testing)."""
        for breaker in cls._instances.values():
            breaker.reset()

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitBreakerState()
        logger.info("circuit_breaker_reset", service=self.service_name)

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state.state

    def is_available(self) -> bool:
        """Check if the circuit allows requests.

        Returns:
            True if requests should be attempted, False if failing fast
        """
        if self._state.state == CircuitState.CLOSED:
            return True

        if self._state.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._state.last_failure_time is not None:
                elapsed = time.time() - self._state.last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    # Transition to half-open
                    self._state.state = CircuitState.HALF_OPEN
                    self._state.success_count = 0
                    self._state.half_open_calls = 0
                    logger.info(
                        "circuit_breaker_half_open",
                        service=self.service_name,
                        elapsed=elapsed,
                    )
                    return True
            return False

        if self._state.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self._state.half_open_calls < self.config.half_open_max_calls

        return False

    def time_until_retry(self) -> float:
        """Get seconds until retry is allowed.

        Returns:
            Seconds until circuit may close, or 0 if available
        """
        if self._state.state != CircuitState.OPEN:
            return 0.0

        if self._state.last_failure_time is None:
            return 0.0

        elapsed = time.time() - self._state.last_failure_time
        remaining = max(0.0, self.config.recovery_timeout - elapsed)
        return remaining

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._state._lock:
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1
                self._state.half_open_calls = max(0, self._state.half_open_calls - 1)

                if self._state.success_count >= self.config.success_threshold:
                    # Fully recovered, close the circuit
                    self._state.state = CircuitState.CLOSED
                    self._state.failure_count = 0
                    self._state.success_count = 0
                    logger.info(
                        "circuit_breaker_closed",
                        service=self.service_name,
                        reason="recovery_successful",
                    )
            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._state.failure_count > 0:
                    self._state.failure_count = 0

    async def record_failure(self, error: Exception | None = None) -> None:
        """Record a failed call.

        Args:
            error: Optional exception that caused the failure
        """
        async with self._state._lock:
            self._state.failure_count += 1
            self._state.last_failure_time = time.time()

            if self._state.state == CircuitState.HALF_OPEN:
                # Recovery failed, reopen circuit
                self._state.state = CircuitState.OPEN
                self._state.half_open_calls = 0
                logger.warning(
                    "circuit_breaker_reopened",
                    service=self.service_name,
                    error=str(error) if error else None,
                )
            elif self._state.state == CircuitState.CLOSED:
                if self._state.failure_count >= self.config.failure_threshold:
                    # Open the circuit
                    self._state.state = CircuitState.OPEN
                    logger.warning(
                        "circuit_breaker_opened",
                        service=self.service_name,
                        failure_count=self._state.failure_count,
                        error=str(error) if error else None,
                    )

    @asynccontextmanager
    async def call(self):
        """Context manager for protected calls.

        Usage:
            async with breaker.call():
                result = await external_service.call()

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        if not self.is_available():
            raise CircuitBreakerOpen(
                self.service_name,
                self.time_until_retry(),
            )

        # Track half-open calls
        if self._state.state == CircuitState.HALF_OPEN:
            async with self._state._lock:
                self._state.half_open_calls += 1

        try:
            yield
            await self.record_success()
        except CircuitBreakerOpen:
            # Don't count circuit breaker exceptions as failures
            raise
        except Exception as e:
            await self.record_failure(e)
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get current circuit breaker statistics.

        Returns:
            Dict with state, failure count, and timing info
        """
        return {
            "service": self.service_name,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure_time": self._state.last_failure_time,
            "time_until_retry": self.time_until_retry(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
            },
        }


def circuit_breaker(
    service_name: str,
    config: CircuitBreakerConfig | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to protect async functions with a circuit breaker.

    Args:
        service_name: Unique identifier for the service
        config: Optional circuit breaker configuration

    Returns:
        Decorated function with circuit breaker protection

    Example:
        @circuit_breaker("tavily")
        async def search(query: str) -> list:
            return await tavily_client.search(query)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = CircuitBreaker.get(service_name, config)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with breaker.call():
                return await func(*args, **kwargs)

        # Expose breaker for testing/monitoring
        wrapper.circuit_breaker = breaker  # type: ignore

        return wrapper

    return decorator


# Pre-configured circuit breakers for common services
TAVILY_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    success_threshold=2,
)

GEMINI_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    success_threshold=2,
)

E2B_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,  # E2B is more critical, trip faster
    recovery_timeout=60.0,  # Longer recovery for sandbox service
    success_threshold=1,
)


def get_tavily_breaker() -> CircuitBreaker:
    """Get circuit breaker for Tavily search service."""
    return CircuitBreaker.get("tavily", TAVILY_CONFIG)


def get_gemini_breaker() -> CircuitBreaker:
    """Get circuit breaker for Gemini image generation service."""
    return CircuitBreaker.get("gemini", GEMINI_CONFIG)


def get_e2b_breaker() -> CircuitBreaker:
    """Get circuit breaker for E2B sandbox service."""
    return CircuitBreaker.get("e2b", E2B_CONFIG)
