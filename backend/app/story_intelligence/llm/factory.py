"""Factory for selecting the configured LLM provider."""

import os

from app.core.config import Settings, get_settings
from app.provider_registry import ProviderType, get_default_registry
from app.story_intelligence.llm.groq import GroqLLMProvider
from app.story_intelligence.llm.provider import LLMProvider


class LLMProviderFactory:
    """Creates an LLM provider adapter from settings."""

    @staticmethod
    def create(settings: Settings | None = None) -> LLMProvider:
        """Return the configured provider instance."""
        if settings is None:
            settings = get_settings()

        provider = settings.llm_provider
        if provider == "fake":
            return get_default_registry().resolve(ProviderType.LLM, "fake")
        if provider == "deterministic":
            raise ValueError(
                'llm_provider="deterministic" is not an LLM provider; '
                "use the deterministic analyzer instead."
            )
        if provider == "groq":
            return GroqLLMProvider(
                model=settings.llm_model or "llama-3.3-70b-versatile",
                api_key=os.getenv("GROQ_API_KEY"),
            )
        if provider == "openai":
            raise NotImplementedError("OpenAI provider is not yet implemented.")
        if provider == "anthropic":
            raise NotImplementedError("Anthropic provider is not yet implemented.")
        if provider == "gemini":
            raise NotImplementedError("Gemini provider is not yet implemented.")
        if provider == "local":
            raise NotImplementedError("Local LLM provider is not yet implemented.")

        raise ValueError(f"Unknown LLM provider: {provider}")
