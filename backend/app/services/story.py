"""Story domain service."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Series, Story, StoryVersion
from app.schemas import StoryCreate, StoryUpdate, StoryVersionCreate


class StoryNotFoundError(Exception):
    """Raised when a Story or StoryVersion cannot be found for a Series."""


class StoryService:
    """Handles story intake, versioning, and retrieval."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _get_story(self, series_id: str, story_id: str) -> Story:
        """Return a Story if it belongs to the Series, else raise."""
        story = self._db.get(Story, story_id)
        if not story or story.series_id != series_id:
            raise StoryNotFoundError("Story not found.")
        return story

    def create(self, series_id: str, data: StoryCreate) -> Story:
        """Create a Story and its initial version 1."""
        series = self._db.get(Series, series_id)
        if not series:
            raise StoryNotFoundError("Series not found.")
        story = Story(series_id=series_id, **data.model_dump(mode="json"))
        self._db.add(story)
        self._db.add(
            StoryVersion(
                story=story,
                version_number=1,
                content=story.source_content,
                change_summary="Original intake",
            )
        )
        return story

    def list_stories(
        self, series_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[Story], int]:
        """Return stories for the Series and total count."""
        items = (
            self._db.execute(
                select(Story).where(Story.series_id == series_id).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        total = (
            self._db.execute(
                select(func.count()).select_from(Story).where(Story.series_id == series_id)
            ).scalar()
            or 0
        )
        return items, total

    def get_story(self, series_id: str, story_id: str) -> Story:
        """Return a Story by ID."""
        return self._get_story(series_id, story_id)

    def update(self, series_id: str, story_id: str, data: StoryUpdate) -> Story:
        """Update mutable Story metadata."""
        story = self._get_story(series_id, story_id)
        for key, value in data.model_dump(exclude_unset=True, mode="json").items():
            setattr(story, key, value)
        return story

    def delete(self, series_id: str, story_id: str) -> Story:
        """Return the Story to be deleted."""
        return self._get_story(series_id, story_id)

    def list_versions(
        self, series_id: str, story_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[StoryVersion], int]:
        """Return versions for a Story and total count."""
        story = self._get_story(series_id, story_id)
        items = (
            self._db.execute(
                select(StoryVersion)
                .where(StoryVersion.story_id == story.id)
                .order_by(StoryVersion.version_number)
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        total = (
            self._db.execute(
                select(func.count())
                .select_from(StoryVersion)
                .where(StoryVersion.story_id == story.id)
            ).scalar()
            or 0
        )
        return items, total

    def get_version(self, series_id: str, story_id: str, version_id: str) -> StoryVersion:
        """Return a StoryVersion if it belongs to the Story and Series."""
        story = self._get_story(series_id, story_id)
        version = self._db.get(StoryVersion, version_id)
        if not version or version.story_id != story.id:
            raise StoryNotFoundError("Version not found.")
        return version

    def create_version(
        self, series_id: str, story_id: str, data: StoryVersionCreate
    ) -> StoryVersion:
        """Create a new StoryVersion."""
        story = self._get_story(series_id, story_id)
        version = StoryVersion(story_id=story.id, **data.model_dump(mode="json"))
        self._db.add(version)
        return version
