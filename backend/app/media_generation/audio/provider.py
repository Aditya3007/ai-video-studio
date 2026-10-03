"""Provider-neutral music/sound-effect generation contract."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AudioReference(BaseModel):
    """Provider-neutral pointer to a generated audio artifact."""

    uri: str
    content_type: str
    audio_format: str
    duration: float | None = None
    data: bytes | None = None
    metadata: dict[str, Any] | None = None


class AudioUsage(BaseModel):
    """Provider-neutral usage/cost metadata."""

    credits: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] | None = None


class AudioGenerationRequest(BaseModel):
    """Provider-neutral music/sound-effect generation request."""

    audio_type: str
    prompt: str
    duration: float | None = Field(default=None, gt=0)
    seed: int | None = None
    output_format: str | None = Field(default=None, max_length=10)
    options: dict[str, Any] | None = None

    @field_validator("audio_type")
    @classmethod
    def _validate_audio_type(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"MUSIC", "SOUND_EFFECT"}:
            raise ValueError("audio_type must be MUSIC or SOUND_EFFECT.")
        return value


class AudioGenerationResult(BaseModel):
    """Provider-neutral music/sound-effect generation result."""

    model_config = ConfigDict(from_attributes=True)

    audio: AudioReference
    provider: str
    model: str
    usage: AudioUsage | None = None
    metadata: dict[str, Any] | None = None
    request_id: str | None = None


@runtime_checkable
class AudioGenerationProvider(Protocol):
    """Abstract contract for music/sound-effect provider adapters."""

    def generate(self, request: AudioGenerationRequest) -> AudioGenerationResult:
        """Generate music or a sound effect and return a provider-neutral result."""
        ...
