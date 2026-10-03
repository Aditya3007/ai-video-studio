"""Story intake, versions, isolation, and episode relationship tests."""

from fastapi.testclient import TestClient


def _series(client: TestClient, name: str = "Story Test") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _story(
    client: TestClient,
    series_id: str,
    source_type: str,
    content: str,
    title: str = "Story",
) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/stories",
        json={
            "title": title,
            "source_type": source_type,
            "source_content": content,
            "description": "A story",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestStoryCreation:
    def test_complete_story_creates_version_one(self, client: TestClient) -> None:
        series = _series(client)
        content = "Once upon a time..."
        story = _story(client, series["id"], "COMPLETE_STORY", content)

        assert story["series_id"] == series["id"]
        assert story["source_type"] == "COMPLETE_STORY"
        assert story["source_content"] == content
        assert story["status"] == "DRAFT"

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}/versions")
        assert response.status_code == 200
        versions = response.json()["items"]
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1
        assert versions[0]["content"] == content

    def test_topic_creates_version_one(self, client: TestClient) -> None:
        series = _series(client)
        topic = "A space adventure"
        story = _story(client, series["id"], "TOPIC", topic)

        assert story["source_type"] == "TOPIC"
        assert story["source_content"] == topic

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}/versions")
        assert response.status_code == 200
        versions = response.json()["items"]
        assert len(versions) == 1
        assert versions[0]["content"] == topic


class TestStoryMetadata:
    def test_update_title_description_language_status(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.patch(
            f"/api/v1/series/{series['id']}/stories/{story['id']}",
            json={
                "title": "New title",
                "description": "New desc",
                "language": "es",
                "status": "READY",
                "extra": {"genre": "sci-fi"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New title"
        assert data["description"] == "New desc"
        assert data["language"] == "es"
        assert data["status"] == "READY"
        assert data["extra"] == {"genre": "sci-fi"}

    def test_update_source_content_rejected(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.patch(
            f"/api/v1/series/{series['id']}/stories/{story['id']}",
            json={"source_content": "changed"},
        )
        assert response.status_code == 422

    def test_update_source_type_rejected(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.patch(
            f"/api/v1/series/{series['id']}/stories/{story['id']}",
            json={"source_type": "TOPIC"},
        )
        assert response.status_code == 422

    def test_invalid_status_rejected(self, client: TestClient) -> None:
        series = _series(client)
        response = client.post(
            f"/api/v1/series/{series['id']}/stories",
            json={
                "title": "T",
                "source_type": "TOPIC",
                "source_content": "c",
                "status": "INVALID",
            },
        )
        assert response.status_code == 422


class TestStoryVersions:
    def test_multiple_versions_ordered(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions",
            json={"version_number": 2, "content": "v2"},
        )
        assert response.status_code == 201

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}/versions")
        assert response.status_code == 200
        versions = response.json()["items"]
        assert [v["version_number"] for v in versions] == [1, 2]

    def test_duplicate_version_rejected(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions",
            json={"version_number": 2, "content": "v2"},
        )
        assert response.status_code == 201

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions",
            json={"version_number": 2, "content": "v2-again"},
        )
        assert response.status_code == 409


class TestEpisodeRelationship:
    def test_episode_can_reference_story(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.post(
            f"/api/v1/series/{series['id']}/episodes",
            json={
                "title": "Ep1",
                "episode_number": 1,
                "story_id": story["id"],
            },
        )
        assert response.status_code == 201
        assert response.json()["story_id"] == story["id"]

    def test_story_can_exist_without_episode(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "TOPIC", "topic")

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == story["id"]


class TestIsolation:
    def test_stories_do_not_leak_across_series(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        story_a = _story(client, series_a["id"], "COMPLETE_STORY", "A content")
        _story(client, series_b["id"], "TOPIC", "B content")

        response = client.get(f"/api/v1/series/{series_a['id']}/stories")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["id"] == story_a["id"]

        response = client.get(f"/api/v1/series/{series_b['id']}/stories/{story_a['id']}")
        assert response.status_code == 404

        response = client.get(f"/api/v1/series/{series_b['id']}/stories/{story_a['id']}/versions")
        assert response.status_code == 404


class TestDeletion:
    def test_delete_story_removes_versions(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "content")

        response = client.delete(f"/api/v1/series/{series['id']}/stories/{story['id']}")
        assert response.status_code == 204

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}")
        assert response.status_code == 404

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}/versions")
        assert response.status_code == 404
