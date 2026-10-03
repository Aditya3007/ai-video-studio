"""Narration/dialogue schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NarrationStatus, NarrationType


class NarrationCreate(BaseModel):
    """Request body for creating a narration item."""

    episode_id: UUID
    scene_id: UUID | None = None
    shot_id: UUID | None = None
    voice_id: UUID | None = None
    character_id: UUID | None = None
    source_text: str
    narration_type: NarrationType = NarrationType.NARRATION
    status: NarrationStatus = NarrationStatus.PENDING
    generated_asset_id: UUID | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    audio_metadata: dict | None = None


class NarrationUpdate(BaseModel):
    """Request body for updating a narration item."""

    source_text: str | None = None
    voice_id: UUID | None = None
    character_id: UUID | None = None
    narration_type: NarrationType | None = None
    status: NarrationStatus | None = None
    generated_asset_id: UUID | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    audio_metadata: dict | None = None


class NarrationResponse(BaseModel):
    """Narration response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    episode_id: UUID
    scene_id: UUID | None
    shot_id: UUID | None
    voice_id: UUID | None
    character_id: UUID | None
    source_text: str
    narration_type: NarrationType
    status: NarrationStatus
    generated_asset_id: UUID | None
    duration_seconds: float | None
    audio_metadata: dict | None
    created_at: datetime
    updated_at: datetime
