"""Tests for provider configuration loading and validation."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from app.config.loader import (
    ImageConfig,
    LLMConfig,
    PipelineConfig,
    ProviderConfig,
    TTSConfig,
    VideoConfig,
    load_provider_config,
    load_provider_config_for_profile,
)


class TestLLMConfig:
    """Tests for LLM configuration validation."""

    def test_valid_llm_config(self) -> None:
        """Test valid LLM configuration."""
        config = LLMConfig(provider="fake", model="llama-3.3-70b-versatile")
        assert config.provider == "fake"
        assert config.model == "llama-3.3-70b-versatile"

    def test_invalid_llm_provider(self) -> None:
        """Test invalid LLM provider raises error."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMConfig(provider="unknown_provider")

    def test_temperature_bounds(self) -> None:
        """Test temperature validation."""
        LLMConfig(temperature=0.0)
        LLMConfig(temperature=1.0)
        LLMConfig(temperature=2.0)

        with pytest.raises(ValueError):
            LLMConfig(temperature=-0.1)

        with pytest.raises(ValueError):
            LLMConfig(temperature=2.1)


class TestImageConfig:
    """Tests for image configuration validation."""

    def test_valid_image_config(self) -> None:
        """Test valid image configuration."""
        config = ImageConfig(provider="fake", aspect_ratio="9:16")
        assert config.provider == "fake"
        assert config.aspect_ratio == "9:16"

    def test_invalid_image_provider(self) -> None:
        """Test invalid image provider raises error."""
        with pytest.raises(ValueError, match="Unknown image provider"):
            ImageConfig(provider="unknown_provider")


class TestTTSConfig:
    """Tests for TTS configuration validation."""

    def test_valid_tts_config(self) -> None:
        """Test valid TTS configuration."""
        config = TTSConfig(provider="fake", language="hi-IN", voice="male")
        assert config.provider == "fake"
        assert config.language == "hi-IN"
        assert config.voice == "male"

    def test_invalid_tts_provider(self) -> None:
        """Test invalid TTS provider raises error."""
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            TTSConfig(provider="unknown_provider")


class TestVideoConfig:
    """Tests for video configuration validation."""

    def test_valid_video_config(self) -> None:
        """Test valid video configuration."""
        config = VideoConfig(provider="fake", mode="composition")
        assert config.provider == "fake"
        assert config.mode == "composition"

    def test_invalid_video_provider(self) -> None:
        """Test invalid video provider raises error."""
        with pytest.raises(ValueError, match="Unknown video provider"):
            VideoConfig(provider="unknown_provider")

    def test_kling_provider_allowed(self) -> None:
        """Test Kling provider is allowed for future compatibility."""
        config = VideoConfig(provider="kling")
        assert config.provider == "kling"


class TestPipelineConfig:
    """Tests for pipeline configuration validation."""

    def test_valid_pipeline_config(self) -> None:
        """Test valid pipeline configuration."""
        config = PipelineConfig(aspect_ratio="9:16", target_duration_seconds=30)
        assert config.aspect_ratio == "9:16"
        assert config.target_duration_seconds == 30

    def test_invalid_duration(self) -> None:
        """Test invalid duration raises error."""
        with pytest.raises(ValueError):
            PipelineConfig(target_duration_seconds=0)


class TestProviderConfig:
    """Tests for complete provider configuration."""

    def test_default_config(self) -> None:
        """Test default configuration uses fake providers."""
        config = ProviderConfig()
        assert config.llm.provider == "fake"
        assert config.image.provider == "fake"
        assert config.tts.provider == "fake"
        assert config.video.provider == "fake"

    def test_real_provider_validation_missing_api_key(self) -> None:
        """Test real provider requires API key."""
        # Remove API key if present
        os.environ.pop("GROQ_API_KEY", None)

        config_data = {
            "llm": {"provider": "groq"},
        }

        with pytest.raises(ValueError, match="Missing required environment variables"):
            ProviderConfig.model_validate(config_data)

    def test_real_provider_validation_with_api_key(self) -> None:
        """Test real provider passes with API key."""
        os.environ["GROQ_API_KEY"] = "test_key"

        config_data = {
            "llm": {"provider": "groq"},
        }

        config = ProviderConfig.model_validate(config_data)
        assert config.llm.provider == "groq"

        # Clean up
        os.environ.pop("GROQ_API_KEY", None)

    def test_multiple_real_providers_validation(self) -> None:
        """Test multiple real providers require all API keys."""
        config_data = {
            "llm": {"provider": "groq"},
            "image": {"provider": "google"},
            "tts": {"provider": "sarvam"},
            "video": {"provider": "json2video"},
        }

        with pytest.raises(ValueError, match="Missing required environment variables"):
            ProviderConfig.model_validate(config_data)

    def test_secret_redaction_in_str(self) -> None:
        """Test configuration string representation doesn't expose secrets."""
        config = ProviderConfig()
        config_str = str(config)
        # Ensure no API keys appear in string representation
        assert "api_key" not in config_str.lower()


class TestLoadProviderConfig:
    """Tests for loading configuration from YAML files."""

    def test_load_from_yaml(self) -> None:
        """Test loading configuration from YAML file."""
        config_content = """
llm:
  provider: fake
  model: test-model

image:
  provider: fake
  aspect_ratio: "9:16"

tts:
  provider: fake
  language: "hi-IN"

video:
  provider: fake
  mode: composition

pipeline:
  aspect_ratio: "9:16"
  target_duration_seconds: 30
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = Path(f.name)

        try:
            config = load_provider_config(config_path)
            assert config.llm.provider == "fake"
            assert config.llm.model == "test-model"
            assert config.image.aspect_ratio == "9:16"
            assert config.tts.language == "hi-IN"
            assert config.video.mode == "composition"
            assert config.pipeline.target_duration_seconds == 30
        finally:
            config_path.unlink()

    def test_load_nonexistent_file(self) -> None:
        """Test loading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_provider_config(Path("/nonexistent/path/config.yaml"))

    def test_load_empty_yaml(self) -> None:
        """Test loading empty YAML uses defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            config_path = Path(f.name)

        try:
            config = load_provider_config(config_path)
            assert config.llm.provider == "fake"
            assert config.image.provider == "fake"
        finally:
            config_path.unlink()

    def test_load_invalid_yaml(self) -> None:
        """Test loading invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            f.flush()
            config_path = Path(f.name)

        try:
            with pytest.raises(yaml.YAMLError):
                load_provider_config(config_path)
        finally:
            config_path.unlink()


class TestLoadProviderConfigForProfile:
    """Tests for loading profile-specific configuration."""

    def test_load_profile_config(self) -> None:
        """Test loading profile-specific configuration."""
        # This test requires the profile file to exist
        # We'll test the function exists and can be called
        # Actual profile testing would require creating test profile files
        with pytest.raises(FileNotFoundError):
            load_provider_config_for_profile("nonexistent_profile")
