"""P5-T05 Image generation job orchestration and approval tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.image import (
    FakeImageGenerationProvider,
    ImageGenerationJobService,
    ImageGenerationProviderFactory,
)
from app.models import (
    Asset,
    Character,
    Episode,
    Scene,
    Series,
    Shot,
    ShotSpecification,
)
from app.models.enums import (
    ApprovalStatus,
    AssetRole,
    AssetStatus,
    AssetType,
    ImageGenerationJobStatus,
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


def _series(client: TestClient, name: str = "Job Series") -> dict:
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


def _spec(
    client: TestClient,
    scene_id: str,
    shot_id: str,
    **kwargs,
) -> dict:
    payload = {
        "intent": "Establish the hero",
        "framing": "Medium close-up",
        "composition": "Rule of thirds",
        "subject_notes": "Hero looking determined",
        "visual_direction": "Golden hour lighting",
        "camera_notes": "Static camera",
        "aspect_ratio": "9:16",
    }
    payload.update(kwargs)
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots/{shot_id}/specification",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


class TestImageGenerationJobApi:
    def test_create_and_run_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-generation-jobs",
            json={},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "SUCCEEDED"
        assert data["approval_status"] == "PENDING"
        assert data["result_asset_ids"] is not None
        assert len(data["result_asset_ids"]) == 1

        asset = client.get(
            f"/api/v1/series/{series['id']}/assets/{data['result_asset_ids'][0]}"
        ).json()
        assert asset["asset_type"] == "STORYBOARD"
        assert asset["approval_status"] == "PENDING"

    def test_get_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])

        create_response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-generation-jobs",
            json={},
        )
        job = create_response.json()

        response = client.get(f"/api/v1/series/{series['id']}/image-generation-jobs/{job['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == job["id"]

    def test_approve_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])

        job = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-generation-jobs",
            json={},
        ).json()

        response = client.post(
            f"/api/v1/series/{series['id']}/image-generation-jobs/{job['id']}/approve"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["approval_status"] == "APPROVED"

        asset = client.get(
            f"/api/v1/series/{series['id']}/assets/{job['result_asset_ids'][0]}"
        ).json()
        assert asset["approval_status"] == "APPROVED"

    def test_reject_job(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])

        job = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-generation-jobs",
            json={},
        ).json()

        response = client.post(
            f"/api/v1/series/{series['id']}/image-generation-jobs/{job['id']}/reject"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["approval_status"] == "REJECTED"

    def test_cross_series_job_creation_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode = _episode(client, series_a["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])

        response = client.post(
            f"/api/v1/series/{series_b['id']}/shots/{shot['id']}/image-generation-jobs",
            json={},
        )
        assert response.status_code == 422

    def test_cross_series_approval_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode = _episode(client, series_a["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, scene["id"], shot["id"])

        job = client.post(
            f"/api/v1/series/{series_a['id']}/shots/{shot['id']}/image-generation-jobs",
            json={},
        ).json()

        response = client.post(
            f"/api/v1/series/{series_b['id']}/image-generation-jobs/{job['id']}/approve"
        )
        assert response.status_code == 422


class TestImageGenerationJobService:
    def _seed_shot(self, db: Session) -> tuple[Series, Shot]:
        series = Series(name="Service Series")
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
            intent="Hero close-up",
            aspect_ratio="9:16",
        )
        db.add(shot_spec)
        db.commit()

        return series, shot

    def _reference_asset(self, db: Session, series_id: str, character: Character) -> Asset:
        asset = Asset(
            series_id=series_id,
            asset_type=AssetType.REFERENCE.value,
            role=AssetRole.REFERENCE.value,
            status=AssetStatus.AVAILABLE.value,
        )
        asset.characters.append(character)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    def test_job_lifecycle_succeeded(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
        assert job.approval_status == ApprovalStatus.PENDING.value
        assert job.attempts == 1
        assert job.result_asset_ids

    def test_failed_job_marks_failed(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        provider = FakeImageGenerationProvider(fail_mode="generation")
        service = ImageGenerationJobService(db, provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        assert job.status == ImageGenerationJobStatus.FAILED.value
        assert job.error_message is not None
        assert job.approval_status == ApprovalStatus.PENDING.value

    def test_retry_failed_job(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        failing_provider = FakeImageGenerationProvider(fail_mode="generation")
        service = ImageGenerationJobService(db, failing_provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        assert job.status == ImageGenerationJobStatus.FAILED.value

        # Switch to a succeeding provider for the retry.
        succeeding_provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, succeeding_provider)
        retried = service.retry(str(series.id), job.id)

        assert retried.status == ImageGenerationJobStatus.SUCCEEDED.value
        assert retried.attempts == 2

    def test_retry_non_failed_job_rejected(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        with pytest.raises(Exception):
            service.retry(str(series.id), job.id)

    def test_approval_state_transitions(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        approved = service.approve(str(series.id), job.id)
        assert approved.approval_status == ApprovalStatus.APPROVED.value

        asset = db.get(Asset, job.result_asset_ids[0])
        assert asset.approval_status == ApprovalStatus.APPROVED.value

    def test_reject_failed_job_rejected(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        provider = FakeImageGenerationProvider(fail_mode="generation")
        service = ImageGenerationJobService(db, provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        with pytest.raises(Exception):
            service.reject(str(series.id), job.id)

    def test_double_approval_rejected(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)

        job = service.create_and_run(str(series.id), str(shot.id))
        service.approve(str(series.id), job.id)
        with pytest.raises(Exception):
            service.approve(str(series.id), job.id)

    def test_reference_conditioning_preserved(self, db: Session) -> None:
        series, shot = self._seed_shot(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()
        self._reference_asset(db, series.id, character)

        shot_spec = shot.specification
        shot_spec.character_refs = [character.id]
        db.commit()

        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)
        job = service.create_and_run(str(series.id), str(shot.id))
        assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
