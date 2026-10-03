"""P10-T01 Studio backend API tests."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models import (
    AssemblyItem,
    Asset,
    Character,
    Episode,
    Location,
    Scene,
    Series,
    Shot,
    ShotSpecification,
    Story,
    StoryObject,
    VideoAssembly,
)
from app.models.enums import (
    AssemblyItemType,
    AssemblyStatus,
    AssemblyTrack,
    AssetRole,
    AssetStatus,
)


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


@pytest.fixture
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_full(db: Session) -> tuple:
    series = Series(name="Studio Series")
    db.add(series)
    db.commit()
    db.refresh(series)

    story = Story(
        series_id=series.id,
        title="Origin",
        source_type="COMPLETE_STORY",
        source_content="Once upon a time.",
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    character = Character(series_id=series.id, name="Hero")
    location = Location(series_id=series.id, name="City")
    obj = StoryObject(series_id=series.id, name="Sword")
    db.add_all([character, location, obj])
    db.commit()
    for entity in [character, location, obj]:
        db.refresh(entity)

    episode = Episode(
        series_id=series.id,
        title="Episode 1",
        episode_number=1,
        source_type="SOURCE_STORY",
        story_id=story.id,
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)

    scene = Scene(
        episode_id=episode.id,
        scene_number=1,
        title="Opening",
        location_id=location.id,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)

    shot = Shot(
        scene_id=scene.id,
        shot_number=1,
        description="Wide shot",
        duration_seconds=5,
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)

    spec = ShotSpecification(
        shot_id=shot.id,
        aspect_ratio="9:16",
        duration_seconds=5,
        character_refs=[character.id],
        location_refs=[location.id],
        object_refs=[obj.id],
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)

    asset = Asset(
        series_id=series.id,
        asset_type="VIDEO",
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="filesystem",
        storage_key="shots/1.mp4",
        shot_id=shot.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    assembly = VideoAssembly(
        series_id=series.id,
        episode_id=episode.id,
        status=AssemblyStatus.READY.value,
        duration_seconds=5.0,
    )
    db.add(assembly)
    db.commit()
    db.refresh(assembly)

    item = AssemblyItem(
        assembly_id=assembly.id,
        series_id=series.id,
        episode_id=episode.id,
        scene_id=scene.id,
        shot_id=shot.id,
        item_type=AssemblyItemType.VIDEO.value,
        track=AssemblyTrack.VIDEO.value,
        start_time_seconds=0.0,
        duration_seconds=5.0,
        asset_id=asset.id,
    )
    db.add(item)
    db.commit()

    return series, episode, scene, shot, asset, assembly


class TestStudioAPI:
    def test_series_overview(self, client, db: Session) -> None:
        series, episode, scene, shot, asset, assembly = _seed_full(db)
        response = client.get(f"/api/v1/series/{series.id}/studio")
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["episodes"] == 1
        assert data["counts"]["stories"] == 1
        assert len(data["episodes"]) == 1
        assert data["episodes"][0]["assembly_status"] == AssemblyStatus.READY.value

    def test_series_overview_not_found(self, client) -> None:
        zero = str(UUID(int=0))
        response = client.get(f"/api/v1/series/{zero}/studio")
        assert response.status_code == 404

    def test_episode_production(self, client, db: Session) -> None:
        series, episode, scene, shot, asset, assembly = _seed_full(db)
        response = client.get(f"/api/v1/series/{series.id}/episodes/{episode.id}/studio")
        assert response.status_code == 200
        data = response.json()
        assert data["series_id"] == series.id
        assert len(data["scenes"]) == 1
        assert data["scenes"][0]["shot_count"] == 1
        assert data["assembly"]["status"] == AssemblyStatus.READY.value

    def test_episode_production_cross_series(self, client, db: Session) -> None:
        series, episode, _scene, _shot, _asset, _assembly = _seed_full(db)
        other = Series(name="Other")
        db.add(other)
        db.commit()
        response = client.get(f"/api/v1/series/{other.id}/episodes/{episode.id}/studio")
        assert response.status_code == 404

    def test_scene_production(self, client, db: Session) -> None:
        series, episode, scene, shot, asset, assembly = _seed_full(db)
        response = client.get(
            f"/api/v1/series/{series.id}/episodes/{episode.id}/scenes/{scene.id}/studio"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["scene"]["id"] == scene.id
        assert len(data["shots"]) == 1
        assert data["shots"][0]["asset_count"] == 1
        assert data["assembly_item_count"] == 1

    def test_shot_production(self, client, db: Session) -> None:
        series, episode, scene, shot, asset, assembly = _seed_full(db)
        response = client.get(f"/api/v1/series/{series.id}/shots/{shot.id}/studio")
        assert response.status_code == 200
        data = response.json()
        assert data["shot"]["id"] == shot.id
        assert data["episode_id"] == episode.id
        assert data["scene_id"] == scene.id
        assert len(data["assets"]) == 1
        assert data["assembly_item_count"] == 1

    def test_shot_production_cross_series(self, client, db: Session) -> None:
        series, _episode, _scene, shot, _asset, _assembly = _seed_full(db)
        other = Series(name="Other")
        db.add(other)
        db.commit()
        response = client.get(f"/api/v1/series/{other.id}/shots/{shot.id}/studio")
        assert response.status_code == 404
