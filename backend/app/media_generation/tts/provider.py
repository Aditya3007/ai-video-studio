"""Provider-neutral text-to-speech contract."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TTSReference(BaseModel):
    """Provider-neutral pointer to a generated audio artifact."""

    uri: str
    content_type: str
    audio_format: str
    duration: float | None = None
    data: bytes | None = None
    metadata: dict[str, Any] | None = None


class TTSUsage(BaseModel):
    """Provider-neutral usage/cost metadata."""

    credits: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] | None = None


class TTSRequest(BaseModel):
    """Provider-neutral text-to-speech synthesis request."""

    text: str
    voice_id: str
    voice_metadata: dict[str, Any] | None = None
    language: str | None = Field(default=None, max_length=10)
    speaking_style: str | None = Field(default=None, max_length=50)
    output_format: str | None = Field(default=None, max_length=10)
    options: dict[str, Any] | None = None

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Text is required for synthesis.")
        return value


class TTSResult(BaseModel):
    """Provider-neutral text-to-speech synthesis result."""

    model_config = ConfigDict(from_attributes=True)

    audio: TTSReference
    provider: str
    model: str
    usage: TTSUsage | None = None
    metadata: dict[str, Any] | None = None
    request_id: str | None = None


@runtime_checkable
class TTSProvider(Protocol):
    """Abstract contract for text-to-speech provider adapters."""

    def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech and return a provider-neutral audio result."""
        ...
