"""Universe context schema."""

from pydantic import BaseModel, ConfigDict

from app.schemas.audio_bible import AudioBibleResponse
from app.schemas.character import CharacterUniverseResponse
from app.schemas.location import LocationUniverseResponse
from app.schemas.series import SeriesResponse
from app.schemas.story_object import StoryObjectResponse
from app.schemas.visual_bible import VisualBibleResponse
from app.schemas.world import WorldResponse


class TimelineResponse(BaseModel):
    """Canonical temporal context for a series."""

    model_config = ConfigDict(from_attributes=True)

    current_era: str | None = None
    history_context: str | None = None
    social_structure: str | None = None
    timeline_notes: str | None = None


class UniverseContextResponse(BaseModel):
    """Aggregated canonical universe context for a Series."""

    model_config = ConfigDict(from_attributes=True)

    series: SeriesResponse
    world: WorldResponse | None = None
    visual_bible: VisualBibleResponse | None = None
    audio_bible: AudioBibleResponse | None = None
    timeline: TimelineResponse | None = None
    characters: list[CharacterUniverseResponse] = []
    locations: list[LocationUniverseResponse] = []
    objects: list[StoryObjectResponse] = []
