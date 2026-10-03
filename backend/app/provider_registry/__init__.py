"""Unified provider registry for provider-neutral AI/media adapters."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from typing import Literal

    from app.media_generation.audio.provider import AudioGenerationProvider
    from app.media_generation.image.provider import ImageGenerationProvider
    from app.media_generation.tts.provider import TTSProvider
    from app.media_generation.video.provider import VideoGenerationProvider
    from app.publishing import PublishingProvider
    from app.services.ai_qa_service import AIQAProvider
    from app.story_intelligence.llm.provider import LLMProvider

__all__ = [
    "DuplicateProviderError",
    "get_default_registry",
    "IncompatibleProviderError",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderType",
]


class ProviderType(StrEnum):
    """Provider category identifiers."""

    LLM = "llm"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    TTS = "tts"
    AUDIO_GENERATION = "audio_generation"
    AI_QA = "ai_qa"
    PUBLISHING = "publishing"


class ProviderRegistryError(Exception):
    """Base error for provider registry failures."""


class ProviderNotFoundError(ProviderRegistryError):
    """Raised when a requested provider is not registered."""


class DuplicateProviderError(ProviderRegistryError):
    """Raised when registering a provider with an existing ID without override."""


class IncompatibleProviderError(ProviderRegistryError):
    """Raised when a provider does not satisfy the expected protocol."""


def _protocol_for_type(type_: ProviderType) -> type:
    """Lazy protocol import to avoid import cycles at module load."""
    if type_ == ProviderType.LLM:
        from app.story_intelligence.llm.provider import LLMProvider

        return LLMProvider
    if type_ == ProviderType.IMAGE_GENERATION:
        from app.media_generation.image.provider import ImageGenerationProvider

        return ImageGenerationProvider
    if type_ == ProviderType.VIDEO_GENERATION:
        from app.media_generation.video.provider import VideoGenerationProvider

        return VideoGenerationProvider
    if type_ == ProviderType.TTS:
        from app.media_generation.tts.provider import TTSProvider

        return TTSProvider
    if type_ == ProviderType.AUDIO_GENERATION:
        from app.media_generation.audio.provider import AudioGenerationProvider

        return AudioGenerationProvider
    if type_ == ProviderType.AI_QA:
        from app.services.ai_qa_service import AIQAProvider

        return AIQAProvider
    if type_ == ProviderType.PUBLISHING:
        from app.publishing import PublishingProvider

        return PublishingProvider
    raise ProviderRegistryError(f"Unknown provider type: {type_}")


def _default_fake_instance(type_: ProviderType) -> Any:
    """Lazy fake provider import to avoid import cycles at module load."""
    if type_ == ProviderType.LLM:
        from app.story_intelligence.llm.fake import FakeLLMProvider

        return FakeLLMProvider()
    if type_ == ProviderType.IMAGE_GENERATION:
        from app.media_generation.image.fake import FakeImageGenerationProvider

        return FakeImageGenerationProvider()
    if type_ == ProviderType.VIDEO_GENERATION:
        from app.media_generation.video.fake import FakeVideoGenerationProvider

        return FakeVideoGenerationProvider()
    if type_ == ProviderType.TTS:
        from app.media_generation.tts.fake import FakeTTSProvider

        return FakeTTSProvider()
    if type_ == ProviderType.AUDIO_GENERATION:
        from app.media_generation.audio.fake import FakeAudioGenerationProvider

        return FakeAudioGenerationProvider()
    if type_ == ProviderType.AI_QA:
        from app.services.ai_qa_service import FakeAIQAProvider

        return FakeAIQAProvider()
    if type_ == ProviderType.PUBLISHING:
        from app.publishing import FakePublishingProvider

        return FakePublishingProvider()
    raise ProviderRegistryError(f"Unknown provider type: {type_}")


class ProviderRegistry:
    """Registers and resolves provider implementations by category and ID."""

    def __init__(self) -> None:
        self._providers: dict[ProviderType, dict[str, Any]] = {t: {} for t in ProviderType}

    def register(
        self,
        type_: ProviderType,
        provider_id: str,
        provider: Any | Callable[[], Any],
        *,
        override: bool = False,
    ) -> None:
        """Register a provider instance or factory for the given type and ID."""
        if not provider_id:
            raise ValueError("provider_id must be non-empty")
        protocol = _protocol_for_type(type_)

        if not override and provider_id in self._providers[type_]:
            raise DuplicateProviderError(
                f"Provider '{provider_id}' is already registered for {type_}"
            )

        self._providers[type_][provider_id] = self._validate(provider, protocol)

    @staticmethod
    def _validate(provider: Any, protocol: type) -> Any:
        if isinstance(provider, protocol):
            return provider
        if isinstance(provider, type) and issubclass(provider, protocol):
            return provider
        if callable(provider):
            return provider
        raise IncompatibleProviderError(
            f"Provider does not satisfy the {protocol.__name__} protocol"
        )

    def has(self, type_: ProviderType, provider_id: str) -> bool:
        """Return True if a provider is registered for the given type and ID."""
        return provider_id in self._providers.get(type_, {})

    def list(self, type_: ProviderType) -> list[str]:
        """Return registered provider IDs for the given type."""
        return sorted(self._providers.get(type_, {}).keys())

    @overload
    def resolve(self, type_: Literal[ProviderType.LLM], provider_id: str) -> LLMProvider:
        ...

    @overload
    def resolve(
        self, type_: Literal[ProviderType.IMAGE_GENERATION], provider_id: str
    ) -> ImageGenerationProvider:
        ...

    @overload
    def resolve(
        self, type_: Literal[ProviderType.VIDEO_GENERATION], provider_id: str
    ) -> VideoGenerationProvider:
        ...

    @overload
    def resolve(self, type_: Literal[ProviderType.TTS], provider_id: str) -> TTSProvider:
        ...

    @overload
    def resolve(
        self, type_: Literal[ProviderType.AUDIO_GENERATION], provider_id: str
    ) -> AudioGenerationProvider:
        ...

    @overload
    def resolve(self, type_: Literal[ProviderType.AI_QA], provider_id: str) -> AIQAProvider:
        ...

    @overload
    def resolve(
        self, type_: Literal[ProviderType.PUBLISHING], provider_id: str
    ) -> PublishingProvider:
        ...

    def resolve(self, type_: ProviderType, provider_id: str) -> Any:
        """Resolve a registered provider by type and ID."""
        protocol = _protocol_for_type(type_)
        provider = self._providers[type_].get(provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found for {type_}")
        if isinstance(provider, type):
            return provider()
        if isinstance(provider, protocol):
            return provider
        if callable(provider):
            resolved = provider()
            if not isinstance(resolved, protocol):
                raise IncompatibleProviderError(
                    f"Factory for '{provider_id}' did not return a valid {type_} provider"
                )
            return resolved
        return provider

    def register_fake_defaults(self) -> None:
        """Register the built-in fake providers for every category."""
        for ptype in ProviderType:
            self.register(ptype, "fake", _default_fake_instance(ptype))


_default_registry: ProviderRegistry | None = None


def get_default_registry() -> ProviderRegistry:
    """Return the process-wide default registry with fake providers registered."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
        _default_registry.register_fake_defaults()
    return _default_registry
