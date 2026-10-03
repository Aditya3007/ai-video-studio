"""Visual Bible schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VisualBibleBase(BaseModel):
    """Common VisualBible fields."""

    art_style: str | None = None
    color_palette: str | None = None
    lighting_style: str | None = None
    camera_style: str | None = None
    lens_style: str | None = None
    composition_style: str | None = None
    environment_style: str | None = None
    character_rendering_style: str | None = None
    aspect_ratio: str | None = Field(default=None, max_length=20)
    visual_notes: str | None = None
    extra: dict | None = None


class VisualBibleCreate(VisualBibleBase):
    """Fields required to create a VisualBible."""


class VisualBibleUpdate(BaseModel):
    """Fields allowed for partial VisualBible updates."""

    art_style: str | None = None
    color_palette: str | None = None
    lighting_style: str | None = None
    camera_style: str | None = None
    lens_style: str | None = None
    composition_style: str | None = None
    environment_style: str | None = None
    character_rendering_style: str | None = None
    aspect_ratio: str | None = Field(default=None, max_length=20)
    visual_notes: str | None = None
    extra: dict | None = None


class VisualBibleResponse(VisualBibleBase):
    """VisualBible response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime
