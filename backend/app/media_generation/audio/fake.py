"""Offline fake music/sound-effect provider for local tests."""

from app.media_generation.audio.errors import (
    AudioCapabilityError,
    AudioGenerationError,
    AudioGenerationFailedError,
    AudioProviderAuthError,
    AudioProviderRateLimitError,
    AudioProviderUnavailableError,
    AudioRequestError,
)
from app.media_generation.audio.provider import (
    AudioGenerationRequest,
    AudioGenerationResult,
    AudioReference,
    AudioUsage,
)


class FakeAudioGenerationProvider:
    """Deterministic offline audio provider requiring no network or API keys."""

    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str = "fake-audio-model",
        fail_mode: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._fail_mode = fail_mode

    def generate(self, request: AudioGenerationRequest) -> AudioGenerationResult:
        """Return deterministic provider-neutral audio references."""
        if not request.prompt or not request.prompt.strip():
            raise AudioRequestError("Prompt is required.")

        if self._fail_mode == "auth":
            raise AudioProviderAuthError("Simulated authentication failure.")
        if self._fail_mode == "unavailable":
            raise AudioProviderUnavailableError("Simulated provider outage.")
        if self._fail_mode == "rate_limit":
            raise AudioProviderRateLimitError("Simulated rate limit.")
        if self._fail_mode == "generation":
            raise AudioGenerationFailedError("Simulated generation failure.")
        if self._fail_mode == "capability":
            raise AudioCapabilityError("Simulated unsupported capability.")
        if self._fail_mode is not None:
            raise AudioGenerationError(f"Simulated failure: {self._fail_mode}")

        seed = request.seed if request.seed is not None else hash(request.prompt)
        duration = request.duration if request.duration is not None else 5.0
        audio_bytes = f"fake audio data for {seed}".encode()
        audio_format = request.output_format or "mp3"

        return AudioGenerationResult(
            audio=AudioReference(
                uri=f"fake://audio/{request.audio_type.lower()}/{seed}.{audio_format}",
                content_type="audio/mpeg",
                audio_format=audio_format,
                duration=duration,
                data=audio_bytes,
                metadata={
                    "seed": seed,
                    "audio_type": request.audio_type,
                    "duration": duration,
                },
            ),
            provider=self._provider,
            model=self._model,
            request_id=f"fake-req-{seed}",
            usage=AudioUsage(credits=1, cost_usd=0.0),
            metadata={
                "provider": self._provider,
                "model": self._model,
                "seed": seed,
                "audio_type": request.audio_type,
                "duration": duration,
            },
        )
