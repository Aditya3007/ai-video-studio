"""Sarvam TTS provider adapter."""

import base64
import os

from app.media_generation.tts.errors import TTSError
from app.media_generation.tts.provider import (
    TTSReference,
    TTSRequest,
    TTSResult,
    TTSUsage,
)


class SarvamTTSProvider:
    """Sarvam TTS provider adapter using SarvamAI SDK."""

    def __init__(
        self,
        *,
        model: str = "bulbul:v3",
        language: str = "hi-IN",
        voice: str = "shubh",
        api_key: str | None = None,
    ) -> None:
        """Initialize Sarvam provider.

        Args:
            model: Sarvam model identifier (bulbul:v3).
            language: Language code (e.g., hi-IN for Hindi).
            voice: Voice identifier (e.g., shubh).
            api_key: Sarvam API key. If None, reads from SARVAM_API_KEY environment variable.
        """
        self._model = model
        self._language = language
        self._voice = voice
        self._api_key = api_key or os.getenv("SARVAM_API_KEY")

        if not self._api_key:
            raise TTSError(
                "Sarvam API key is required. Set SARVAM_API_KEY environment "
                "variable or pass api_key parameter."
            )

        try:
            from sarvamai import SarvamAI

            self._client = SarvamAI(api_subscription_key=self._api_key)
        except ImportError as exc:
            raise TTSError(
                "SarvamAI SDK is not installed. Install with: pip install sarvamai"
            ) from exc

    def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech using Sarvam.

        Args:
            request: Provider-neutral TTS request.

        Returns:
            Provider-neutral TTS result.

        Raises:
            TTSError: If synthesis fails.
        """
        try:
            # Call Sarvam text-to-speech API
            response = self._client.text_to_speech.convert(
                text=request.text,
                language_code=request.language or self._language,
                model=self._model,
                speaker=request.voice_id or self._voice,
            )

            # Extract audio data from response
            # Sarvam returns audio as a list of base64-encoded WAV strings
            if response.audios and len(response.audios) > 0:
                # Join and decode the base64 audio data
                audio_data = base64.b64decode("".join(response.audios))

                # Create base64 URI for the audio
                uri = f"data:audio/wav;base64,{base64.b64encode(audio_data).decode('utf-8')}"

                audio_ref = TTSReference(
                    uri=uri,
                    content_type="audio/wav",
                    audio_format="wav",
                    duration=None,  # Duration not provided in basic response
                )

                return TTSResult(
                    audio=audio_ref,
                    provider="sarvam",
                    model=self._model,
                    usage=TTSUsage(
                        cost_usd=0.0,  # Placeholder for actual pricing
                    ),
                    metadata={
                        "language": request.language or self._language,
                        "voice": request.voice_id or self._voice,
                    },
                )

            raise TTSError("Sarvam did not return audio data")

        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Sarvam TTS synthesis failed: {exc}") from exc
