"""Utility functions for guardrails."""

import asyncio
from functools import lru_cache
from typing import Any, TypeVar

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def run_with_timeout(
    coro: Any,
    timeout_ms: int | None = None,
    default: T | None = None,
) -> T | None:
    """Run a coroutine with a timeout.

    Args:
        coro: Coroutine to run
        timeout_ms: Timeout in milliseconds (defaults to settings.guardrails_timeout_ms)
        default: Value to return on timeout

    Returns:
        Result of coroutine or default value on timeout
    """
    timeout = (timeout_ms or settings.guardrails_timeout_ms) / 1000.0
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("guardrails_scan_timeout", timeout_ms=timeout_ms)
        return default


@lru_cache(maxsize=1000)
def cached_pattern_check(pattern: str, text: str) -> bool:
    """Cache pattern matching results for repeated checks.

    Args:
        pattern: Pattern to match
        text: Text to check

    Returns:
        Whether pattern matches text
    """
    import re

    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        logger.warning("invalid_pattern", pattern=pattern)
        return False


def truncate_for_logging(text: str, max_length: int = 200) -> str:
    """Truncate text for safe logging.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
