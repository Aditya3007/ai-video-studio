"""LLM provider abstraction and fake provider tests."""

import pytest

from app.core.config import load_settings
from app.story_intelligence import (
    FakeLLMProvider,
    LLMProviderError,
    LLMProviderFactory,
    LLMResponse,
)
from app.story_intelligence.schemas import StoryAnalysisResult


def test_fake_provider_returns_configured_response() -> None:
    response = {"status": "COMPLETED", "metadata": {"title": "Fake"}}
    provider = FakeLLMProvider(response=response)
    result = provider.generate(user_prompt="analyze")
    assert isinstance(result, LLMResponse)
    assert result.provider == "fake"
    assert result.parsed == response


def test_fake_provider_validates_response_model() -> None:
    provider = FakeLLMProvider(response={"status": "COMPLETED"})
    with pytest.raises(LLMProviderError):
        provider.generate(
            user_prompt="x",
            response_model=StoryAnalysisResult,
        )


def test_fake_provider_simulates_failure() -> None:
    provider = FakeLLMProvider(fail=True)
    with pytest.raises(LLMProviderError, match="Simulated"):
        provider.generate(user_prompt="x")


def test_fake_provider_returns_malformed_text() -> None:
    provider = FakeLLMProvider(text="not json")
    result = provider.generate(user_prompt="x")
    assert result.parsed is None
    assert result.content == "not json"


def test_fake_provider_default_response() -> None:
    provider = FakeLLMProvider()
    result = provider.generate(user_prompt="x")
    assert result.parsed is not None
    assert "status" in result.parsed


def test_factory_selects_fake_provider() -> None:
    settings = load_settings(env={"LLM_PROVIDER": "fake"})
    provider = LLMProviderFactory.create(settings)
    assert isinstance(provider, FakeLLMProvider)


def test_factory_rejects_deterministic() -> None:
    settings = load_settings(env={"LLM_PROVIDER": "deterministic"})
    with pytest.raises(ValueError, match="deterministic"):
        LLMProviderFactory.create(settings)


@pytest.mark.parametrize("provider_name", ["openai", "anthropic", "gemini", "local"])
def test_factory_unimplemented_providers(provider_name: str) -> None:
    settings = load_settings(env={"LLM_PROVIDER": provider_name})
    with pytest.raises(NotImplementedError):
        LLMProviderFactory.create(settings)
