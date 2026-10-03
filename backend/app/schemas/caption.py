"""Caption/subtitle Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptionStyle(BaseModel):
    """Provider-neutral caption styling defaults for 9:16 Shorts."""

    model_config = ConfigDict(extra="ignore")

    font_family: str = "Arial"
    font_size: int = Field(default=60, ge=1)
    primary_color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    outline_width: int = Field(default=2, ge=0)
    shadow: int = Field(default=0, ge=0)
    alignment: int = Field(default=2, ge=1, le=9)
    margin_h: int = Field(default=40, ge=0)
    margin_v: int = Field(default=80, ge=0)
    max_chars_per_line: int = Field(default=24, ge=1)
    max_lines: int = Field(default=2, ge=1)
    line_spacing: int = Field(default=0, ge=0)
    wrap_style: int = Field(default=2, ge=0, le=3)

    @field_validator("primary_color", "outline_color")
    @classmethod
    def _color_format(cls, value: str) -> str:
        if not (value.startswith("&H") and len(value) == 10):
            raise ValueError("Color must be in ASS &H00BBGGRR format.")
        return value


class CaptionCreate(BaseModel):
    """Request body for creating a caption."""

    assembly_id: UUID
    episode_id: UUID
    scene_id: UUID | None = None
    shot_id: UUID | None = None
    narration_id: UUID | None = None
    text: str = Field(..., min_length=1, max_length=500)
    start_time_seconds: float = Field(..., ge=0)
    end_time_seconds: float = Field(..., gt=0)
    sequence_order: int = Field(default=0, ge=0)
    style: CaptionStyle | None = None
    locale: str | None = None
    caption_metadata: dict | None = None

    @field_validator("end_time_seconds")
    @classmethod
    def _end_after_start(cls, value: float, info) -> float:
        if value <= info.data.get("start_time_seconds", 0.0):
            raise ValueError("end_time_seconds must be greater than start_time_seconds")
        return value


class CaptionUpdate(BaseModel):
    """Request body for updating a caption."""

    scene_id: UUID | None = None
    shot_id: UUID | None = None
    narration_id: UUID | None = None
    text: str | None = Field(default=None, min_length=1, max_length=500)
    start_time_seconds: float | None = Field(default=None, ge=0)
    end_time_seconds: float | None = Field(default=None, gt=0)
    sequence_order: int | None = Field(default=None, ge=0)
    style: CaptionStyle | None = None
    locale: str | None = None
    caption_metadata: dict | None = None


class CaptionResponse(BaseModel):
    """Caption response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    episode_id: UUID
    assembly_id: UUID
    scene_id: UUID | None
    shot_id: UUID | None
    narration_id: UUID | None
    text: str
    start_time_seconds: float
    end_time_seconds: float
    sequence_order: int
    style: dict | None
    locale: str | None
    caption_metadata: dict | None
    created_at: datetime
    updated_at: datetime
