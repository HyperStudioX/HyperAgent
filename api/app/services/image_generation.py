"""Image generation service using Gemini Imagen."""

import base64
from io import BytesIO
from typing import List, Optional

from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import ImageGenerationResult
from app.services.circuit_breaker import CircuitBreakerOpen, get_gemini_breaker

logger = get_logger(__name__)


class ImageGenerationService:
    """Image generation using Gemini Imagen."""

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        safety_filter: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[ImageGenerationResult]:
        """Generate images from a text prompt using Gemini Imagen.

        Args:
            prompt: Text prompt for image generation
            size: Image size (e.g., "1024x1024")
            n: Number of images to generate
            safety_filter: Safety filter level (block_none, block_some, block_most)
            model: Optional model override (defaults to configured image gen model)

        Returns:
            List of generated images
        """
        import google.generativeai as genai

        # Use configured defaults
        if model is None:
            model = settings.image_gen_model
        if safety_filter is None:
            safety_filter = settings.image_gen_safety_filter

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

        # Parse size
        width, height = map(int, size.split("x"))

        # Get circuit breaker for Gemini
        breaker = get_gemini_breaker()

        # Generate images
        imagen_model = genai.ImageGenerationModel(model)
        results = []

        try:
            for _ in range(n):
                async with breaker.call():
                    response = await imagen_model.generate_images_async(
                        prompt=prompt,
                        number_of_images=1,
                        aspect_ratio=f"{width}:{height}" if width == height else "1:1",
                        safety_filter_level=safety_filter,
                    )

                # Convert to base64 PNG
                if response.images:
                    image = response.images[0]
                    # Save PIL image to PNG format in memory buffer
                    buf = BytesIO()
                    image._pil_image.save(buf, format='PNG')
                    buf.seek(0)
                    b64_data = base64.b64encode(buf.getvalue()).decode()
                    results.append(
                        ImageGenerationResult(
                            base64_data=b64_data,
                            url=None,
                            revised_prompt=None,
                        )
                    )

            return results

        except CircuitBreakerOpen as e:
            logger.warning(
                "image_generation_circuit_open",
                prompt=prompt[:50],
                service="gemini",
                retry_after=e.retry_after,
            )
            raise
        except Exception as e:
            logger.error("image_generation_failed", prompt=prompt[:50], error=str(e))
            raise


# Global service instance
image_generation_service = ImageGenerationService()
