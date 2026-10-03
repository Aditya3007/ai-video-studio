"""Scene schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SceneBase(BaseModel):
    """Common Scene fields."""

    scene_number: int = Field(..., ge=1)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    time_of_day: str | None = Field(default=None, max_length=255)
    sequence_order: int = Field(default=0, ge=0)


class SceneCreate(SceneBase):
    """Fields required to create a Scene."""

    location_id: UUID | None = None


class SceneUpdate(BaseModel):
    """Fields allowed for partial Scene updates."""

    scene_number: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    time_of_day: str | None = Field(default=None, max_length=255)
    sequence_order: int | None = Field(default=None, ge=0)
    location_id: UUID | None = None


class SceneResponse(SceneBase):
    """Scene response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    episode_id: UUID
    location_id: UUID | None
    created_at: datetime
    updated_at: datetime
