"""Universe engine API and isolation tests."""

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Test") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _world(client: TestClient, series_id: str, name: str = "World") -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/world", json={"name": name, "current_era": "2025"}
    )
    assert response.status_code == 201
    return response.json()


def _character(client: TestClient, series_id: str, name: str = "Hero") -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/characters",
        json={"name": name, "voice_reference": "warm"},
    )
    assert response.status_code == 201
    return response.json()


def _character_version(client: TestClient, character_id: str, version: int) -> dict:
    response = client.post(
        f"/api/v1/characters/{character_id}/versions",
        json={"version": version, "appearance": "young"},
    )
    assert response.status_code == 201
    return response.json()


def _location_version(client: TestClient, location_id: str, version: int) -> dict:
    response = client.post(
        f"/api/v1/locations/{location_id}/versions",
        json={"version": version, "description": "day"},
    )
    assert response.status_code == 201
    return response.json()


def _location(client: TestClient, series_id: str, name: str = "Base") -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/locations",
        json={"name": name, "atmosphere": "cozy"},
    )
    assert response.status_code == 201
    return response.json()


def _object(client: TestClient, series_id: str, name: str = "MacGuffin") -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/objects",
        json={"name": name, "significance": "key"},
    )
    assert response.status_code == 201
    return response.json()


def _visual_bible(client: TestClient, series_id: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/visual-bible",
        json={"art_style": "anime", "aspect_ratio": "9:16"},
    )
    assert response.status_code == 201
    return response.json()


def _audio_bible(client: TestClient, series_id: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/audio-bible",
        json={"voice_style": "energetic"},
    )
    assert response.status_code == 201
    return response.json()


class TestUniverseContext:
    def test_empty_universe(self, client: TestClient) -> None:
        series = _series(client, "Empty")
        response = client.get(f"/api/v1/series/{series['id']}/universe")
        assert response.status_code == 200
        data = response.json()
        assert data["series"]["id"] == series["id"]
        assert data["characters"] == []
        assert data["locations"] == []
        assert data["objects"] == []
        assert data["world"] is None
        assert data["visual_bible"] is None
        assert data["audio_bible"] is None

    def test_populated_universe(self, client: TestClient) -> None:
        series = _series(client, "Populated")
        world = _world(client, series["id"])
        visual = _visual_bible(client, series["id"])
        audio = _audio_bible(client, series["id"])
        character = _character(client, series["id"])
        _character_version(client, character["id"], 1)
        _character_version(client, character["id"], 2)
        location = _location(client, series["id"])
        _location_version(client, location["id"], 1)
        _object(client, series["id"])

        response = client.get(f"/api/v1/series/{series['id']}/universe")
        assert response.status_code == 200
        data = response.json()
        assert data["series"]["id"] == series["id"]
        assert data["world"]["id"] == world["id"]
        assert data["visual_bible"]["id"] == visual["id"]
        assert data["audio_bible"]["id"] == audio["id"]
        assert len(data["characters"]) == 1
        assert len(data["characters"][0]["versions"]) == 2
        assert data["characters"][0]["voice_reference"] == "warm"
        assert len(data["locations"]) == 1
        assert len(data["locations"][0]["versions"]) == 1
        assert data["locations"][0]["atmosphere"] == "cozy"
        assert len(data["objects"]) == 1
        assert data["objects"][0]["significance"] == "key"
        assert data["timeline"]["current_era"] == "2025"

    def test_nonexistent_series(self, client: TestClient) -> None:
        response = client.get("/api/v1/series/00000000-0000-0000-0000-000000000000/universe")
        assert response.status_code == 404


class TestVisualBible:
    def test_lifecycle(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/visual-bible",
            json={"art_style": "anime"},
        )
        assert response.status_code == 201
        assert response.json()["art_style"] == "anime"

        response = client.get(f"/api/v1/series/{series['id']}/visual-bible")
        assert response.status_code == 200
        assert response.json()["art_style"] == "anime"

        response = client.patch(
            f"/api/v1/series/{series['id']}/visual-bible",
            json={"color_palette": "neon"},
        )
        assert response.status_code == 200
        assert response.json()["color_palette"] == "neon"

    def test_duplicate_rejected(self, client: TestClient) -> None:
        series = _series(client)
        _visual_bible(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/visual-bible",
            json={"art_style": "realistic"},
        )
        assert response.status_code == 409

    def test_missing_series(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/series/00000000-0000-0000-0000-000000000000/visual-bible",
            json={"art_style": "anime"},
        )
        assert response.status_code == 404


class TestAudioBible:
    def test_lifecycle(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-bible",
            json={"voice_style": "calm"},
        )
        assert response.status_code == 201
        assert response.json()["voice_style"] == "calm"

        response = client.get(f"/api/v1/series/{series['id']}/audio-bible")
        assert response.status_code == 200
        assert response.json()["voice_style"] == "calm"

        response = client.patch(
            f"/api/v1/series/{series['id']}/audio-bible",
            json={"music_style": "orchestral"},
        )
        assert response.status_code == 200
        assert response.json()["music_style"] == "orchestral"

    def test_duplicate_rejected(self, client: TestClient) -> None:
        series = _series(client)
        _audio_bible(client, series["id"])
        response = client.post(
            f"/api/v1/series/{series['id']}/audio-bible",
            json={"voice_style": "loud"},
        )
        assert response.status_code == 409


class TestIsolation:
    def test_series_isolation(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        _world(client, series_a["id"], "World A")
        _world(client, series_b["id"], "World B")
        _character(client, series_a["id"], "A Hero")
        _character(client, series_b["id"], "B Hero")
        _location(client, series_a["id"], "A Base")
        _location(client, series_b["id"], "B Base")
        _object(client, series_a["id"], "A Object")
        _object(client, series_b["id"], "B Object")
        _visual_bible(client, series_a["id"])
        _audio_bible(client, series_b["id"])

        data_a = client.get(f"/api/v1/series/{series_a['id']}/universe").json()
        data_b = client.get(f"/api/v1/series/{series_b['id']}/universe").json()

        assert data_a["world"]["name"] == "World A"
        assert data_b["world"]["name"] == "World B"
        assert all(character["name"] == "A Hero" for character in data_a["characters"])
        assert all(character["name"] == "B Hero" for character in data_b["characters"])
        assert all(location["name"] == "A Base" for location in data_a["locations"])
        assert all(location["name"] == "B Base" for location in data_b["locations"])
        assert all(obj["name"] == "A Object" for obj in data_a["objects"])
        assert all(obj["name"] == "B Object" for obj in data_b["objects"])
        assert data_a["visual_bible"] is not None
        assert data_a["audio_bible"] is None
        assert data_b["visual_bible"] is None
        assert data_b["audio_bible"] is not None
