"""Location and location version schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    """Common Location fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    location_type: str | None = Field(default=None, max_length=255)
    atmosphere: str | None = None
    visual_characteristics: str | None = None
    extra: dict | None = None


class LocationCreate(LocationBase):
    """Fields required to create a Location."""


class LocationUpdate(BaseModel):
    """Fields allowed for partial Location updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    location_type: str | None = Field(default=None, max_length=255)
    atmosphere: str | None = None
    visual_characteristics: str | None = None
    extra: dict | None = None


class LocationResponse(LocationBase):
    """Location response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime


class LocationVersionBase(BaseModel):
    """Common LocationVersion fields."""

    version: int = Field(..., ge=1)
    description: str | None = None
    architecture: str | None = None
    lighting: str | None = None
    visual_description: str | None = None
    reference_asset_id: UUID | None = None
    is_current: bool = False


class LocationVersionCreate(LocationVersionBase):
    """Fields required to create a LocationVersion."""


class LocationVersionUpdate(BaseModel):
    """Fields allowed for partial LocationVersion updates."""

    description: str | None = None
    architecture: str | None = None
    lighting: str | None = None
    visual_description: str | None = None
    reference_asset_id: UUID | None = None
    is_current: bool | None = None


class LocationVersionResponse(LocationVersionBase):
    """LocationVersion response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    created_at: datetime


class LocationUniverseResponse(LocationResponse):
    """Location response including version history for universe context."""

    versions: list[LocationVersionResponse] = []
