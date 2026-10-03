"""Image-to-video workflow schemas."""

from uuid import UUID

from pydantic import BaseModel


class ImageToVideoRequest(BaseModel):
    """Request body for generating video from a storyboard/keyframe."""

    storyboard_asset_id: UUID
    prompt_override: str | None = None
    duration_seconds: int | None = None
    aspect_ratio: str | None = None
    motion_description: str | None = None
    reference_asset_ids: list[UUID] = []


class ImageToVideoResponse(BaseModel):
    """Response for a successful image-to-video generation."""

    videos: list[dict]
    provider: str
    model: str
    request_id: str | None
    metadata: dict | None = None
