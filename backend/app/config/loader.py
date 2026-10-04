"""YAML-based provider configuration loader and validator."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(default="fake", description="Provider ID (e.g., groq, fake)")
    model: str | None = Field(default=None, description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Validate provider is a known identifier."""
        known_providers = {"fake", "groq", "openai", "anthropic", "gemini", "local"}
        if value not in known_providers:
            raise ValueError(
                f"Unknown LLM provider '{value}'. Known providers: {sorted(known_providers)}"
            )
        return value


class ImageConfig(BaseModel):
    """Image generation provider configuration."""

    provider: str = Field(default="fake", description="Provider ID (e.g., gemini, fake)")
    model: str | None = Field(default=None, description="Model name")
    aspect_ratio: str = Field(default="9:16", description="Target aspect ratio")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Validate provider is a known identifier."""
        known_providers = {"fake", "openai", "stability", "google", "local"}
        if value not in known_providers:
            raise ValueError(
                f"Unknown image provider '{value}'. Known providers: {sorted(known_providers)}"
            )
        return value


class TTSConfig(BaseModel):
    """Text-to-speech provider configuration."""

    provider: str = Field(default="fake", description="Provider ID (e.g., sarvam, fake)")
    model: str | None = Field(default=None, description="Model name")
    language: str | None = Field(default=None, description="Language code (e.g., hi-IN)")
    voice: str | None = Field(default=None, description="Voice identifier")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Validate provider is a known identifier."""
        known_providers = {"fake", "openai", "elevenlabs", "google", "azure", "amazon", "sarvam"}
        if value not in known_providers:
            raise ValueError(
                f"Unknown TTS provider '{value}'. Known providers: {sorted(known_providers)}"
            )
        return value


class VideoConfig(BaseModel):
    """Video generation provider configuration."""

    provider: str = Field(default="fake", description="Provider ID (e.g., json2video, kling, fake)")
    mode: str | None = Field(default=None, description="Generation mode (e.g., composition)")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Validate provider is a known identifier."""
        known_providers = {"fake", "runway", "kling", "luma", "sora", "veo", "local", "json2video"}
        if value not in known_providers:
            raise ValueError(
                f"Unknown video provider '{value}'. Known providers: {sorted(known_providers)}"
            )
        return value


class PipelineConfig(BaseModel):
    """Pipeline-level configuration."""

    aspect_ratio: str = Field(default="9:16", description="Target aspect ratio")
    target_duration_seconds: int = Field(default=30, ge=1)


class ProviderConfig(BaseModel):
    """Complete provider configuration."""

    model_config = ConfigDict(extra="ignore")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    image: ImageConfig = Field(default_factory=ImageConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @model_validator(mode="after")
    def validate_real_provider_credentials(self) -> "ProviderConfig":
        """Ensure real providers have required environment variables."""
        errors = []

        if self.llm.provider != "fake":
            if self.llm.provider == "groq":
                if not os.getenv("GROQ_API_KEY"):
                    errors.append("GROQ_API_KEY environment variable is required for Groq provider")

        if self.image.provider != "fake":
            if self.image.provider == "google":
                if not os.getenv("GEMINI_API_KEY"):
                    errors.append(
                        "GEMINI_API_KEY environment variable is required for Gemini provider"
                    )

        if self.tts.provider != "fake":
            if self.tts.provider == "sarvam":
                if not os.getenv("SARVAM_API_KEY"):
                    errors.append(
                        "SARVAM_API_KEY environment variable is required for Sarvam provider"
                    )

        if self.video.provider != "fake":
            if self.video.provider == "json2video":
                if not os.getenv("JSON2VIDEO_API_KEY"):
                    errors.append(
                        "JSON2VIDEO_API_KEY environment variable is required for "
                        "JSON2Video provider"
                    )
            if self.video.provider == "kling":
                if not os.getenv("KLING_API_KEY"):
                    errors.append(
                        "KLING_API_KEY environment variable is required for Kling provider"
                    )

        if errors:
            raise ValueError(
                "Missing required environment variables for real providers: " + "; ".join(errors)
            )

        return self


def load_provider_config(config_path: str | Path | None = None) -> ProviderConfig:
    """Load provider configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file. If None, uses default
                    app/config/providers.yaml relative to this module.

    Returns:
        Validated ProviderConfig instance.

    Raises:
        FileNotFoundError: If configuration file does not exist.
        ValueError: If configuration is invalid or missing required credentials.
    """
    if config_path is None:
        # Default to app/config/providers.yaml relative to this module
        module_dir = Path(__file__).parent
        config_path = module_dir / "providers.yaml"

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Provider configuration file not found: {config_file}")

    with open(config_file) as f:
        raw_config = yaml.safe_load(f) or {}

    return ProviderConfig.model_validate(raw_config)


def load_provider_config_for_profile(profile_name: str) -> ProviderConfig:
    """Load provider configuration from a profile-specific YAML file.

    Args:
        profile_name: Name of the profile (e.g., "real_e2e").

    Returns:
        Validated ProviderConfig instance.

    Raises:
        FileNotFoundError: If profile configuration file does not exist.
        ValueError: If configuration is invalid or missing required credentials.
    """
    module_dir = Path(__file__).parent
    profiles_dir = module_dir / "profiles"
    config_path = profiles_dir / f"{profile_name}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Profile configuration file not found: {config_path}")

    return load_provider_config(config_path)
