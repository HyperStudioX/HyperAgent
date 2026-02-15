"""Shared Anthropic client initialization."""

from anthropic import AsyncAnthropic

from app.config import get_settings


def get_anthropic_client() -> AsyncAnthropic:
    """Get configured async Anthropic client."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("Anthropic API key not configured")
    return AsyncAnthropic(api_key=settings.anthropic_api_key)
