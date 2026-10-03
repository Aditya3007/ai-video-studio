"""Tests for core data models."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Character,
    CharacterVersion,
    Episode,
    Location,
    LocationVersion,
    Scene,
    Series,
    Shot,
    StoryObject,
    World,
)
from app.models.enums import EpisodeSourceType, EpisodeStatus


def _enable_sqlite_fk(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session():
    """Provide a fresh in-memory SQLite session for model tests."""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_sqlite_fk)
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess
        sess.rollback()


def _create_full_series(session: Session, name: str = "Test Series") -> Series:
    series = Series(name=name)
    World(name=f"{name} World", series=series)
    character = Character(name="Hero", series=series)
    CharacterVersion(version=1, is_current=True, character=character)
    location = Location(name="Village", series=series)
    LocationVersion(version=1, is_current=True, location=location)
    StoryObject(name="Ring", series=series)
    episode = Episode(
        title="Pilot",
        episode_number=1,
        status=EpisodeStatus.DRAFT.value,
        source_type=EpisodeSourceType.TOPIC.value,
        series=series,
    )
    scene = Scene(scene_number=1, episode=episode, location=location)
    Shot(shot_number=1, scene=scene)
    session.add(series)
    session.commit()
    return series


def test_create_full_series_graph(session: Session) -> None:
    """All core models can be persisted together in a series graph."""
    series = _create_full_series(session)

    assert series.id is not None
    assert series.world is not None
    assert len(series.characters) == 1
    assert len(series.locations) == 1
    assert len(series.objects) == 1
    assert len(series.episodes) == 1
    assert series.episodes[0].scenes[0].shots[0].shot_number == 1


def test_series_isolation(session: Session) -> None:
    """Entities remain associated with the correct series."""
    series_a = _create_full_series(session, "Series A")
    series_b = _create_full_series(session, "Series B")

    characters_a = session.query(Character).filter(Character.series_id == series_a.id).all()
    characters_b = session.query(Character).filter(Character.series_id == series_b.id).all()

    assert len(characters_a) == 1
    assert len(characters_b) == 1
    assert characters_a[0].series_id != characters_b[0].series_id


def test_character_version_uniqueness(session: Session) -> None:
    """Duplicate character version numbers are rejected."""
    series = Series(name="Version Test")
    character = Character(name="Hero", series=series)
    session.add(series)
    session.commit()

    session.add(CharacterVersion(version=1, character_id=character.id))
    session.add(CharacterVersion(version=2, character_id=character.id))
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(CharacterVersion(version=1, character_id=character.id))
        session.commit()


def test_location_version_uniqueness(session: Session) -> None:
    """Duplicate location version numbers are rejected."""
    series = Series(name="Version Test")
    location = Location(name="Village", series=series)
    session.add(series)
    session.commit()

    session.add(LocationVersion(version=1, location_id=location.id))
    session.add(LocationVersion(version=2, location_id=location.id))
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(LocationVersion(version=1, location_id=location.id))
        session.commit()


def test_episode_number_unique_within_series(session: Session) -> None:
    """Episode numbers must be unique within a series."""
    series = Series(name="Episode Ordering")
    session.add(series)
    session.commit()

    session.add(Episode(title="One", episode_number=1, series_id=series.id))
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(Episode(title="Duplicate", episode_number=1, series_id=series.id))
        session.commit()


def test_scene_number_unique_within_episode(session: Session) -> None:
    """Scene numbers must be unique within an episode."""
    series = Series(name="Scene Ordering")
    episode = Episode(title="Ep", episode_number=1, series=series)
    session.add(series)
    session.add(episode)
    session.commit()

    session.add(Scene(scene_number=1, episode=episode))
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(Scene(scene_number=1, episode=episode))
        session.commit()


def test_shot_number_unique_within_scene(session: Session) -> None:
    """Shot numbers must be unique within a scene."""
    series = Series(name="Shot Ordering")
    episode = Episode(title="Ep", episode_number=1, series=series)
    scene = Scene(scene_number=1, episode=episode)
    session.add(series)
    session.add(episode)
    session.add(scene)
    session.commit()

    session.add(Shot(shot_number=1, scene=scene))
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(Shot(shot_number=1, scene=scene))
        session.commit()


def test_invalid_foreign_key_rejected(session: Session) -> None:
    """References to non-existent parents raise an integrity error."""
    session.add(Episode(title="Orphan", episode_number=1, series_id="missing-series"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_timestamps_set_on_creation(session: Session) -> None:
    """Created and updated timestamps are populated on insert."""
    series = Series(name="Timestamped")
    session.add(series)
    session.commit()

    assert series.created_at is not None
    assert series.updated_at is not None


def test_cascade_delete_series(session: Session) -> None:
    """Deleting a series removes owned children."""
    series = _create_full_series(session, "Cascade Test")
    series_id = series.id
    session.delete(series)
    session.commit()

    assert session.get(Series, series_id) is None
    assert session.query(Character).filter_by(series_id=series_id).count() == 0
    assert session.query(Episode).filter_by(series_id=series_id).count() == 0
