"""Factory for selecting the configured audio generation provider."""

from app.core.config import Settings, get_settings
from app.media_generation.audio.provider import AudioGenerationProvider
from app.provider_registry import ProviderType, get_default_registry


class AudioGenerationProviderFactory:
    """Creates a music/sound-effect provider adapter from settings."""

    @staticmethod
    def create(settings: Settings | None = None) -> AudioGenerationProvider:
        """Return the configured audio generation provider instance."""
        if settings is None:
            settings = get_settings()

        provider = getattr(settings, "audio_generation_provider", "fake")
        if provider == "fake":
            return get_default_registry().resolve(ProviderType.AUDIO_GENERATION, "fake")
        if provider == "openai":
            raise NotImplementedError("OpenAI audio provider is not yet implemented.")
        if provider == "stability":
            raise NotImplementedError("Stability audio provider is not yet implemented.")
        if provider == "suno":
            raise NotImplementedError("Suno audio provider is not yet implemented.")
        if provider == "udio":
            raise NotImplementedError("Udio audio provider is not yet implemented.")
        if provider == "elevenlabs":
            raise NotImplementedError("ElevenLabs audio provider is not yet implemented.")
        if provider == "local":
            raise NotImplementedError("Local audio provider is not yet implemented.")

        raise ValueError(f"Unknown audio generation provider: {provider}")
