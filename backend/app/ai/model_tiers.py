"""Model tier configuration and selection logic.

This module is the single source of truth for all tier resolution:
- ModelTier enum and ModelMapping dataclass
- Task-to-tier routing
- Building tier mappings from settings + custom providers
- Resolving (provider, model) for a given tier or task type
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class ModelTier(str, Enum):
    """Model tiers for different task complexities."""

    MAX = "max"  # Complex tasks: planning, reasoning, research
    PRO = "pro"  # Balanced general tasks: chat, code assistance
    FLASH = "flash"  # Quick tasks: naming, summarization, routing


@dataclass
class ModelMapping:
    """Maps a tier to specific models across providers.

    Uses a dict internally so new providers can be added without code changes.
    """

    models: dict[str, str] = field(default_factory=dict)


# Task type to tier routing
TASK_TIER_ROUTING: Dict[str, ModelTier] = {
    "research": ModelTier.MAX,
    "computer": ModelTier.MAX,  # Computer use requires reasoning about visual elements
    "app": ModelTier.MAX,  # App building requires complex reasoning and code generation
    "task": ModelTier.PRO,
    "data": ModelTier.PRO,
    "routing": ModelTier.FLASH,
    "naming": ModelTier.FLASH,
    "summary": ModelTier.FLASH,
}


# ---------------------------------------------------------------------------
# Lazy import helper (avoids circular deps: config → model_tiers → config)
# ---------------------------------------------------------------------------


def _get_settings():
    """Lazy import of settings to avoid circular dependency."""
    from app.config import settings

    return settings


# ---------------------------------------------------------------------------
# Tier mapping builders
# ---------------------------------------------------------------------------


_tier_mappings_cache: Dict[ModelTier, ModelMapping] | None = None


def build_tier_mappings(settings=None) -> Dict[ModelTier, ModelMapping]:
    """Assemble tier-to-ModelMapping dict from settings + custom providers."""
    global _tier_mappings_cache
    if _tier_mappings_cache is not None and settings is None:
        return _tier_mappings_cache

    if settings is None:
        settings = _get_settings()

    from app.core.provider_registry import provider_registry

    # Built-in provider models from env vars
    max_models = {
        "anthropic": settings.tier_max_anthropic,
        "openai": settings.tier_max_openai,
        "gemini": settings.tier_max_gemini,
    }
    pro_models = {
        "anthropic": settings.tier_pro_anthropic,
        "openai": settings.tier_pro_openai,
        "gemini": settings.tier_pro_gemini,
    }
    flash_models = {
        "anthropic": settings.tier_flash_anthropic,
        "openai": settings.tier_flash_openai,
        "gemini": settings.tier_flash_gemini,
    }

    # Merge custom provider tier models
    for cp in provider_registry.all_custom_providers():
        if "max" in cp.tier_models:
            max_models[cp.name] = cp.tier_models["max"]
        if "pro" in cp.tier_models:
            pro_models[cp.name] = cp.tier_models["pro"]
        if "flash" in cp.tier_models:
            flash_models[cp.name] = cp.tier_models["flash"]

    result = {
        ModelTier.MAX: ModelMapping(models=max_models),
        ModelTier.PRO: ModelMapping(models=pro_models),
        ModelTier.FLASH: ModelMapping(models=flash_models),
    }
    if settings is _get_settings():
        _tier_mappings_cache = result
    return result


_tier_providers_cache: Dict[ModelTier, str] | None = None


def build_tier_providers(settings=None) -> Dict[ModelTier, str]:
    """Assemble tier-to-provider dict from settings.

    Uses ``default_provider`` for all tiers (single source of truth).
    """
    global _tier_providers_cache
    if _tier_providers_cache is not None and settings is None:
        return _tier_providers_cache

    if settings is None:
        settings = _get_settings()

    fallback = settings.default_provider
    result = {
        ModelTier.MAX: settings.max_model_provider or fallback,
        ModelTier.PRO: settings.pro_model_provider or fallback,
        ModelTier.FLASH: settings.flash_model_provider or fallback,
    }
    if settings is _get_settings():
        _tier_providers_cache = result
    return result


# ---------------------------------------------------------------------------
# High-level resolvers
# ---------------------------------------------------------------------------


def resolve_model(
    tier: ModelTier,
    provider: str | None = None,
    model_override: str | None = None,
) -> tuple[str, str]:
    """Resolve (provider, model) for a given tier.

    Priority: model_override > tier mapping lookup.
    If *provider* is None, auto-selects from tier_providers config.

    Returns:
        (provider, model) tuple.
    """
    if provider is None:
        tier_providers = build_tier_providers()
        provider = tier_providers.get(tier, "anthropic")

    if model_override:
        return provider, model_override

    mappings = build_tier_mappings()
    mapping = mappings.get(tier, mappings[ModelTier.PRO])
    model = mapping.models.get(provider)
    if model is None:
        # Fallback 1: PRO tier model for same provider
        pro_mapping = mappings.get(ModelTier.PRO)
        if pro_mapping:
            model = pro_mapping.models.get(provider)
    if model is None:
        # Fallback 2: custom provider's default_model
        from app.core.provider_registry import provider_registry

        custom = provider_registry.get_custom(provider)
        if custom and custom.default_model:
            model = custom.default_model
        else:
            # Fallback 3: anthropic PRO model (last resort)
            model = mappings[ModelTier.PRO].models.get("anthropic", "")
    return provider, model


def resolve_model_for_task(
    task_type: str,
    provider: str | None = None,
    tier_override: ModelTier | None = None,
    model_override: str | None = None,
) -> tuple[ModelTier, str, str]:
    """Full auto-routing: resolve (tier, provider, model) for a task.

    Priority: model_override > tier_override > TASK_TIER_ROUTING.

    Returns:
        (tier, provider, model) tuple.
    """
    tier = tier_override or TASK_TIER_ROUTING.get(task_type, ModelTier.PRO)
    p, m = resolve_model(tier, provider, model_override)
    return tier, p, m


# ---------------------------------------------------------------------------
# Provider API helper
# ---------------------------------------------------------------------------


def get_all_tier_models() -> dict[str, dict[str, str]]:
    """Return ``{provider_id: {max: model, pro: model, flash: model}}`` for all providers.

    Used by the ``/providers`` API so the frontend can show which model each
    tier resolves to for each provider.
    """
    mappings = build_tier_mappings()

    # Collect all provider ids that appear in any tier
    provider_ids: set[str] = set()
    for mapping in mappings.values():
        provider_ids.update(mapping.models.keys())

    result: dict[str, dict[str, str]] = {}
    for pid in sorted(provider_ids):
        result[pid] = {}
        for tier in ModelTier:
            mapping = mappings.get(tier)
            if mapping and pid in mapping.models:
                result[pid][tier.value] = mapping.models[pid]

    return result
