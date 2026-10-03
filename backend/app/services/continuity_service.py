"""Deterministic, provider-neutral continuity rules engine."""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Character, Episode, Location, Scene, Series, Shot, StoryObject
from app.models.enums import ContinuitySeverity
from app.schemas import ShotSpecificationResponse
from app.schemas.continuity import ContinuityFinding
from app.services.universe import UniverseContextService


class ContinuityNotFoundError(Exception):
    """Raised when the requested continuity scope cannot be resolved."""


class ContinuityService:
    """Evaluates deterministic continuity rules for canonical production data."""

    _SEVERITY_ORDER = {
        ContinuitySeverity.ERROR: 0,
        ContinuitySeverity.WARNING: 1,
        ContinuitySeverity.INFO: 2,
    }

    def __init__(self, db: Session) -> None:
        self._db = db

    def check_episode(self, series_id: str, episode_id: str) -> list[ContinuityFinding]:
        """Evaluate all deterministic continuity rules for an Episode."""
        series, episode = self._load_series_and_episode(series_id, episode_id)
        canonical = self._load_canonical_lookup(series)
        findings: list[ContinuityFinding] = []

        for scene in episode.scenes:
            self._check_scene_location(scene, canonical, findings)
            for shot in scene.shots:
                self._check_shot_scene(shot, scene, canonical, findings)
                if shot.specification:
                    self._check_shot_specification(shot, canonical, findings)

        return self._sort(findings)

    def check_shot(self, series_id: str, shot_id: str) -> list[ContinuityFinding]:
        """Evaluate deterministic continuity rules for a single Shot."""
        series = self._db.get(Series, series_id)
        if not series:
            raise ContinuityNotFoundError("Series not found.")

        shot = self._db.get(Shot, shot_id)
        if not shot:
            raise ContinuityNotFoundError("Shot not found.")

        scene = self._db.get(Scene, shot.scene_id)
        if not scene:
            raise ContinuityNotFoundError("Shot scene not found.")

        episode = self._db.get(Episode, scene.episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise ContinuityNotFoundError("Shot not found in this series.")

        canonical = self._load_canonical_lookup(series)
        findings: list[ContinuityFinding] = []
        self._check_shot_scene(shot, scene, canonical, findings)
        if shot.specification:
            self._check_shot_specification(shot, canonical, findings)
        return self._sort(findings)

    def _load_series_and_episode(self, series_id: str, episode_id: str) -> tuple[Series, Episode]:
        """Assert series/episode existence and ownership."""
        series = self._db.get(Series, series_id)
        if not series:
            raise ContinuityNotFoundError("Series not found.")

        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise ContinuityNotFoundError("Episode not found.")

        return series, episode

    def _load_canonical_lookup(self, series: Series) -> dict[str, set[str]]:
        """Load canonical entity IDs for the series using UniverseContextService."""
        context = UniverseContextService(self._db).get_context(series)
        return {
            "characters": {str(c.id) for c in context.characters},
            "locations": {str(c.id) for c in context.locations},
            "objects": {str(c.id) for c in context.objects},
        }

    def _check_scene_location(
        self,
        scene: Scene,
        canonical: dict[str, set[str]],
        findings: list[ContinuityFinding],
    ) -> None:
        """Check that a Scene's Location reference is valid and in-series."""
        if not scene.location_id:
            return

        if scene.location_id in canonical["locations"]:
            return

        location = self._db.get(Location, scene.location_id)
        if location is None:
            findings.append(
                self._finding(
                    ContinuitySeverity.ERROR,
                    "missing-scene-location",
                    "LOCATION",
                    scene,
                    f"Scene references missing location {scene.location_id}.",
                    actual=scene.location_id,
                )
            )
        else:
            findings.append(
                self._finding(
                    ContinuitySeverity.ERROR,
                    "cross-series-scene-location",
                    "LOCATION",
                    scene,
                    f"Scene references location from another series ({scene.location_id}).",
                    actual=scene.location_id,
                    related_ids=[UUID(location.series_id)],
                )
            )

    def _check_shot_scene(
        self,
        shot: Shot,
        scene: Scene,
        canonical: dict[str, set[str]],
        findings: list[ContinuityFinding],
    ) -> None:
        """Check deterministic shot/scene hierarchy consistency."""
        if str(shot.scene_id) != str(scene.id):
            findings.append(
                self._finding(
                    ContinuitySeverity.ERROR,
                    "shot-scene-mismatch",
                    "SHOT",
                    shot,
                    f"Shot belongs to scene {shot.scene_id} "
                    f"but was evaluated under scene {scene.id}.",
                    expected=str(scene.id),
                    actual=str(shot.scene_id),
                )
            )

    def _check_shot_specification(
        self,
        shot: Shot,
        canonical: dict[str, set[str]],
        findings: list[ContinuityFinding],
    ) -> None:
        """Check a Shot's canonical refs and reuse existing ShotSpecification validators."""
        spec = shot.specification
        if spec is None:
            return

        try:
            ShotSpecificationResponse.model_validate(spec)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", ()))
                findings.append(
                    self._finding(
                        ContinuitySeverity.ERROR,
                        "invalid-shot-specification",
                        "PRODUCTION_CONSTRAINT",
                        spec,
                        f"Shot specification field {loc} is invalid: {err['msg']}",
                        entity_type="SHOT_SPECIFICATION",
                        metadata={"field": loc, "error": err["msg"]},
                    )
                )

        for ref_id in spec.character_refs or []:
            self._check_canonical_ref(
                ref_id,
                canonical["characters"],
                Character,
                "CHARACTER",
                shot,
                "shot-spec-missing-character",
                "shot-spec-cross-series-character",
                findings,
            )

        for ref_id in spec.location_refs or []:
            self._check_canonical_ref(
                ref_id,
                canonical["locations"],
                Location,
                "LOCATION",
                shot,
                "shot-spec-missing-location",
                "shot-spec-cross-series-location",
                findings,
            )

        for ref_id in spec.object_refs or []:
            self._check_canonical_ref(
                ref_id,
                canonical["objects"],
                StoryObject,
                "STORY_OBJECT",
                shot,
                "shot-spec-missing-object",
                "shot-spec-cross-series-object",
                findings,
            )

    def _check_canonical_ref(
        self,
        ref_id: str,
        valid_ids: set[str],
        model,
        category: str,
        shot: Shot,
        missing_rule: str,
        cross_series_rule: str,
        findings: list[ContinuityFinding],
    ) -> None:
        """Check a single canonical reference for existence and series ownership."""
        if ref_id in valid_ids:
            return

        entity = self._db.get(model, ref_id)
        if entity is None:
            findings.append(
                self._finding(
                    ContinuitySeverity.ERROR,
                    missing_rule,
                    category,
                    shot,
                    f"Shot references missing {category.lower()} {ref_id}.",
                    actual=ref_id,
                )
            )
        else:
            findings.append(
                self._finding(
                    ContinuitySeverity.ERROR,
                    cross_series_rule,
                    category,
                    shot,
                    f"Shot references {category.lower()} from another series ({ref_id}).",
                    actual=ref_id,
                    related_ids=[UUID(entity.series_id)],
                )
            )

    def _finding(
        self,
        severity: ContinuitySeverity,
        rule_id: str,
        category: str,
        entity,
        message: str,
        entity_type: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
        related_ids: list[UUID] | None = None,
        metadata: dict | None = None,
    ) -> ContinuityFinding:
        """Build a deterministic ContinuityFinding."""
        return ContinuityFinding(
            severity=severity,
            rule_id=rule_id,
            category=category,
            message=message,
            entity_type=entity_type or entity.__class__.__name__.upper(),
            entity_id=UUID(entity.id),
            related_entity_ids=related_ids or [],
            expected=expected,
            actual=actual,
            metadata=metadata,
        )

    def _sort(self, findings: list[ContinuityFinding]) -> list[ContinuityFinding]:
        """Sort findings deterministically by severity, rule, category, entity."""
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
