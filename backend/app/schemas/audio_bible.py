"""Audio Bible schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AudioBibleBase(BaseModel):
    """Common AudioBible fields."""

    voice_style: str | None = None
    narration_style: str | None = None
    dialogue_style: str | None = None
    music_style: str | None = None
    sound_effect_style: str | None = None
    ambient_style: str | None = None
    audio_notes: str | None = None
    extra: dict | None = None


class AudioBibleCreate(AudioBibleBase):
    """Fields required to create an AudioBible."""


class AudioBibleUpdate(BaseModel):
    """Fields allowed for partial AudioBible updates."""

    voice_style: str | None = None
    narration_style: str | None = None
    dialogue_style: str | None = None
    music_style: str | None = None
    sound_effect_style: str | None = None
    ambient_style: str | None = None
    audio_notes: str | None = None
    extra: dict | None = None


class AudioBibleResponse(AudioBibleBase):
    """AudioBible response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime
