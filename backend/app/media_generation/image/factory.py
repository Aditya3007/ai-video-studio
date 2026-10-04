"""Factory for selecting the configured image generation provider."""

import os

from app.core.config import Settings, get_settings
from app.media_generation.image.gemini import GeminiImageProvider
from app.media_generation.image.provider import ImageGenerationProvider
from app.model_registry import ModelCapabilityType
from app.provider_registry import ProviderType, get_default_registry
from app.services.cost_aware_selector import CostAwareSelector


class ImageGenerationProviderFactory:
    """Creates an image generation provider adapter from settings."""

    @staticmethod
    def create(
        settings: Settings | None = None,
        *,
        request=None,
    ) -> ImageGenerationProvider:
        """Return the configured image provider instance."""
        if settings is None:
            settings = get_settings()

        if (
            getattr(settings, "provider_selection_mode", "default") == "cost_aware"
            and request is not None
        ):
            selector = CostAwareSelector(allow_unknown=settings.cost_aware_allow_unknown)
            return selector.select_provider(
                ProviderType.IMAGE_GENERATION,
                {ModelCapabilityType.IMAGE_GENERATION.value},
                cost_context={
                    "generation_type": "IMAGE",
                    "num_images": getattr(request, "num_images", 1),
                    "width": getattr(request, "width", None),
                    "height": getattr(request, "height", None),
                },
            )

        provider = getattr(settings, "image_generation_provider", "fake")
        if provider == "fake":
            return get_default_registry().resolve(ProviderType.IMAGE_GENERATION, "fake")
        if provider == "google":
            return GeminiImageProvider(
                model=settings.image_generation_model or "gemini-3.1-flash-image",
                api_key=os.getenv("GEMINI_API_KEY"),
            )
        if provider == "openai":
            raise NotImplementedError("OpenAI image provider is not yet implemented.")
        if provider == "stability":
            raise NotImplementedError("Stability provider is not yet implemented.")
        if provider == "local":
            raise NotImplementedError("Local image provider is not yet implemented.")

        raise ValueError(f"Unknown image generation provider: {provider}")
