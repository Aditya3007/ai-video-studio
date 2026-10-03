"""Tests for the unified provider registry."""

import pytest

from app.media_generation.audio import FakeAudioGenerationProvider
from app.media_generation.image import FakeImageGenerationProvider
from app.media_generation.tts import FakeTTSProvider
from app.media_generation.video import FakeVideoGenerationProvider
from app.provider_registry import (
    DuplicateProviderError,
    IncompatibleProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
    ProviderRegistryError,
    ProviderType,
    get_default_registry,
)
from app.services.ai_qa_service import FakeAIQAProvider
from app.story_intelligence.llm import FakeLLMProvider


class TestProviderRegistry:
    def test_register_and_resolve_by_type_and_id(self) -> None:
        registry = ProviderRegistry()
        provider = FakeLLMProvider()
        registry.register(ProviderType.LLM, "fake", provider)
        resolved = registry.resolve(ProviderType.LLM, "fake")
        assert resolved is provider

    def test_has_and_list(self) -> None:
        registry = ProviderRegistry()
        assert not registry.has(ProviderType.LLM, "fake")
        registry.register(ProviderType.LLM, "fake", FakeLLMProvider())
        assert registry.has(ProviderType.LLM, "fake")
        assert registry.list(ProviderType.LLM) == ["fake"]

    def test_missing_provider_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.resolve(ProviderType.LLM, "missing")

    def test_duplicate_registration_without_override_fails(self) -> None:
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "fake", FakeLLMProvider())
        with pytest.raises(DuplicateProviderError):
            registry.register(ProviderType.LLM, "fake", FakeLLMProvider())

    def test_override_allowed(self) -> None:
        registry = ProviderRegistry()
        first = FakeLLMProvider()
        second = FakeLLMProvider()
        registry.register(ProviderType.LLM, "fake", first)
        registry.register(ProviderType.LLM, "fake", second, override=True)
        assert registry.resolve(ProviderType.LLM, "fake") is second

    def test_category_separation(self) -> None:
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "fake", FakeLLMProvider())
        registry.register(ProviderType.IMAGE_GENERATION, "fake", FakeImageGenerationProvider())
        assert isinstance(registry.resolve(ProviderType.LLM, "fake"), FakeLLMProvider)
        assert isinstance(
            registry.resolve(ProviderType.IMAGE_GENERATION, "fake"),
            FakeImageGenerationProvider,
        )

    def test_incompatible_provider_rejected(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(IncompatibleProviderError):
            registry.register(ProviderType.LLM, "bad", object())

    def test_empty_provider_id_rejected(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ValueError):
            registry.register(ProviderType.LLM, "", FakeLLMProvider())

    def test_unknown_provider_type_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderRegistryError):
            # type: ignore[arg-type]
            registry.resolve("unknown", "fake")  # type: ignore[arg-type]

    def test_isolated_registries(self) -> None:
        first = ProviderRegistry()
        second = ProviderRegistry()
        first.register(ProviderType.LLM, "fake", FakeLLMProvider())
        assert first.has(ProviderType.LLM, "fake")
        assert not second.has(ProviderType.LLM, "fake")

    def test_register_factory_class(self) -> None:
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "fake", FakeLLMProvider)
        resolved = registry.resolve(ProviderType.LLM, "fake")
        assert isinstance(resolved, FakeLLMProvider)

    def test_register_fake_defaults(self) -> None:
        registry = ProviderRegistry()
        registry.register_fake_defaults()
        assert isinstance(registry.resolve(ProviderType.LLM, "fake"), FakeLLMProvider)
        assert isinstance(
            registry.resolve(ProviderType.IMAGE_GENERATION, "fake"),
            FakeImageGenerationProvider,
        )
        assert isinstance(
            registry.resolve(ProviderType.VIDEO_GENERATION, "fake"),
            FakeVideoGenerationProvider,
        )
        assert isinstance(registry.resolve(ProviderType.TTS, "fake"), FakeTTSProvider)
        assert isinstance(
            registry.resolve(ProviderType.AUDIO_GENERATION, "fake"),
            FakeAudioGenerationProvider,
        )
        assert isinstance(registry.resolve(ProviderType.AI_QA, "fake"), FakeAIQAProvider)

    def test_default_registry_resolves_fake_without_credentials(self) -> None:
        registry = get_default_registry()
        assert isinstance(registry.resolve(ProviderType.LLM, "fake"), FakeLLMProvider)
        assert isinstance(
            registry.resolve(ProviderType.IMAGE_GENERATION, "fake"),
            FakeImageGenerationProvider,
        )
