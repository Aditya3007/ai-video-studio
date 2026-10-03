"""Shot schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.shot_specification import ShotSpecificationResponse


class ShotBase(BaseModel):
    """Common Shot fields."""

    shot_number: int = Field(..., ge=1)
    description: str | None = None
    action: str | None = None
    camera: str | None = Field(default=None, max_length=255)
    camera_movement: str | None = Field(default=None, max_length=255)
    lighting: str | None = Field(default=None, max_length=255)
    mood: str | None = Field(default=None, max_length=255)
    duration_seconds: int = Field(default=0, ge=0)
    dialogue: str | None = None
    narration: str | None = None
    sequence_order: int = Field(default=0, ge=0)


class ShotCreate(ShotBase):
    """Fields required to create a Shot."""


class ShotUpdate(BaseModel):
    """Fields allowed for partial Shot updates."""

    shot_number: int | None = Field(default=None, ge=1)
    description: str | None = None
    action: str | None = None
    camera: str | None = Field(default=None, max_length=255)
    camera_movement: str | None = Field(default=None, max_length=255)
    lighting: str | None = Field(default=None, max_length=255)
    mood: str | None = Field(default=None, max_length=255)
    duration_seconds: int | None = Field(default=None, ge=0)
    dialogue: str | None = None
    narration: str | None = None
    sequence_order: int | None = Field(default=None, ge=0)


class ShotResponse(ShotBase):
    """Shot response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scene_id: UUID
    specification: ShotSpecificationResponse | None = None
    created_at: datetime
    updated_at: datetime
