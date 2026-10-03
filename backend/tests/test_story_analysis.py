"""Story analysis boundary, deterministic analyzer, and entity resolver tests."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.character import CharacterUniverseResponse
from app.schemas.series import SeriesResponse
from app.schemas.universe import UniverseContextResponse
from app.story_intelligence import (
    DeterministicStoryAnalyzer,
    StoryAnalysisResult,
    StoryEntityResolver,
    StoryMetadata,
)
from app.story_intelligence.schemas import CharacterReference, SourceReference


def _series(client: TestClient, name: str = "Analysis Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _story(client: TestClient, series_id: str, source_type: str, content: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/stories",
        json={
            "title": "Test Story",
            "source_type": source_type,
            "source_content": content,
        },
    )
    assert response.status_code == 201
    return response.json()


def _version(client: TestClient, series_id: str, story_id: str, number: int, content: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/stories/{story_id}/versions",
        json={"version_number": number, "content": content},
    )
    assert response.status_code == 201
    return response.json()


def _character(client: TestClient, series_id: str, name: str) -> dict:
    response = client.post(f"/api/v1/series/{series_id}/characters", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _location(client: TestClient, series_id: str, name: str) -> dict:
    response = client.post(f"/api/v1/series/{series_id}/locations", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _now() -> datetime:
    return datetime(2025, 1, 1, 0, 0, 0)


class TestStructuredSchemas:
    def test_story_analysis_result_optional_fields(self) -> None:
        result = StoryAnalysisResult(
            story_id="00000000-0000-0000-0000-000000000001",
            story_version_id="00000000-0000-0000-0000-000000000002",
            status="PENDING",
        )
        assert result.metadata.title is None
        assert result.characters == []

    def test_story_analysis_result_serialization(self) -> None:
        result = StoryAnalysisResult(
            story_id="00000000-0000-0000-0000-000000000001",
            story_version_id="00000000-0000-0000-0000-000000000002",
            status="COMPLETED",
            metadata=StoryMetadata(title="T", language="en"),
            characters=[
                CharacterReference(
                    name="Hero",
                    canonical_character_id=UUID("00000000-0000-0000-0000-000000000003"),
                    source_refs=[
                        SourceReference(
                            source_version_id=UUID("00000000-0000-0000-0000-000000000002")
                        )
                    ],
                )
            ],
        )
        data = result.model_dump(mode="json")
        assert data["metadata"]["title"] == "T"
        assert data["characters"][0]["name"] == "Hero"

    def test_duplicate_event_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StoryAnalysisResult(
                story_id="00000000-0000-0000-0000-000000000001",
                story_version_id="00000000-0000-0000-0000-000000000002",
                status="COMPLETED",
                events=[
                    {
                        "id": "e1",
                        "sequence": 0,
                        "summary": "a",
                    },
                    {
                        "id": "e1",
                        "sequence": 1,
                        "summary": "b",
                    },
                ],
            )


class TestEntityResolver:
    def _universe(self, character_name: str | None = None) -> UniverseContextResponse:
        series = SeriesResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            name="S",
            created_at=_now(),
            updated_at=_now(),
        )
        characters = []
        if character_name:
            characters.append(
                CharacterUniverseResponse(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    name=character_name,
                    series_id=series.id,
                    created_at=_now(),
                    updated_at=_now(),
                    versions=[],
                )
            )
        return UniverseContextResponse(series=series, characters=characters)

    def test_exact_character_match(self) -> None:
        resolver = StoryEntityResolver(self._universe("Arjun"))
        result = resolver.resolve_character("Arjun")
        assert result.status == "MATCHED"
        assert result.canonical_id == UUID("00000000-0000-0000-0000-000000000001")
        assert result.confidence == 1.0

    def test_unresolved_character(self) -> None:
        resolver = StoryEntityResolver(self._universe("Arjun"))
        result = resolver.resolve_character("Unknown")
        assert result.status == "UNRESOLVED"

    def test_case_insensitive_match(self) -> None:
        resolver = StoryEntityResolver(self._universe("Arjun"))
        result = resolver.resolve_character("arjun")
        assert result.status == "MATCHED"

    def test_no_cross_series_match(self) -> None:
        resolver = StoryEntityResolver(self._universe("Arjun"))
        result = resolver.resolve_character("Other")
        assert result.status == "UNRESOLVED"

    def test_location_match(self) -> None:
        from app.schemas.location import LocationUniverseResponse

        series = SeriesResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            name="S",
            created_at=_now(),
            updated_at=_now(),
        )
        location = LocationUniverseResponse(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            name="Base",
            series_id=series.id,
            created_at=_now(),
            updated_at=_now(),
            versions=[],
        )
        universe = UniverseContextResponse(series=series, locations=[location])
        resolver = StoryEntityResolver(universe)
        result = resolver.resolve_location("Base")
        assert result.status == "MATCHED"


class TestDeterministicAnalyzer:
    def test_topic_requires_review(self) -> None:
        from app.models.story import Story, StoryVersion

        story_id = uuid4()
        version_id = uuid4()
        story = Story(
            id=str(story_id),
            series_id="ser1",
            title="T",
            source_type="TOPIC",
            source_content="A topic",
        )
        version = StoryVersion(
            id=str(version_id),
            story_id=str(story_id),
            version_number=1,
            content="A topic",
        )
        analyzer = DeterministicStoryAnalyzer()
        result = analyzer.analyze(story, version, None)
        assert result.status == "REVIEW_REQUIRED"
        assert any("TOPIC" in w for w in result.warnings)
        assert result.metadata.premise == "A topic"

    def test_complete_story_preserved(self) -> None:
        from app.models.story import Story, StoryVersion

        story_id = uuid4()
        version_id = uuid4()
        story = Story(
            id=str(story_id),
            series_id="ser1",
            title="T",
            source_type="COMPLETE_STORY",
            source_content="Long text...",
        )
        version = StoryVersion(
            id=str(version_id),
            story_id=str(story_id),
            version_number=1,
            content="Long text...",
        )
        analyzer = DeterministicStoryAnalyzer()
        result = analyzer.analyze(story, version, None)
        assert result.status == "COMPLETED"
        assert result.story_version_id == version_id
        assert len(result.source_refs) == 1
        assert result.source_refs[0].source_version_id == version_id
        assert result.characters == []


class TestAnalysisAPI:
    def _first_version_id(self, client: TestClient, series_id: str, story_id: str) -> str:
        response = client.get(f"/api/v1/series/{series_id}/stories/{story_id}/versions")
        assert response.status_code == 200
        return response.json()["items"][0]["id"]

    def test_create_and_retrieve_analysis(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "Once upon a time.")
        version_id = self._first_version_id(client, series["id"], story["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions/{version_id}/analysis"
        )
        assert response.status_code == 201
        analysis = response.json()
        assert analysis["story_id"] == story["id"]
        assert analysis["story_version_id"] == version_id
        assert analysis["result"]["status"] == "COMPLETED"

        response = client.get(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/analysis/{analysis['id']}"
        )
        assert response.status_code == 200
        assert response.json()["id"] == analysis["id"]

    def test_topic_analysis_review_required(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "TOPIC", "A haunted house")
        version_id = self._first_version_id(client, series["id"], story["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions/{version_id}/analysis"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["result"]["status"] == "REVIEW_REQUIRED"
        assert any("expansion" in w.lower() for w in data["warnings"])

    def test_list_analyses(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "Content")
        version_id = self._first_version_id(client, series["id"], story["id"])
        _version(client, series["id"], story["id"], 2, "V2 content")

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions/{version_id}/analysis"
        )
        assert response.status_code == 201

        response = client.get(f"/api/v1/series/{series['id']}/stories/{story['id']}/analysis")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_missing_version(self, client: TestClient) -> None:
        series = _series(client)
        story = _story(client, series["id"], "COMPLETE_STORY", "Content")
        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions/00000000-0000-0000-0000-000000000000/analysis"
        )
        assert response.status_code == 404

    def test_cross_series_analysis_access(self, client: TestClient) -> None:
        series_a = _series(client, "A")
        series_b = _series(client, "B")
        story_a = _story(client, series_a["id"], "COMPLETE_STORY", "A")
        _character(client, series_a["id"], "Arjun")
        _character(client, series_b["id"], "Arjun")

        version_id = self._first_version_id(client, series_a["id"], story_a["id"])
        response = client.post(
            f"/api/v1/series/{series_a['id']}/stories/{story_a['id']}/versions/{version_id}/analysis"
        )
        assert response.status_code == 201
        analysis_id = response.json()["id"]

        response = client.get(
            f"/api/v1/series/{series_b['id']}/stories/{story_a['id']}/analysis/{analysis_id}"
        )
        assert response.status_code == 404

    def test_api_ai_mode_with_fake_provider(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        get_settings.cache_clear()

        series = _series(client, "AI")
        story = _story(client, series["id"], "COMPLETE_STORY", "A short story.")
        version_id = self._first_version_id(client, series["id"], story["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions/{version_id}/analysis?mode=ai"
        )
        assert response.status_code == 201
        assert response.json()["result"]["status"] == "COMPLETED"

    def test_api_invalid_mode(self, client: TestClient) -> None:
        series = _series(client, "Invalid")
        story = _story(client, series["id"], "COMPLETE_STORY", "A short story.")
        version_id = self._first_version_id(client, series["id"], story["id"])

        response = client.post(
            f"/api/v1/series/{series['id']}/stories/{story['id']}/versions/{version_id}/analysis?mode=unknown"
        )
        assert response.status_code == 422
