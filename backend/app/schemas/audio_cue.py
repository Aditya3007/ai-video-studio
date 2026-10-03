"""Audio cue schemas for music and sound effects."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AudioCueStatus, AudioCueType


class AudioCueCreate(BaseModel):
    """Request body for creating an audio cue."""

    episode_id: UUID
    scene_id: UUID | None = None
    shot_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    audio_type: AudioCueType = AudioCueType.MUSIC
    status: AudioCueStatus = AudioCueStatus.PENDING
    prompt: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    start_time_seconds: float | None = Field(default=None, ge=0)
    end_time_seconds: float | None = Field(default=None, ge=0)
    volume: float | None = Field(default=None, ge=0, le=1)
    loop: bool = False
    fade_in: bool = False
    fade_out: bool = False
    generated_asset_id: UUID | None = None
    audio_metadata: dict | None = None


class AudioCueUpdate(BaseModel):
    """Request body for updating an audio cue."""

    name: str | None = None
    description: str | None = None
    audio_type: AudioCueType | None = None
    status: AudioCueStatus | None = None
    prompt: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    start_time_seconds: float | None = Field(default=None, ge=0)
    end_time_seconds: float | None = Field(default=None, ge=0)
    volume: float | None = Field(default=None, ge=0, le=1)
    loop: bool | None = None
    fade_in: bool | None = None
    fade_out: bool | None = None
    generated_asset_id: UUID | None = None
    audio_metadata: dict | None = None


class AudioCueResponse(BaseModel):
    """Audio cue response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    episode_id: UUID
    scene_id: UUID | None
    shot_id: UUID | None
    name: str | None
    description: str | None
    audio_type: AudioCueType
    status: AudioCueStatus
    prompt: str | None
    duration_seconds: float | None
    start_time_seconds: float | None
    end_time_seconds: float | None
    volume: float | None
    loop: bool
    fade_in: bool
    fade_out: bool
    generated_asset_id: UUID | None
    audio_metadata: dict | None
    created_at: datetime
    updated_at: datetime
