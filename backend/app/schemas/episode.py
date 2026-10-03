"""Episode schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EpisodeSourceType, EpisodeStatus


class EpisodeBase(BaseModel):
    """Common Episode fields."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    episode_number: int = Field(..., ge=1)
    status: EpisodeStatus = EpisodeStatus.DRAFT
    source_type: EpisodeSourceType = EpisodeSourceType.TOPIC
    source_text: str | None = None
    story_id: UUID | None = None


class EpisodeCreate(EpisodeBase):
    """Fields required to create an Episode."""


class EpisodeUpdate(BaseModel):
    """Fields allowed for partial Episode updates."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    episode_number: int | None = Field(default=None, ge=1)
    status: EpisodeStatus | None = None
    source_type: EpisodeSourceType | None = None
    source_text: str | None = None
    story_id: UUID | None = None


class EpisodeResponse(EpisodeBase):
    """Episode response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime
