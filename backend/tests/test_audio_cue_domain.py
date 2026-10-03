"""P7-T04 Audio cue domain, API, and series isolation tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import Asset
from app.models.enums import ApprovalStatus, AssetRole, AssetStatus, AssetType


def _memory_db() -> tuple[Session, object]:
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


def _series(client: TestClient, name: str = "Audio Cue Series") -> dict:
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


def _asset(client: TestClient, series_id: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/assets",
        json={
            "asset_type": "AUDIO",
            "role": "GENERATED",
            "status": "AVAILABLE",
            "approval_status": "PENDING",
            "storage_backend": "fake",
            "storage_key": "fake://audio/1.mp3",
            "name": "Generated audio",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestAudioCueDomain:
    def test_create_music_cue(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-cues",
            json={
                "episode_id": episode["id"],
                "name": "Hero Theme",
                "audio_type": "MUSIC",
                "prompt": "Epic orchestral theme",
                "duration_seconds": 30.0,
                "loop": True,
                "fade_in": True,
                "fade_out": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["series_id"] == series["id"]
        assert data["episode_id"] == episode["id"]
        assert data["name"] == "Hero Theme"
        assert data["audio_type"] == "MUSIC"
        assert data["status"] == "PENDING"
        assert data["loop"] is True
        assert data["fade_in"] is True
        assert data["fade_out"] is True
        assert data["duration_seconds"] == 30.0

    def test_create_sound_effect_cue(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-cues",
            json={
                "episode_id": episode["id"],
                "scene_id": scene["id"],
                "shot_id": shot["id"],
                "name": "Door Creak",
                "audio_type": "SOUND_EFFECT",
                "prompt": "Old wooden door creaking",
                "volume": 0.75,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["audio_type"] == "SOUND_EFFECT"
        assert data["volume"] == 0.75
        assert data["scene_id"] == scene["id"]
        assert data["shot_id"] == shot["id"]

    def test_get_and_list_audio_cues(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        created = client.post(
            f"/api/v1/series/{series['id']}/audio-cues",
            json={
                "episode_id": episode["id"],
                "name": "Test Cue",
                "audio_type": "MUSIC",
                "prompt": "Test",
            },
        ).json()

        get_response = client.get(f"/api/v1/series/{series['id']}/audio-cues/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == created["id"]

        list_response = client.get(f"/api/v1/series/{series['id']}/audio-cues")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

    def test_invalid_volume_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-cues",
            json={
                "episode_id": episode["id"],
                "audio_type": "MUSIC",
                "prompt": "Test",
                "volume": 1.5,
            },
        )
        assert response.status_code == 422

    def test_invalid_audio_type_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-cues",
            json={
                "episode_id": episode["id"],
                "audio_type": "VOICE",
                "prompt": "Test",
            },
        )
        assert response.status_code == 422

    def test_cross_series_episode_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_b = _episode(client, series_b["id"])
        response = client.post(
            f"/api/v1/series/{series_a['id']}/audio-cues",
            json={
                "episode_id": episode_b["id"],
                "audio_type": "MUSIC",
                "prompt": "Test",
            },
        )
        assert response.status_code == 422

    def test_cross_series_asset_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        asset_b = _asset(client, series_b["id"])
        response = client.post(
            f"/api/v1/series/{series_a['id']}/audio-cues",
            json={
                "episode_id": episode_a["id"],
                "audio_type": "MUSIC",
                "prompt": "Test",
                "generated_asset_id": asset_b["id"],
            },
        )
        assert response.status_code == 422

    def test_cross_series_get_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        cue = client.post(
            f"/api/v1/series/{series_a['id']}/audio-cues",
            json={
                "episode_id": episode_a["id"],
                "audio_type": "MUSIC",
                "prompt": "Test",
            },
        ).json()

        response = client.get(f"/api/v1/series/{series_b['id']}/audio-cues/{cue['id']}")
        assert response.status_code == 404

    def test_audio_asset_association(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        asset = _asset(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-cues",
            json={
                "episode_id": episode["id"],
                "audio_type": "MUSIC",
                "prompt": "Test",
                "generated_asset_id": asset["id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["generated_asset_id"] == asset["id"]


class TestAudioCueAssetIntegration:
    def test_audio_asset_type_is_accepted(self, db: Session) -> None:
        from app.models import Series

        series = Series(name="Asset Test")
        db.add(series)
        db.commit()
        db.refresh(series)

        asset = Asset(
            series_id=series.id,
            asset_type=AssetType.AUDIO.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            approval_status=ApprovalStatus.PENDING.value,
            storage_backend="fake",
            storage_key="fake://audio/1.mp3",
            name="Generated audio",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        assert asset.asset_type == AssetType.AUDIO.value
        assert asset.series_id == series.id
