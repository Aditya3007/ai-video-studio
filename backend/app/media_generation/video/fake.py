"""Offline fake video generation provider for local tests."""

from app.media_generation.video.errors import (
    VideoCapabilityError,
    VideoGenerationError,
    VideoGenerationFailedError,
    VideoProviderAuthError,
    VideoProviderRateLimitError,
    VideoProviderUnavailableError,
    VideoRequestError,
)
from app.media_generation.video.provider import (
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoReference,
    VideoUsage,
)


class FakeVideoGenerationProvider:
    """Deterministic offline video provider requiring no network or API keys."""

    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str = "fake-video-model",
        fail_mode: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._fail_mode = fail_mode

    @staticmethod
    def _resolve_dimensions(aspect_ratio: str | None) -> tuple[int, int]:
        if aspect_ratio is None:
            return 1080, 1920
        try:
            width, height = aspect_ratio.split(":")
            w = int(width)
            h = int(height)
        except (ValueError, AttributeError):
            return 1080, 1920
        if w <= 0 or h <= 0:
            return 1080, 1920
        return w * 160, h * 160

    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """Return deterministic provider-neutral video references."""
        if not request.prompt or not request.prompt.strip():
            raise VideoRequestError("Prompt is required.")

        if self._fail_mode == "auth":
            raise VideoProviderAuthError("Simulated authentication failure.")
        if self._fail_mode == "unavailable":
            raise VideoProviderUnavailableError("Simulated provider outage.")
        if self._fail_mode == "rate_limit":
            raise VideoProviderRateLimitError("Simulated rate limit.")
        if self._fail_mode == "generation":
            raise VideoGenerationFailedError("Simulated generation failure.")
        if self._fail_mode == "capability":
            raise VideoCapabilityError("Simulated unsupported capability.")
        if self._fail_mode is not None:
            raise VideoGenerationError(f"Simulated failure: {self._fail_mode}")

        if request.duration is not None and request.duration <= 0:
            raise VideoRequestError("Duration must be positive.")

        width, height = self._resolve_dimensions(request.aspect_ratio)
        if request.width and request.height:
            width, height = request.width, request.height

        duration = request.duration if request.duration is not None else 5.0
        seed = request.seed if request.seed is not None else hash(request.prompt)

        video_bytes = f"fake video data for {seed}".encode()
        return VideoGenerationResult(
            videos=[
                VideoReference(
                    uri=f"fake://video/{seed}.mp4",
                    width=width,
                    height=height,
                    duration=duration,
                    content_type="video/mp4",
                    data=video_bytes,
                    metadata={
                        "seed": seed,
                        "reference_assets": [str(aid) for aid in request.reference_asset_ids],
                        "keyframes": [str(aid) for aid in request.keyframe_asset_ids],
                    },
                )
            ],
            provider=self._provider,
            model=self._model,
            request_id=f"fake-req-{seed}",
            usage=VideoUsage(credits=1, cost_usd=0.0),
            metadata={
                "provider": self._provider,
                "model": self._model,
                "seed": seed,
                "aspect_ratio": request.aspect_ratio,
                "duration": duration,
            },
        )
