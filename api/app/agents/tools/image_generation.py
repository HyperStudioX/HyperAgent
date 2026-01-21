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
    size: Literal[
        "512x512", "768x768", "512x768", "768x512",
        "1024x1024", "1792x1024", "1024x1792"
    ] = Field(
        default="1024x1024",
        description="Image size. Square (1024x1024), landscape (1792x1024), or portrait (1024x1792). Smaller sizes (512x, 768x) also available."
    )
    n: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1-4). More images take longer."
    )
    model: str | None = Field(
        default=None,
        description="Model to use: 'gemini-3-pro-image-preview' (default), 'dall-e-3', 'dall-e-2'. OpenAI models require valid API key."
    )
    quality: Literal["standard", "hd"] = Field(
        default="standard",
        description="Quality setting for DALL-E 3. 'hd' produces more detailed images but takes longer."
    )


@tool(args_schema=GenerateImageInput)
async def generate_image(
    prompt: str,
    size: str = "1024x1024",
    n: int = 1,
    model: str | None = None,
    quality: str = "standard",
) -> str:
    """Generate images from a text description using AI.

    Use this tool when the user asks you to:
    - Create, generate, or make an image
    - Visualize or illustrate a concept
    - Design graphics, logos, or artwork
    - Create visual content for any purpose

    The tool generates high-quality images based on your prompt.
    Be specific and detailed in your prompt for best results.

    Supports multiple providers:
    - Gemini/Imagen (default): Good for general images
    - DALL-E 3: Better for photorealistic images and text

    Args:
        prompt: Detailed description of the desired image
        size: Image dimensions (default 1024x1024)
        n: Number of images to generate (1-4)
        model: Model to use (gemini-3-pro-image-preview, dall-e-3, dall-e-2)
        quality: Quality setting for DALL-E 3 (standard or hd)

    Returns:
        JSON string with base64-encoded images
    """
    logger.info(
        "generate_image_tool_invoked",
        prompt=prompt[:100],
        size=size,
        n=n,
        model=model,
        quality=quality,
    )

    try:
        results = await image_generation_service.generate_image(
            prompt=prompt,
            size=size,
            n=n,
            model=model,
            quality=quality,
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
