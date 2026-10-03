"""Provider-neutral video generation contract."""

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoReference(BaseModel):
    """Provider-neutral pointer to a generated video artifact."""

    uri: str
    width: int
    height: int
    duration: float
    content_type: str
    data: bytes | None = None
    metadata: dict[str, Any] | None = None


class VideoUsage(BaseModel):
    """Provider-neutral usage/cost metadata."""

    credits: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] | None = None


class VideoGenerationRequest(BaseModel):
    """Provider-neutral video generation request."""

    prompt: str
    negative_prompt: str | None = None
    aspect_ratio: str | None = Field(default=None, max_length=20)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration: float | None = Field(default=None, gt=0)
    seed: int | None = None
    reference_asset_ids: list[UUID] = []
    keyframe_asset_ids: list[UUID] = []
    canonical_character_ids: list[UUID] = []
    canonical_location_ids: list[UUID] = []
    canonical_object_ids: list[UUID] = []
    motion_description: str | None = None
    output_constraints: dict[str, Any] | None = None
    options: dict[str, Any] | None = None

    @field_validator("aspect_ratio")
    @classmethod
    def _validate_aspect_ratio(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("Aspect ratio must be 'width:height'.")
        try:
            width = int(parts[0])
            height = int(parts[1])
        except ValueError as exc:
            raise ValueError("Aspect ratio dimensions must be integers.") from exc
        if width <= 0 or height <= 0:
            raise ValueError("Aspect ratio dimensions must be positive.")
        return value

    @field_validator("width", "height")
    @classmethod
    def _validate_dimension(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Dimensions must be positive.")
        return value


class VideoGenerationResult(BaseModel):
    """Provider-neutral video generation result."""

    model_config = ConfigDict(from_attributes=True)

    videos: list[VideoReference]
    provider: str
    model: str
    usage: VideoUsage | None = None
    metadata: dict[str, Any] | None = None
    request_id: str | None = None


@runtime_checkable
class VideoGenerationProvider(Protocol):
    """Abstract contract for video generation provider adapters."""

    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """Generate videos and return a provider-neutral result."""
        ...
