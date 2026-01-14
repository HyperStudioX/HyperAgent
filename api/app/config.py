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

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hyperagent"
    redis_url: str = "redis://localhost:6379"

    # Storage
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "hyperagent"
    r2_endpoint_url: str = ""

    # E2B Sandbox
    e2b_api_key: str = ""

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings."""
    return Settings()


settings = get_settings()
