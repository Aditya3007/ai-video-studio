"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import load_settings


def test_load_settings_uses_defaults() -> None:
    """Configuration loads sensible defaults when no environment is provided."""
    settings = load_settings({})

    assert settings.app_env == "development"
    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000
    assert settings.log_level == "INFO"


def test_load_settings_from_environment() -> None:
    """Configuration loads and coerces values from environment variables."""
    settings = load_settings(
        {
            "APP_ENV": "production",
            "APP_HOST": "127.0.0.1",
            "APP_PORT": "9000",
            "LOG_LEVEL": "DEBUG",
        }
    )

    assert settings.app_env == "production"
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 9000
    assert settings.log_level == "DEBUG"


def test_optional_credentials_can_be_absent() -> None:
    """Future provider and infrastructure credentials are optional."""
    settings = load_settings({})

    assert settings.database_url is None
    assert settings.redis_url is None
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None
    assert settings.youtube_client_id is None
    assert settings.youtube_client_secret is None
    assert settings.youtube_refresh_token is None


def test_optional_credentials_can_be_present() -> None:
    """Optional credentials are parsed and stored as SecretStr."""
    settings = load_settings(
        {
            "OPENAI_API_KEY": "sk-openai",
            "ANTHROPIC_API_KEY": "sk-anthropic",
            "YOUTUBE_CLIENT_SECRET": "yt-secret",
        }
    )

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-openai"
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-anthropic"
    assert settings.youtube_client_secret is not None
    assert settings.youtube_client_secret.get_secret_value() == "yt-secret"


def test_secret_values_not_exposed_in_representation() -> None:
    """Secret values must not appear in repr or str output."""
    settings = load_settings({"OPENAI_API_KEY": "sk-secret"})
    representation = repr(settings)
    string_form = str(settings)

    assert "sk-secret" not in representation
    assert "sk-secret" not in string_form


def test_invalid_port_raises_validation_error() -> None:
    """Malformed APP_PORT produces a clear validation error."""
    with pytest.raises(ValidationError) as exc_info:
        load_settings({"APP_PORT": "not_a_number"})

    error_message = str(exc_info.value)
    assert "APP_PORT" in error_message


def test_log_level_validation() -> None:
    """Invalid LOG_LEVEL is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        load_settings({"LOG_LEVEL": "SILENT"})

    error_message = str(exc_info.value)
    assert "LOG_LEVEL" in error_message


def test_port_range_validation() -> None:
    """APP_PORT must be a valid TCP port."""
    with pytest.raises(ValidationError):
        load_settings({"APP_PORT": "99999"})
