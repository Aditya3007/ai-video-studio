"""End-to-end publishing workflow and scheduling service."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from app.models import Asset, Episode, PublishingJob, Series, VideoAssembly
from app.models.enums import (
    AssemblyStatus,
    AssetStatus,
    AssetType,
    AuditEventType,
    AuditStatus,
    PublishingStatus,
)
from app.orchestration import ImmediateWorker, JobTask, JobType, Worker
from app.provider_registry import get_default_registry
from app.publishing import PublishingRequest
from app.services.audit_service import AuditService
from app.services.publishing_service import PublishingService, PublishingServiceError
from app.services.shorts_metadata_service import ShortsMetadata, ShortsMetadataService
from app.services.thumbnail_service import ThumbnailError, ThumbnailService
from app.storage import StorageBackend


class PublishingWorkflowError(Exception):
    """Raised when a publishing workflow cannot proceed."""


class PublishingWorkflowResult(BaseModel):
    """Result of a publishing workflow operation."""

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: str
    external_publication_id: str | None
    external_url: str | None
    attempts: int
    error_message: str | None


class PublishingWorkflowService:
    """Coordinates Series/Episode/Asset validation, metadata, and publishing."""

    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000

    @staticmethod
    def _now() -> datetime:
        """Return a naive UTC datetime for SQLite-compatible comparisons."""
        return datetime.now(UTC).replace(tzinfo=None)

    def __init__(
        self,
        db: Session,
        storage: StorageBackend,
        *,
        publishing_service: PublishingService | None = None,
        metadata_service: ShortsMetadataService | None = None,
        thumbnail_service: ThumbnailService | None = None,
        audit_service: AuditService | None = None,
        db_factory: Any | None = None,
        worker: Any | None = None,
    ) -> None:
        self._db = db
        self._storage = storage
        self._publishing = publishing_service or PublishingService(
            db,
            storage,
            registry=get_default_registry(),
            provider_id="fake",
        )
        self._metadata = metadata_service or ShortsMetadataService(db)
        self._thumbnail = thumbnail_service or ThumbnailService(db, storage)
        self._audit = audit_service or AuditService(db)
        self._db_factory = db_factory or sessionmaker(
            autocommit=False, autoflush=False, bind=db.get_bind()
        )
        if worker is None:
            self._worker: Worker = ImmediateWorker(self._handle_task)
        else:
            self._worker = worker

    @staticmethod
    def _sanitize_error(value: str | None) -> str | None:
        if not value:
            return value
        patterns = [
            (r"(Bearer\s+)[A-Za-z0-9_\-]+", r"\1***REDACTED***"),
            (r"(?i)(api[_-]?key\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
            (r"(?i)(token\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
            (r"(?i)(password\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
        ]
        for pattern, repl in patterns:
            value = re.sub(pattern, repl, value)
        return value

    def _get_job(self, series_id: str, job_id: str) -> PublishingJob:
        job = self._db.get(PublishingJob, job_id)
        if not job or str(job.series_id) != series_id:
            raise PublishingWorkflowError("Publishing job not found in this Series.")
        return job

    def get(self, series_id: str, job_id: str) -> PublishingJob:
        """Return a publishing job for the given Series and ID."""
        return self._get_job(series_id, job_id)

    def _record(
        self,
        *,
        event_type: AuditEventType,
        series_id: str,
        episode_id: str,
        job_id: str,
        status: AuditStatus,
        metadata: dict | None = None,
        error_message: str | None = None,
        attempt: int | None = None,
    ) -> None:
        event_metadata = metadata or {}
        if attempt is not None:
            event_metadata["attempt"] = attempt
        self._audit.record(
            series_id=series_id,
            event_type=event_type,
            episode_id=episode_id,
            job_id=job_id,
            status=status,
            metadata=event_metadata or None,
            error_message=self._sanitize_error(error_message),
        )

    def _validate_publishability(
        self,
        series: Series,
        episode: Episode,
        asset: Asset,
        thumbnail_asset_id: str | None,
    ) -> None:
        if str(episode.series_id) != series.id:
            raise PublishingWorkflowError("Episode does not belong to the Series.")
        if str(asset.series_id) != series.id:
            raise PublishingWorkflowError("Asset does not belong to the Series.")
        if asset.asset_type != AssetType.VIDEO.value:
            raise PublishingWorkflowError("Asset is not a video.")
        if asset.status != AssetStatus.AVAILABLE.value:
            raise PublishingWorkflowError("Asset is not available.")

        assembly = self._db.query(VideoAssembly).filter_by(episode_id=episode.id).first()
        if not assembly or str(assembly.final_asset_id) != asset.id:
            raise PublishingWorkflowError("Asset is not the final export for this Episode.")
        if assembly.status != AssemblyStatus.RENDERED.value:
            raise PublishingWorkflowError("Episode has not been rendered successfully.")

        if thumbnail_asset_id:
            self._thumbnail.select(series.id, episode.id, thumbnail_asset_id)

    def _build_publishing_request(
        self,
        series_id: str,
        episode_id: str,
        asset_id: str,
        metadata: ShortsMetadata,
    ) -> PublishingRequest:
        return PublishingRequest(
            asset_id=UUID(asset_id),
            series_id=UUID(series_id),
            episode_id=UUID(episode_id),
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            visibility="public",
            category=metadata.category,
            language=metadata.language,
            is_shorts=True,
            call_to_action=metadata.call_to_action,
        )

    def _transition(
        self,
        job: PublishingJob,
        target: PublishingStatus,
    ) -> None:
        allowed = {
            PublishingStatus.READY.value: {
                PublishingStatus.PUBLISHING.value,
                PublishingStatus.SCHEDULED.value,
                PublishingStatus.FAILED.value,
                PublishingStatus.CANCELLED.value,
            },
            PublishingStatus.SCHEDULED.value: {
                PublishingStatus.PUBLISHING.value,
                PublishingStatus.FAILED.value,
                PublishingStatus.CANCELLED.value,
            },
            PublishingStatus.FAILED.value: {
                PublishingStatus.READY.value,
                PublishingStatus.PUBLISHING.value,
            },
            PublishingStatus.PUBLISHING.value: {
                PublishingStatus.PUBLISHED.value,
                PublishingStatus.FAILED.value,
                PublishingStatus.CANCELLED.value,
            },
        }
        if target.value not in allowed.get(job.status, set()):
            raise PublishingWorkflowError(
                f"Invalid state transition from {job.status} to {target.value}"
            )
        job.status = target.value
        self._db.flush()

    def _handle_task(self, task: JobTask) -> None:
        """Worker handler for asynchronous publishing tasks."""
        if task.job_type != JobType.PUBLISHING:
            return
        db = self._db_factory()
        try:
            service = PublishingWorkflowService(
                db,
                self._storage,
                db_factory=self._db_factory,
                worker=self._worker,
            )
            service.execute(str(task.series_id), task.job_id)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def request_publication(
        self,
        series_id: str,
        episode_id: str,
        asset_id: str,
        *,
        thumbnail_asset_id: str | None = None,
        metadata: ShortsMetadata | None = None,
        scheduled_at: datetime | None = None,
        idempotency_key: str | None = None,
        provider_id: str = "fake",
        max_attempts: int = 3,
        correlation_id: str | None = None,
    ) -> PublishingJob:
        """Create a publishing job and enqueue/immediate execution."""
        series = self._db.get(Series, series_id)
        if not series:
            raise PublishingWorkflowError("Series not found.")
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise PublishingWorkflowError("Episode not found in this Series.")
        asset = self._db.get(Asset, asset_id)
        if not asset:
            raise PublishingWorkflowError("Asset not found.")

        if idempotency_key:
            existing = (
                self._db.query(PublishingJob)
                .filter(PublishingJob.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return existing

        scheduled_at_naive = (
            scheduled_at.replace(tzinfo=None)
            if scheduled_at and scheduled_at.tzinfo
            else scheduled_at
        )

        metadata_snapshot: dict | None = None
        if isinstance(metadata, ShortsMetadata):
            metadata_snapshot = metadata.model_dump(mode="json")
        elif isinstance(metadata, dict):
            metadata_snapshot = metadata

        status = (
            PublishingStatus.SCHEDULED.value
            if scheduled_at_naive is not None
            else PublishingStatus.READY.value
        )
        job = PublishingJob(
            series_id=series_id,
            episode_id=episode_id,
            asset_id=asset_id,
            thumbnail_asset_id=thumbnail_asset_id,
            metadata_snapshot=metadata_snapshot,
            provider_id=provider_id,
            status=status,
            scheduled_at=scheduled_at_naive,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
            attempts=0,
            correlation_id=correlation_id,
        )
        self._db.add(job)
        self._db.flush()
        self._record(
            event_type=AuditEventType.PUBLICATION_REQUESTED,
            series_id=series_id,
            episode_id=episode_id,
            job_id=job.id,
            status=AuditStatus.PENDING,
            metadata={"scheduled": bool(scheduled_at)},
        )
        if status == PublishingStatus.SCHEDULED.value:
            self._record(
                event_type=AuditEventType.PUBLICATION_SCHEDULED,
                series_id=series_id,
                episode_id=episode_id,
                job_id=job.id,
                status=AuditStatus.PENDING,
                metadata={"scheduled_at": scheduled_at.isoformat() if scheduled_at else None},
            )
        self._db.commit()

        if status == PublishingStatus.READY.value:
            self._worker.enqueue(
                JobTask(
                    job_type=JobType.PUBLISHING,
                    job_id=job.id,
                    series_id=series_id,
                    production_run_id=correlation_id,
                )
            )
        return job

    def execute(self, series_id: str, job_id: str) -> PublishingWorkflowResult:
        """Execute a publishing job."""
        job = self._get_job(series_id, job_id)

        if job.status == PublishingStatus.PUBLISHED.value:
            return self._result(job)
        if job.status == PublishingStatus.PUBLISHING.value:
            raise PublishingWorkflowError("Job is already being published.")
        if job.status == PublishingStatus.CANCELLED.value:
            raise PublishingWorkflowError("Job has been cancelled.")
        if job.status not in {
            PublishingStatus.READY.value,
            PublishingStatus.SCHEDULED.value,
            PublishingStatus.FAILED.value,
        }:
            raise PublishingWorkflowError(f"Job is in an unexpected state: {job.status}")
        if job.attempts >= job.max_attempts:
            raise PublishingWorkflowError("Maximum retry attempts exhausted.")

        if (
            job.status == PublishingStatus.SCHEDULED.value
            and job.scheduled_at
            and job.scheduled_at > self._now()
        ):
            raise PublishingWorkflowError("Scheduled publication is not yet due.")

        series = self._db.get(Series, job.series_id)
        episode = self._db.get(Episode, job.episode_id)
        asset = self._db.get(Asset, job.asset_id)
        if not series or not episode or not asset:
            raise PublishingWorkflowError("Required entities missing.")

        job.attempts += 1
        self._db.flush()

        try:
            self._validate_publishability(series, episode, asset, job.thumbnail_asset_id)
        except (PublishingWorkflowError, ThumbnailError) as exc:
            job.error_message = self._sanitize_error(str(exc))
            self._transition(job, PublishingStatus.FAILED)
            self._record(
                event_type=AuditEventType.PUBLICATION_FAILED,
                series_id=series_id,
                episode_id=episode.id,
                job_id=job.id,
                status=AuditStatus.FAILED,
                error_message=job.error_message,
            )
            self._db.commit()
            return self._result(job)

        if job.metadata_snapshot:
            metadata = ShortsMetadata(**job.metadata_snapshot)
        else:
            metadata = self._metadata.generate(series.id, episode.id, mode="deterministic")

        self._record(
            event_type=AuditEventType.PUBLICATION_VALIDATED,
            series_id=series_id,
            episode_id=episode.id,
            job_id=job.id,
            status=AuditStatus.SUCCESS,
            metadata={"provider_id": job.provider_id},
        )

        self._transition(job, PublishingStatus.PUBLISHING)
        self._record(
            event_type=AuditEventType.PUBLICATION_STARTED,
            series_id=series_id,
            episode_id=episode.id,
            job_id=job.id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"provider_id": job.provider_id, "attempt": job.attempts},
        )

        request = self._build_publishing_request(series_id, episode.id, asset.id, metadata)
        try:
            result = self._publishing.publish(request)
        except PublishingServiceError as exc:
            job.error_message = self._sanitize_error(str(exc))
            self._transition(job, PublishingStatus.FAILED)
            self._record(
                event_type=AuditEventType.PUBLICATION_FAILED,
                series_id=series_id,
                episode_id=episode.id,
                job_id=job.id,
                status=AuditStatus.FAILED,
                error_message=job.error_message,
            )
            self._db.commit()
            return self._result(job)

        if result.status == PublishingStatus.PUBLISHED.value:
            job.published_at = self._now()
            job.external_publication_id = result.publication_id
            job.external_url = result.url
            job.error_message = None
            self._transition(job, PublishingStatus.PUBLISHED)
            self._record(
                event_type=AuditEventType.PUBLICATION_COMPLETED,
                series_id=series_id,
                episode_id=episode.id,
                job_id=job.id,
                status=AuditStatus.SUCCESS,
                attempt=job.attempts,
                metadata={
                    "publication_id": result.publication_id,
                    "provider": result.provider,
                },
            )
        else:
            job.error_message = self._sanitize_error(result.error_message)
            self._transition(job, PublishingStatus.FAILED)
            self._record(
                event_type=AuditEventType.PUBLICATION_FAILED,
                series_id=series_id,
                episode_id=episode.id,
                job_id=job.id,
                status=AuditStatus.FAILED,
                error_message=job.error_message,
            )
        self._db.commit()
        return self._result(job)

    def execute_due(self) -> list[PublishingWorkflowResult]:
        """Execute scheduled jobs whose scheduled time has passed."""
        due_jobs = (
            self._db.query(PublishingJob)
            .filter(
                PublishingJob.status == PublishingStatus.SCHEDULED.value,
                PublishingJob.scheduled_at <= self._now(),
            )
            .all()
        )
        results: list[PublishingWorkflowResult] = []
        for job in due_jobs:
            try:
                result = self.execute(job.series_id, job.id)
                results.append(result)
            except Exception:
                # Due-job executor must not crash on one failed job.
                self._db.rollback()
                continue
        return results

    def cancel(self, series_id: str, job_id: str) -> PublishingWorkflowResult:
        """Cancel a scheduled/ready publishing job."""
        job = self._get_job(series_id, job_id)
        if job.status in {
            PublishingStatus.PUBLISHED.value,
            PublishingStatus.CANCELLED.value,
        }:
            raise PublishingWorkflowError("Cannot cancel a finished or already cancelled job.")
        self._transition(job, PublishingStatus.CANCELLED)
        self._record(
            event_type=AuditEventType.PUBLICATION_CANCELLED,
            series_id=series_id,
            episode_id=job.episode_id,
            job_id=job.id,
            status=AuditStatus.SUCCESS,
        )
        self._db.commit()
        return self._result(job)

    def retry(self, series_id: str, job_id: str) -> PublishingWorkflowResult:
        """Mark a failed job ready for retry if attempts remain."""
        job = self._get_job(series_id, job_id)
        if job.status != PublishingStatus.FAILED.value:
            raise PublishingWorkflowError("Only failed jobs can be retried.")
        if job.attempts >= job.max_attempts:
            raise PublishingWorkflowError("Maximum retry attempts exhausted.")
        self._transition(job, PublishingStatus.READY)
        self._record(
            event_type=AuditEventType.PUBLICATION_RETRIED,
            series_id=series_id,
            episode_id=job.episode_id,
            job_id=job.id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"max_attempts": job.max_attempts},
        )
        self._db.commit()
        return self._result(job)

    def _result(self, job: PublishingJob) -> PublishingWorkflowResult:
        return PublishingWorkflowResult(
            job_id=UUID(job.id),
            status=job.status,
            external_publication_id=job.external_publication_id,
            external_url=job.external_url,
            attempts=job.attempts,
            error_message=job.error_message,
        )
