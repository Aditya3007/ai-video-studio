"""P9-T04 QA issue resolution and regeneration loop service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.media_generation.image.factory import ImageGenerationProviderFactory
from app.media_generation.image.job_service import ImageGenerationJobService
from app.media_generation.video.job_service import VideoGenerationJobService
from app.models import Asset, Episode, Narration, QAIssue, QAResolutionAction, Series, Shot
from app.models.enums import (
    AuditEventType,
    AuditStatus,
    QAIssueSource,
    QAIssueStatus,
    ResolutionActionStatus,
    ResolutionActionType,
)
from app.schemas.ai_qa import AIQAFinding
from app.schemas.continuity import ContinuityFinding
from app.services.audit_service import AuditService
from app.services.continuity_service import ContinuityService
from app.services.narration_generation_service import NarrationGenerationService


class IssueResolutionError(Exception):
    """Raised when issue resolution state is invalid or an operation cannot proceed."""


class IssueNotFoundError(IssueResolutionError):
    """Raised when a QA issue cannot be found or accessed."""


class ActionNotFoundError(IssueResolutionError):
    """Raised when a resolution action cannot be found or accessed."""


class IssueResolutionService:
    """Structured QA issue → resolution action → regeneration → re-QA lifecycle."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditService(db)
        self._continuity = ContinuityService(db)

    # ------------------------------------------------------------------
    # Issue creation and retrieval
    # ------------------------------------------------------------------

    def create_issue_from_finding(
        self,
        series_id: str,
        episode_id: str,
        finding: ContinuityFinding | AIQAFinding,
        *,
        source: QAIssueSource | str = QAIssueSource.CONTINUITY,
        scene_id: str | None = None,
        shot_id: str | None = None,
        asset_id: str | None = None,
        max_attempts: int = 3,
    ) -> QAIssue:
        """Create a structured QAIssue from a continuity or AI QA finding."""
        self._assert_series_episode_ownership(series_id, episode_id)

        entity_id = str(finding.entity_id) if finding.entity_id else None
        rule_id = getattr(finding, "rule_id", None)
        category = finding.category

        existing = (
            self._db.query(QAIssue)
            .filter_by(
                series_id=series_id,
                episode_id=episode_id,
                shot_id=shot_id,
                rule_id=rule_id,
                category=category,
                entity_id=entity_id,
            )
            .filter(
                QAIssue.status.notin_(
                    [QAIssueStatus.RESOLVED.value, QAIssueStatus.MANUALLY_RESOLVED.value]
                )
            )
            .first()
        )
        if existing:
            return existing

        issue = QAIssue(
            series_id=series_id,
            episode_id=episode_id,
            scene_id=scene_id,
            shot_id=shot_id,
            asset_id=asset_id,
            category=category,
            severity=str(finding.severity),
            rule_id=rule_id,
            message=finding.message,
            entity_type=finding.entity_type,
            entity_id=entity_id,
            source=str(source),
            status=QAIssueStatus.OPEN.value,
            max_attempts=max_attempts,
            attempt_count=0,
            qa_finding_metadata=(
                finding.model_dump(mode="json") if hasattr(finding, "model_dump") else dict(finding)
            ),
        )
        self._db.add(issue)
        self._db.flush()
        self._audit.record(
            series_id=series_id,
            event_type=AuditEventType.QA_ISSUE_CREATED,
            episode_id=episode_id,
            scene_id=scene_id,
            shot_id=shot_id,
            asset_id=asset_id,
            status=AuditStatus.SUCCESS,
            metadata={
                "issue_id": issue.id,
                "category": category,
                "severity": issue.severity,
                "source": issue.source,
                "rule_id": rule_id,
            },
        )
        return issue

    def get_issue(self, series_id: str, issue_id: str) -> QAIssue:
        issue = self._db.get(QAIssue, issue_id)
        if not issue or str(issue.series_id) != series_id:
            raise IssueNotFoundError("Issue not found.")
        return issue

    def list_issues(
        self,
        series_id: str,
        *,
        episode_id: str | None = None,
        shot_id: str | None = None,
        status: str | None = None,
    ) -> list[QAIssue]:
        query = self._db.query(QAIssue).filter_by(series_id=series_id)
        if episode_id:
            query = query.filter_by(episode_id=episode_id)
        if shot_id:
            query = query.filter_by(shot_id=shot_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(QAIssue.created_at.desc()).all()

    # ------------------------------------------------------------------
    # Resolution actions
    # ------------------------------------------------------------------

    def request_resolution(
        self,
        series_id: str,
        issue_id: str,
        action_type: ResolutionActionType | str,
        *,
        action_metadata: dict[str, Any] | None = None,
    ) -> QAResolutionAction:
        issue = self.get_issue(series_id, issue_id)
        action_type = str(action_type)

        if issue.status in {QAIssueStatus.RESOLVED.value, QAIssueStatus.MANUALLY_RESOLVED.value}:
            raise IssueResolutionError("Issue is already resolved.")
        if issue.attempt_count >= issue.max_attempts:
            raise IssueResolutionError("Maximum regeneration attempts reached.")

        attempt_number = issue.attempt_count + 1
        action = QAResolutionAction(
            issue_id=issue.id,
            series_id=series_id,
            action_type=action_type,
            attempt_number=attempt_number,
            status=ResolutionActionStatus.PENDING.value,
            action_metadata=action_metadata or {},
        )
        self._db.add(action)
        issue.status = QAIssueStatus.QUEUED.value
        issue.resolution_type = action_type
        self._db.flush()
        self._audit.record(
            series_id=series_id,
            event_type=AuditEventType.REGENERATION_REQUESTED,
            episode_id=issue.episode_id,
            scene_id=issue.scene_id,
            shot_id=issue.shot_id,
            asset_id=issue.asset_id,
            status=AuditStatus.PENDING,
            attempt=attempt_number,
            metadata={
                "issue_id": issue.id,
                "action_id": action.id,
                "action_type": action_type,
                "max_attempts": issue.max_attempts,
            },
        )
        return action

    def get_action(self, series_id: str, action_id: str) -> QAResolutionAction:
        action = self._db.get(QAResolutionAction, action_id)
        if not action or str(action.series_id) != series_id:
            raise ActionNotFoundError("Resolution action not found.")
        return action

    def list_actions(self, series_id: str, issue_id: str) -> list[QAResolutionAction]:
        issue = self.get_issue(series_id, issue_id)
        return (
            self._db.query(QAResolutionAction)
            .filter_by(issue_id=issue.id)
            .order_by(QAResolutionAction.attempt_number.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_action(self, series_id: str, action_id: str) -> QAResolutionAction:
        action = self.get_action(series_id, action_id)
        issue = self.get_issue(series_id, action.issue_id)

        if action.status != ResolutionActionStatus.PENDING.value:
            raise IssueResolutionError("Action is not pending.")

        action.status = ResolutionActionStatus.IN_PROGRESS.value
        issue.status = QAIssueStatus.REGENERATING.value
        issue.attempt_count = action.attempt_number
        self._db.flush()

        self._audit.record(
            series_id=series_id,
            event_type=AuditEventType.REGENERATION_STARTED,
            episode_id=issue.episode_id,
            scene_id=issue.scene_id,
            shot_id=issue.shot_id,
            asset_id=issue.asset_id,
            status=AuditStatus.PENDING,
            attempt=action.attempt_number,
            metadata={
                "issue_id": issue.id,
                "action_id": action.id,
                "action_type": action.action_type,
            },
        )

        try:
            generated_asset_id = self._dispatch_regeneration(issue, action)
            action.status = ResolutionActionStatus.SUCCEEDED.value
            action.generated_asset_id = generated_asset_id
            self._db.flush()
            self._audit.record(
                series_id=series_id,
                event_type=AuditEventType.REGENERATION_SUCCEEDED,
                episode_id=issue.episode_id,
                scene_id=issue.scene_id,
                shot_id=issue.shot_id,
                asset_id=generated_asset_id or issue.asset_id,
                status=AuditStatus.SUCCESS,
                attempt=action.attempt_number,
                metadata={
                    "issue_id": issue.id,
                    "action_id": action.id,
                    "generated_asset_id": generated_asset_id,
                },
            )
            if generated_asset_id:
                issue.regenerated_asset_id = generated_asset_id
        except Exception as exc:
            action.status = ResolutionActionStatus.FAILED.value
            action.error_message = str(exc)
            issue.status = QAIssueStatus.OPEN.value
            self._db.flush()
            self._audit.record(
                series_id=series_id,
                event_type=AuditEventType.REGENERATION_FAILED,
                episode_id=issue.episode_id,
                scene_id=issue.scene_id,
                shot_id=issue.shot_id,
                asset_id=issue.asset_id,
                status=AuditStatus.FAILED,
                attempt=action.attempt_number,
                metadata={
                    "issue_id": issue.id,
                    "action_id": action.id,
                    "action_type": action.action_type,
                },
                error_message=str(exc),
            )
            return action

        # Re-run relevant QA after a successful regeneration.
        issue.status = QAIssueStatus.RECHECKING.value
        self._db.flush()
        self._recheck_issue(issue, action)
        return action

    def _dispatch_regeneration(self, issue: QAIssue, action: QAResolutionAction) -> str | None:
        if action.action_type == ResolutionActionType.REGENERATE_IMAGE.value:
            return self._regenerate_image(issue, action)
        if action.action_type == ResolutionActionType.REGENERATE_VIDEO.value:
            return self._regenerate_video(issue, action)
        if action.action_type == ResolutionActionType.REGENERATE_TTS.value:
            return self._regenerate_tts(issue, action)
        if action.action_type in {
            ResolutionActionType.RE_RUN_QA.value,
            ResolutionActionType.MANUAL_REVIEW.value,
        }:
            return None
        raise IssueResolutionError(f"Unsupported resolution action: {action.action_type}")

    def _regenerate_image(self, issue: QAIssue, action: QAResolutionAction) -> str | None:
        if not issue.shot_id:
            raise IssueResolutionError("Image regeneration requires a shot_id.")
        provider = ImageGenerationProviderFactory.create()
        job_service = ImageGenerationJobService(self._db, provider)
        job = job_service.create_and_run(issue.series_id, issue.shot_id)
        action.generated_job_id = str(job.id)
        if job.status != "SUCCEEDED":
            raise IssueResolutionError(f"Image generation failed: {job.error_message}")
        return str(job.result_asset_ids[0]) if job.result_asset_ids else None

    def _regenerate_video(self, issue: QAIssue, action: QAResolutionAction) -> str | None:
        if not issue.shot_id:
            raise IssueResolutionError("Video regeneration requires a shot_id.")
        storyboard_asset_id = self._resolve_storyboard_asset_id(issue, action)
        if not storyboard_asset_id:
            raise IssueResolutionError("Video regeneration requires a storyboard asset_id.")
        job_service = VideoGenerationJobService(self._db)
        job = job_service.create_and_run(
            issue.series_id,
            issue.shot_id,
            storyboard_asset_id,
        )
        action.generated_job_id = str(job.id)
        if job.status != "SUCCEEDED":
            raise IssueResolutionError(f"Video generation failed: {job.error_message}")
        asset_id = (job.result_metadata or {}).get("asset_id") if job.result_metadata else None
        return str(asset_id) if asset_id else None

    def _regenerate_tts(self, issue: QAIssue, action: QAResolutionAction) -> str | None:
        narration_id = self._resolve_narration_id(issue, action)
        if not narration_id:
            raise IssueResolutionError("TTS regeneration requires a narration_id.")
        narration = self._db.get(Narration, narration_id)
        if not narration:
            raise IssueResolutionError("Narration not found.")
        narration.status = "PENDING"
        narration.generated_asset_id = None
        self._db.flush()
        service = NarrationGenerationService(self._db)
        narration = service.generate(issue.series_id, narration_id)
        return str(narration.generated_asset_id) if narration.generated_asset_id else None

    def _resolve_storyboard_asset_id(
        self, issue: QAIssue, action: QAResolutionAction
    ) -> str | None:
        metadata = action.action_metadata or {}
        storyboard_asset_id = metadata.get("storyboard_asset_id")
        if storyboard_asset_id:
            return str(storyboard_asset_id)
        if issue.asset_id:
            asset = self._db.get(Asset, issue.asset_id)
            if asset and asset.asset_type in {"STORYBOARD", "KEYFRAME"}:
                return issue.asset_id
        shot = self._db.get(Shot, issue.shot_id) if issue.shot_id else None
        if shot:
            latest = (
                self._db.query(Asset)
                .filter_by(shot_id=shot.id)
                .filter(Asset.asset_type.in_(["STORYBOARD", "KEYFRAME"]))
                .order_by(Asset.created_at.desc())
                .first()
            )
            if latest:
                return latest.id
        return None

    def _resolve_narration_id(self, issue: QAIssue, action: QAResolutionAction) -> str | None:
        metadata = action.action_metadata or {}
        narration_id = metadata.get("narration_id")
        if narration_id:
            return str(narration_id)
        shot = self._db.get(Shot, issue.shot_id) if issue.shot_id else None
        if shot:
            from app.models import Narration

            narration = (
                self._db.query(Narration)
                .filter_by(shot_id=shot.id)
                .order_by(Narration.created_at.desc())
                .first()
            )
            if narration:
                return narration.id
        return None

    # ------------------------------------------------------------------
    # Re-QA
    # ------------------------------------------------------------------

    def _recheck_issue(self, issue: QAIssue, action: QAResolutionAction) -> None:
        self._audit.record(
            series_id=issue.series_id,
            event_type=AuditEventType.QA_RECHECK_STARTED,
            episode_id=issue.episode_id,
            scene_id=issue.scene_id,
            shot_id=issue.shot_id,
            asset_id=issue.regenerated_asset_id or issue.asset_id,
            status=AuditStatus.PENDING,
            attempt=action.attempt_number,
            metadata={
                "issue_id": issue.id,
                "action_id": action.id,
                "source": issue.source,
            },
        )

        resolved = False
        if issue.shot_id:
            findings = self._continuity.check_shot(issue.series_id, issue.shot_id)
            resolved = not self._finding_matches_issue(findings, issue)
        elif issue.episode_id:
            findings = self._continuity.check_episode(issue.series_id, issue.episode_id)
            resolved = not self._finding_matches_issue(findings, issue)
        else:
            # No reproducible scope; leave issue open for manual review.
            resolved = False

        if resolved:
            issue.status = QAIssueStatus.RESOLVED.value
            self._audit.record(
                series_id=issue.series_id,
                event_type=AuditEventType.QA_ISSUE_RESOLVED,
                episode_id=issue.episode_id,
                scene_id=issue.scene_id,
                shot_id=issue.shot_id,
                asset_id=issue.regenerated_asset_id or issue.asset_id,
                status=AuditStatus.SUCCESS,
                attempt=action.attempt_number,
                metadata={
                    "issue_id": issue.id,
                    "action_id": action.id,
                    "source": issue.source,
                },
            )
        else:
            if action.attempt_number >= issue.max_attempts:
                issue.status = QAIssueStatus.MAX_ATTEMPTS_REACHED.value
                self._audit.record(
                    series_id=issue.series_id,
                    event_type=AuditEventType.QA_MAX_ATTEMPTS_REACHED,
                    episode_id=issue.episode_id,
                    scene_id=issue.scene_id,
                    shot_id=issue.shot_id,
                    asset_id=issue.regenerated_asset_id or issue.asset_id,
                    status=AuditStatus.FAILED,
                    attempt=action.attempt_number,
                    metadata={
                        "issue_id": issue.id,
                        "action_id": action.id,
                    },
                )
            else:
                issue.status = QAIssueStatus.OPEN.value
                self._audit.record(
                    series_id=issue.series_id,
                    event_type=AuditEventType.QA_ISSUE_REOPENED,
                    episode_id=issue.episode_id,
                    scene_id=issue.scene_id,
                    shot_id=issue.shot_id,
                    asset_id=issue.regenerated_asset_id or issue.asset_id,
                    status=AuditStatus.SUCCESS,
                    attempt=action.attempt_number,
                    metadata={
                        "issue_id": issue.id,
                        "action_id": action.id,
                    },
                )

    def _finding_matches_issue(
        self,
        findings: list[ContinuityFinding | AIQAFinding],
        issue: QAIssue,
    ) -> bool:
        for finding in findings:
            entity_id = str(finding.entity_id) if finding.entity_id else None
            rule_id = getattr(finding, "rule_id", None)
            if (
                finding.category == issue.category
                and rule_id == issue.rule_id
                and entity_id == issue.entity_id
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # Manual resolution
    # ------------------------------------------------------------------

    def resolve_manually(
        self,
        series_id: str,
        issue_id: str,
        *,
        resolution_note: str | None = None,
    ) -> QAIssue:
        issue = self.get_issue(series_id, issue_id)
        if issue.status == QAIssueStatus.MANUALLY_RESOLVED.value:
            raise IssueResolutionError("Issue is already manually resolved.")
        previous = issue.status
        issue.status = QAIssueStatus.MANUALLY_RESOLVED.value
        self._db.flush()
        self._audit.record(
            series_id=series_id,
            event_type=AuditEventType.QA_MANUALLY_RESOLVED,
            episode_id=issue.episode_id,
            scene_id=issue.scene_id,
            shot_id=issue.shot_id,
            asset_id=issue.asset_id,
            status=AuditStatus.SUCCESS,
            metadata={
                "issue_id": issue.id,
                "previous_status": previous,
                "resolution_note": resolution_note,
            },
        )
        return issue

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _assert_series_episode_ownership(self, series_id: str, episode_id: str) -> None:
        series = self._db.get(Series, series_id)
        if not series:
            raise IssueNotFoundError("Series not found.")
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise IssueNotFoundError("Episode not found.")
