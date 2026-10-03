"""Universe context aggregation service."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AudioBible,
    Character,
    Location,
    Series,
    StoryObject,
    VisualBible,
    World,
)
from app.schemas import (
    AudioBibleResponse,
    CharacterUniverseResponse,
    LocationUniverseResponse,
    SeriesResponse,
    StoryObjectResponse,
    TimelineResponse,
    UniverseContextResponse,
    VisualBibleResponse,
    WorldResponse,
)


class UniverseContextService:
    """Assembles canonical universe context for a Series."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_context(self, series: Series) -> UniverseContextResponse:
        """Return a read-only aggregate of canonical Series context."""
        world = self._db.execute(
            select(World).where(World.series_id == series.id)
        ).scalar_one_or_none()
        visual_bible = self._db.execute(
            select(VisualBible).where(VisualBible.series_id == series.id)
        ).scalar_one_or_none()
        audio_bible = self._db.execute(
            select(AudioBible).where(AudioBible.series_id == series.id)
        ).scalar_one_or_none()
        characters = (
            self._db.execute(
                select(Character)
                .where(Character.series_id == series.id)
                .options(selectinload(Character.versions))
            )
            .scalars()
            .all()
        )
        locations = (
            self._db.execute(
                select(Location)
                .where(Location.series_id == series.id)
                .options(selectinload(Location.versions))
            )
            .scalars()
            .all()
        )
        objects = (
            self._db.execute(select(StoryObject).where(StoryObject.series_id == series.id))
            .scalars()
            .all()
        )

        timeline = None
        if world:
            timeline = TimelineResponse(
                current_era=world.current_era,
                history_context=world.history_context,
                social_structure=world.social_structure,
                timeline_notes=world.timeline_notes,
            )

        return UniverseContextResponse(
            series=SeriesResponse.model_validate(series),
            world=WorldResponse.model_validate(world) if world else None,
            visual_bible=VisualBibleResponse.model_validate(visual_bible) if visual_bible else None,
            audio_bible=AudioBibleResponse.model_validate(audio_bible) if audio_bible else None,
            timeline=timeline,
            characters=[
                CharacterUniverseResponse.model_validate(character) for character in characters
            ],
            locations=[LocationUniverseResponse.model_validate(location) for location in locations],
            objects=[StoryObjectResponse.model_validate(obj) for obj in objects],
        )
