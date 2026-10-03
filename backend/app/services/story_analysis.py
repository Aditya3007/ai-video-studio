"""Story analysis orchestration service."""

from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Story, StoryAnalysis, StoryVersion
from app.services.story import StoryNotFoundError
from app.services.universe import UniverseContextService
from app.story_intelligence.ai_analyzer import AIStoryAnalyzer
from app.story_intelligence.analyzer import DeterministicStoryAnalyzer
from app.story_intelligence.llm.factory import LLMProviderFactory
from app.story_intelligence.schemas import StoryAnalysisResult, StoryAnalyzer


class StoryAnalysisNotFoundError(Exception):
    """Raised when a StoryAnalysis cannot be found for the given Series/Story."""


class StoryAnalysisService:
    """Analyzes stories and persists provider-neutral results."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_story(self, series_id: str, story_id: str) -> Story:
        """Return a Story if it belongs to the Series, else raise."""
        story = self._db.get(Story, story_id)
        if not story or story.series_id != series_id:
            raise StoryNotFoundError("Story not found.")
        return story

    def _assert_version(self, series_id: str, story_id: str, version_id: str) -> StoryVersion:
        """Return a StoryVersion if it belongs to the Story and Series."""
        story = self._assert_story(series_id, story_id)
        version = self._db.get(StoryVersion, version_id)
        if not version or version.story_id != story.id:
            raise StoryNotFoundError("Version not found.")
        return version

    def analyze(
        self,
        series_id: str,
        story_id: str,
        version_id: str,
        mode: Literal["deterministic", "ai"] = "deterministic",
    ) -> StoryAnalysis:
        """Run the selected analyzer and persist the result."""
        version = self._assert_version(series_id, story_id, version_id)
        story = version.story
        universe = UniverseContextService(self._db).get_context(story.series)
        analyzer = self._create_analyzer(mode)
        result = analyzer.analyze(story, version, universe)
        return self._persist(story.id, version.id, result)

    def _create_analyzer(self, mode: Literal["deterministic", "ai"]) -> "StoryAnalyzer":
        """Select the analyzer implementation based on mode."""
        if mode == "deterministic":
            return DeterministicStoryAnalyzer()
        if mode == "ai":
            return AIStoryAnalyzer(LLMProviderFactory.create())
        raise ValueError(f"Unknown analysis mode: {mode}")

    def _persist(
        self, story_id: str, version_id: str, result: StoryAnalysisResult
    ) -> StoryAnalysis:
        """Persist a StoryAnalysisResult."""
        analysis = StoryAnalysis(
            story_id=story_id,
            story_version_id=version_id,
            status=result.status,
            result=result.model_dump(mode="json"),
            warnings=result.warnings,
        )
        self._db.add(analysis)
        return analysis

    def list_analyses(
        self, series_id: str, story_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[StoryAnalysis], int]:
        """Return persisted analyses for a Story."""
        self._assert_story(series_id, story_id)
        items = (
            self._db.execute(
                select(StoryAnalysis)
                .where(StoryAnalysis.story_id == story_id)
                .order_by(StoryAnalysis.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        total = (
            self._db.execute(
                select(func.count())
                .select_from(StoryAnalysis)
                .where(StoryAnalysis.story_id == story_id)
            ).scalar()
            or 0
        )
        return items, total

    def get_analysis(self, series_id: str, story_id: str, analysis_id: str) -> StoryAnalysis:
        """Return a specific analysis."""
        self._assert_story(series_id, story_id)
        analysis = self._db.get(StoryAnalysis, analysis_id)
        if not analysis or analysis.story_id != story_id:
            raise StoryAnalysisNotFoundError("Analysis not found.")
        return analysis
