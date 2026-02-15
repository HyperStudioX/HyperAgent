"""Image understanding service using Gemini vision models."""

import base64
from typing import Optional

from app.ai.gemini import get_gemini_client
from app.config import settings


class VisionService:
    """Image understanding using Gemini vision models."""

    async def analyze_image(
        self,
        image_data: bytes | str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """Analyze an image with the given prompt using Gemini.

        Args:
            image_data: Image data as bytes or base64 string
            prompt: Prompt for image analysis
            model: Optional model override (defaults to configured vision model)

        Returns:
            Analysis result as text
        """
        from google.genai import types

        # Use configured model if not specified
        if model is None:
            model = settings.vision_model

        # Create client based on configuration
        client = get_gemini_client()

        # Handle base64 or raw bytes
        if isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            image_bytes = base64.b64decode(image_data)

        # Analyze image
        response = await client.aio.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )

        return response.text


# Global service instance
vision_service = VisionService()
