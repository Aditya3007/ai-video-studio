"""QA workflow orchestration service."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Episode, Series, Shot
from app.models.enums import AIQAMode, ContinuitySeverity, QAWorkflowStatus
from app.schemas.ai_qa import AIQAFinding
from app.schemas.qa_workflow import QAWorkflowCounts, QAWorkflowResponse
from app.services.ai_qa_service import AIQAProvider, AIQAProviderError, AIQAService
from app.services.continuity_service import ContinuityService


class QAWorkflowNotFoundError(Exception):
    """Raised when the requested QA workflow scope cannot be resolved."""


class QAWorkflowService:
    """Orchestrates P9-T01 deterministic continuity and P9-T02 AI QA."""

    _SEVERITY_ORDER = {
        ContinuitySeverity.ERROR: 0,
        ContinuitySeverity.WARNING: 1,
        ContinuitySeverity.INFO: 2,
    }

    def __init__(
        self,
        db: Session,
        ai_provider: AIQAProvider | None = None,
    ) -> None:
        self._db = db
        self._continuity = ContinuityService(db)
        self._ai_qa = AIQAService(db, provider=ai_provider)

    def evaluate_episode(
        self,
        series_id: str,
        episode_id: str,
        ai_modes: list[AIQAMode],
    ) -> QAWorkflowResponse:
        """Run the full QA workflow for an episode."""
        series, episode = self._load_series_and_episode(series_id, episode_id)
        return self._evaluate(
            series,
            episode,
            scope_type="episode",
            scope_id=episode.id,
            ai_modes=ai_modes,
            evaluator=lambda: self._continuity.check_episode(series_id, episode_id),
            ai_evaluators=[
                (mode, lambda m=mode: self._ai_qa.evaluate_episode(series_id, episode_id, m))
                for mode in ai_modes
            ],
        )

    def evaluate_shot(
        self,
        series_id: str,
        shot_id: str,
        ai_modes: list[AIQAMode],
    ) -> QAWorkflowResponse:
        """Run the full QA workflow for a shot."""
        series, shot = self._load_series_and_shot(series_id, shot_id)
        return self._evaluate(
            series,
            shot,
            scope_type="shot",
            scope_id=shot.id,
            ai_modes=ai_modes,
            evaluator=lambda: self._continuity.check_shot(series_id, shot_id),
            ai_evaluators=[
                (mode, lambda m=mode: self._ai_qa.evaluate_shot(series_id, shot_id, m))
                for mode in ai_modes
            ],
        )

    def _load_series_and_episode(self, series_id: str, episode_id: str) -> tuple[Series, Episode]:
        series = self._db.get(Series, series_id)
        if not series:
            raise QAWorkflowNotFoundError("Series not found.")

        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise QAWorkflowNotFoundError("Episode not found.")

        return series, episode

    def _load_series_and_shot(self, series_id: str, shot_id: str) -> tuple[Series, Shot]:
        series = self._db.get(Series, series_id)
        if not series:
            raise QAWorkflowNotFoundError("Series not found.")

        shot = self._db.get(Shot, shot_id)
        if not shot:
            raise QAWorkflowNotFoundError("Shot not found.")

        from app.models import Scene

        scene = self._db.get(Scene, shot.scene_id)
        if not scene:
            raise QAWorkflowNotFoundError("Shot scene not found.")

        episode = self._db.get(Episode, scene.episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise QAWorkflowNotFoundError("Shot not found in this series.")

        return series, shot

    def _evaluate(
        self,
        series: Series,
        _scope_entity: Any,
        scope_type: str,
        scope_id: str,
        ai_modes: list[AIQAMode],
        evaluator: Any,
        ai_evaluators: list[tuple[AIQAMode, Any]],
    ) -> QAWorkflowResponse:
        findings: list[AIQAFinding] = []
        ai_failed = False
        ai_error: str | None = None

        continuity_findings = evaluator()
        for finding in continuity_findings:
            findings.append(AIQAFinding(**finding.model_dump(), source="deterministic"))

        for mode, ai_evaluator in ai_evaluators:
            try:
                ai_response = ai_evaluator()
                for finding in ai_response.findings:
                    findings.append(finding)
            except AIQAProviderError as exc:
                ai_failed = True
                ai_error = f"{mode.value} QA failed: {exc}"

        findings = self._deduplicate(findings)
        findings = self._sort(findings)

        counts = self._counts(findings)
        status = self._status(findings, ai_failed)

        return QAWorkflowResponse(
            series_id=UUID(series.id),
            scope_type=scope_type,
            scope_id=UUID(scope_id),
            status=status,
            findings=findings,
            counts=counts,
            ai_failed=ai_failed,
            ai_error=ai_error,
            metadata={"ai_modes": [m.value for m in ai_modes]},
        )

    def _deduplicate(self, findings: list[AIQAFinding]) -> list[AIQAFinding]:
        seen: set[tuple[str, str, str, str, str]] = set()
        deduped: list[AIQAFinding] = []
        for finding in findings:
            key = (
                finding.source,
                finding.rule_id,
                finding.category,
                finding.entity_type,
                str(finding.entity_id),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    def _sort(self, findings: list[AIQAFinding]) -> list[AIQAFinding]:
        return sorted(
            findings,
            key=lambda f: (
                self._SEVERITY_ORDER[f.severity],
                f.source,
                f.rule_id,
                f.category,
                f.entity_type,
                str(f.entity_id),
            ),
        )

    def _counts(self, findings: list[AIQAFinding]) -> QAWorkflowCounts:
        return QAWorkflowCounts(
            total=len(findings),
            error=sum(1 for f in findings if f.severity == ContinuitySeverity.ERROR),
            warning=sum(1 for f in findings if f.severity == ContinuitySeverity.WARNING),
            info=sum(1 for f in findings if f.severity == ContinuitySeverity.INFO),
            deterministic=sum(1 for f in findings if f.source == "deterministic"),
            ai=sum(1 for f in findings if f.source == "ai"),
        )

    def _status(self, findings: list[AIQAFinding], ai_failed: bool) -> QAWorkflowStatus:
        has_error = any(f.severity == ContinuitySeverity.ERROR for f in findings)
        has_warning = any(f.severity == ContinuitySeverity.WARNING for f in findings)

        if has_error:
            return QAWorkflowStatus.FAIL
        if ai_failed:
            return QAWorkflowStatus.DEGRADED
        if has_warning:
            return QAWorkflowStatus.WARN
        return QAWorkflowStatus.PASS
