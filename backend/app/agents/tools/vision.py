"""Vision analysis tool for LangGraph agents."""

import asyncio
import base64
import json
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.ai.vision import vision_service

logger = get_logger(__name__)

# Module-level HTTP client for connection reuse (avoids creating new client per request)
_http_client: httpx.AsyncClient | None = None
_http_client_lock = asyncio.Lock()


async def get_http_client() -> httpx.AsyncClient:
    """Get or create a shared HTTP client with connection pooling (async-safe)."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        async with _http_client_lock:
            if _http_client is None or _http_client.is_closed:
                _http_client = httpx.AsyncClient(
                    timeout=30.0,
                    limits=httpx.Limits(
                        max_keepalive_connections=20,
                        max_connections=100,
                        keepalive_expiry=30.0,
                    ),
                )
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client (call on app shutdown)."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


class AnalyzeImageInput(BaseModel):
    """Input schema for image analysis tool."""

    image: str = Field(
        description="The image to analyze. Can be a base64-encoded string or a URL (http/https)."
    )
    prompt: str = Field(
        default="Describe this image in detail.",
        description="What to analyze or look for in the image. Be specific about what information you need."
    )


def _is_url(s: str) -> bool:
    """Check if string is a URL."""
    try:
        result = urlparse(s)
        return result.scheme in ("http", "https")
    except Exception:
        return False


async def _fetch_image_as_base64(url: str) -> str:
    """Fetch an image from URL and return as base64 using pooled HTTP client."""
    client = await get_http_client()
    response = await client.get(url)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")


@tool(args_schema=AnalyzeImageInput)
async def analyze_image(
    image: str,
    prompt: str = "Describe this image in detail.",
) -> str:
    """Analyze an image and answer questions about it using AI vision.

    Use this tool when you need to:
    - Understand or describe what's in an image
    - Extract text, data, or information from images
    - Answer questions about image content
    - Analyze charts, diagrams, screenshots, or photos
    - Identify objects, people, places, or text in images

    The image can be provided as:
    - A base64-encoded string (from file uploads)
    - A URL pointing to an image (http/https)

    Args:
        image: Base64 image data or image URL
        prompt: Question or instruction for analyzing the image

    Returns:
        JSON string with the analysis result
    """
    logger.info(
        "analyze_image_tool_invoked",
        is_url=_is_url(image),
        prompt=prompt[:100],
    )

    try:
        # Handle URL vs base64
        if _is_url(image):
            logger.info("fetching_image_from_url", url=image[:100])
            image_data = await _fetch_image_as_base64(image)
        else:
            image_data = image

        # Call vision service
        analysis = await vision_service.analyze_image(
            image_data=image_data,
            prompt=prompt,
        )

        logger.info(
            "analyze_image_completed",
            prompt=prompt[:50],
            analysis_length=len(analysis),
        )

        return json.dumps({
            "success": True,
            "analysis": analysis,
            "prompt": prompt,
        })

    except httpx.HTTPError as e:
        logger.error(
            "analyze_image_fetch_failed",
            error=str(e),
        )
        return json.dumps({
            "success": False,
            "error": f"Failed to fetch image from URL: {e}",
            "prompt": prompt,
        })
    except Exception as e:
        logger.error(
            "analyze_image_failed",
            prompt=prompt[:50],
            error=str(e),
        )
        return json.dumps({
            "success": False,
            "error": str(e),
            "prompt": prompt,
        })
