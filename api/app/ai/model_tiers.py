"""Model tier configuration and selection logic."""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional

from app.models.schemas import LLMProvider


class ModelTier(str, Enum):
    """Model tiers for different task complexities."""

    MAX = "max"  # Complex tasks: planning, reasoning, research
    PRO = "pro"  # Balanced general tasks: chat, code assistance
    FLASH = "flash"  # Quick tasks: naming, summarization, routing


@dataclass
class ModelMapping:
    """Maps a tier to specific models across providers."""

    anthropic: str
    openai: str
    gemini: str


# Default tier-to-model mappings
DEFAULT_TIER_MODELS: Dict[ModelTier, ModelMapping] = {
    ModelTier.MAX: ModelMapping(
        anthropic="claude-opus-4-20250514",
        openai="gpt-4o",
        gemini="gemini-2.5-pro",
    ),
    ModelTier.PRO: ModelMapping(
        anthropic="claude-sonnet-4-20250514",
        openai="gpt-4o-mini",
        gemini="gemini-2.5-flash",
    ),
    ModelTier.FLASH: ModelMapping(
        anthropic="claude-3-5-haiku-20241022",
        openai="gpt-4o-mini",
        gemini="gemini-2.0-flash",
    ),
}

# Task type to tier routing
TASK_TIER_ROUTING: Dict[str, ModelTier] = {
    "research": ModelTier.MAX,
    "writing": ModelTier.MAX,
    "computer": ModelTier.MAX,  # Computer use requires reasoning about visual elements
    "code": ModelTier.PRO,
    "chat": ModelTier.PRO,
    "data": ModelTier.PRO,
    "routing": ModelTier.FLASH,
    "naming": ModelTier.FLASH,
    "summary": ModelTier.FLASH,
}


def get_model_for_tier(
    tier: ModelTier,
    provider: LLMProvider,
    custom_mappings: Optional[Dict[ModelTier, ModelMapping]] = None,
) -> str:
    """Get the model identifier for a tier and provider.

    Args:
        tier: The model tier to get model for
        provider: The LLM provider
        custom_mappings: Optional custom tier-to-model mappings

    Returns:
        Model identifier string for the specified tier and provider
    """
    mappings = custom_mappings or DEFAULT_TIER_MODELS
    mapping = mappings.get(tier, DEFAULT_TIER_MODELS[ModelTier.PRO])

    provider_map = {
        LLMProvider.ANTHROPIC: mapping.anthropic,
        LLMProvider.OPENAI: mapping.openai,
        LLMProvider.GEMINI: mapping.gemini,
    }
    return provider_map.get(provider, mapping.anthropic)


def get_tier_for_task(task_type: str) -> ModelTier:
    """Get the recommended tier for a task type.

    Args:
        task_type: The type of task (e.g., "research", "chat", "code")

    Returns:
        The recommended model tier for the task type
    """
    return TASK_TIER_ROUTING.get(task_type, ModelTier.PRO)


def get_provider_for_tier(
    tier: ModelTier,
    tier_providers: Optional[Dict[ModelTier, LLMProvider]] = None,
) -> LLMProvider:
    """Get the provider for a given tier.

    Args:
        tier: The model tier to get provider for
        tier_providers: Optional custom tier-to-provider mappings from config

    Returns:
        LLMProvider for the specified tier
    """
    if tier_providers and tier in tier_providers:
        return tier_providers[tier]

    # Default to Anthropic if no custom mapping provided
    return LLMProvider.ANTHROPIC
