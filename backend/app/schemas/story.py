"""Story and story version schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

StorySourceTypeLiteral = Literal["COMPLETE_STORY", "TOPIC"]
StoryStatusLiteral = Literal["DRAFT", "READY", "PROCESSING", "COMPLETED", "FAILED"]


class StoryBase(BaseModel):
    """Common Story fields."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    source_type: StorySourceTypeLiteral
    source_content: str = Field(..., min_length=1)
    language: str = Field(default="en", max_length=10)
    status: StoryStatusLiteral = "DRAFT"
    extra: dict | None = None


class StoryCreate(StoryBase):
    """Fields required to create a Story."""


class StoryUpdate(BaseModel):
    """Fields allowed for partial Story updates.

    source_type and source_content are immutable after intake.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    language: str | None = Field(default=None, max_length=10)
    status: StoryStatusLiteral | None = None
    extra: dict | None = None


class StoryResponse(StoryBase):
    """Story response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime


class StoryVersionBase(BaseModel):
    """Common StoryVersion fields."""

    version_number: int = Field(..., ge=1)
    content: str = Field(..., min_length=1)
    change_summary: str | None = None
    extra: dict | None = None


class StoryVersionCreate(StoryVersionBase):
    """Fields required to create a StoryVersion."""


class StoryVersionResponse(StoryVersionBase):
    """StoryVersion response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    story_id: UUID
    created_at: datetime
