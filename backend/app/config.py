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
    langgraph_recursion_limit: int = (
        50  # Maximum recursion depth for graph execution (increased for handoff-heavy workflows)
    )
    subgraph_timeout: int = 300  # Timeout in seconds for subgraph invocations (5 minutes)
    routing_timeout: int = 30  # Timeout in seconds for routing decisions
    research_task_timeout: int = 1800  # Timeout in seconds for research tasks (30 minutes)

    # Context Compression
    context_compression_enabled: bool = True  # Enable LLM-based context compression
    context_compression_token_threshold: int = (
        60000  # Token threshold to trigger compression (60% of 100k budget)
    )
    context_compression_preserve_recent: int = 10  # Number of recent messages to always preserve

    # Sandbox Provider
    sandbox_provider: Literal["e2b", "boxlite"] = "e2b"

    # E2B Code Sandbox
    e2b_api_key: str = ""
    e2b_template_id: str = (
        ""  # Optional: custom template with pre-installed packages for faster startup
    )
    e2b_code_timeout: int = 300  # 5 minutes for code execution sandbox
    e2b_session_timeout_minutes: int = 10  # Session timeout for code sandbox manager

    # E2B Desktop Sandbox
    e2b_desktop_timeout: int = 900  # 15 minutes (longer for browser startup)
    e2b_desktop_default_browser: str = "google-chrome"
    e2b_desktop_session_timeout_minutes: int = 15  # Session timeout for browser sandbox manager
    e2b_desktop_stream_ready_wait_ms: int = 3000  # Wait time for stream to be ready before actions

    # BoxLite Local Sandbox
    boxlite_code_image: str = "python:3.12-slim"
    boxlite_desktop_image: str = "boxlite/desktop:latest"
    boxlite_app_image: str = "node:20-slim"
    boxlite_cpus: int = 2
    boxlite_memory_mib: int = 1024
    boxlite_disk_size_gb: int = 4  # Disk size in GB (needed for npm/node scaffolding)
    boxlite_working_dir: str = "/home/user"
    boxlite_code_timeout: int = 300
    boxlite_desktop_timeout: int = 900
    boxlite_desktop_default_browser: str = "chromium-browser"
    boxlite_auto_remove: bool = True
    boxlite_app_host_port_start: int = 10000

    # Search
    tavily_api_key: str = ""

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 30  # requests per minute

    # Human-in-the-Loop (HITL) Settings
    hitl_enabled: bool = True  # Enable HITL by default
    hitl_approval_timeout: int = 120  # 2 minutes for tool approvals
    hitl_decision_timeout: int = 300  # 5 minutes for decision interrupts
    hitl_input_timeout: int = 300  # 5 minutes for input interrupts
    hitl_default_risk_threshold: str = "high"  # high, medium, or all

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    # Guardrails
    guardrails_enabled: bool = True
    guardrails_input_enabled: bool = True
    guardrails_output_enabled: bool = True
    guardrails_tool_enabled: bool = True
    guardrails_violation_action: Literal["block", "warn", "log"] = "block"
    guardrails_timeout_ms: int = 500

    # ReAct Loop Configuration
    react_max_iterations: int = 5  # Maximum number of tool-calling iterations

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
        from app.ai.model_tiers import ModelMapping, ModelTier

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
