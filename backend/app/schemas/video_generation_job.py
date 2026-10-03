"""Video generation job schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import VideoGenerationJobStatus


class VideoGenerationJobCreate(BaseModel):
    """Optional overrides for starting a video generation job."""

    storyboard_asset_id: UUID
    prompt_override: str | None = None
    duration_seconds: int | None = None
    aspect_ratio: str | None = None
    motion_description: str | None = None
    reference_asset_ids: list[UUID] = []


class VideoGenerationJobResponse(BaseModel):
    """Video generation job response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    shot_id: UUID | None
    source_asset_id: UUID | None
    request_payload: dict | None
    status: VideoGenerationJobStatus
    attempts: int
    max_attempts: int
    result_metadata: dict | None
    provider: str | None
    model: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
