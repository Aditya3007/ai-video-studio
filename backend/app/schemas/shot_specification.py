"""Shot specification schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_aspect_ratio(value: str | None) -> str | None:
    if value is None:
        return value
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Aspect ratio must be in 'width:height' format.")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise ValueError("Aspect ratio dimensions must be positive integers.") from exc
    if width <= 0 or height <= 0:
        raise ValueError("Aspect ratio dimensions must be positive integers.")
    return value


class ShotSpecificationBase(BaseModel):
    """Common ShotSpecification fields."""

    intent: str | None = None
    framing: str | None = None
    composition: str | None = None
    camera_notes: str | None = None
    camera_movement: str | None = None
    subject_notes: str | None = None
    visual_direction: str | None = None
    aspect_ratio: str | None = Field(default=None, max_length=20)
    duration_seconds: int | None = Field(default=None, gt=0, le=300)
    character_refs: list[UUID] | None = None
    location_refs: list[UUID] | None = None
    object_refs: list[UUID] | None = None
    output_constraints: dict | None = None
    extra: dict | None = None

    @field_validator("aspect_ratio")
    @classmethod
    def check_aspect_ratio(cls, value: str | None) -> str | None:
        return _validate_aspect_ratio(value)


class ShotSpecificationCreate(ShotSpecificationBase):
    """Fields required to create a ShotSpecification."""


class ShotSpecificationUpdate(ShotSpecificationBase):
    """Fields allowed for partial ShotSpecification updates."""


class ShotSpecificationResponse(ShotSpecificationBase):
    """ShotSpecification response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shot_id: UUID
    created_at: datetime
    updated_at: datetime
