"""Story analysis result schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.story_intelligence.schemas import StoryAnalysisResult


class StoryAnalysisResponse(BaseModel):
    """Persisted story analysis result response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    story_id: UUID
    story_version_id: UUID
    status: str
    result: StoryAnalysisResult
    warnings: list[str] = []
    created_at: datetime
    updated_at: datetime
