"""P7-T01 Voice and narration domain tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base


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


def _series(client: TestClient, name: str = "Voice Series") -> dict:
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


def _character(client: TestClient, series_id: str, name: str = "Hero") -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/characters",
        json={"name": name, "role": "PROTAGONIST"},
    )
    assert response.status_code == 201
    return response.json()


def _audio_asset(client: TestClient, series_id: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/assets",
        json={
            "asset_type": "AUDIO",
            "role": "GENERATED",
            "status": "AVAILABLE",
            "storage_backend": "filesystem",
            "storage_key": "audio/generated.mp3",
            "name": "Generated audio",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestVoiceDomain:
    def test_create_voice(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/voices",
            json={"name": "Narrator", "description": "Main narrator voice"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Narrator"
        assert data["series_id"] == series["id"]

    def test_voice_character_association(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/voices",
            json={
                "name": "Hero Voice",
                "character_id": character["id"],
                "voice_metadata": {"gender": "neutral", "age_range": "adult"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["character_id"] == character["id"]
        assert data["voice_metadata"]["gender"] == "neutral"

    def test_cross_series_character_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        character_b = _character(client, series_b["id"], "Other")
        response = client.post(
            f"/api/v1/series/{series_a['id']}/voices",
            json={"name": "Hero Voice", "character_id": character_b["id"]},
        )
        assert response.status_code == 422

    def test_list_and_get_voice(self, client: TestClient) -> None:
        series = _series(client)
        voice = client.post(
            f"/api/v1/series/{series['id']}/voices",
            json={"name": "Narrator"},
        ).json()

        response = client.get(f"/api/v1/series/{series['id']}/voices")
        assert response.status_code == 200
        assert len(response.json()) == 1

        response = client.get(f"/api/v1/series/{series['id']}/voices/{voice['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == voice["id"]


class TestNarrationDomain:
    def test_create_narration(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/narrations",
            json={
                "episode_id": episode["id"],
                "source_text": "Once upon a time...",
                "narration_type": "NARRATION",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_text"] == "Once upon a time..."
        assert data["series_id"] == series["id"]
        assert data["episode_id"] == episode["id"]
        assert data["status"] == "PENDING"
        assert data["narration_type"] == "NARRATION"

    def test_narration_with_scene_and_shot(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        voice = client.post(
            f"/api/v1/series/{series['id']}/voices",
            json={"name": "Narrator"},
        ).json()
        character = _character(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/narrations",
            json={
                "episode_id": episode["id"],
                "scene_id": scene["id"],
                "shot_id": shot["id"],
                "voice_id": voice["id"],
                "character_id": character["id"],
                "source_text": "Watch out!",
                "narration_type": "DIALOGUE",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scene_id"] == scene["id"]
        assert data["shot_id"] == shot["id"]
        assert data["voice_id"] == voice["id"]
        assert data["character_id"] == character["id"]
        assert data["narration_type"] == "DIALOGUE"

    def test_narration_audio_asset_relationship(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        asset = _audio_asset(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/narrations",
            json={
                "episode_id": episode["id"],
                "source_text": "Hello world",
                "generated_asset_id": asset["id"],
                "status": "GENERATED",
                "duration_seconds": 3.5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["generated_asset_id"] == asset["id"]
        assert data["status"] == "GENERATED"
        assert data["duration_seconds"] == 3.5

    def test_cross_series_episode_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_b = _episode(client, series_b["id"])
        response = client.post(
            f"/api/v1/series/{series_a['id']}/narrations",
            json={
                "episode_id": episode_b["id"],
                "source_text": "Should fail",
            },
        )
        assert response.status_code == 422

    def test_cross_series_voice_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        voice_b = client.post(
            f"/api/v1/series/{series_b['id']}/voices",
            json={"name": "Other"},
        ).json()
        response = client.post(
            f"/api/v1/series/{series_a['id']}/narrations",
            json={
                "episode_id": episode_a["id"],
                "voice_id": voice_b["id"],
                "source_text": "Should fail",
            },
        )
        assert response.status_code == 422

    def test_cross_series_asset_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        asset_b = _audio_asset(client, series_b["id"])
        response = client.post(
            f"/api/v1/series/{series_a['id']}/narrations",
            json={
                "episode_id": episode_a["id"],
                "generated_asset_id": asset_b["id"],
                "source_text": "Should fail",
            },
        )
        assert response.status_code == 422

    def test_get_narration_cross_series(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        narration = client.post(
            f"/api/v1/series/{series_a['id']}/narrations",
            json={"episode_id": episode_a["id"], "source_text": "Text"},
        ).json()
        response = client.get(f"/api/v1/series/{series_b['id']}/narrations/{narration['id']}")
        assert response.status_code == 404
