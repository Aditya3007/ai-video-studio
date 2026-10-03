"""P6-T02 Image-to-video generation workflow tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.video import (
    ImageToVideoService,
    VideoRequestError,
)
from app.models import Asset, Episode, Scene, Series, Shot, ShotSpecification
from app.models.enums import (
    ApprovalStatus,
    AssetRole,
    AssetStatus,
    AssetType,
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
    return session, engine


@pytest.fixture
def db():
    session, engine = _memory_db()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _series(client: TestClient, name: str = "I2V Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _episode(client: TestClient, series_id: str, episode_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={
            "title": f"Episode {episode_number}",
            "episode_number": episode_number,
            "source_type": "TOPIC",
        },
    )
    assert response.status_code == 201
    return response.json()


def _scene(client: TestClient, episode_id: str, scene_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/episodes/{episode_id}/scenes",
        json={
            "scene_number": scene_number,
            "sequence_order": scene_number - 1,
            "title": f"Scene {scene_number}",
        },
    )
    assert response.status_code == 201
    return response.json()


def _shot(client: TestClient, scene_id: str, shot_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": shot_number,
            "sequence_order": shot_number - 1,
            "description": f"Shot {shot_number}",
        },
    )
    assert response.status_code == 201
    return response.json()


def _spec(client: TestClient, scene_id: str, shot_id: str, **kwargs) -> dict:
    payload = {
        "intent": "Hero runs",
        "camera_movement": "Camera follows the hero",
        "camera_notes": "Handheld motion",
        "visual_direction": "Golden hour",
        "subject_notes": "Hero in motion",
        "aspect_ratio": "9:16",
        "duration_seconds": 5,
    }
    payload.update(kwargs)
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots/{shot_id}/specification",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def _storyboard_asset(
    client: TestClient, series_id: str, approval_status: str = "APPROVED"
) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/assets",
        json={
            "asset_type": "STORYBOARD",
            "role": "GENERATED",
            "status": "AVAILABLE",
            "approval_status": approval_status,
            "storage_backend": "image-provider",
            "storage_key": "fake://image/1.png",
            "name": "Storyboard",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestImageToVideoApi:
    def test_happy_path(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-to-video",
            json={"storyboard_asset_id": asset["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "fake"
        assert data["videos"]
        assert data["videos"][0]["metadata"]["keyframes"] == [asset["id"]]
        assert data["videos"][0]["duration"] == 5.0

    def test_unapproved_storyboard_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series["id"], approval_status="PENDING")

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-to-video",
            json={"storyboard_asset_id": asset["id"]},
        )
        assert response.status_code == 422

    def test_wrong_asset_type_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset_response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={
                "asset_type": "IMAGE",
                "role": "CANONICAL",
                "status": "AVAILABLE",
                "approval_status": "APPROVED",
                "storage_backend": "default",
                "storage_key": "fake://image/1.png",
                "name": "Image",
            },
        )
        assert asset_response.status_code == 201
        asset = asset_response.json()

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-to-video",
            json={"storyboard_asset_id": asset["id"]},
        )
        assert response.status_code == 422

    def test_cross_series_asset_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode = _episode(client, series_a["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset_b = _storyboard_asset(client, series_b["id"])

        response = client.post(
            f"/api/v1/series/{series_a['id']}/shots/{shot['id']}/image-to-video",
            json={"storyboard_asset_id": asset_b["id"]},
        )
        assert response.status_code == 422

    def test_cross_series_shot_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_b = _episode(client, series_b["id"])
        scene_b = _scene(client, episode_b["id"])
        shot_b = _shot(client, scene_b["id"])
        _spec(client, scene_b["id"], shot_b["id"])
        asset_a = _storyboard_asset(client, series_a["id"])

        response = client.post(
            f"/api/v1/series/{series_a['id']}/shots/{shot_b['id']}/image-to-video",
            json={"storyboard_asset_id": asset_a["id"]},
        )
        assert response.status_code == 422

    def test_missing_shot_specification(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        asset = _storyboard_asset(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-to-video",
            json={"storyboard_asset_id": asset["id"]},
        )
        assert response.status_code == 422


class TestImageToVideoService:
    def _seed_shot(self, db: Session, **spec_kwargs) -> tuple[Series, Shot, Asset]:
        series = Series(name="I2V Service Series")
        db.add(series)
        db.commit()
        db.refresh(series)

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
            sequence_order=0,
            title="Scene 1",
        )
        db.add(scene)
        db.commit()
        db.refresh(scene)

        shot = Shot(
            scene_id=scene.id,
            shot_number=1,
            sequence_order=0,
        )
        db.add(shot)
        db.commit()
        db.refresh(shot)

        shot_spec = ShotSpecification(
            shot_id=shot.id,
            intent="Hero runs",
            camera_movement="Camera follows",
            visual_direction="Golden hour",
            aspect_ratio="9:16",
            duration_seconds=5,
            **spec_kwargs,
        )
        db.add(shot_spec)
        db.commit()

        asset = Asset(
            series_id=series.id,
            asset_type=AssetType.STORYBOARD.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            approval_status=ApprovalStatus.APPROVED.value,
            storage_backend="image-provider",
            storage_key="fake://image/1.png",
            name="Storyboard",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        return series, shot, asset

    def test_service_happy_path(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        service = ImageToVideoService(db)
        result = service.generate(str(series.id), str(shot.id), str(asset.id))

        assert result["provider"] == "fake"
        assert result["videos"][0]["metadata"]["keyframes"] == [asset.id]
        assert result["videos"][0]["duration"] == 5.0

    def test_rejects_unapproved_asset(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        asset.approval_status = ApprovalStatus.PENDING.value
        db.commit()

        service = ImageToVideoService(db)
        with pytest.raises(VideoRequestError):
            service.generate(str(series.id), str(shot.id), str(asset.id))

    def test_rejects_unavailable_asset(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        asset.status = AssetStatus.FAILED.value
        db.commit()

        service = ImageToVideoService(db)
        with pytest.raises(VideoRequestError):
            service.generate(str(series.id), str(shot.id), str(asset.id))
