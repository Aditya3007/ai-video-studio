"""AI-driven StoryAnalyzer implementation."""

import json
import logging

from app.models.story import Story, StoryVersion
from app.schemas.universe import UniverseContextResponse
from app.story_intelligence.llm.errors import LLMProviderError
from app.story_intelligence.llm.provider import LLMProvider
from app.story_intelligence.prompts import build_analysis_prompt
from app.story_intelligence.resolver import StoryEntityResolver
from app.story_intelligence.schemas import StoryAnalysisResult

logger = logging.getLogger(__name__)


class AIStoryAnalyzer:
    """Analyzer that uses an LLMProvider to produce a StoryAnalysisResult."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def analyze(
        self,
        story: Story,
        story_version: StoryVersion,
        universe_context: UniverseContextResponse,
    ) -> StoryAnalysisResult:
        """Run the AI provider and normalize the response into the domain contract."""
        system_prompt, user_prompt = build_analysis_prompt(story, story_version, universe_context)
        try:
            response = self._provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("LLM provider raised an unexpected error")
            raise LLMProviderError(f"LLM provider failed: {exc}") from exc

        parsed = response.parsed
        if parsed is None:
            try:
                parsed = json.loads(response.content)
            except (json.JSONDecodeError, TypeError) as exc:
                raise LLMProviderError("Provider returned malformed JSON.") from exc

        if not isinstance(parsed, dict):
            raise LLMProviderError("Provider response is not a JSON object.")

        result_data = {
            **parsed,
            "story_id": story.id,
            "story_version_id": story_version.id,
        }
        try:
            result = StoryAnalysisResult(**result_data)
        except Exception as exc:
            raise LLMProviderError(
                f"Provider response failed StoryAnalysisResult validation: {exc}"
            ) from exc

        self._resolve_entities(result, universe_context)
        return result

    def _resolve_entities(
        self,
        result: StoryAnalysisResult,
        universe_context: UniverseContextResponse,
    ) -> None:
        """Resolve AI-identified entities against canonical universe entities."""
        resolver = StoryEntityResolver(universe_context)
        for character in result.characters:
            resolution = resolver.resolve_character(character.name)
            character.canonical_character_id = resolution.canonical_id
            character.status = resolution.status
        for location in result.locations:
            resolution = resolver.resolve_location(location.name)
            location.canonical_location_id = resolution.canonical_id
            location.status = resolution.status
        for obj in result.objects:
            resolution = resolver.resolve_object(obj.name)
            obj.canonical_object_id = resolution.canonical_id
            obj.status = resolution.status
