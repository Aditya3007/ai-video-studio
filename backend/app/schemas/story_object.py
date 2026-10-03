"""StoryObject schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StoryObjectBase(BaseModel):
    """Common StoryObject fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    object_type: str | None = Field(default=None, max_length=255)
    significance: str | None = None
    extra: dict | None = None


class StoryObjectCreate(StoryObjectBase):
    """Fields required to create a StoryObject."""


class StoryObjectUpdate(BaseModel):
    """Fields allowed for partial StoryObject updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    object_type: str | None = Field(default=None, max_length=255)
    significance: str | None = None
    extra: dict | None = None


class StoryObjectResponse(StoryObjectBase):
    """StoryObject response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime
