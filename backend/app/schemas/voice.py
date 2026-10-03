"""Voice schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VoiceCreate(BaseModel):
    """Request body for creating a voice."""

    name: str
    description: str | None = None
    character_id: UUID | None = None
    voice_metadata: dict | None = None


class VoiceUpdate(BaseModel):
    """Request body for updating a voice."""

    name: str | None = None
    description: str | None = None
    character_id: UUID | None = None
    voice_metadata: dict | None = None


class VoiceResponse(BaseModel):
    """Voice response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    name: str
    description: str | None
    character_id: UUID | None
    voice_metadata: dict | None
    created_at: datetime
    updated_at: datetime
