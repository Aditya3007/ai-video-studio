"""World schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorldBase(BaseModel):
    """Common World fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    setting: str | None = None
    era: str | None = Field(default=None, max_length=255)
    current_era: str | None = Field(default=None, max_length=255)
    geography: str | None = None
    technology: str | None = None
    rules: str | None = None
    cultural_context: str | None = None
    history_context: str | None = None
    social_structure: str | None = None
    timeline_notes: str | None = None
    extra: dict | None = None


class WorldCreate(WorldBase):
    """Fields required to create a World."""


class WorldUpdate(BaseModel):
    """Fields allowed for partial World updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    setting: str | None = None
    era: str | None = Field(default=None, max_length=255)
    current_era: str | None = Field(default=None, max_length=255)
    geography: str | None = None
    technology: str | None = None
    rules: str | None = None
    cultural_context: str | None = None
    history_context: str | None = None
    social_structure: str | None = None
    timeline_notes: str | None = None
    extra: dict | None = None


class WorldResponse(WorldBase):
    """World response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime
