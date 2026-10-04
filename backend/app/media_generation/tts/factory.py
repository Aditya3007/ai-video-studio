"""Factory for selecting the configured TTS provider."""

import os

from app.core.config import Settings, get_settings
from app.media_generation.tts.provider import TTSProvider
from app.media_generation.tts.sarvam import SarvamTTSProvider
from app.model_registry import ModelCapabilityType
from app.provider_registry import ProviderType, get_default_registry
from app.services.cost_aware_selector import CostAwareSelector


class TTSProviderFactory:
    """Creates a text-to-speech provider adapter from settings."""

    @staticmethod
    def create(
        settings: Settings | None = None,
        *,
        request=None,
    ) -> TTSProvider:
        """Return the configured TTS provider instance."""
        if settings is None:
            settings = get_settings()

        if (
            getattr(settings, "provider_selection_mode", "default") == "cost_aware"
            and request is not None
        ):
            selector = CostAwareSelector(allow_unknown=settings.cost_aware_allow_unknown)
            return selector.select_provider(
                ProviderType.TTS,
                {ModelCapabilityType.SPEECH_SYNTHESIS.value},
                cost_context={
                    "generation_type": "TTS",
                    "character_count": len(getattr(request, "text", "")),
                },
            )

        provider = getattr(settings, "tts_provider", "fake")
        if provider == "fake":
            return get_default_registry().resolve(ProviderType.TTS, "fake")
        if provider == "sarvam":
            return SarvamTTSProvider(
                model=settings.tts_model or "bulbul:v3",
                api_key=os.getenv("SARVAM_API_KEY"),
            )
        if provider == "openai":
            raise NotImplementedError("OpenAI TTS provider is not yet implemented.")
        if provider == "elevenlabs":
            raise NotImplementedError("ElevenLabs TTS provider is not yet implemented.")
        if provider == "google":
            raise NotImplementedError("Google Cloud TTS provider is not yet implemented.")
        if provider == "azure":
            raise NotImplementedError("Azure Speech TTS provider is not yet implemented.")
        if provider == "amazon":
            raise NotImplementedError("AWS Polly TTS provider is not yet implemented.")

        raise ValueError(f"Unknown TTS provider: {provider}")
