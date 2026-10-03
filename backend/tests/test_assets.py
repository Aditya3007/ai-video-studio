"""P5-T01 Asset domain and canonical reference management tests."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Asset Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _character(client: TestClient, series_id: str, name: str = "Hero") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/characters", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _location(client: TestClient, series_id: str, name: str = "Village") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/locations", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _object(client: TestClient, series_id: str, name: str = "Sword") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/objects", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _episode(client: TestClient, series_id: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={
            "title": "Episode",
            "episode_number": 1,
            "source_type": "TOPIC",
        },
    )
    assert response.status_code == 201
    return response.json()


def _scene(client: TestClient, episode_id: str) -> dict:
    response = client.post(
        f"/api/v1/episodes/{episode_id}/scenes",
        json={"scene_number": 1, "sequence_order": 0, "title": "Scene"},
    )
    assert response.status_code == 201
    return response.json()


def _shot(client: TestClient, scene_id: str) -> dict:
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": 1,
            "sequence_order": 0,
            "description": "Shot",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestAssetDomain:
    def test_create_and_retrieve_asset(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={
                "asset_type": "IMAGE",
                "role": "GENERATED",
                "status": "PENDING",
                "storage_backend": "default",
                "storage_key": "series/a/key.png",
                "name": "Hero keyframe",
                "asset_metadata": {"source": "test"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["series_id"] == series["id"]
        assert data["asset_type"] == "IMAGE"
        assert data["storage_key"] == "series/a/key.png"

        response = client.get(f"/api/v1/series/{series['id']}/assets/{data['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == data["id"]

    def test_list_assets_in_series(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        client.post(
            f"/api/v1/series/{series_a['id']}/assets",
            json={"asset_type": "IMAGE"},
        )
        client.post(
            f"/api/v1/series/{series_b['id']}/assets",
            json={"asset_type": "AUDIO"},
        )

        response = client.get(f"/api/v1/series/{series_a['id']}/assets")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["asset_type"] == "IMAGE"

    def test_update_asset_metadata(self, client: TestClient) -> None:
        series = _series(client)
        asset = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={"asset_type": "IMAGE"},
        ).json()

        response = client.patch(
            f"/api/v1/series/{series['id']}/assets/{asset['id']}",
            json={"status": "AVAILABLE", "storage_key": "new/key.png"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "AVAILABLE"
        assert data["storage_key"] == "new/key.png"

    def test_delete_asset(self, client: TestClient) -> None:
        series = _series(client)
        asset = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={"asset_type": "REFERENCE"},
        ).json()

        response = client.delete(f"/api/v1/series/{series['id']}/assets/{asset['id']}")
        assert response.status_code == 204

        response = client.get(f"/api/v1/series/{series['id']}/assets/{asset['id']}")
        assert response.status_code == 404

    def test_canonical_character_reference(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={
                "asset_type": "IMAGE",
                "role": "CANONICAL",
                "character_ids": [character["id"]],
            },
        )
        assert response.status_code == 201
        assert response.json()["character_ids"] == [character["id"]]

    def test_canonical_reference_rejects_other_series(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        character_b = _character(client, series_b["id"])

        response = client.post(
            f"/api/v1/series/{series_a['id']}/assets",
            json={
                "asset_type": "IMAGE",
                "character_ids": [character_b["id"]],
            },
        )
        assert response.status_code == 422

    def test_nonexistent_canonical_reference_rejected(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={
                "asset_type": "IMAGE",
                "character_ids": [str(uuid4())],
            },
        )
        assert response.status_code == 422

    def test_multiple_canonical_refs(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        location = _location(client, series["id"])
        obj = _object(client, series["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={
                "asset_type": "STORYBOARD",
                "character_ids": [character["id"]],
                "location_ids": [location["id"]],
                "object_ids": [obj["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["character_ids"] == [character["id"]]
        assert data["location_ids"] == [location["id"]]
        assert data["object_ids"] == [obj["id"]]

    def test_update_canonical_refs(self, client: TestClient) -> None:
        series = _series(client)
        character_a = _character(client, series["id"], "A")
        character_b = _character(client, series["id"], "B")
        asset = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={"asset_type": "IMAGE", "character_ids": [character_a["id"]]},
        ).json()

        response = client.patch(
            f"/api/v1/series/{series['id']}/assets/{asset['id']}",
            json={"character_ids": [character_b["id"]]},
        )
        assert response.status_code == 200
        assert response.json()["character_ids"] == [character_b["id"]]

    def test_shot_reference_in_same_series(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={"asset_type": "VIDEO", "shot_id": shot["id"]},
        )
        assert response.status_code == 201
        assert response.json()["shot_id"] == shot["id"]

    def test_shot_from_other_series_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        episode_b = _episode(client, series_b["id"])
        scene_b = _scene(client, episode_b["id"])
        shot_b = _shot(client, scene_b["id"])

        response = client.post(
            f"/api/v1/series/{series_a['id']}/assets",
            json={"asset_type": "VIDEO", "shot_id": shot_b["id"]},
        )
        assert response.status_code == 422

    def test_cross_series_asset_access_rejected(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        asset_b = client.post(
            f"/api/v1/series/{series_b['id']}/assets",
            json={"asset_type": "IMAGE"},
        ).json()

        response = client.get(f"/api/v1/series/{series_a['id']}/assets/{asset_b['id']}")
        assert response.status_code == 404

    def test_storage_key_is_provider_neutral(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={
                "asset_type": "REFERENCE",
                "storage_backend": "default",
                "storage_key": "assets/test/keyframe.png",
            },
        )
        assert response.status_code == 201
        assert response.json()["storage_key"] == "assets/test/keyframe.png"

    def test_invalid_asset_type_rejected(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/assets",
            json={"asset_type": "INVALID_TYPE"},
        )
        assert response.status_code == 422
