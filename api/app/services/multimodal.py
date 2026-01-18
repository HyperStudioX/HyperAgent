"""Multimodal services - backward compatibility layer.

This module re-exports services from their individual modules for backward compatibility.
New code should import directly from the specific service modules:
- vision.py: Image understanding/analysis
- image_generation.py: Image generation
"""

from app.services.image_generation import (
    ImageGenerationService,
    image_generation_service,
)
from app.services.vision import VisionService, vision_service

# Re-export individual service classes and instances
__all__ = [
    # Classes
    "VisionService",
    "ImageGenerationService",
    # Instances
    "vision_service",
    "image_generation_service",
]
