from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # App
    app_name: str = "HyperAgent API"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5000"

    # LLM Providers
    default_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Models
    default_model_anthropic: str = "claude-sonnet-4-20250514"
    default_model_openai: str = "gpt-4o"
    default_model_gemini: str = "gemini-2.5-flash"

    # Model Tier Configuration
    # Providers for each tier (which provider to use for each complexity level)
    tier_max_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"
    tier_pro_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"
    tier_flash_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"

    # Models for each tier and provider combination
    tier_max_anthropic: str = "claude-opus-4-20250514"
    tier_max_openai: str = "gpt-4o"
    tier_max_gemini: str = "gemini-2.5-pro"

    tier_pro_anthropic: str = "claude-sonnet-4-20250514"
    tier_pro_openai: str = "gpt-4o-mini"
    tier_pro_gemini: str = "gemini-2.5-flash"

    tier_flash_anthropic: str = "claude-3-5-haiku-20241022"
    tier_flash_openai: str = "gpt-4o-mini"
    tier_flash_gemini: str = "gemini-2.0-flash"

    # Multimodal Model Configuration
    # Image Understanding (Vision - Gemini only)
    vision_model: str = "gemini-2.5-flash"

    # Image Generation (Multi-provider)
    image_gen_model: str = "gemini-3-pro-image-preview"
    image_gen_default_size: str = "1024x1024"
    image_gen_safety_filter: str = "block_some"  # block_none, block_some, block_most
    image_gen_default_provider: Literal["gemini", "openai"] = "gemini"

    # OpenAI Image Generation (DALL-E)
    image_gen_openai_model: str = "dall-e-3"
    image_gen_openai_quality: str = "standard"  # standard or hd

    # Audio Transcription (Gemini only)
    audio_transcription_model: str = "gemini-2.0-flash-exp"

    # Audio Text-to-Speech (Gemini only)
    audio_tts_model: str = "gemini-2.0-flash-exp"
    audio_tts_voice: str = "Puck"  # Voice options: Puck, Charon, Kore, Fenrir, Aoede

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hyperagent"
    redis_url: str = "redis://localhost:6379"

    # Storage
    storage_backend: Literal["r2", "local"] = "local"  # r2 for production, local for dev
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "hyperagent"
    r2_endpoint_url: str = ""
    local_storage_path: str = "./uploads"  # For local development

    # LangGraph Configuration
    langgraph_recursion_limit: int = 25  # Maximum recursion depth for graph execution

    # E2B Code Sandbox
    e2b_api_key: str = ""
    e2b_template_id: str = ""  # Optional: custom template with pre-installed packages for faster startup
    e2b_code_timeout: int = 300  # 5 minutes for code execution sandbox
    e2b_session_timeout_minutes: int = 10  # Session timeout for code sandbox manager

    # E2B Desktop Sandbox
    e2b_desktop_timeout: int = 900  # 15 minutes (longer for browser startup)
    e2b_desktop_default_browser: str = "google-chrome"
    e2b_desktop_session_timeout_minutes: int = 15  # Session timeout for browser sandbox manager
    e2b_desktop_stream_ready_wait_ms: int = 3000  # Wait time for stream to be ready before actions

    # Search
    tavily_api_key: str = ""

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 30  # requests per minute

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    # Authentication
    nextauth_secret: str = ""
    google_client_id: str = ""
    auth_enabled: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def tier_mappings(self) -> dict:
        """Get tier mappings from configuration."""
        from app.ai.model_tiers import ModelTier, ModelMapping

        return {
            ModelTier.MAX: ModelMapping(
                anthropic=self.tier_max_anthropic,
                openai=self.tier_max_openai,
                gemini=self.tier_max_gemini,
            ),
            ModelTier.PRO: ModelMapping(
                anthropic=self.tier_pro_anthropic,
                openai=self.tier_pro_openai,
                gemini=self.tier_pro_gemini,
            ),
            ModelTier.FLASH: ModelMapping(
                anthropic=self.tier_flash_anthropic,
                openai=self.tier_flash_openai,
                gemini=self.tier_flash_gemini,
            ),
        }

    @property
    def tier_providers(self) -> dict:
        """Get provider for each tier from configuration."""
        from app.ai.model_tiers import ModelTier
        from app.models.schemas import LLMProvider

        provider_map = {
            "anthropic": LLMProvider.ANTHROPIC,
            "openai": LLMProvider.OPENAI,
            "gemini": LLMProvider.GEMINI,
        }

        return {
            ModelTier.MAX: provider_map[self.tier_max_provider],
            ModelTier.PRO: provider_map[self.tier_pro_provider],
            ModelTier.FLASH: provider_map[self.tier_flash_provider],
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings."""
    return Settings()


settings = get_settings()
