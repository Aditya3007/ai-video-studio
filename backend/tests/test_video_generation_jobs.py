"""P6-T03 Video generation job lifecycle and retry tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.video import (
    FakeVideoGenerationProvider,
    VideoGenerationJobService,
    VideoRequestError,
)
from app.models import Asset, Episode, Scene, Series, Shot, ShotSpecification
from app.models.enums import (
    ApprovalStatus,
    AssetRole,
    AssetStatus,
    AssetType,
    VideoGenerationJobStatus,
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


def _series(client: TestClient, name: str = "Video Job Series") -> dict:
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
        "camera_movement": "Camera follows",
        "visual_direction": "Golden hour",
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


class TestVideoGenerationJobApi:
    def test_create_and_run_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/video-generation-jobs",
            json={"storyboard_asset_id": asset["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "SUCCEEDED"
        assert data["attempts"] == 1
        assert data["result_metadata"] is not None
        assert data["source_asset_id"] == asset["id"]

    def test_get_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series["id"])

        job = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/video-generation-jobs",
            json={"storyboard_asset_id": asset["id"]},
        ).json()

        response = client.get(f"/api/v1/series/{series['id']}/video-generation-jobs/{job['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == job["id"]

    def test_cancel_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series["id"])

        job = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/video-generation-jobs",
            json={"storyboard_asset_id": asset["id"]},
        ).json()

        # Jobs run synchronously, so the job is already SUCCEEDED and cannot be cancelled.
        response = client.post(
            f"/api/v1/series/{series['id']}/video-generation-jobs/{job['id']}/cancel"
        )
        assert response.status_code == 422

    def test_unapproved_asset_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series["id"], approval_status="PENDING")

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/video-generation-jobs",
            json={"storyboard_asset_id": asset["id"]},
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
            f"/api/v1/series/{series_a['id']}/shots/{shot_b['id']}/video-generation-jobs",
            json={"storyboard_asset_id": asset_a["id"]},
        )
        assert response.status_code == 422

    def test_cross_series_job_access(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode = _episode(client, series_a["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])
        asset = _storyboard_asset(client, series_a["id"])

        job = client.post(
            f"/api/v1/series/{series_a['id']}/shots/{shot['id']}/video-generation-jobs",
            json={"storyboard_asset_id": asset["id"]},
        ).json()

        response = client.get(f"/api/v1/series/{series_b['id']}/video-generation-jobs/{job['id']}")
        assert response.status_code == 404


class TestVideoGenerationJobService:
    def _seed_shot(self, db: Session) -> tuple[Series, Shot, Asset]:
        series = Series(name="Video Job Service")
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

    def test_happy_path(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        service = VideoGenerationJobService(db)
        job = service.create_and_run(str(series.id), str(shot.id), str(asset.id))

        assert job.status == VideoGenerationJobStatus.SUCCEEDED.value
        assert job.attempts == 1
        assert job.result_metadata is not None
        assert job.source_asset_id == asset.id

    def test_failed_job_and_retry(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        failing_provider = FakeVideoGenerationProvider(fail_mode="generation")
        service = VideoGenerationJobService(db, provider=failing_provider)
        job = service.create_and_run(str(series.id), str(shot.id), str(asset.id))

        assert job.status == VideoGenerationJobStatus.FAILED.value
        assert job.attempts == 1
        assert job.error_message is not None

        succeeding_provider = FakeVideoGenerationProvider()
        retry_service = VideoGenerationJobService(db, provider=succeeding_provider)
        retried = retry_service.retry(str(series.id), job.id)

        assert retried.status == VideoGenerationJobStatus.SUCCEEDED.value
        assert retried.attempts == 2

    def test_retry_exhausted(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        provider = FakeVideoGenerationProvider(fail_mode="generation")
        service = VideoGenerationJobService(db, provider=provider)
        job = service.create_and_run(str(series.id), str(shot.id), str(asset.id))
        service.retry(str(series.id), job.id)
        service.retry(str(series.id), job.id)
        with pytest.raises(VideoRequestError):
            service.retry(str(series.id), job.id)

    def test_retry_successful_job_rejected(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        service = VideoGenerationJobService(db)
        job = service.create_and_run(str(series.id), str(shot.id), str(asset.id))
        with pytest.raises(VideoRequestError):
            service.retry(str(series.id), job.id)

    def test_retry_cancelled_job_rejected(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)
        request = VideoGenerationJobService(db)._image_to_video.build_video_request(
            str(series.id), str(shot.id), str(asset.id)
        )
        from app.models import VideoGenerationJob

        job = VideoGenerationJob(
            series_id=str(series.id),
            shot_id=str(shot.id),
            source_asset_id=str(asset.id),
            request_payload=request.model_dump(mode="json"),
            status=VideoGenerationJobStatus.QUEUED.value,
            attempts=0,
            max_attempts=3,
        )
        db.add(job)
        db.commit()

        service = VideoGenerationJobService(db)
        service.cancel(str(series.id), job.id)
        with pytest.raises(VideoRequestError):
            service.retry(str(series.id), job.id)

    def test_cancel_queued_job(self, db: Session) -> None:
        series, shot, asset = self._seed_shot(db)

        # Create a job manually and cancel before execution to test the QUEUED state.
        request = VideoGenerationJobService(db)._image_to_video.build_video_request(
            str(series.id), str(shot.id), str(asset.id)
        )
        from app.models import VideoGenerationJob

        job = VideoGenerationJob(
            series_id=str(series.id),
            shot_id=str(shot.id),
            source_asset_id=str(asset.id),
            request_payload=request.model_dump(mode="json"),
            status=VideoGenerationJobStatus.QUEUED.value,
            attempts=0,
            max_attempts=3,
        )
        db.add(job)
        db.commit()

        cancelled = VideoGenerationJobService(db).cancel(str(series.id), job.id)
        assert cancelled.status == VideoGenerationJobStatus.CANCELLED.value
