"""P4-T01 production planning domain tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Episode, Scene, Series, Shot, ShotSpecification
from app.models.enums import EpisodeSourceType, EpisodeStatus


def _enable_sqlite_fk(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_sqlite_fk)
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess
        sess.rollback()


def _create_series(client: TestClient, name: str = "Production Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _create_episode(client: TestClient, series_id: str, number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={
            "title": f"Episode {number}",
            "episode_number": number,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_scene(client: TestClient, episode_id: str, number: int, order: int = 0) -> dict:
    response = client.post(
        f"/api/v1/episodes/{episode_id}/scenes",
        json={"scene_number": number, "sequence_order": order, "title": f"Scene {number}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_shot(client: TestClient, scene_id: str, number: int, order: int = 0) -> dict:
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"shot_number": number, "sequence_order": order, "description": f"Shot {number}"},
    )
    assert response.status_code == 201
    return response.json()


class TestProductionPlanningORM:
    def test_shot_specification_lifecycle(self, session: Session) -> None:
        series = Series(name="ORM Series")
        episode = Episode(
            title="Pilot",
            episode_number=1,
            status=EpisodeStatus.DRAFT.value,
            source_type=EpisodeSourceType.TOPIC.value,
            series=series,
        )
        scene = Scene(scene_number=1, episode=episode)
        shot = Shot(shot_number=1, scene=scene)
        spec = ShotSpecification(
            shot=shot,
            intent="Establish the village.",
            framing="Wide",
            output_constraints={"aspect_ratio": "9:16"},
        )
        session.add(series)
        session.commit()

        spec.character_refs = [str(series.id)]
        session.commit()

        assert spec.id is not None
        assert shot.specification is spec
        assert spec.character_refs == [str(series.id)]

    def test_series_cascade_deletes_specification(self, session: Session) -> None:
        series = Series(name="Cascade Series")
        episode = Episode(
            title="Pilot",
            episode_number=1,
            status=EpisodeStatus.DRAFT.value,
            source_type=EpisodeSourceType.TOPIC.value,
            series=series,
        )
        scene = Scene(scene_number=1, episode=episode)
        shot = Shot(shot_number=1, scene=scene)
        ShotSpecification(shot=shot, intent="Test")
        session.add(series)
        session.commit()

        shot_id = shot.id
        session.delete(series)
        session.commit()

        assert session.get(Shot, shot_id) is None
        assert (
            session.query(ShotSpecification).filter(ShotSpecification.shot_id == shot_id).count()
            == 0
        )


class TestProductionPlanningAPI:
    def test_episode_scene_shot_specification_hierarchy(self, client: TestClient) -> None:
        series = _create_series(client)
        episode = _create_episode(client, series["id"])
        scene = _create_scene(client, episode["id"], number=1)
        shot = _create_shot(client, scene["id"], number=1)

        spec_payload = {
            "intent": "Establish village",
            "framing": "Wide",
            "character_refs": [str(series["id"])],
            "output_constraints": {"aspect_ratio": "9:16"},
        }
        response = client.post(
            f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}/specification",
            json=spec_payload,
        )
        assert response.status_code == 201
        spec = response.json()
        assert spec["intent"] == "Establish village"
        assert spec["character_refs"] == [series["id"]]

        response = client.get(f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}")
        assert response.status_code == 200
        assert response.json()["specification"]["id"] == spec["id"]

    def test_scene_ordering_deterministic(self, client: TestClient) -> None:
        series = _create_series(client)
        episode = _create_episode(client, series["id"])
        _create_scene(client, episode["id"], number=3, order=2)
        _create_scene(client, episode["id"], number=1, order=0)
        _create_scene(client, episode["id"], number=2, order=1)

        response = client.get(f"/api/v1/episodes/{episode['id']}/scenes")
        assert response.status_code == 200
        numbers = [s["scene_number"] for s in response.json()["items"]]
        assert numbers == [1, 2, 3]

    def test_shot_ordering_deterministic(self, client: TestClient) -> None:
        series = _create_series(client)
        episode = _create_episode(client, series["id"])
        scene = _create_scene(client, episode["id"], number=1)
        _create_shot(client, scene["id"], number=2, order=1)
        _create_shot(client, scene["id"], number=1, order=0)
        _create_shot(client, scene["id"], number=3, order=2)

        response = client.get(f"/api/v1/scenes/{scene['id']}/shots")
        assert response.status_code == 200
        numbers = [s["shot_number"] for s in response.json()["items"]]
        assert numbers == [1, 2, 3]

    def test_shot_isolation(self, client: TestClient) -> None:
        series_a = _create_series(client, "A")
        series_b = _create_series(client, "B")
        episode_a = _create_episode(client, series_a["id"], number=1)
        episode_b = _create_episode(client, series_b["id"], number=1)
        scene_a = _create_scene(client, episode_a["id"], number=1)
        scene_b = _create_scene(client, episode_b["id"], number=1)
        shot_a = _create_shot(client, scene_a["id"], number=1)

        response = client.get(f"/api/v1/scenes/{scene_b['id']}/shots/{shot_a['id']}")
        assert response.status_code == 404

    def test_shot_specification_isolation(self, client: TestClient) -> None:
        series_a = _create_series(client, "A")
        series_b = _create_series(client, "B")
        episode_a = _create_episode(client, series_a["id"], number=1)
        episode_b = _create_episode(client, series_b["id"], number=1)
        scene_a = _create_scene(client, episode_a["id"], number=1)
        scene_b = _create_scene(client, episode_b["id"], number=1)
        shot_a = _create_shot(client, scene_a["id"], number=1)
        spec_a = client.post(
            f"/api/v1/scenes/{scene_a['id']}/shots/{shot_a['id']}/specification",
            json={"intent": "A"},
        ).json()

        response = client.get(f"/api/v1/scenes/{scene_b['id']}/shots/{shot_a['id']}/specification")
        assert response.status_code == 404

        response = client.get(f"/api/v1/scenes/{scene_a['id']}/shots/{shot_a['id']}/specification")
        assert response.status_code == 200
        assert response.json()["id"] == spec_a["id"]

    def test_duplicate_specification_conflict(self, client: TestClient) -> None:
        series = _create_series(client)
        episode = _create_episode(client, series["id"])
        scene = _create_scene(client, episode["id"], number=1)
        shot = _create_shot(client, scene["id"], number=1)

        response = client.post(
            f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}/specification",
            json={"intent": "First"},
        )
        assert response.status_code == 201

        response = client.post(
            f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}/specification",
            json={"intent": "Second"},
        )
        assert response.status_code == 409

    def test_update_specification(self, client: TestClient) -> None:
        series = _create_series(client)
        episode = _create_episode(client, series["id"])
        scene = _create_scene(client, episode["id"], number=1)
        shot = _create_shot(client, scene["id"], number=1)

        response = client.post(
            f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}/specification",
            json={"intent": "Original"},
        )
        assert response.status_code == 201

        response = client.patch(
            f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}/specification",
            json={"intent": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["intent"] == "Updated"

    def test_missing_specification(self, client: TestClient) -> None:
        series = _create_series(client)
        episode = _create_episode(client, series["id"])
        scene = _create_scene(client, episode["id"], number=1)
        shot = _create_shot(client, scene["id"], number=1)

        response = client.get(f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}/specification")
        assert response.status_code == 404
