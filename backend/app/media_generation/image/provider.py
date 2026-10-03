"""Provider-neutral image generation contract."""

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImageReference(BaseModel):
    """Provider-neutral pointer to a generated image artifact."""

    uri: str
    width: int
    height: int
    content_type: str
    metadata: dict[str, Any] | None = None


class ImageUsage(BaseModel):
    """Provider-neutral usage/cost metadata."""

    credits: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] | None = None


class ImageGenerationRequest(BaseModel):
    """Provider-neutral image generation request."""

    prompt: str
    negative_prompt: str | None = None
    aspect_ratio: str | None = Field(default=None, max_length=20)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    num_images: int = Field(default=1, ge=1, le=10)
    seed: int | None = None
    reference_asset_ids: list[UUID] = []
    canonical_character_ids: list[UUID] = []
    canonical_location_ids: list[UUID] = []
    canonical_object_ids: list[UUID] = []
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

    @classmethod
    def from_shot_specification(
        cls,
        shot_spec: dict[str, Any],
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list[UUID] | None = None,
    ) -> "ImageGenerationRequest":
        """Build a provider-neutral request from a shot specification dict."""
        parts = [
            str(shot_spec.get(field) or "")
            for field in (
                "intent",
                "framing",
                "composition",
                "camera_notes",
                "camera_movement",
                "subject_notes",
                "visual_direction",
            )
        ]
        prompt = prompt_override or " ".join(p.strip() for p in parts if p.strip())
        if not prompt:
            prompt = "Generate an image for the shot."

        return cls(
            prompt=prompt,
            aspect_ratio=shot_spec.get("aspect_ratio") or "9:16",
            width=(shot_spec.get("output_constraints") or {}).get("width"),
            height=(shot_spec.get("output_constraints") or {}).get("height"),
            canonical_character_ids=shot_spec.get("character_refs") or [],
            canonical_location_ids=shot_spec.get("location_refs") or [],
            canonical_object_ids=shot_spec.get("object_refs") or [],
            output_constraints=shot_spec.get("output_constraints"),
            options=shot_spec.get("extra"),
            reference_asset_ids=reference_asset_ids or [],
        )


class ImageGenerationResult(BaseModel):
    """Provider-neutral image generation result."""

    model_config = ConfigDict(from_attributes=True)

    images: list[ImageReference]
    provider: str
    model: str
    usage: ImageUsage | None = None
    metadata: dict[str, Any] | None = None
    request_id: str | None = None


@runtime_checkable
class ImageGenerationProvider(Protocol):
    """Abstract contract for image generation provider adapters."""

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate images and return a provider-neutral result."""
        ...
