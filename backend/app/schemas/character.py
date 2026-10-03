"""Character and character version schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CharacterBase(BaseModel):
    """Common Character fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    personality: str | None = None
    role: str | None = Field(default=None, max_length=255)
    voice_reference: str | None = None
    extra: dict | None = None


class CharacterCreate(CharacterBase):
    """Fields required to create a Character."""


class CharacterUpdate(BaseModel):
    """Fields allowed for partial Character updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    personality: str | None = None
    role: str | None = Field(default=None, max_length=255)
    voice_reference: str | None = None
    extra: dict | None = None


class CharacterResponse(CharacterBase):
    """Character response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime


class CharacterVersionBase(BaseModel):
    """Common CharacterVersion fields."""

    version: int = Field(..., ge=1)
    appearance: str | None = None
    clothing: str | None = None
    personality_details: str | None = None
    visual_description: str | None = None
    reference_asset_id: UUID | None = None
    is_current: bool = False


class CharacterVersionCreate(CharacterVersionBase):
    """Fields required to create a CharacterVersion."""


class CharacterVersionUpdate(BaseModel):
    """Fields allowed for partial CharacterVersion updates."""

    appearance: str | None = None
    clothing: str | None = None
    personality_details: str | None = None
    visual_description: str | None = None
    reference_asset_id: UUID | None = None
    is_current: bool | None = None


class CharacterVersionResponse(CharacterVersionBase):
    """CharacterVersion response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    character_id: UUID
    created_at: datetime


class CharacterUniverseResponse(CharacterResponse):
    """Character response including version history for universe context."""

    versions: list[CharacterVersionResponse] = []
