"""Offline fake image generation provider for local tests."""

from app.media_generation.image.errors import (
    ImageGenerationError,
    ImageGenerationFailedError,
    ImageProviderAuthError,
    ImageProviderRateLimitError,
    ImageProviderUnavailableError,
    ImageRequestError,
)
from app.media_generation.image.provider import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageReference,
    ImageUsage,
)


class FakeImageGenerationProvider:
    """Deterministic offline image provider requiring no network or API keys."""

    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str = "fake-image-model",
        fail_mode: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._fail_mode = fail_mode

    @staticmethod
    def _resolve_dimensions(aspect_ratio: str | None) -> tuple[int, int]:
        if aspect_ratio is None:
            return 1024, 1024
        try:
            width, height = aspect_ratio.split(":")
            w = int(width)
            h = int(height)
        except (ValueError, AttributeError):
            return 1024, 1024
        if w <= 0 or h <= 0:
            return 1024, 1024
        # Scale to a reference short side of 1024 while preserving ratio.
        if w >= h:
            return int(1024 * (w / h)), 1024
        return 1024, int(1024 * (h / w))

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Return deterministic provider-neutral image references."""
        if not request.prompt or not request.prompt.strip():
            raise ImageRequestError("Prompt is required.")

        if self._fail_mode == "auth":
            raise ImageProviderAuthError("Simulated authentication failure.")
        if self._fail_mode == "unavailable":
            raise ImageProviderUnavailableError("Simulated provider outage.")
        if self._fail_mode == "rate_limit":
            raise ImageProviderRateLimitError("Simulated rate limit.")
        if self._fail_mode == "generation":
            raise ImageGenerationFailedError("Simulated generation failure.")
        if self._fail_mode is not None:
            raise ImageGenerationError(f"Simulated failure: {self._fail_mode}")

        width, height = self._resolve_dimensions(request.aspect_ratio)
        if request.width and request.height:
            width, height = request.width, request.height

        seed = request.seed if request.seed is not None else hash(request.prompt)
        images: list[ImageReference] = []
        for idx in range(request.num_images):
            images.append(
                ImageReference(
                    uri=f"fake://image/{seed}/{idx}.png",
                    width=width,
                    height=height,
                    content_type="image/png",
                    metadata={"seed": seed, "index": idx},
                )
            )

        return ImageGenerationResult(
            images=images,
            provider=self._provider,
            model=self._model,
            request_id=f"fake-req-{seed}",
            usage=ImageUsage(credits=request.num_images, cost_usd=0.0),
            metadata={
                "provider": self._provider,
                "model": self._model,
                "seed": seed,
                "aspect_ratio": request.aspect_ratio,
            },
        )
