"""Episode → Scene breakdown planner service."""

from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.models import Episode, Scene
from app.schemas.scene_plan import EpisodePlanResponse, ScenePlan
from app.schemas.universe import UniverseContextResponse
from app.services.universe import UniverseContextService
from app.story_intelligence.resolver import StoryEntityResolver


class EpisodePlanningError(Exception):
    """Raised when episode scene planning fails."""


class EpisodeNotFoundError(Exception):
    """Raised when an Episode cannot be found for the given Series."""


@runtime_checkable
class ScenePlannerStrategy(Protocol):
    """Provider-neutral strategy for breaking an Episode into Scenes."""

    def plan_scenes(self, episode: Episode, context: UniverseContextResponse) -> list[ScenePlan]:
        """Return an ordered list of scene plans for the episode."""
        ...


class DeterministicScenePlanner:
    """Deterministic/local scene planner; no AI or network calls."""

    def plan_scenes(self, episode: Episode, context: UniverseContextResponse) -> list[ScenePlan]:
        """Derive scenes from episode source text or linked story source."""
        source = self._source_text(episode)
        resolver = StoryEntityResolver(context)

        if not source:
            return [
                ScenePlan(
                    scene_number=1,
                    sequence_order=0,
                    title="Scene 1",
                    description=episode.description or episode.title,
                    location_id=self._resolve_location(episode.description or "", resolver),
                    source_excerpt=None,
                )
            ]

        paragraphs = [p.strip() for p in source.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [source]

        plans: list[ScenePlan] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            location_id = self._resolve_location(paragraph, resolver)
            title = self._extract_title(paragraph)
            plans.append(
                ScenePlan(
                    scene_number=index,
                    sequence_order=index - 1,
                    title=title,
                    description=paragraph[:500],
                    location_id=location_id,
                    source_excerpt=paragraph[:200] if source else None,
                )
            )
        return plans

    def _source_text(self, episode: Episode) -> str | None:
        if episode.source_text:
            return episode.source_text
        if episode.story and episode.story.source_content:
            return episode.story.source_content
        return None

    def _resolve_location(self, text: str, resolver: StoryEntityResolver) -> str | None:
        target = text.lower()
        for location in resolver._context.locations:
            if location.name.lower() in target:
                return str(location.id)
        return None

    def _extract_title(self, paragraph: str) -> str | None:
        first_line = paragraph.split("\n")[0].strip()
        if len(first_line) <= 120:
            return first_line[:120]
        return first_line[:120].rsplit(" ", 1)[0] + "…"


class EpisodePlanningService:
    """Plans and persists scenes for an episode."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_episode(self, series_id: str, episode_id: str) -> Episode:
        episode = self._db.get(Episode, episode_id)
        if not episode or episode.series_id != series_id:
            raise EpisodeNotFoundError("Episode not found.")
        return episode

    def plan_and_create(
        self,
        series_id: str,
        episode_id: str,
        *,
        strategy: ScenePlannerStrategy | None = None,
        replace: bool = False,
    ) -> EpisodePlanResponse:
        """Generate and persist scene breakdown for an episode."""
        episode = self._assert_episode(series_id, episode_id)

        if episode.scenes and not replace:
            raise EpisodePlanningError("Episode already has scenes. Use replace=True to overwrite.")

        if strategy is None:
            strategy = DeterministicScenePlanner()

        had_scenes = bool(episode.scenes)
        context = UniverseContextService(self._db).get_context(episode.series)
        plans = strategy.plan_scenes(episode, context)

        if replace:
            for scene in list(episode.scenes):
                self._db.delete(scene)
            self._db.flush()

        scenes: list[Scene] = []
        for plan in plans:
            scene = Scene(
                episode_id=episode.id,
                scene_number=plan.scene_number,
                sequence_order=plan.sequence_order,
                title=plan.title,
                description=plan.description,
                location_id=str(plan.location_id) if plan.location_id else None,
            )
            self._db.add(scene)
            scenes.append(scene)

        self._db.flush()
        for scene in scenes:
            self._db.refresh(scene)

        return EpisodePlanResponse(
            episode_id=episode.id,
            scenes_planned=len(scenes),
            replaced_existing=replace and had_scenes,
            scenes=scenes,
        )
