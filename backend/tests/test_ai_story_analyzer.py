"""AIStoryAnalyzer tests using FakeLLMProvider."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.models.story import Story, StoryVersion
from app.schemas.character import CharacterUniverseResponse
from app.schemas.location import LocationUniverseResponse
from app.schemas.series import SeriesResponse
from app.schemas.story_object import StoryObjectResponse
from app.schemas.universe import UniverseContextResponse
from app.story_intelligence import AIStoryAnalyzer, FakeLLMProvider, LLMProviderError


def _now() -> datetime:
    return datetime(2025, 1, 1, 0, 0, 0)


def _story(source_type: str, content: str) -> tuple[Story, StoryVersion]:
    story_id = uuid4()
    version_id = uuid4()
    story = Story(
        id=str(story_id),
        series_id=str(uuid4()),
        title="Test Story",
        source_type=source_type,
        source_content=content,
    )
    version = StoryVersion(
        id=str(version_id), story_id=str(story_id), version_number=1, content=content
    )
    return story, version


def _universe(
    characters: list[str] | None = None,
    locations: list[str] | None = None,
    objects: list[str] | None = None,
) -> UniverseContextResponse:
    series_id = uuid4()
    series = SeriesResponse(id=series_id, name="U", created_at=_now(), updated_at=_now())
    char_models = [
        CharacterUniverseResponse(
            id=uuid4(),
            name=name,
            series_id=series_id,
            created_at=_now(),
            updated_at=_now(),
            versions=[],
        )
        for name in (characters or [])
    ]
    loc_models = [
        LocationUniverseResponse(
            id=uuid4(),
            name=name,
            series_id=series_id,
            created_at=_now(),
            updated_at=_now(),
            versions=[],
        )
        for name in (locations or [])
    ]
    obj_models = [
        StoryObjectResponse(
            id=uuid4(),
            name=name,
            series_id=series_id,
            created_at=_now(),
            updated_at=_now(),
        )
        for name in (objects or [])
    ]
    return UniverseContextResponse(
        series=series, characters=char_models, locations=loc_models, objects=obj_models
    )


class TestAIStoryAnalyzer:
    def test_complete_story_returns_structured_result(self) -> None:
        story, version = _story("COMPLETE_STORY", "It was a dark and stormy night.")
        universe = _universe(characters=["Hero"], locations=["Base"])
        response = {
            "status": "COMPLETED",
            "metadata": {"title": "Dark Night", "genre": "Thriller"},
            "characters": [
                {
                    "name": "Hero",
                    "role": "protagonist",
                }
            ],
            "locations": [
                {
                    "name": "Base",
                    "significance": "hideout",
                }
            ],
            "events": [{"id": "e1", "sequence": 0, "summary": "storm begins"}],
            "beats": [{"id": "b1", "type": "SETUP", "summary": "setup", "sequence": 0}],
        }
        analyzer = AIStoryAnalyzer(FakeLLMProvider(response=response))
        result = analyzer.analyze(story, version, universe)

        assert result.story_id == UUID(story.id)
        assert result.story_version_id == UUID(version.id)
        assert result.status == "COMPLETED"
        assert result.metadata.title == "Dark Night"
        assert result.characters[0].canonical_character_id == universe.characters[0].id
        assert result.locations[0].canonical_location_id == universe.locations[0].id

    def test_topic_expansion_review_required(self) -> None:
        story, version = _story("TOPIC", "A haunted radio receives future messages.")
        universe = _universe()
        response = {
            "status": "REVIEW_REQUIRED",
            "metadata": {"title": "Future Radio", "premise": "Haunted radio"},
            "warnings": ["Topic expanded; review required."],
        }
        analyzer = AIStoryAnalyzer(FakeLLMProvider(response=response))
        result = analyzer.analyze(story, version, universe)

        assert result.status == "REVIEW_REQUIRED"
        assert result.metadata.title == "Future Radio"

    def test_malformed_response_raises(self) -> None:
        story, version = _story("COMPLETE_STORY", "Text.")
        universe = _universe()
        analyzer = AIStoryAnalyzer(FakeLLMProvider(text="not valid json"))
        with pytest.raises(LLMProviderError, match="malformed"):
            analyzer.analyze(story, version, universe)

    def test_provider_failure_raises(self) -> None:
        story, version = _story("COMPLETE_STORY", "Text.")
        universe = _universe()
        analyzer = AIStoryAnalyzer(FakeLLMProvider(fail=True))
        with pytest.raises(LLMProviderError, match="Simulated"):
            analyzer.analyze(story, version, universe)

    def test_empty_provider_response_raises(self) -> None:
        story, version = _story("COMPLETE_STORY", "Text.")
        universe = _universe()
        analyzer = AIStoryAnalyzer(FakeLLMProvider(text=""))
        with pytest.raises(LLMProviderError):
            analyzer.analyze(story, version, universe)

    def test_entity_resolution_overrides_ai_ids(self) -> None:
        story, version = _story("COMPLETE_STORY", "Text.")
        universe = _universe(characters=["Ravi"])
        fake_canonical = str(uuid4())
        response = {
            "status": "COMPLETED",
            "characters": [
                {
                    "name": "Ravi",
                    "canonical_character_id": fake_canonical,
                    "status": "MATCHED",
                }
            ],
        }
        analyzer = AIStoryAnalyzer(FakeLLMProvider(response=response))
        result = analyzer.analyze(story, version, universe)

        assert result.characters[0].canonical_character_id == universe.characters[0].id

    def test_unknown_entity_remains_unresolved(self) -> None:
        story, version = _story("COMPLETE_STORY", "Text.")
        universe = _universe(characters=["Ravi"])
        response = {
            "status": "COMPLETED",
            "characters": [{"name": "Unknown"}],
        }
        analyzer = AIStoryAnalyzer(FakeLLMProvider(response=response))
        result = analyzer.analyze(story, version, universe)

        assert result.characters[0].canonical_character_id is None
        assert result.characters[0].status == "UNRESOLVED"

    def test_object_resolution(self) -> None:
        story, version = _story("COMPLETE_STORY", "Text.")
        universe = _universe(objects=["Amulet"])
        response = {
            "status": "COMPLETED",
            "objects": [{"name": "Amulet"}],
        }
        analyzer = AIStoryAnalyzer(FakeLLMProvider(response=response))
        result = analyzer.analyze(story, version, universe)

        assert result.objects[0].canonical_object_id == universe.objects[0].id
