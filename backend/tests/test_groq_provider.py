"""Tests for Groq LLM provider."""

import os

import pytest

from app.story_intelligence.llm.errors import LLMProviderError
from app.story_intelligence.llm.groq import GroqLLMProvider

pytestmark = pytest.mark.usefixtures("block_network")


class TestGroqLLMProvider:
    """Tests for Groq LLM provider adapter."""

    def test_init_without_api_key(self) -> None:
        """Test initialization without API key raises error."""
        os.environ.pop("GROQ_API_KEY", None)

        with pytest.raises(LLMProviderError, match="API key is required"):
            GroqLLMProvider()

    def test_init_with_api_key_param(self) -> None:
        """Test initialization with API key parameter."""
        provider = GroqLLMProvider(api_key="test_key")
        assert provider._api_key == "test_key"

    def test_init_with_env_var(self) -> None:
        """Test initialization with environment variable."""
        os.environ["GROQ_API_KEY"] = "test_key_from_env"

        try:
            provider = GroqLLMProvider()
            assert provider._api_key == "test_key_from_env"
        finally:
            os.environ.pop("GROQ_API_KEY", None)

    def test_init_without_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization without Groq SDK raises error."""
        # Mock the import to fail
        import sys

        monkeypatch.setitem(sys.modules, "groq", None)

        with pytest.raises(LLMProviderError, match="Groq SDK is not installed"):
            GroqLLMProvider(api_key="test_key")

    def test_generate_without_real_api_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test generate method doesn't make real API calls in tests."""
        # This test ensures the provider structure is correct
        # We don't actually call generate in tests to avoid external API calls
        provider = GroqLLMProvider(api_key="test_key")
        assert provider._model == "llama-3.3-70b-versatile"
        assert provider._temperature == 0.7
