"""P7-T04 Music/sound-effect generation provider boundary tests."""

import pytest

from app.media_generation.audio import (
    AudioCapabilityError,
    AudioGenerationFailedError,
    AudioGenerationProvider,
    AudioGenerationProviderFactory,
    AudioGenerationRequest,
    AudioGenerationResult,
    AudioProviderAuthError,
    AudioProviderRateLimitError,
    AudioProviderUnavailableError,
    AudioReference,
    AudioRequestError,
    AudioUsage,
    FakeAudioGenerationProvider,
)


class TestAudioGenerationRequest:
    def test_valid_music_request(self) -> None:
        request = AudioGenerationRequest(
            audio_type="MUSIC",
            prompt="Epic orchestral theme",
            duration=10.0,
            output_format="mp3",
        )
        assert request.audio_type == "MUSIC"
        assert request.prompt == "Epic orchestral theme"
        assert request.duration == 10.0
        assert request.output_format == "mp3"

    def test_valid_sound_effect_request(self) -> None:
        request = AudioGenerationRequest(
            audio_type="sound_effect",
            prompt="Door creak",
        )
        assert request.audio_type == "SOUND_EFFECT"
        assert request.prompt == "Door creak"

    def test_invalid_audio_type(self) -> None:
        with pytest.raises(ValueError):
            AudioGenerationRequest(audio_type="VOICE", prompt="Test")

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValueError):
            AudioGenerationRequest(audio_type="MUSIC", prompt="Test", duration=-1.0)


class TestFakeAudioGenerationProvider:
    def test_successful_music_generation(self) -> None:
        provider = FakeAudioGenerationProvider()
        request = AudioGenerationRequest(audio_type="MUSIC", prompt="Hero theme")
        result = provider.generate(request)
        assert isinstance(result, AudioGenerationResult)
        assert isinstance(result.audio, AudioReference)
        assert result.audio.content_type == "audio/mpeg"
        assert result.audio.audio_format == "mp3"
        assert result.audio.duration is not None
        assert result.audio.data is not None
        assert result.provider == "fake"
        assert result.request_id.startswith("fake-req-")
        assert isinstance(result.usage, AudioUsage)
        assert result.usage.cost_usd == 0.0

    def test_successful_sound_effect_generation(self) -> None:
        provider = FakeAudioGenerationProvider()
        request = AudioGenerationRequest(audio_type="SOUND_EFFECT", prompt="Explosion")
        result = provider.generate(request)
        assert result.audio.audio_format == "mp3"
        assert "sound_effect" in result.audio.uri

    def test_custom_output_format(self) -> None:
        provider = FakeAudioGenerationProvider()
        request = AudioGenerationRequest(
            audio_type="MUSIC",
            prompt="Theme",
            output_format="wav",
        )
        result = provider.generate(request)
        assert result.audio.audio_format == "wav"

    def test_empty_prompt_rejected(self) -> None:
        provider = FakeAudioGenerationProvider()
        request = AudioGenerationRequest(audio_type="MUSIC", prompt="   ")
        with pytest.raises(AudioRequestError):
            provider.generate(request)

    @pytest.mark.parametrize(
        "fail_mode,exc_type",
        [
            ("auth", AudioProviderAuthError),
            ("unavailable", AudioProviderUnavailableError),
            ("rate_limit", AudioProviderRateLimitError),
            ("generation", AudioGenerationFailedError),
            ("capability", AudioCapabilityError),
        ],
    )
    def test_failure_modes(self, fail_mode: str, exc_type: type[Exception]) -> None:
        provider = FakeAudioGenerationProvider(fail_mode=fail_mode)
        request = AudioGenerationRequest(audio_type="MUSIC", prompt="Test failure")
        with pytest.raises(exc_type):
            provider.generate(request)


class TestAudioGenerationProviderInterface:
    def test_fake_provider_satisfies_protocol(self) -> None:
        provider = FakeAudioGenerationProvider()
        assert isinstance(provider, AudioGenerationProvider)

    def test_interface_returns_provider_neutral_result(self) -> None:
        provider: AudioGenerationProvider = FakeAudioGenerationProvider()
        result = provider.generate(AudioGenerationRequest(audio_type="MUSIC", prompt="Hello"))
        assert isinstance(result, AudioGenerationResult)
        assert not isinstance(result, Exception)


class TestAudioGenerationProviderFactory:
    def test_factory_returns_fake_by_default(self) -> None:
        provider = AudioGenerationProviderFactory.create()
        assert isinstance(provider, FakeAudioGenerationProvider)

    def test_factory_rejects_unknown_provider(self) -> None:
        settings = type("Settings", (), {"audio_generation_provider": "unknown"})()
        with pytest.raises(ValueError):
            AudioGenerationProviderFactory.create(settings)

    def test_factory_rejects_unimplemented_real_providers(self) -> None:
        for provider_name in ("openai", "stability", "suno", "udio", "elevenlabs", "local"):
            settings = type("Settings", (), {"audio_generation_provider": provider_name})()
            with pytest.raises(NotImplementedError):
                AudioGenerationProviderFactory.create(settings)


class TestProviderIsolation:
    def test_no_vendor_types_in_result(self) -> None:
        provider = FakeAudioGenerationProvider()
        result = provider.generate(AudioGenerationRequest(audio_type="MUSIC", prompt="Hello"))
        result_dict = result.model_dump()
        text = str(result_dict).lower()
        assert "openai" not in text
        assert "suno" not in text
        assert "elevenlabs" not in text
        assert "stability" not in text
        assert "replicate" not in text
