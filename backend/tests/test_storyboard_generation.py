"""P5-T03 Storyboard / keyframe generation tests."""

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Storyboard Series") -> dict:
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
    series_id: str,
    episode_id: str,
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


class TestStoryboardGeneration:
    def test_successful_storyboard_generation(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, series["id"], episode["id"], scene["id"], shot["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/storyboard",
            json={},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["asset_type"] == "STORYBOARD"
        assert data["role"] == "GENERATED"
        assert data["status"] == "AVAILABLE"
        assert data["shot_id"] == shot["id"]
        assert data["series_id"] == series["id"]
        assert data["storage_key"].startswith("fake://")
        assert "Establish the hero" in data["asset_metadata"]["prompt"]

    def test_prompt_override(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, series["id"], episode["id"], scene["id"], shot["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/storyboard",
            json={"prompt_override": "Custom storyboard prompt"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["asset_metadata"]["prompt"] == "Custom storyboard prompt"

    def test_missing_specification_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/storyboard",
            json={},
        )
        assert response.status_code == 422

    def test_wrong_series_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode = _episode(client, series_a["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, series_a["id"], episode["id"], scene["id"], shot["id"])

        response = client.post(
            f"/api/v1/series/{series_b['id']}/shots/{shot['id']}/storyboard",
            json={},
        )
        assert response.status_code == 422

    def test_nonexistent_shot_rejected(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/shots/00000000-0000-0000-0000-000000000000/storyboard",
            json={},
        )
        assert response.status_code == 422

    def test_reference_asset_other_series_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        scene_a = _scene(client, episode_a["id"])
        shot_a = _shot(client, scene_a["id"])
        _spec(client, series_a["id"], episode_a["id"], scene_a["id"], shot_a["id"])

        asset_b = client.post(
            f"/api/v1/series/{series_b['id']}/assets",
            json={"asset_type": "IMAGE"},
        ).json()

        response = client.post(
            f"/api/v1/series/{series_a['id']}/shots/{shot_a['id']}/storyboard",
            json={"reference_asset_ids": [asset_b["id"]]},
        )
        assert response.status_code == 422

    def test_multiple_storyboards_for_shot_possible(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(client, series["id"], episode["id"], scene["id"], shot["id"])

        response1 = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/storyboard",
            json={},
        )
        response2 = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/storyboard",
            json={},
        )
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["id"] != response2.json()["id"]

    def test_storyboard_preserves_aspect_ratio(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        _spec(
            client,
            series["id"],
            episode["id"],
            scene["id"],
            shot["id"],
            aspect_ratio="16:9",
        )

        response = client.post(
            f"/api/v1/series/{series['id']}/shots/{shot['id']}/storyboard",
            json={},
        )
        assert response.status_code == 201
        image = response.json()["asset_metadata"]["images"][0]
        assert image["width"] > image["height"]
