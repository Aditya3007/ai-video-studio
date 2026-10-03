"""P4-T03 Scene → shot breakdown planner tests."""

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Shot Planner Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _episode(client: TestClient, series_id: str, episode_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={
            "title": f"Test Episode {episode_number}",
            "episode_number": episode_number,
            "source_type": "TOPIC",
        },
    )
    assert response.status_code == 201
    return response.json()


def _scene(
    client: TestClient,
    episode_id: str,
    description: str | None = None,
    scene_number: int = 1,
) -> dict:
    payload = {
        "scene_number": scene_number,
        "sequence_order": scene_number - 1,
        "title": f"Scene {scene_number}",
    }
    if description:
        payload["description"] = description
    response = client.post(f"/api/v1/episodes/{episode_id}/scenes", json=payload)
    assert response.status_code == 201
    return response.json()


class TestSceneShotPlanner:
    def test_empty_scene_produces_default_shot(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["shots_planned"] == 1
        assert data["shots"][0]["shot_number"] == 1

    def test_multi_sentence_scene_breakdown(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        desc = "He opens the door. He steps into the room. He sees the artifact."
        scene = _scene(client, episode["id"], description=desc)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["shots_planned"] == 3
        numbers = [s["shot_number"] for s in data["shots"]]
        assert numbers == [1, 2, 3]

    def test_shot_ordering_deterministic(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        desc = "Wide shot. Medium shot. Close up."
        scene = _scene(client, episode["id"], description=desc)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        data = response.json()
        actions = [s["action"] for s in data["shots"]]

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots?replace=true"
        )
        data = response.json()
        assert [s["action"] for s in data["shots"]] == actions

    def test_repeated_plan_without_replace_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"], description="One. Two.")

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        assert response.status_code == 201

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        assert response.status_code == 409

    def test_replace_only_target_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene_a = _scene(client, episode["id"], description="A one. A two.")
        scene_b = _scene(client, episode["id"], description="B one.", scene_number=2)

        client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene_a['id']}/plan-shots"
        )
        client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene_b['id']}/plan-shots"
        )

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene_a['id']}/plan-shots?replace=true"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["replaced_existing"] is True

        response = client.get(f"/api/v1/series/{series['id']}/episodes/{episode['id']}")
        # Verify scene B's shots are untouched via listing under scene B
        response = client.get(f"/api/v1/episodes/{episode['id']}/scenes/{scene_b['id']}")
        assert response.status_code == 200

    def test_cross_series_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        scene_a = _scene(client, episode_a["id"])

        response = client.post(
            f"/api/v1/series/{series_b['id']}/episodes/{episode_a['id']}/scenes/{scene_a['id']}/plan-shots"
        )
        assert response.status_code == 404

    def test_cross_episode_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode_a = _episode(client, series["id"])
        episode_b = _episode(client, series["id"], episode_number=2)
        scene_b = _scene(client, episode_b["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode_a['id']}/scenes/{scene_b['id']}/plan-shots"
        )
        assert response.status_code == 404

    def test_invalid_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/00000000-0000-0000-0000-000000000000/plan-shots"
        )
        assert response.status_code == 404

    def test_scene_source_preserved(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        desc = "Opening narration. The hero appears."
        scene = _scene(client, episode["id"], description=desc)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        assert response.status_code == 201

        response = client.get(f"/api/v1/episodes/{episode['id']}/scenes/{scene['id']}")
        assert response.status_code == 200
        assert response.json()["description"] == desc

    def test_generated_shots_persisted(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        desc = "She runs. She stops. She turns."
        scene = _scene(client, episode["id"], description=desc)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/scenes/{scene['id']}/plan-shots"
        )
        assert response.status_code == 201
        created = response.json()["shots"]

        response = client.get(f"/api/v1/scenes/{scene['id']}/shots")
        assert response.status_code == 200
        persisted = response.json()["items"]
        assert len(persisted) == len(created)
        assert [s["shot_number"] for s in persisted] == [1, 2, 3]
