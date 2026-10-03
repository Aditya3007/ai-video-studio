"""Video assembly and timeline schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssemblyItemType, AssemblyStatus, AssemblyTrack


class VideoAssemblyCreate(BaseModel):
    """Request body for creating a video assembly."""

    episode_id: UUID
    status: AssemblyStatus = AssemblyStatus.DRAFT
    output_config: dict | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    assembly_metadata: dict | None = None


class VideoAssemblyUpdate(BaseModel):
    """Request body for updating an assembly."""

    status: AssemblyStatus | None = None
    output_config: dict | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    assembly_metadata: dict | None = None


class VideoAssemblyResponse(BaseModel):
    """Video assembly response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    episode_id: UUID
    status: AssemblyStatus
    output_config: dict | None
    duration_seconds: float | None
    assembly_metadata: dict | None
    final_asset_id: UUID | None
    rendered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssemblyItemCreate(BaseModel):
    """Request body for adding an assembly timeline item."""

    scene_id: UUID | None = None
    shot_id: UUID | None = None
    item_type: AssemblyItemType
    track: AssemblyTrack
    sequence_order: int = Field(..., ge=0)
    start_time_seconds: float
    duration_seconds: float
    asset_id: UUID | None = None
    narration_id: UUID | None = None
    audio_cue_id: UUID | None = None
    item_metadata: dict | None = None


class AssemblyItemUpdate(BaseModel):
    """Request body for updating an assembly timeline item."""

    scene_id: UUID | None = None
    shot_id: UUID | None = None
    item_type: AssemblyItemType | None = None
    track: AssemblyTrack | None = None
    sequence_order: int | None = Field(default=None, ge=0)
    start_time_seconds: float | None = None
    duration_seconds: float | None = None
    asset_id: UUID | None = None
    narration_id: UUID | None = None
    audio_cue_id: UUID | None = None
    item_metadata: dict | None = None


class AssemblyItemResponse(BaseModel):
    """Assembly timeline item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assembly_id: UUID
    series_id: UUID
    episode_id: UUID
    scene_id: UUID | None
    shot_id: UUID | None
    item_type: AssemblyItemType
    track: AssemblyTrack
    sequence_order: int
    start_time_seconds: float
    duration_seconds: float
    asset_id: UUID | None
    narration_id: UUID | None
    audio_cue_id: UUID | None
    item_metadata: dict | None
    created_at: datetime
    updated_at: datetime
