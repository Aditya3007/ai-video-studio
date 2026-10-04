"""Factory for selecting the configured video generation provider."""

import os

from app.core.config import Settings, get_settings
from app.media_generation.video.json2video import JSON2VideoProvider
from app.media_generation.video.provider import VideoGenerationProvider
from app.model_registry import ModelCapabilityType
from app.provider_registry import ProviderType, get_default_registry
from app.services.cost_aware_selector import CostAwareSelector


class VideoGenerationProviderFactory:
    """Creates a video generation provider adapter from settings."""

    @staticmethod
    def create(
        settings: Settings | None = None,
        *,
        request=None,
    ) -> VideoGenerationProvider:
        """Return the configured video provider instance."""
        if settings is None:
            settings = get_settings()

        if (
            getattr(settings, "provider_selection_mode", "default") == "cost_aware"
            and request is not None
        ):
            selector = CostAwareSelector(allow_unknown=settings.cost_aware_allow_unknown)
            return selector.select_provider(
                ProviderType.VIDEO_GENERATION,
                {ModelCapabilityType.IMAGE_TO_VIDEO.value},
                cost_context={
                    "generation_type": "VIDEO",
                    "duration_seconds": getattr(request, "duration", None),
                },
            )

        provider = getattr(settings, "video_generation_provider", "fake")
        if provider == "fake":
            return get_default_registry().resolve(ProviderType.VIDEO_GENERATION, "fake")
        if provider == "json2video":
            return JSON2VideoProvider(
                api_key=os.getenv("JSON2VIDEO_API_KEY"),
            )
        if provider == "kling":
            raise NotImplementedError("Kling video provider is not yet implemented.")
        if provider == "runway":
            raise NotImplementedError("Runway video provider is not yet implemented.")
        if provider == "luma":
            raise NotImplementedError("Luma video provider is not yet implemented.")
        if provider == "sora":
            raise NotImplementedError("Sora video provider is not yet implemented.")
        if provider == "veo":
            raise NotImplementedError("Veo video provider is not yet implemented.")
        if provider == "local":
            raise NotImplementedError("Local video provider is not yet implemented.")

        raise ValueError(f"Unknown video generation provider: {provider}")
