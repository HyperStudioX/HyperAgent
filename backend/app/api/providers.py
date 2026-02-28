"""Providers API endpoint for listing configured LLM providers."""

from fastapi import APIRouter, Depends

from app.ai.model_tiers import build_tier_providers, get_all_tier_models
from app.config import settings
from app.core.auth import CurrentUser, get_current_user
from app.core.provider_registry import provider_registry

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/")
async def list_providers(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all configured LLM providers."""
    all_tier_models = get_all_tier_models()
    providers = []

    # Built-in providers (only if API key configured)
    if settings.anthropic_api_key:
        providers.append(
            {
                "id": "anthropic",
                "name": "Anthropic",
                "type": "builtin",
                "default_model": settings.tier_pro_anthropic,
                "available": True,
                "tier_models": all_tier_models.get("anthropic", {}),
            }
        )
    if settings.openai_api_key:
        providers.append(
            {
                "id": "openai",
                "name": "OpenAI",
                "type": "builtin",
                "default_model": settings.tier_pro_openai,
                "available": True,
                "tier_models": all_tier_models.get("openai", {}),
            }
        )
    if settings.gemini_api_key or settings.gemini_use_vertex_ai:
        providers.append(
            {
                "id": "gemini",
                "name": "Google Gemini",
                "type": "builtin",
                "default_model": settings.tier_pro_gemini,
                "available": True,
                "tier_models": all_tier_models.get("gemini", {}),
            }
        )

    # Custom providers
    for cp in provider_registry.all_custom_providers():
        providers.append(
            {
                "id": cp.name,
                "name": cp.display_name or cp.name.title(),
                "type": "openai_compatible",
                "default_model": cp.default_model,
                "available": True,
                "tier_models": all_tier_models.get(cp.name, {}),
            }
        )

    tier_providers = build_tier_providers()
    return {
        "providers": providers,
        "default": settings.default_provider,
        "tier_providers": {tier.value: prov for tier, prov in tier_providers.items()},
        "vision_provider": settings.vision_model_provider or settings.default_provider,
        "image_provider": settings.image_model_provider or settings.default_provider,
    }
