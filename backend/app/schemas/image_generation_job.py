"""Image generation job schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ApprovalStatus, ImageGenerationJobStatus


class ImageGenerationJobCreate(BaseModel):
    """Optional overrides for starting an image generation job."""

    prompt_override: str | None = None
    reference_asset_ids: list[UUID] = []


class ImageGenerationJobResponse(BaseModel):
    """Image generation job response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    shot_id: UUID | None
    request_payload: dict | None
    status: ImageGenerationJobStatus
    approval_status: ApprovalStatus | None
    attempts: int
    max_attempts: int
    result_asset_ids: list[UUID] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
