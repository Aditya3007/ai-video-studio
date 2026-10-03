"""Scene → Shot breakdown planner service."""

import re
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.models import Episode, Scene, Shot
from app.schemas.shot_plan import ScenePlanResponse, ShotPlan


class ShotPlanningError(Exception):
    """Raised when scene shot planning fails."""


class SceneNotFoundError(Exception):
    """Raised when a Scene cannot be found for the given Episode/Series."""


@runtime_checkable
class ShotPlannerStrategy(Protocol):
    """Provider-neutral strategy for breaking a Scene into Shots."""

    def plan_shots(self, scene: Scene) -> list[ShotPlan]:
        """Return an ordered list of shot plans for the scene."""
        ...


class DeterministicShotPlanner:
    """Deterministic/local shot planner; no AI or network calls."""

    _SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

    def plan_shots(self, scene: Scene) -> list[ShotPlan]:
        """Derive shots from scene title and description."""
        source = scene.description or scene.title or ""
        sentences = [s.strip() for s in self._SENTENCE_RE.split(source) if s.strip()]

        if not sentences:
            return [
                ShotPlan(
                    shot_number=1,
                    sequence_order=0,
                    description=scene.title,
                    action=scene.description,
                )
            ]

        plans: list[ShotPlan] = []
        for index, sentence in enumerate(sentences, start=1):
            plans.append(
                ShotPlan(
                    shot_number=index,
                    sequence_order=index - 1,
                    description=scene.title or f"Shot {index}",
                    action=sentence,
                )
            )
        return plans


class ShotPlanningService:
    """Plans and persists shots for a scene."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_episode(self, series_id: str, episode_id: str) -> Episode:
        episode = self._db.get(Episode, episode_id)
        if not episode or episode.series_id != series_id:
            raise SceneNotFoundError("Episode not found.")
        return episode

    def _assert_scene(self, episode_id: str, scene_id: str) -> Scene:
        scene = self._db.get(Scene, scene_id)
        if not scene or scene.episode_id != episode_id:
            raise SceneNotFoundError("Scene not found.")
        return scene

    def plan_and_create(
        self,
        series_id: str,
        episode_id: str,
        scene_id: str,
        *,
        strategy: ShotPlannerStrategy | None = None,
        replace: bool = False,
    ) -> ScenePlanResponse:
        """Generate and persist shot breakdown for a scene."""
        episode = self._assert_episode(series_id, episode_id)
        scene = self._assert_scene(episode.id, scene_id)

        if scene.shots and not replace:
            raise ShotPlanningError("Scene already has shots. Use replace=True to overwrite.")

        if strategy is None:
            strategy = DeterministicShotPlanner()

        had_shots = bool(scene.shots)
        plans = strategy.plan_shots(scene)

        if replace:
            for shot in list(scene.shots):
                self._db.delete(shot)
            self._db.flush()

        shots: list[Shot] = []
        for plan in plans:
            shot = Shot(
                scene_id=scene.id,
                shot_number=plan.shot_number,
                sequence_order=plan.sequence_order,
                description=plan.description,
                action=plan.action,
            )
            self._db.add(shot)
            shots.append(shot)

        self._db.flush()
        for shot in shots:
            self._db.refresh(shot)

        return ScenePlanResponse(
            episode_id=episode.id,
            scene_id=scene.id,
            shots_planned=len(shots),
            replaced_existing=replace and had_shots,
            shots=shots,
        )
