"""P4-T02 Episode → Scene breakdown planner tests."""

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Planner Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _episode(client: TestClient, series_id: str, source_text: str | None = None) -> dict:
    payload = {
        "title": "Test Episode",
        "episode_number": 1,
        "source_type": "TOPIC",
    }
    if source_text:
        payload["source_text"] = source_text
    response = client.post(f"/api/v1/series/{series_id}/episodes", json=payload)
    assert response.status_code == 201
    return response.json()


def _location(client: TestClient, series_id: str, name: str) -> dict:
    response = client.post(f"/api/v1/series/{series_id}/locations", json={"name": name})
    assert response.status_code == 201
    return response.json()


class TestEpisodeScenePlanner:
    def test_empty_episode_produces_default_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scenes_planned"] == 1
        assert data["scenes"][0]["scene_number"] == 1

    def test_multi_scene_breakdown(self, client: TestClient) -> None:
        series = _series(client)
        source = "Scene one description.\n\nScene two description.\n\nScene three description."
        episode = _episode(client, series["id"], source_text=source)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scenes_planned"] == 3
        numbers = [s["scene_number"] for s in data["scenes"]]
        assert numbers == [1, 2, 3]

    def test_scene_ordering_deterministic(self, client: TestClient) -> None:
        series = _series(client)
        source = "Third block.\n\nFirst block.\n\nSecond block."
        episode = _episode(client, series["id"], source_text=source)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201
        data = response.json()
        descriptions = [s["description"] for s in data["scenes"]]
        assert descriptions == ["Third block.", "First block.", "Second block."]

    def test_repeated_plan_without_replace_is_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"], source_text="One.\n\nTwo.")

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 409

    def test_repeated_plan_with_replace(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"], source_text="One.\n\nTwo.")

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201
        first_id = response.json()["scenes"][0]["id"]

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes?replace=true"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["replaced_existing"] is True
        assert data["scenes"][0]["id"] != first_id

    def test_series_isolation(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])

        response = client.post(
            f"/api/v1/series/{series_b['id']}/episodes/{episode_a['id']}/plan-scenes"
        )
        assert response.status_code == 404

    def test_missing_episode(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/00000000-0000-0000-0000-000000000000/plan-scenes"
        )
        assert response.status_code == 404

    def test_canonical_location_resolution(self, client: TestClient) -> None:
        series = _series(client)
        village = _location(client, series["id"], "Village")
        source = "They arrive at the Village early in the morning."
        episode = _episode(client, series["id"], source_text=source)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scenes"][0]["location_id"] == village["id"]

    def test_planner_does_not_invent_canonical_ids(self, client: TestClient) -> None:
        series = _series(client)
        source = "They arrive at an UnknownPlace."
        episode = _episode(client, series["id"], source_text=source)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scenes"][0]["location_id"] is None

    def test_source_text_preserved(self, client: TestClient) -> None:
        series = _series(client)
        source = "Original story text.\n\nSecond paragraph."
        episode = _episode(client, series["id"], source_text=source)

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}/plan-scenes"
        )
        assert response.status_code == 201

        response = client.get(f"/api/v1/series/{series['id']}/episodes/{episode['id']}")
        assert response.status_code == 200
        assert response.json()["source_text"] == source
