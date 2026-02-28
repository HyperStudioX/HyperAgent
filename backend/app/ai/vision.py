"""Image understanding service with multi-provider support (Gemini and OpenAI)."""

import base64
from typing import Optional

from app.ai.gemini import get_gemini_client
from app.ai.openai import get_openai_client
from app.config import settings


class VisionService:
    """Image understanding using Gemini or OpenAI vision models."""

    def _resolve_provider_and_model(self, model: Optional[str]) -> tuple[str, str]:
        """Resolve the effective provider and model for vision.

        Returns:
            (provider, model) tuple.
        """
        if model is not None:
            # Detect provider from explicit model name
            lower = model.lower()
            if lower.startswith("gpt-") or lower.startswith("o"):
                return "openai", model
            return "gemini", model

        provider = settings.vision_model_provider or settings.default_provider
        # Built-in providers
        if provider == "openai":
            return "openai", settings.vision_model_openai
        if provider == "gemini":
            return "gemini", settings.vision_model_gemini
        # Custom providers
        from app.core.provider_registry import provider_registry

        custom = provider_registry.get_custom(provider)
        if custom and custom.vision_model:
            return provider, custom.vision_model
        # Fallback to gemini
        return "gemini", settings.vision_model_gemini

    async def analyze_image(
        self,
        image_data: bytes | str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """Analyze an image with the given prompt.

        Args:
            image_data: Image data as bytes or base64 string
            prompt: Prompt for image analysis
            model: Optional model override (defaults to configured vision model)

        Returns:
            Analysis result as text
        """
        provider, resolved_model = self._resolve_provider_and_model(model)

        # Handle base64 or raw bytes
        if isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            image_bytes = base64.b64decode(image_data)

        if provider == "openai":
            return await self._analyze_with_openai(image_bytes, prompt, resolved_model)
        return await self._analyze_with_gemini(image_bytes, prompt, resolved_model)

    async def _analyze_with_gemini(self, image_bytes: bytes, prompt: str, model: str) -> str:
        """Analyze image using Gemini."""
        from google.genai import types

        client = get_gemini_client()
        response = await client.aio.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )
        return response.text

    async def _analyze_with_openai(self, image_bytes: bytes, prompt: str, model: str) -> str:
        """Analyze image using OpenAI."""
        client = get_openai_client()
        b64 = base64.b64encode(image_bytes).decode()
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content


# Global service instance
vision_service = VisionService()
