"""API CRUD integration tests."""

from fastapi.testclient import TestClient

MISSING_UUID = "00000000-0000-0000-0000-000000000000"


def _series(client: TestClient, name: str = "Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _world(client: TestClient, series_id: str, name: str = "World") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/world", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _character(client: TestClient, series_id: str, name: str = "Hero") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/characters", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _character_version(client: TestClient, character_id: str, version: int = 1) -> dict:
    response = client.post(
        f"/api/v1/characters/{character_id}/versions",
        json={"version": version},
    )
    assert response.status_code == 201
    return response.json()


def _location(client: TestClient, series_id: str, name: str = "Village") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/locations", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _location_version(client: TestClient, location_id: str, version: int = 1) -> dict:
    response = client.post(
        f"/api/v1/locations/{location_id}/versions",
        json={"version": version},
    )
    assert response.status_code == 201
    return response.json()


def _object(client: TestClient, series_id: str, name: str = "Ring") -> dict:
    response = client.post(f"/api/v1/series/{series_id}/objects", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _episode(client: TestClient, series_id: str, episode_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={"title": "Episode", "episode_number": episode_number},
    )
    assert response.status_code == 201
    return response.json()


def _scene(client: TestClient, episode_id: str, scene_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/episodes/{episode_id}/scenes",
        json={"scene_number": scene_number},
    )
    assert response.status_code == 201
    return response.json()


def _shot(client: TestClient, scene_id: str, shot_number: int = 1) -> dict:
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"shot_number": shot_number},
    )
    assert response.status_code == 201
    return response.json()


