"""Provider-neutral AI visual/narrative QA service."""

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Asset, Episode, Scene, Series, Shot
from app.models.enums import AIQAMode, ContinuitySeverity
from app.schemas.ai_qa import (
    AIQAContext,
    AIQAFinding,
    AIQARequest,
    AIQAResponse,
    AIQAResult,
    MediaReference,
)
from app.services.universe import UniverseContextService


class AIQAProviderError(Exception):
    """Raised when the AI QA provider fails."""


class AIQAValidationError(Exception):
    """Raised when an AI QA result fails validation."""


class AIQANotFoundError(Exception):
    """Raised when the requested QA scope cannot be resolved."""


@runtime_checkable
class AIQAProvider(Protocol):
    """Abstract contract for AI visual/narrative QA providers."""

    def evaluate(self, request: AIQARequest) -> AIQAResult:
        """Evaluate the request and return structured QA findings."""
        ...


class FakeAIQAProvider:
    """Offline, deterministic AI QA provider for tests."""

    def __init__(
        self,
        findings: list[AIQAFinding] | None = None,
        *,
        fail: bool = False,
        provider: str = "fake",
        model: str = "fake-qa-model",
    ) -> None:
        self._findings = findings or []
        self._fail = fail
        self._provider = provider
        self._model = model

    def evaluate(self, request: AIQARequest) -> AIQAResult:
        """Return a deterministic response without network calls."""
        if self._fail:
            raise AIQAProviderError("Simulated AI QA provider failure.")
        return AIQAResult(
            findings=list(self._findings),
            provider=self._provider,
            model=self._model,
            metadata={"mode": request.mode.value, "scope_type": request.scope_type},
        )


