"""Application configuration loaded from environment variables."""

import os
from collections.abc import Mapping
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    """Application settings.

    Values are loaded from environment variables. Secret values are masked in
    string representations to prevent accidental exposure in logs or error
    messages.
    """

    model_config = ConfigDict(
        alias_generator=lambda field_name: field_name.upper(),
        populate_by_name=True,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # CORS (optional, comma-separated list of origins)
    cors_origins: str | None = None

    # Infrastructure (optional until implemented)
    database_url: str | None = None
    redis_url: str | None = None

    # Object storage (optional until P1 storage implementation)
    storage_backend: Literal["filesystem", "s3"] = "filesystem"
    storage_local_root: str = "storage"
    storage_endpoint: str | None = None
    storage_region: str | None = None
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_bucket: str | None = None

    # AI provider credentials (optional until P11)
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # LLM provider selection (optional until P3-T03)
    llm_provider: Literal[
        "deterministic", "fake", "openai", "anthropic", "gemini", "groq", "local"
    ] = "deterministic"
    llm_model: str | None = None

    # Image generation provider selection (optional until P5-T02)
    image_generation_provider: Literal["fake", "openai", "stability", "google", "local"] = "fake"
    image_generation_model: str | None = None

    # Video generation provider selection (optional until P6-T01)
    video_generation_provider: Literal[
        "fake", "runway", "kling", "luma", "sora", "veo", "local", "json2video"
    ] = "fake"
    video_generation_model: str | None = None

    # TTS provider selection (optional until P7-T02)
    tts_provider: Literal[
        "fake", "openai", "elevenlabs", "google", "azure", "amazon", "sarvam"
    ] = "fake"
    tts_model: str | None = None

    # Provider/model selection policy (P14-T04)
    provider_selection_mode: Literal["default", "cost_aware"] = "default"
    cost_aware_allow_unknown: bool = False

    # Audio generation provider selection (optional until P7-T04)
    audio_generation_provider: Literal[
        "fake", "openai", "stability", "suno", "udio", "elevenlabs", "local"
    ] = "fake"
    audio_generation_model: str | None = None

    # YouTube OAuth (optional until P13)
    youtube_client_id: SecretStr | None = None
    youtube_client_secret: SecretStr | None = None
    youtube_refresh_token: SecretStr | None = None

    def __repr__(self) -> str:
        return (
            f"<Settings(app_env={self.app_env!r}, app_host={self.app_host!r}, "
            f"app_port={self.app_port}, log_level={self.log_level!r})>"
        )

    def __str__(self) -> str:
        return self.__repr__()


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Load and validate settings from environment variables.

    Args:
        env: Optional mapping of environment variables. Defaults to ``os.environ``.

    Returns:
        Validated ``Settings`` instance.
    """
    source = dict(os.environ) if env is None else dict(env)
    return Settings.model_validate(source)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return load_settings()
