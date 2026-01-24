"""Image generation service with multi-provider support (Gemini and OpenAI)."""

import base64
from enum import Enum
from typing import List, Optional

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import ImageGenerationResult
from app.middleware.circuit_breaker import CircuitBreakerOpen, get_gemini_breaker

logger = get_logger(__name__)


class ImageProvider(str, Enum):
    """Supported image generation providers."""

    GEMINI = "gemini"
    OPENAI = "openai"


class ImageGenerationService:
    """Image generation with multi-provider support (Gemini and OpenAI)."""

    def _is_gemini_model(self, model: str) -> bool:
        """Check if model is a Gemini model (vs Imagen)."""
        return model.startswith("gemini-")

    def detect_provider(self, model: str) -> ImageProvider:
        """Detect which provider to use based on model name.

        Args:
            model: Model name/identifier

        Returns:
            ImageProvider enum value

        Model prefix detection:
        - "gemini-*", "imagen-*" → Gemini
        - "dall-e*", "gpt-image*" → OpenAI
        - Default → config.image_gen_default_provider
        """
        model_lower = model.lower()

        # Gemini models
        if model_lower.startswith("gemini-") or model_lower.startswith("imagen-"):
            return ImageProvider.GEMINI

        # OpenAI models
        if model_lower.startswith("dall-e") or model_lower.startswith("gpt-image"):
            return ImageProvider.OPENAI

        # Fall back to default provider
        default = getattr(settings, "image_gen_default_provider", "gemini")
        return ImageProvider.OPENAI if default == "openai" else ImageProvider.GEMINI

    def _map_to_openai_size(self, size: str) -> str:
        """Map size string to OpenAI supported dimensions.

        OpenAI DALL-E 3 supports: 1024x1024, 1792x1024, 1024x1792
        DALL-E 2 supports: 256x256, 512x512, 1024x1024

        Args:
            size: Size string like "512x512"

        Returns:
            Closest supported OpenAI size
        """
        width, height = map(int, size.split("x"))
        aspect_ratio = width / height

        # Square-ish (aspect ratio close to 1)
        if 0.8 <= aspect_ratio <= 1.2:
            return "1024x1024"
        # Landscape (wider than tall)
        elif aspect_ratio > 1.2:
            return "1792x1024"
        # Portrait (taller than wide)
        else:
            return "1024x1792"

    # Supported aspect ratios for Gemini image generation
    SUPPORTED_ASPECT_RATIOS = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}

    def _parse_aspect_ratio(self, size: str) -> str:
        """Parse size string to supported aspect ratio."""
        width, height = map(int, size.split("x"))

        # Simplify common ratios
        if width == height:
            return "1:1"

        # Calculate GCD for simplified ratio
        from math import gcd
        divisor = gcd(width, height)
        ratio = f"{width // divisor}:{height // divisor}"

        # Check if the calculated ratio is supported
        if ratio in self.SUPPORTED_ASPECT_RATIOS:
            return ratio

        # Fall back to closest supported ratio based on actual ratio
        actual_ratio = width / height
        closest_ratio = "1:1"
        closest_diff = float("inf")

        for supported in self.SUPPORTED_ASPECT_RATIOS:
            w, h = map(int, supported.split(":"))
            supported_ratio = w / h
            diff = abs(actual_ratio - supported_ratio)
            if diff < closest_diff:
                closest_diff = diff
                closest_ratio = supported

        logger.warning(
            "aspect_ratio_fallback",
            original_size=size,
            calculated_ratio=ratio,
            fallback_ratio=closest_ratio,
        )
        return closest_ratio

    def _get_image_size(self, size: str) -> str:
        """Map pixel size to Gemini image size option."""
        width, height = map(int, size.split("x"))
        max_dim = max(width, height)
        if max_dim <= 1024:
            return "1K"
        elif max_dim <= 2048:
            return "2K"
        return "4K"

    async def _generate_with_gemini(
        self,
        client: genai.Client,
        model: str,
        prompt: str,
        aspect_ratio: str,
        image_size: str,
        n: int,
    ) -> List[ImageGenerationResult]:
        """Generate images using Gemini model (generate_content API)."""
        breaker = get_gemini_breaker()
        results = []

        # Only gemini-3-pro-image-preview supports image_size parameter
        supports_image_size = "gemini-3" in model

        logger.debug(
            "gemini_image_generation_request",
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size if supports_image_size else "not_supported",
            prompt=prompt[:50],
        )

        for _ in range(n):
            async with breaker.call():
                # Build image config based on model capabilities
                if supports_image_size:
                    image_config = types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=image_size,
                    )
                else:
                    image_config = types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                    )

                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=image_config,
                    ),
                )

            # Extract image from response parts
            candidates = response.candidates or []
            if not candidates:
                logger.warning(
                    "gemini_image_generation_no_candidates",
                    model=model,
                    prompt=prompt[:50],
                )
                continue

            found_image = False
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None) if content else None
                if not parts:
                    logger.debug(
                        "gemini_image_generation_candidate_no_parts",
                        model=model,
                        finish_reason=getattr(candidate, "finish_reason", None),
                    )
                    continue

                for part in parts:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and getattr(inline_data, "data", None):
                        b64_data = base64.b64encode(inline_data.data).decode()
                        results.append(
                            ImageGenerationResult(
                                base64_data=b64_data,
                                url=None,
                                revised_prompt=None,
                            )
                        )
                        found_image = True
                        break

                if found_image:
                    break

            if not found_image:
                logger.warning(
                    "gemini_image_generation_no_image_parts",
                    model=model,
                    prompt=prompt[:50],
                    candidate_count=len(candidates),
                )

        return results

    async def _generate_with_imagen(
        self,
        client: genai.Client,
        model: str,
        prompt: str,
        aspect_ratio: str,
        safety_filter: str,
        n: int,
    ) -> List[ImageGenerationResult]:
        """Generate images using Imagen model (generate_images API)."""
        breaker = get_gemini_breaker()
        results = []

        for _ in range(n):
            async with breaker.call():
                response = await client.aio.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio=aspect_ratio,
                        safety_filter_level=safety_filter,
                    ),
                )

            if response.generated_images:
                image = response.generated_images[0]
                b64_data = base64.b64encode(image.image.image_bytes).decode()
                results.append(
                    ImageGenerationResult(
                        base64_data=b64_data,
                        url=None,
                        revised_prompt=None,
                    )
                )

        return results

    async def _generate_with_openai(
        self,
        prompt: str,
        size: str,
        n: int,
        model: str,
        quality: str,
    ) -> List[ImageGenerationResult]:
        """Generate images using OpenAI DALL-E models.

        Args:
            prompt: Text prompt for image generation
            size: Image size (will be mapped to OpenAI supported sizes)
            n: Number of images to generate
            model: OpenAI model name (dall-e-2 or dall-e-3)
            quality: Quality setting (standard or hd, DALL-E 3 only)

        Returns:
            List of generated image results
        """
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        openai_size = self._map_to_openai_size(size)
        results = []

        logger.debug(
            "openai_image_generation_request",
            model=model,
            size=openai_size,
            quality=quality,
            n=n,
            prompt=prompt[:50],
        )

        try:
            # DALL-E 3 only supports n=1, so we need to loop
            is_dalle3 = "dall-e-3" in model.lower()
            iterations = n if is_dalle3 else 1
            images_per_request = 1 if is_dalle3 else n

            for _ in range(iterations):
                # Build request parameters
                request_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": openai_size,
                    "n": images_per_request,
                    "response_format": "b64_json",
                }

                # Add quality parameter for DALL-E 3
                if is_dalle3:
                    request_params["quality"] = quality

                response = await client.images.generate(**request_params)

                for image_data in response.data:
                    results.append(
                        ImageGenerationResult(
                            base64_data=image_data.b64_json,
                            url=None,
                            revised_prompt=image_data.revised_prompt,
                        )
                    )

            logger.info(
                "openai_image_generation_completed",
                model=model,
                image_count=len(results),
            )

            return results

        except Exception as e:
            logger.error(
                "openai_image_generation_failed",
                model=model,
                error=str(e),
            )
            raise

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        safety_filter: Optional[str] = None,
        model: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> List[ImageGenerationResult]:
        """Generate images from a text prompt using the appropriate provider.

        Args:
            prompt: Text prompt for image generation
            size: Image size (e.g., "1024x1024")
            n: Number of images to generate
            safety_filter: Safety filter level (for Imagen: block_none, block_some, block_most)
            model: Optional model override (defaults to configured image gen model)
            quality: Quality setting for OpenAI (standard or hd)

        Returns:
            List of generated images
        """
        if model is None:
            model = settings.image_gen_model
        if safety_filter is None:
            safety_filter = settings.image_gen_safety_filter
        if quality is None:
            quality = getattr(settings, "image_gen_openai_quality", "standard")

        # Detect provider based on model name
        provider = self.detect_provider(model)

        logger.info(
            "generate_image_request",
            provider=provider.value,
            model=model,
            size=size,
            quality=quality if provider == ImageProvider.OPENAI else None,
        )

        try:
            if provider == ImageProvider.OPENAI:
                # Use OpenAI DALL-E
                return await self._generate_with_openai(
                    prompt=prompt,
                    size=size,
                    n=n,
                    model=model,
                    quality=quality,
                )
            else:
                # Use Gemini/Imagen
                client = genai.Client(api_key=settings.gemini_api_key)
                aspect_ratio = self._parse_aspect_ratio(size)

                if self._is_gemini_model(model):
                    image_size = self._get_image_size(size)
                    return await self._generate_with_gemini(
                        client, model, prompt, aspect_ratio, image_size, n
                    )
                else:
                    return await self._generate_with_imagen(
                        client, model, prompt, aspect_ratio, safety_filter, n
                    )

        except CircuitBreakerOpen as e:
            logger.warning(
                "image_generation_circuit_open",
                provider=provider.value,
                model=model,
                prompt=prompt[:50],
                retry_after=e.retry_after,
            )
            raise
        except Exception as e:
            logger.error(
                "generate_image_failed",
                provider=provider.value,
                model=model,
                size=size,
                prompt=prompt[:50],
                error=str(e),
            )
            raise


# Global service instance
image_generation_service = ImageGenerationService()