class AIQAService:
    """Constructs QA context, invokes the configured provider, and validates results."""

    _VALID_CATEGORIES = {
        "CHARACTER",
        "LOCATION",
        "STORY_OBJECT",
        "SHOT",
        "SCENE",
        "EPISODE",
        "PRODUCTION_CONSTRAINT",
        "NARRATIVE",
        "VISUAL",
    }

    _SEVERITY_ORDER = {
        ContinuitySeverity.ERROR: 0,
        ContinuitySeverity.WARNING: 1,
        ContinuitySeverity.INFO: 2,
    }

    def __init__(self, db: Session, provider: AIQAProvider | None = None) -> None:
        self._db = db
        self._provider = provider or FakeAIQAProvider()

    def evaluate_episode(
        self,
        series_id: str,
        episode_id: str,
        mode: AIQAMode,
    ) -> AIQAResponse:
        """Run AI QA over an episode's production context."""
        series, episode = self._load_series_and_episode(series_id, episode_id)
        allowed_ids = self._allowed_ids_for_episode(series_id, episode_id)
        context = self._build_episode_context(series, episode)
        request = AIQARequest(
            mode=mode,
            scope_type="episode",
            scope_id=UUID(episode.id),
            series_id=UUID(series.id),
            context=context,
        )
        result = self._invoke_provider(request)
        self._validate_result(result, allowed_ids)
        return AIQAResponse(
            series_id=UUID(series.id),
            scope_type="episode",
            scope_id=UUID(episode.id),
            mode=mode,
            findings=self._sort(result.findings),
            provider=result.provider,
            model=result.model,
        )

    def evaluate_shot(
        self,
        series_id: str,
        shot_id: str,
        mode: AIQAMode,
    ) -> AIQAResponse:
        """Run AI QA over a single shot's production context."""
        series, shot, scene, episode = self._load_series_shot(series_id, shot_id)
        allowed_ids = self._allowed_ids_for_shot(series_id, shot, scene, episode)
        context = self._build_shot_context(series, episode, scene, shot)
        request = AIQARequest(
            mode=mode,
            scope_type="shot",
            scope_id=UUID(shot.id),
            series_id=UUID(series.id),
            context=context,
        )
        result = self._invoke_provider(request)
        self._validate_result(result, allowed_ids)
        return AIQAResponse(
            series_id=UUID(series.id),
            scope_type="shot",
            scope_id=UUID(shot.id),
            mode=mode,
            findings=self._sort(result.findings),
            provider=result.provider,
            model=result.model,
        )

    def _load_series_and_episode(self, series_id: str, episode_id: str) -> tuple[Series, Episode]:
        series = self._db.get(Series, series_id)
        if not series:
            raise AIQANotFoundError("Series not found.")

        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise AIQANotFoundError("Episode not found.")

        return series, episode

    def _load_series_shot(
        self, series_id: str, shot_id: str
    ) -> tuple[Series, Shot, Scene, Episode]:
        series = self._db.get(Series, series_id)
        if not series:
            raise AIQANotFoundError("Series not found.")

        shot = self._db.get(Shot, shot_id)
        if not shot:
            raise AIQANotFoundError("Shot not found.")

        scene = self._db.get(Scene, shot.scene_id)
        if not scene:
            raise AIQANotFoundError("Shot scene not found.")

        episode = self._db.get(Episode, scene.episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise AIQANotFoundError("Shot not found in this series.")

        return series, shot, scene, episode

    def _allowed_ids_for_episode(self, series_id: str, episode_id: str) -> set[str]:
        """Collect all entity IDs the provider may legitimately reference for an episode."""
        allowed: set[str] = {series_id, episode_id}
        episode = self._db.get(Episode, episode_id)
        for scene in episode.scenes:
            allowed.add(scene.id)
            for shot in scene.shots:
                allowed.add(shot.id)
                if shot.specification:
                    allowed.add(shot.specification.id)

        universe = UniverseContextService(self._db).get_context(self._db.get(Series, series_id))
        allowed.update(str(c.id) for c in universe.characters)
        allowed.update(str(c.id) for c in universe.locations)
        allowed.update(str(c.id) for c in universe.objects)
        return allowed

    def _allowed_ids_for_shot(
        self,
        series_id: str,
        shot: Shot,
        scene: Scene,
        episode: Episode,
    ) -> set[str]:
        """Collect all entity IDs the provider may legitimately reference for a shot."""
        allowed: set[str] = {series_id, episode.id, scene.id, shot.id}
        if shot.specification:
            allowed.add(shot.specification.id)

        universe = UniverseContextService(self._db).get_context(self._db.get(Series, series_id))
        allowed.update(str(c.id) for c in universe.characters)
        allowed.update(str(c.id) for c in universe.locations)
        allowed.update(str(c.id) for c in universe.objects)
        return allowed

    def _build_episode_context(self, series: Series, episode: Episode) -> Any:
        universe = UniverseContextService(self._db).get_context(series)
        return AIQAContext(
            series={
                "id": str(series.id),
                "name": series.name,
                "genre": series.genre,
                "language": series.language,
                "target_audience": series.target_audience,
            },
            episode={
                "id": str(episode.id),
                "title": episode.title,
                "description": episode.description,
                "episode_number": episode.episode_number,
                "status": episode.status,
            },
            canonical_characters=[
                {"id": str(c.id), "name": c.name, "description": c.description}
                for c in universe.characters
            ],
            canonical_locations=[
                {"id": str(c.id), "name": c.name, "description": c.description}
                for c in universe.locations
            ],
            canonical_objects=[
                {"id": str(c.id), "name": c.name, "description": c.description}
                for c in universe.objects
            ],
        )

    def _build_shot_context(
        self, series: Series, episode: Episode, scene: Scene, shot: Shot
    ) -> Any:
        context = self._build_episode_context(series, episode)
        context.scene = {
            "id": str(scene.id),
            "scene_number": scene.scene_number,
            "title": scene.title,
            "description": scene.description,
            "location_id": scene.location_id,
        }
        context.shot = {
            "id": str(shot.id),
            "shot_number": shot.shot_number,
            "description": shot.description,
            "action": shot.action,
            "dialogue": shot.dialogue,
            "narration": shot.narration,
            "camera": shot.camera,
            "duration_seconds": shot.duration_seconds,
        }
        if shot.specification:
            context.shot["specification"] = {
                "aspect_ratio": shot.specification.aspect_ratio,
                "duration_seconds": shot.specification.duration_seconds,
                "character_refs": shot.specification.character_refs,
                "location_refs": shot.specification.location_refs,
                "object_refs": shot.specification.object_refs,
            }

        assets = self._db.query(Asset).filter_by(series_id=series.id, shot_id=shot.id).all()
        context.asset_refs = [
            MediaReference(
                asset_id=UUID(a.id),
                asset_type=a.asset_type,
                storage_backend=a.storage_backend or "default",
                storage_key=a.storage_key or "",
                description=a.description,
            )
            for a in assets
        ]
        return context

    def _invoke_provider(self, request: AIQARequest) -> AIQAResult:
        try:
            return self._provider.evaluate(request)
        except AIQAProviderError:
            raise
        except Exception as exc:
            raise AIQAProviderError(f"AI QA provider failed: {exc}") from exc

    def _validate_result(self, result: AIQAResult, allowed_ids: set[str]) -> None:
        if not isinstance(result.findings, list):
            raise AIQAValidationError("Provider result findings must be a list.")

        for finding in result.findings:
            if finding.category not in self._VALID_CATEGORIES:
                raise AIQAValidationError(f"Invalid finding category: {finding.category}")
            if str(finding.entity_id) not in allowed_ids:
                raise AIQAValidationError(
                    "AI finding references an entity outside the requested series scope."
                )
            for related_id in finding.related_entity_ids:
                if str(related_id) not in allowed_ids:
                    raise AIQAValidationError(
                        "AI finding references a related entity outside the requested series scope."
                    )

    def _sort(self, findings: list[AIQAFinding]) -> list[AIQAFinding]:
        return sorted(
            findings,
            key=lambda f: (
                self._SEVERITY_ORDER[f.severity],
                f.rule_id,
                f.category,
                f.entity_type,
                str(f.entity_id),
            ),
        )
