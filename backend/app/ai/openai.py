"""Shared OpenAI client initialization."""

from openai import AsyncOpenAI

from app.config import get_settings


def get_openai_client() -> AsyncOpenAI:
    """Get configured async OpenAI client."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")
    return AsyncOpenAI(api_key=settings.openai_api_key)
