"""P4-T04 Shot specification and production constraints tests."""

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Spec Series") -> dict:
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


def _spec_url(scene_id: str, shot_id: str) -> str:
    return f"/api/v1/scenes/{scene_id}/shots/{shot_id}/specification"


class TestShotSpecificationConstraints:
    def test_valid_9_16_specification(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"aspect_ratio": "9:16", "duration_seconds": 15},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aspect_ratio"] == "9:16"
        assert data["duration_seconds"] == 15

    def test_invalid_aspect_ratio_format(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"aspect_ratio": "16/9"},
        )
        assert response.status_code == 422

    def test_zero_aspect_ratio_dimension_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"aspect_ratio": "0:9"},
        )
        assert response.status_code == 422

    def test_zero_duration_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"duration_seconds": 0},
        )
        assert response.status_code == 422

    def test_negative_duration_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"duration_seconds": -5},
        )
        assert response.status_code == 422

    def test_duration_upper_bound_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"duration_seconds": 301},
        )
        assert response.status_code == 422

    def test_valid_canonical_refs_accepted(self, client: TestClient) -> None:
        series = _series(client)
        character = client.post(
            f"/api/v1/series/{series['id']}/characters", json={"name": "Hero"}
        ).json()
        location = client.post(
            f"/api/v1/series/{series['id']}/locations", json={"name": "Village"}
        ).json()
        obj = client.post(f"/api/v1/series/{series['id']}/objects", json={"name": "Sword"}).json()
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={
                "character_refs": [character["id"]],
                "location_refs": [location["id"]],
                "object_refs": [obj["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["character_refs"] == [character["id"]]
        assert data["location_refs"] == [location["id"]]
        assert data["object_refs"] == [obj["id"]]

    def test_malformed_canonical_refs_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"character_refs": ["not-a-uuid"]},
        )
        assert response.status_code == 422

    def test_output_constraints_preserved(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={
                "output_constraints": {
                    "fps": 30,
                    "safe_area_top": 120,
                    "captions": True,
                }
            },
        )
        assert response.status_code == 201
        assert response.json()["output_constraints"]["fps"] == 30

    def test_extra_preserved(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"extra": {"mood_board": "dark"}},
        )
        assert response.status_code == 201
        assert response.json()["extra"] == {"mood_board": "dark"}

    def test_partial_patch(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"aspect_ratio": "9:16", "duration_seconds": 15},
        )
        assert response.status_code == 201
        spec_id = response.json()["id"]

        response = client.patch(
            _spec_url(scene["id"], shot["id"]),
            json={"duration_seconds": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == spec_id
        assert data["aspect_ratio"] == "9:16"
        assert data["duration_seconds"] == 20

    def test_existing_spec_retrieval(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"intent": "Introduce the village."},
        )
        assert response.status_code == 201
        spec_id = response.json()["id"]

        response = client.get(_spec_url(scene["id"], shot["id"]))
        assert response.status_code == 200
        assert response.json()["id"] == spec_id

    def test_duplicate_specification_protected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"intent": "First"},
        )
        assert response.status_code == 201

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={"intent": "Second"},
        )
        assert response.status_code == 409

    def test_isolation_cross_series(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_a = _episode(client, series_a["id"])
        scene_a = _scene(client, episode_a["id"])
        shot_a = _shot(client, scene_a["id"])
        episode_b = _episode(client, series_b["id"])
        scene_b = _scene(client, episode_b["id"])

        response = client.post(
            _spec_url(scene_b["id"], shot_a["id"]),
            json={"intent": "Cross"},
        )
        assert response.status_code == 404

    def test_isolation_cross_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene_a = _scene(client, episode["id"], scene_number=1)
        scene_b = _scene(client, episode["id"], scene_number=2)
        shot_a = _shot(client, scene_a["id"])

        response = client.post(
            _spec_url(scene_b["id"], shot_a["id"]),
            json={"intent": "Cross scene"},
        )
        assert response.status_code == 404

    def test_creative_fields_unconstrained(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            _spec_url(scene["id"], shot["id"]),
            json={
                "intent": "A very long and creative description " * 100,
                "framing": "Wide, then tight, then Dutch angle",
                "visual_direction": "Any text should be allowed here.",
            },
        )
        assert response.status_code == 201
