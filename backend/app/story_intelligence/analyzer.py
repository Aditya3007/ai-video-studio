"""Deterministic story analyzer implementation and contract."""

from app.models.story import Story, StoryVersion
from app.schemas.universe import UniverseContextResponse
from app.story_intelligence.schemas import (
    SourceReference,
    StoryAnalysisResult,
    StoryMetadata,
)


class DeterministicStoryAnalyzer:
    """Deterministic analyzer that proves the analysis contract without using AI."""

    def analyze(
        self,
        story: Story,
        story_version: StoryVersion,
        universe_context: UniverseContextResponse,
    ) -> StoryAnalysisResult:
        """Return a valid, deterministic analysis result."""
        source_ref = SourceReference(
            source_version_id=story_version.id,
            excerpt=(
                story_version.content[:200]
                if len(story_version.content) > 200
                else story_version.content
            ),
        )

        if story.source_type == "TOPIC":
            return StoryAnalysisResult(
                story_id=story.id,
                story_version_id=story_version.id,
                status="REVIEW_REQUIRED",
                metadata=StoryMetadata(
                    title=story.title,
                    language=story.language,
                    premise=story_version.content,
                ),
                source_refs=[source_ref],
                warnings=["TOPIC source requires AI story expansion before full analysis."],
            )

        return StoryAnalysisResult(
            story_id=story.id,
            story_version_id=story_version.id,
            status="COMPLETED",
            metadata=StoryMetadata(
                title=story.title,
                language=story.language,
            ),
            source_refs=[source_ref],
            warnings=["Deterministic analyzer only; no semantic extraction performed."],
        )
