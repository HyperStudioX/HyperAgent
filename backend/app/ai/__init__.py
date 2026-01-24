"""AI package for LLM, vision, and image generation services.

This package contains:
- LLM service for language model interactions
- Vision service for image analysis
- Model tiers configuration
- Image generation service
"""

from app.ai.image import (
    ImageGenerationService,
    ImageProvider,
    image_generation_service,
)
from app.ai.llm import (
    LLMService,
    llm_service,
    extract_text_from_content,
)
from app.ai.model_tiers import (
    ModelTier,
    ModelMapping,
    get_model_for_tier,
    get_tier_for_task,
    get_provider_for_tier,
)
from app.ai.vision import VisionService, vision_service

__all__ = [
    # LLM service
    "LLMService",
    "llm_service",
    "extract_text_from_content",
    # Vision service
    "VisionService",
    "vision_service",
    # Image generation service
    "ImageGenerationService",
    "ImageProvider",
    "image_generation_service",
    # Model tiers
    "ModelTier",
    "ModelMapping",
    "get_model_for_tier",
    "get_tier_for_task",
    "get_provider_for_tier",
]
