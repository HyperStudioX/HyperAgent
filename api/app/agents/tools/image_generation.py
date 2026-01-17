"""Image generation tool for LangGraph agents."""

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.image_generation import image_generation_service

logger = get_logger(__name__)


class GenerateImageInput(BaseModel):
    """Input schema for image generation tool."""

    prompt: str = Field(
        description="Detailed description of the image to generate. Be specific about style, composition, colors, and subject."
    )
    size: Literal["1024x1024", "1536x1536", "1024x1536", "1536x1024"] = Field(
        default="1024x1024",
        description="Image size. Square (1024x1024), large square (1536x1536), portrait (1024x1536), or landscape (1536x1024)."
    )
    n: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1-4). More images take longer."
    )


@tool(args_schema=GenerateImageInput)
async def generate_image(
    prompt: str,
    size: str = "1024x1024",
    n: int = 1,
) -> str:
    """Generate images from a text description using AI.

    Use this tool when the user asks you to:
    - Create, generate, or make an image
    - Visualize or illustrate a concept
    - Design graphics, logos, or artwork
    - Create visual content for any purpose

    The tool generates high-quality images based on your prompt.
    Be specific and detailed in your prompt for best results.

    Args:
        prompt: Detailed description of the desired image
        size: Image dimensions (default 1024x1024)
        n: Number of images to generate (1-4)

    Returns:
        JSON string with base64-encoded images
    """
    logger.info(
        "generate_image_tool_invoked",
        prompt=prompt[:100],
        size=size,
        n=n,
    )

    try:
        results = await image_generation_service.generate_image(
            prompt=prompt,
            size=size,
            n=n,
        )

        if not results:
            return json.dumps({
                "success": False,
                "error": "No images generated",
                "prompt": prompt,
            })

        images = [
            {"base64_data": result.base64_data, "index": i}
            for i, result in enumerate(results)
        ]

        logger.info(
            "generate_image_completed",
            prompt=prompt[:50],
            image_count=len(images),
        )

        return json.dumps({
            "success": True,
            "images": images,
            "prompt": prompt,
            "count": len(images),
        })

    except Exception as e:
        logger.error(
            "generate_image_failed",
            prompt=prompt[:50],
            error=str(e),
        )
        return json.dumps({
            "success": False,
            "error": str(e),
            "prompt": prompt,
        })
