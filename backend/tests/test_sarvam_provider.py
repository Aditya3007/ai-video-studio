"""Tests for Sarvam TTS provider.

The provider is built on the real ``sarvamai`` SDK (``from sarvamai import SarvamAI``)
and calls ``SarvamAI.text_to_speech.convert`` over HTTPS to ``api.sarvam.ai``.
Every test here mocks the SDK client so no real Sarvam request is ever issued and
no real ``SARVAM_API_KEY`` is required.
"""

import base64
import sys
from unittest import mock

import pytest
import sarvamai

from app.media_generation.tts.errors import TTSError
from app.media_generation.tts.provider import TTSRequest
from app.media_generation.tts.sarvam import SarvamTTSProvider

pytestmark = pytest.mark.usefixtures("block_network")

WAV_BYTES = b"RIFF....WAVEfake-audio-payload"
INVALID_KEY_BODY = {
    "error": {
        "message": "Invalid or missing authentication credentials",
        "code": "invalid_api_key_error",
        "request_id": "sarvam-request-0001",
    }
}


def _build_response(audios: list[str] | None) -> mock.MagicMock:
    """Build a fake sarvamai text_to_speech response."""
    response = mock.MagicMock()
    response.audios = audios if audios is not None else []
    return response


class TestSarvamTTSProvider:
    """Tests for Sarvam TTS provider adapter."""

    def test_init_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization without API key raises error."""
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)

        with pytest.raises(TTSError, match="API key is required"):
            SarvamTTSProvider()

    def test_init_with_api_key_param(self) -> None:
        """Test initialization with API key parameter."""
        provider = SarvamTTSProvider(api_key="test_key")
        assert provider._api_key == "test_key"

    def test_init_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with environment variable."""
        monkeypatch.setenv("SARVAM_API_KEY", "test_key_from_env")

        provider = SarvamTTSProvider()
        assert provider._api_key == "test_key_from_env"

    def test_init_parameters(self) -> None:
        """Test initialization with custom parameters."""
        provider = SarvamTTSProvider(
            api_key="test_key",
            model="custom-model",
            language="en-US",
            voice="female",
        )
        assert provider._model == "custom-model"
        assert provider._language == "en-US"
        assert provider._voice == "female"

    def test_init_defaults(self) -> None:
        """Test that defaults match app/config/providers.yaml (tts section)."""
        provider = SarvamTTSProvider(api_key="test_key")
        assert provider._model == "bulbul:v3"
        assert provider._language == "hi-IN"
        assert provider._voice == "shubh"

    def test_init_without_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization without the sarvamai SDK raises a clear error."""
        monkeypatch.setitem(sys.modules, "sarvamai", None)

        with pytest.raises(TTSError, match="SarvamAI SDK is not installed"):
            SarvamTTSProvider(api_key="test_key")

    def test_init_builds_client_with_api_key(self) -> None:
        """Test that the Sarvam client is constructed with the configured subscription key."""
        with mock.patch("sarvamai.SarvamAI") as client_cls:
            provider = SarvamTTSProvider(api_key="test_key")

        client_cls.assert_called_once_with(api_subscription_key="test_key")
        assert provider._client is client_cls.return_value

    def test_synthesize_without_real_api_call(self) -> None:
        """Test synthesize returns a provider-neutral result with the SDK fully mocked."""
        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="test_key")
            provider._client.text_to_speech.convert.return_value = _build_response(
                [base64.b64encode(WAV_BYTES).decode("utf-8")]
            )

            result = provider.synthesize(TTSRequest(text="Hello world", voice_id="male"))

        assert result.provider == "sarvam"
        assert result.model == "bulbul:v3"
        assert result.audio.audio_format == "wav"
        assert result.audio.content_type == "audio/wav"

        expected_uri = f"data:audio/wav;base64,{base64.b64encode(WAV_BYTES).decode('utf-8')}"
        assert result.audio.uri == expected_uri
        assert result.metadata == {"language": "hi-IN", "voice": "male"}

    def test_synthesize_sends_request_parameters(self) -> None:
        """Test synthesize forwards text, voice, language and model to the SDK."""
        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="test_key")
            provider._client.text_to_speech.convert.return_value = _build_response(
                [base64.b64encode(WAV_BYTES).decode("utf-8")]
            )

            provider.synthesize(TTSRequest(text="Hello world", voice_id="male", language="en-US"))

        provider._client.text_to_speech.convert.assert_called_once_with(
            text="Hello world",
            language_code="en-US",
            model="bulbul:v3",
            speaker="male",
        )

    def test_synthesize_rejoins_base64_audio_fragments(self) -> None:
        """Test synthesize rejoins base64 fragments of a single audio stream.

        The provider concatenates the base64 strings before decoding, so a
        chunked response is a list of base64 fragments of one continuous stream.
        """
        encoded = base64.b64encode(WAV_BYTES).decode("utf-8")
        midpoint = len(encoded) // 2
        fragments = [encoded[:midpoint], encoded[midpoint:]]

        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="test_key")
            provider._client.text_to_speech.convert.return_value = _build_response(fragments)

            result = provider.synthesize(TTSRequest(text="Hello world", voice_id="male"))

        assert base64.b64decode(result.audio.uri.split(",", 1)[1]) == WAV_BYTES

    def test_synthesize_without_audio_data(self) -> None:
        """Test synthesize raises when Sarvam returns an empty audio list."""
        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="test_key")
            provider._client.text_to_speech.convert.return_value = _build_response([])

            with pytest.raises(TTSError, match="Sarvam did not return audio data"):
                provider.synthesize(TTSRequest(text="Hello world", voice_id="male"))

    def test_synthesize_rejects_invalid_credentials(self) -> None:
        """Test synthesize surfaces a 403 credential rejection without a real HTTP call."""
        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="invalid_key")
            provider._client.text_to_speech.convert.side_effect = sarvamai.ForbiddenError(
                INVALID_KEY_BODY, headers={"content-type": "application/json"}
            )

            with pytest.raises(TTSError, match="Sarvam TTS synthesis failed") as exc:
                provider.synthesize(TTSRequest(text="Hello world", voice_id="male"))

        message = str(exc.value)
        assert "403" in message
        assert "Invalid or missing authentication credentials" in message
        assert "invalid_api_key_error" in message

    def test_synthesize_rejects_expired_credentials(self) -> None:
        """Test synthesize surfaces a 401 credential rejection as a TTSError."""
        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="expired_key")
            provider._client.text_to_speech.convert.side_effect = sarvamai.UnauthorizedError(
                {"error": {"message": "Invalid or missing authentication credentials"}},
                headers={},
            )

            with pytest.raises(TTSError, match="Sarvam TTS synthesis failed") as exc:
                provider.synthesize(TTSRequest(text="Hello world", voice_id="male"))

        assert "401" in str(exc.value)

    def test_synthesize_wraps_transport_failure(self) -> None:
        """Test synthesize wraps unexpected transport errors as TTSError."""
        with mock.patch("sarvamai.SarvamAI"):
            provider = SarvamTTSProvider(api_key="test_key")
            provider._client.text_to_speech.convert.side_effect = sarvamai.BadGatewayError(
                {"error": {"message": "Upstream unavailable"}}, headers={}
            )

            with pytest.raises(TTSError, match="Sarvam TTS synthesis failed"):
                provider.synthesize(TTSRequest(text="Hello world", voice_id="male"))
