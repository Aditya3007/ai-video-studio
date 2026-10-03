"""Offline fake TTS provider for local tests."""

from app.media_generation.tts.errors import (
    TTSCapabilityError,
    TTSError,
    TTSProviderAuthError,
    TTSProviderRateLimitError,
    TTSProviderUnavailableError,
    TTSRequestError,
    TTSSynthesisFailedError,
)
from app.media_generation.tts.provider import (
    TTSReference,
    TTSRequest,
    TTSResult,
    TTSUsage,
)


class FakeTTSProvider:
    """Deterministic offline TTS provider requiring no network or API keys."""

    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str = "fake-tts-model",
        fail_mode: str | None = None,
        voice_mapping: dict[str, str] | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._fail_mode = fail_mode
        self._voice_mapping = voice_mapping or {}

    def _map_voice(self, request: TTSRequest) -> str:
        """Return the provider-specific voice id for the canonical voice_id.

        The mapping is kept entirely inside the adapter boundary. The canonical
        ``Voice.id`` from the application domain is never used as the vendor
        voice identifier.
        """
        if request.voice_id in self._voice_mapping:
            return self._voice_mapping[request.voice_id]
        return f"fake-voice-{request.voice_id}"

    def synthesize(self, request: TTSRequest) -> TTSResult:
        """Return deterministic provider-neutral audio references."""
        if not request.text or not request.text.strip():
            raise TTSRequestError("Text is required.")

        if self._fail_mode == "auth":
            raise TTSProviderAuthError("Simulated authentication failure.")
        if self._fail_mode == "unavailable":
            raise TTSProviderUnavailableError("Simulated provider outage.")
        if self._fail_mode == "rate_limit":
            raise TTSProviderRateLimitError("Simulated rate limit.")
        if self._fail_mode == "synthesis":
            raise TTSSynthesisFailedError("Simulated synthesis failure.")
        if self._fail_mode == "capability":
            raise TTSCapabilityError("Simulated unsupported capability.")
        if self._fail_mode is not None:
            raise TTSError(f"Simulated failure: {self._fail_mode}")

        provider_voice_id = self._map_voice(request)
        seed = hash(request.text)
        audio_bytes = f"fake audio data for {seed}".encode()
        duration = 1.0 + (len(request.text) / 20.0)

        return TTSResult(
            audio=TTSReference(
                uri=f"fake://audio/{seed}.mp3",
                content_type="audio/mpeg",
                audio_format=request.output_format or "mp3",
                duration=duration,
                data=audio_bytes,
                metadata={
                    "provider_voice_id": provider_voice_id,
                    "seed": seed,
                    "language": request.language,
                    "speaking_style": request.speaking_style,
                },
            ),
            provider=self._provider,
            model=self._model,
            request_id=f"fake-req-{seed}",
            usage=TTSUsage(credits=1, cost_usd=0.0),
            metadata={
                "provider": self._provider,
                "model": self._model,
                "provider_voice_id": provider_voice_id,
                "language": request.language,
                "output_format": request.output_format,
            },
        )
