"""Series schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SeriesBase(BaseModel):
    """Common Series fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    genre: str | None = Field(default=None, max_length=255)
    language: str = Field(default="en", max_length=10)
    target_audience: str | None = Field(default=None, max_length=255)
    episode_duration_seconds: int = Field(default=60, ge=1)


class SeriesCreate(SeriesBase):
    """Fields required to create a Series."""


class SeriesUpdate(BaseModel):
    """Fields allowed for partial Series updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    genre: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=10)
    target_audience: str | None = Field(default=None, max_length=255)
    episode_duration_seconds: int | None = Field(default=None, ge=1)


class SeriesResponse(SeriesBase):
    """Series response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