class TestSeries:
    """Series CRUD lifecycle."""

    def test_create_series(self, client: TestClient) -> None:
        response = client.post("/api/v1/series", json={"name": "Test Series"})
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Test Series"
        assert "id" in body

    def test_get_series(self, client: TestClient) -> None:
        series = _series(client)
        response = client.get(f"/api/v1/series/{series['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == series["id"]

    def test_list_series(self, client: TestClient) -> None:
        _series(client, "One")
        _series(client, "Two")
        response = client.get("/api/v1/series")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 2

    def test_update_series(self, client: TestClient) -> None:
        series = _series(client)
        response = client.patch(
            f"/api/v1/series/{series['id']}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_delete_series(self, client: TestClient) -> None:
        series = _series(client)
        response = client.delete(f"/api/v1/series/{series['id']}")
        assert response.status_code == 204
        assert client.get(f"/api/v1/series/{series['id']}").status_code == 404

    def test_series_not_found(self, client: TestClient) -> None:
        response = client.get(f"/api/v1/series/{MISSING_UUID}")
        assert response.status_code == 404

    def test_create_series_validation(self, client: TestClient) -> None:
        response = client.post("/api/v1/series", json={"name": ""})
        assert response.status_code == 422


class TestWorld:
    """World CRUD lifecycle."""

    def test_create_and_get_world_by_series(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/world",
            json={"name": "World"},
        )
        assert response.status_code == 201
        assert response.json()["series_id"] == series["id"]

    def test_get_world_by_id(self, client: TestClient) -> None:
        series = _series(client)
        world = _world(client, series["id"])
        response = client.get(f"/api/v1/worlds/{world['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == world["id"]

    def test_update_world(self, client: TestClient) -> None:
        series = _series(client)
        world = _world(client, series["id"])
        response = client.patch(
            f"/api/v1/worlds/{world['id']}",
            json={"name": "Updated World"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated World"

    def test_delete_world(self, client: TestClient) -> None:
        series = _series(client)
        world = _world(client, series["id"])
        response = client.delete(f"/api/v1/worlds/{world['id']}")
        assert response.status_code == 204
        assert client.get(f"/api/v1/series/{series['id']}/world").status_code == 404

    def test_world_invalid_series(self, client: TestClient) -> None:
        response = client.post(
            f"/api/v1/series/{MISSING_UUID}/world",
            json={"name": "Orphan"},
        )
        assert response.status_code == 404

    def test_duplicate_world(self, client: TestClient) -> None:
        series = _series(client)
        _world(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/world",
            json={"name": "Another"},
        )
        assert response.status_code == 409


class TestCharacter:
    """Character CRUD lifecycle."""

    def test_create_character(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        assert character["series_id"] == series["id"]

    def test_list_characters_by_series(self, client: TestClient) -> None:
        series = _series(client)
        _character(client, series["id"], "A")
        _character(client, series["id"], "B")
        response = client.get(f"/api/v1/series/{series['id']}/characters")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

    def test_get_character(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        response = client.get(f"/api/v1/series/{series['id']}/characters/{character['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == character["id"]

    def test_update_character(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        response = client.patch(
            f"/api/v1/series/{series['id']}/characters/{character['id']}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_delete_character(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        response = client.delete(f"/api/v1/series/{series['id']}/characters/{character['id']}")
        assert response.status_code == 204

    def test_character_invalid_series(self, client: TestClient) -> None:
        response = client.post(
            f"/api/v1/series/{MISSING_UUID}/characters",
            json={"name": "Orphan"},
        )
        assert response.status_code == 404

    def test_character_not_in_series(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        character = _character(client, series_a["id"])
        response = client.get(f"/api/v1/series/{series_b['id']}/characters/{character['id']}")
        assert response.status_code == 404


class TestCharacterVersion:
    """Character version CRUD."""

    def test_create_and_list_versions(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        _character_version(client, character["id"], 1)
        _character_version(client, character["id"], 2)
        response = client.get(f"/api/v1/characters/{character['id']}/versions")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

    def test_duplicate_version(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        _character_version(client, character["id"], 1)
        response = client.post(
            f"/api/v1/characters/{character['id']}/versions",
            json={"version": 1},
        )
        assert response.status_code == 409

    def test_update_version(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        version = _character_version(client, character["id"], 1)
        response = client.patch(
            f"/api/v1/characters/{character['id']}/versions/{version['id']}",
            json={"is_current": True},
        )
        assert response.status_code == 200
        assert response.json()["is_current"] is True

    def test_delete_version(self, client: TestClient) -> None:
        series = _series(client)
        character = _character(client, series["id"])
        version = _character_version(client, character["id"], 1)
        response = client.delete(f"/api/v1/characters/{character['id']}/versions/{version['id']}")
        assert response.status_code == 204


class TestLocation:
    """Location CRUD lifecycle."""

    def test_create_and_list(self, client: TestClient) -> None:
        series = _series(client)
        _location(client, series["id"], "A")
        _location(client, series["id"], "B")
        response = client.get(f"/api/v1/series/{series['id']}/locations")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_get_and_update(self, client: TestClient) -> None:
        series = _series(client)
        location = _location(client, series["id"])
        response = client.get(f"/api/v1/series/{series['id']}/locations/{location['id']}")
        assert response.status_code == 200
        response = client.patch(
            f"/api/v1/series/{series['id']}/locations/{location['id']}",
            json={"location_type": "city"},
        )
        assert response.status_code == 200
        assert response.json()["location_type"] == "city"

    def test_delete_location(self, client: TestClient) -> None:
        series = _series(client)
        location = _location(client, series["id"])
        response = client.delete(f"/api/v1/series/{series['id']}/locations/{location['id']}")
        assert response.status_code == 204


class TestLocationVersion:
    """Location version CRUD."""

    def test_create_and_list_versions(self, client: TestClient) -> None:
        series = _series(client)
        location = _location(client, series["id"])
        _location_version(client, location["id"], 1)
        _location_version(client, location["id"], 2)
        response = client.get(f"/api/v1/locations/{location['id']}/versions")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

    def test_duplicate_version(self, client: TestClient) -> None:
        series = _series(client)
        location = _location(client, series["id"])
        _location_version(client, location["id"], 1)
        response = client.post(
            f"/api/v1/locations/{location['id']}/versions",
            json={"version": 1},
        )
        assert response.status_code == 409


class TestStoryObject:
    """StoryObject CRUD lifecycle."""

    def test_create_and_list(self, client: TestClient) -> None:
        series = _series(client)
        _object(client, series["id"], "Ring")
        _object(client, series["id"], "Book")
        response = client.get(f"/api/v1/series/{series['id']}/objects")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_get_update_delete(self, client: TestClient) -> None:
        series = _series(client)
        obj = _object(client, series["id"])
        response = client.get(f"/api/v1/series/{series['id']}/objects/{obj['id']}")
        assert response.status_code == 200
        response = client.patch(
            f"/api/v1/series/{series['id']}/objects/{obj['id']}",
            json={"object_type": "artifact"},
        )
        assert response.status_code == 200
        assert response.json()["object_type"] == "artifact"
        response = client.delete(f"/api/v1/series/{series['id']}/objects/{obj['id']}")
        assert response.status_code == 204


class TestEpisode:
    """Episode CRUD lifecycle."""

    def test_create_and_list(self, client: TestClient) -> None:
        series = _series(client)
        _episode(client, series["id"], 1)
        _episode(client, series["id"], 2)
        response = client.get(f"/api/v1/series/{series['id']}/episodes")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_update_episode(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        response = client.patch(
            f"/api/v1/series/{series['id']}/episodes/{episode['id']}",
            json={"title": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated"

    def test_delete_episode(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        response = client.delete(f"/api/v1/series/{series['id']}/episodes/{episode['id']}")
        assert response.status_code == 204

    def test_duplicate_episode_number(self, client: TestClient) -> None:
        series = _series(client)
        _episode(client, series["id"], 1)
        response = client.post(
            f"/api/v1/series/{series['id']}/episodes",
            json={"title": "Duplicate", "episode_number": 1},
        )
        assert response.status_code == 409

    def test_invalid_episode_status(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/episodes",
            json={"title": "Bad", "episode_number": 1, "status": "INVALID"},
        )
        assert response.status_code == 422


class TestScene:
    """Scene CRUD lifecycle."""

    def test_create_and_list(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        _scene(client, episode["id"], 1)
        _scene(client, episode["id"], 2)
        response = client.get(f"/api/v1/episodes/{episode['id']}/scenes")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_scene_with_location(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        location = _location(client, series["id"])
        response = client.post(
            f"/api/v1/episodes/{episode['id']}/scenes",
            json={"scene_number": 1, "location_id": location["id"]},
        )
        assert response.status_code == 201
        assert response.json()["location_id"] == location["id"]

    def test_invalid_scene_location(self, client: TestClient) -> None:
        series = _series(client)
        other_series = _series(client, "Other")
        episode = _episode(client, series["id"])
        location = _location(client, other_series["id"])
        response = client.post(
            f"/api/v1/episodes/{episode['id']}/scenes",
            json={"scene_number": 1, "location_id": location["id"]},
        )
        assert response.status_code == 404

    def test_duplicate_scene_number(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        _scene(client, episode["id"], 1)
        response = client.post(
            f"/api/v1/episodes/{episode['id']}/scenes",
            json={"scene_number": 1},
        )
        assert response.status_code == 409

    def test_update_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        response = client.patch(
            f"/api/v1/episodes/{episode['id']}/scenes/{scene['id']}",
            json={"title": "New Title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_delete_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        response = client.delete(f"/api/v1/episodes/{episode['id']}/scenes/{scene['id']}")
        assert response.status_code == 204


class TestShot:
    """Shot CRUD lifecycle."""

    def test_create_and_list(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        _shot(client, scene["id"], 1)
        _shot(client, scene["id"], 2)
        response = client.get(f"/api/v1/scenes/{scene['id']}/shots")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_negative_duration_rejected(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        response = client.post(
            f"/api/v1/scenes/{scene['id']}/shots",
            json={"shot_number": 1, "duration_seconds": -1},
        )
        assert response.status_code == 422

    def test_duplicate_shot_number(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        _shot(client, scene["id"], 1)
        response = client.post(
            f"/api/v1/scenes/{scene['id']}/shots",
            json={"shot_number": 1},
        )
        assert response.status_code == 409

    def test_update_and_delete_shot(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        response = client.patch(
            f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}",
            json={"description": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Updated"
        response = client.delete(f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}")
        assert response.status_code == 204


class TestIsolation:
    """Ownership boundary tests."""

    def test_episode_scene_shot_hierarchy(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene = _scene(client, episode["id"])
        shot = _shot(client, scene["id"])
        response = client.get(f"/api/v1/scenes/{scene['id']}/shots/{shot['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == shot["id"]

    def test_shot_under_wrong_scene(self, client: TestClient) -> None:
        series = _series(client)
        episode = _episode(client, series["id"])
        scene_a = _scene(client, episode["id"])
        other_episode = _episode(client, series["id"], 2)
        scene_b = _scene(client, other_episode["id"])
        shot = _shot(client, scene_a["id"])
        response = client.get(f"/api/v1/scenes/{scene_b['id']}/shots/{shot['id']}")
        assert response.status_code == 404

    def test_invalid_parent_returns_404(self, client: TestClient) -> None:
        response = client.post(
            f"/api/v1/episodes/{MISSING_UUID}/scenes",
            json={"scene_number": 1},
        )
        assert response.status_code == 404
