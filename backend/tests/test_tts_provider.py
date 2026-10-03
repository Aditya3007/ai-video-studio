"""P7-T02 TTS provider boundary tests."""

import pytest

from app.media_generation.tts import (
    FakeTTSProvider,
    TTSCapabilityError,
    TTSError,
    TTSProvider,
    TTSProviderAuthError,
    TTSProviderFactory,
    TTSProviderRateLimitError,
    TTSProviderUnavailableError,
    TTSReference,
    TTSRequest,
    TTSResult,
    TTSSynthesisFailedError,
    TTSUsage,
)


class TestTTSRequest:
    def test_valid_request(self) -> None:
        request = TTSRequest(text="Hello world", voice_id="voice-123")
        assert request.text == "Hello world"
        assert request.voice_id == "voice-123"

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValueError):
            TTSRequest(text="", voice_id="voice-123")

    def test_optional_fields(self) -> None:
        request = TTSRequest(
            text="Hello",
            voice_id="voice-123",
            language="en-US",
            speaking_style="narrative",
            output_format="mp3",
            options={"speed": 1.0},
        )
        assert request.language == "en-US"
        assert request.speaking_style == "narrative"
        assert request.output_format == "mp3"
        assert request.options == {"speed": 1.0}


class TestFakeTTSProvider:
    def test_successful_synthesis(self) -> None:
        provider = FakeTTSProvider()
        request = TTSRequest(text="Hello world", voice_id="voice-123")
        result = provider.synthesize(request)
        assert isinstance(result, TTSResult)
        assert isinstance(result.audio, TTSReference)
        assert result.audio.content_type == "audio/mpeg"
        assert result.audio.audio_format == "mp3"
        assert result.audio.duration is not None
        assert result.audio.data is not None
        assert result.provider == "fake"
        assert result.request_id.startswith("fake-req-")
        assert isinstance(result.usage, TTSUsage)
        assert result.usage.cost_usd == 0.0

    def test_provider_neutral_result(self) -> None:
        provider = FakeTTSProvider()
        result = provider.synthesize(TTSRequest(text="Hello", voice_id="voice-1"))
        assert "fake://audio/" in result.audio.uri
        assert result.provider == "fake"
        assert result.model == "fake-tts-model"

    def test_custom_output_format(self) -> None:
        provider = FakeTTSProvider()
        request = TTSRequest(text="Hello", voice_id="voice-1", output_format="wav")
        result = provider.synthesize(request)
        assert result.audio.audio_format == "wav"

    @pytest.mark.parametrize(
        "fail_mode,exc_type",
        [
            ("auth", TTSProviderAuthError),
            ("unavailable", TTSProviderUnavailableError),
            ("rate_limit", TTSProviderRateLimitError),
            ("synthesis", TTSSynthesisFailedError),
            ("capability", TTSCapabilityError),
        ],
    )
    def test_failure_modes(self, fail_mode: str, exc_type: type[Exception]) -> None:
        provider = FakeTTSProvider(fail_mode=fail_mode)
        request = TTSRequest(text="Test failure", voice_id="voice-1")
        with pytest.raises(exc_type):
            provider.synthesize(request)

    def test_unknown_fail_mode_raises_base_error(self) -> None:
        provider = FakeTTSProvider(fail_mode="unknown")
        request = TTSRequest(text="Test", voice_id="voice-1")
        with pytest.raises(TTSError):
            provider.synthesize(request)


class TestTTSProviderInterface:
    def test_fake_provider_satisfies_protocol(self) -> None:
        provider = FakeTTSProvider()
        assert isinstance(provider, TTSProvider)

    def test_interface_returns_provider_neutral_result(self) -> None:
        provider: TTSProvider = FakeTTSProvider()
        result = provider.synthesize(TTSRequest(text="Hello", voice_id="voice-1"))
        assert isinstance(result, TTSResult)
        assert not isinstance(result, Exception)


class TestVoiceMapping:
    def test_voice_mapping_stays_inside_adapter(self) -> None:
        canonical_voice_id = "canonical-narrator"
        provider_voice_id = "elevenlabs-voice-abc123"
        provider = FakeTTSProvider(voice_mapping={canonical_voice_id: provider_voice_id})
        request = TTSRequest(text="Hello", voice_id=canonical_voice_id)
        result = provider.synthesize(request)
        assert result.audio.metadata["provider_voice_id"] == provider_voice_id
        assert result.audio.metadata["provider_voice_id"] != canonical_voice_id
        assert result.metadata["provider_voice_id"] == provider_voice_id

    def test_default_voice_mapping_is_deterministic(self) -> None:
        provider = FakeTTSProvider()
        request = TTSRequest(text="Hello", voice_id="canonical-voice")
        result = provider.synthesize(request)
        assert result.audio.metadata["provider_voice_id"] == "fake-voice-canonical-voice"
        assert result.audio.metadata["provider_voice_id"] != request.voice_id


class TestTTSProviderFactory:
    def test_factory_returns_fake_by_default(self) -> None:
        provider = TTSProviderFactory.create()
        assert isinstance(provider, FakeTTSProvider)

    def test_factory_rejects_unknown_provider(self) -> None:
        settings = type("Settings", (), {"tts_provider": "unknown"})()
        with pytest.raises(ValueError):
            TTSProviderFactory.create(settings)

    def test_factory_rejects_unimplemented_real_providers(self) -> None:
        for provider_name in ("openai", "elevenlabs", "google", "azure", "amazon"):
            settings = type("Settings", (), {"tts_provider": provider_name})()
            with pytest.raises(NotImplementedError):
                TTSProviderFactory.create(settings)


class TestProviderIsolation:
    def test_no_vendor_types_in_result(self) -> None:
        provider = FakeTTSProvider()
        result = provider.synthesize(TTSRequest(text="Hello", voice_id="voice-1"))
        result_dict = result.model_dump()
        assert "openai" not in str(result_dict).lower()
        assert "elevenlabs" not in str(result_dict).lower()
