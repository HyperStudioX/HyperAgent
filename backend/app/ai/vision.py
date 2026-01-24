"""Image understanding service using Gemini vision models."""

import base64
from typing import Optional

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
        import google.generativeai as genai

        # Use configured model if not specified
        if model is None:
            model = settings.vision_model

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

        # Handle base64 or raw bytes
        if isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            image_bytes = base64.b64decode(image_data)

        # Create model
        gemini_model = genai.GenerativeModel(model)

        # Analyze image
        response = await gemini_model.generate_content_async([
            {"mime_type": "image/png", "data": image_bytes},
            prompt
        ])

        return response.text


# Global service instance
vision_service = VisionService()
