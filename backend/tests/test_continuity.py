"""P9-T01 deterministic continuity rules engine tests."""

from uuid import UUID

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import (
    Character,
    Episode,
    Location,
    Scene,
    Series,
    Shot,
    ShotSpecification,
    StoryObject,
)
from app.models.enums import ContinuitySeverity
from app.services.continuity_service import ContinuityNotFoundError, ContinuityService


def _memory_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return session


@pytest.fixture
def db():
    session = _memory_db()
    try:
        yield session
    finally:
        session.close()


def _seed_valid(db: Session) -> tuple:
    series = Series(name="Continuity Series")
    db.add(series)
    db.commit()
    db.refresh(series)

    character = Character(series_id=series.id, name="Hero")
    location = Location(series_id=series.id, name="City")
    obj = StoryObject(series_id=series.id, name="Sword")
    db.add_all([character, location, obj])
    db.commit()
    db.refresh(character)
    db.refresh(location)
    db.refresh(obj)

    episode = Episode(
        series_id=series.id,
        title="Episode 1",
        episode_number=1,
        source_type="TOPIC",
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)

    scene = Scene(
        episode_id=episode.id,
        scene_number=1,
        location_id=location.id,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)

    shot = Shot(scene_id=scene.id, shot_number=1)
    db.add(shot)
    db.commit()
    db.refresh(shot)

    spec = ShotSpecification(
        shot_id=shot.id,
        aspect_ratio="9:16",
        duration_seconds=10,
        character_refs=[character.id],
        location_refs=[location.id],
        object_refs=[obj.id],
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)

    return series, episode, scene, shot, character, location, obj


class TestContinuityService:
    def test_valid_episode_has_no_findings(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed_valid(db)
        service = ContinuityService(db)
        findings = service.check_episode(str(series.id), str(episode.id))
        assert findings == []

    def test_missing_character_ref(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed_valid(db)
        shot.specification.character_refs = ["does-not-exist"]

        service = ContinuityService(db)
        findings = service.check_episode(str(series.id), str(episode.id))

        rule_ids = [f.rule_id for f in findings]
        assert "shot-spec-missing-character" in rule_ids
        assert all(f.severity == ContinuitySeverity.ERROR for f in findings)

    def test_cross_series_location_ref(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed_valid(db)

        other = Series(name="Other")
        db.add(other)
        db.commit()
        db.refresh(other)
        other_loc = Location(series_id=other.id, name="Other City")
        db.add(other_loc)
        db.commit()
        db.refresh(other_loc)

        shot.specification.location_refs = [other_loc.id]

        service = ContinuityService(db)
        findings = service.check_episode(str(series.id), str(episode.id))

        rule_ids = [f.rule_id for f in findings]
        assert "shot-spec-cross-series-location" in rule_ids
        finding = next(f for f in findings if f.rule_id == "shot-spec-cross-series-location")
        assert UUID(other.id) in finding.related_entity_ids

    def test_missing_scene_location(self, db: Session) -> None:
        series, episode, scene, _shot, _char, _loc, _obj = _seed_valid(db)
        scene.location_id = "does-not-exist"

        service = ContinuityService(db)
        with db.no_autoflush:
            findings = service.check_episode(str(series.id), str(episode.id))

        assert any(f.rule_id == "missing-scene-location" for f in findings)

    def test_invalid_shot_specification(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed_valid(db)
        shot.specification.aspect_ratio = "not-a-ratio"

        service = ContinuityService(db)
        findings = service.check_episode(str(series.id), str(episode.id))

        assert any(f.rule_id == "invalid-shot-specification" for f in findings)
        field_finding = next(f for f in findings if f.rule_id == "invalid-shot-specification")
        assert field_finding.metadata is not None
        assert "aspect_ratio" in field_finding.metadata.get("field", "")

    def test_deterministic_ordering(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed_valid(db)
        shot.specification.character_refs = ["missing-1"]
        shot.specification.location_refs = ["missing-2"]
        shot.specification.aspect_ratio = "bad"

        service = ContinuityService(db)
        run_1 = service.check_episode(str(series.id), str(episode.id))
        run_2 = service.check_episode(str(series.id), str(episode.id))

        assert run_1 == run_2
        assert [f.rule_id for f in run_1] == sorted(
            [f.rule_id for f in run_1],
            key=lambda rid: (
                0 if rid.startswith("invalid") else 1,
                rid,
            ),
        )

    def test_series_isolation(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed_valid(db)
        other = Series(name="Other")
        db.add(other)
        db.commit()

        service = ContinuityService(db)
        with pytest.raises(ContinuityNotFoundError):
            service.check_episode(str(other.id), str(episode.id))

    def test_shot_scope_isolation(self, db: Session) -> None:
        _series, _episode, _scene, shot, _char, _loc, _obj = _seed_valid(db)

        other = Series(name="Other")
        db.add(other)
        db.commit()
        db.refresh(other)

        service = ContinuityService(db)
        with pytest.raises(ContinuityNotFoundError):
            service.check_shot(str(other.id), str(shot.id))


class TestContinuityAPI:
    def test_episode_continuity_not_found(self, client) -> None:
        zero = str(UUID(int=0))
        response = client.get(f"/api/v1/series/{zero}/episodes/{zero}/continuity")
        assert response.status_code == 404
