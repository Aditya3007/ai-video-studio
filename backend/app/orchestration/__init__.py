"""Provider-neutral asynchronous workflow/job orchestration boundary."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.media_generation.image import (
    ImageGenerationJobService,
    ImageGenerationProviderFactory,
)
from app.media_generation.video import VideoGenerationJobService
from app.media_generation.video.provider import VideoGenerationRequest
from app.models import ImageGenerationJob, VideoGenerationJob
from app.models.enums import AuditEventType, AuditStatus, ImageGenerationJobStatus
from app.services.audit_service import AuditService

__all__ = [
    "ImmediateWorker",
    "JobTask",
    "JobType",
    "OrchestrationError",
    "Orchestrator",
    "ThreadedWorker",
    "UnknownJobError",
    "Worker",
]


class OrchestrationError(Exception):
    """Base error for orchestration failures."""


class UnknownJobError(OrchestrationError):
    """Raised when a requested orchestration job cannot be found."""


class JobType(StrEnum):
    """Supported asynchronous production job types."""

    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    PUBLISHING = "publishing"


class JobTask(BaseModel):
    """Unit of work enqueued for asynchronous execution."""

    job_type: JobType
    job_id: str
    series_id: str
    production_run_id: str | None = None

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class Worker(Protocol):
    """Provider-neutral worker contract for executing queued tasks."""

    def enqueue(self, task: JobTask) -> None:
        """Queue a task for execution."""
        ...

    def wait_for(self, job_id: str, timeout: float | None = None) -> None:
        """Wait for the task identified by job_id to complete."""
        ...


class ImmediateWorker:
    """Synchronous worker that executes tasks immediately in the calling thread."""

    def __init__(self, handler: Callable[[JobTask], None]) -> None:
        self._handler = handler

    def enqueue(self, task: JobTask) -> None:
        self._handler(task)

    def wait_for(self, job_id: str, timeout: float | None = None) -> None:
        return


class ThreadedWorker:
    """Worker that executes tasks on a thread pool."""

    def __init__(
        self,
        handler: Callable[[JobTask], None],
        *,
        max_workers: int = 1,
    ) -> None:
        self._handler = handler
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Any] = {}

    def enqueue(self, task: JobTask) -> None:
        future = self._executor.submit(self._handler, task)
        self._futures[task.job_id] = future

    def wait_for(self, job_id: str, timeout: float | None = None) -> None:
        future = self._futures.pop(job_id, None)
        if future is None:
            raise UnknownJobError(f"No pending task for job '{job_id}'")
        try:
            future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            raise OrchestrationError(f"Timeout waiting for job '{job_id}'") from exc

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


class ExecutionGuard:
    """Deterministic, application-level idempotency and recovery checks."""

    @staticmethod
    def is_eligible_for_execution(job: ImageGenerationJob | VideoGenerationJob) -> bool:
        """Return True if the job can be safely executed now."""
        status = job.status
        if status == ImageGenerationJobStatus.QUEUED.value:
            return True
        if status == ImageGenerationJobStatus.FAILED.value:
            return job.attempts < job.max_attempts
        return False

    @staticmethod
    def is_recoverable(job: ImageGenerationJob | VideoGenerationJob) -> bool:
        """Return True if the job can be resumed/recovered."""
        status = job.status
        if status in {
            ImageGenerationJobStatus.QUEUED.value,
            ImageGenerationJobStatus.RUNNING.value,
        }:
            return True
        if status == ImageGenerationJobStatus.FAILED.value:
            return job.attempts < job.max_attempts
        return False


class Orchestrator:
    """Provider-neutral orchestrator for asynchronous production jobs."""

    def __init__(
        self,
        db_factory: Callable[[], Session] | None = None,
        worker: Worker | type[Worker] | None = None,
    ) -> None:
        self._db_factory = db_factory or SessionLocal
        if worker is None:
            self._worker: Worker = ImmediateWorker(self._execute)
        elif isinstance(worker, type):
            self._worker = worker(self._execute)
        else:
            self._worker = worker

    def _execute(self, task: JobTask) -> None:
        db = self._db_factory()
        try:
            if task.job_type == JobType.IMAGE_GENERATION:
                self._run_image_generation(db, task)
            elif task.job_type == JobType.VIDEO_GENERATION:
                self._run_video_generation(db, task)
            else:
                raise OrchestrationError(f"Unsupported job type: {task.job_type}")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _run_image_generation(self, db: Session, task: JobTask) -> None:
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)
        job = service._get_job(task.series_id, task.job_id)
        if not ExecutionGuard.is_eligible_for_execution(job):
            return
        payload = job.request_payload or {}
        shot, request = service._storyboard.build_image_request(
            task.series_id,
            str(job.shot_id),
            prompt_override=payload.get("prompt_override"),
            reference_asset_ids=payload.get("reference_asset_ids"),
        )
        audit = AuditService(db)
        audit.record(
            series_id=task.series_id,
            event_type=AuditEventType.JOB_STARTED,
            shot_id=str(job.shot_id) if job.shot_id else None,
            job_id=job.id,
            production_run_id=task.production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts + 1,
            metadata={"job_type": JobType.IMAGE_GENERATION.value},
        )
        service.run(job, shot, request)
        if job.status == ImageGenerationJobStatus.SUCCEEDED.value and job.result_asset_ids:
            audit.record(
                series_id=task.series_id,
                event_type=AuditEventType.JOB_COMPLETED,
                shot_id=str(job.shot_id) if job.shot_id else None,
                asset_id=job.result_asset_ids[0],
                job_id=job.id,
                production_run_id=task.production_run_id,
                status=AuditStatus.SUCCESS,
                attempt=job.attempts,
                metadata={"job_type": JobType.IMAGE_GENERATION.value},
            )
            audit.record(
                series_id=task.series_id,
                event_type=AuditEventType.ASSET_CREATED,
                shot_id=str(job.shot_id) if job.shot_id else None,
                asset_id=job.result_asset_ids[0],
                job_id=job.id,
                production_run_id=task.production_run_id,
                status=AuditStatus.SUCCESS,
                metadata={"asset_role": "storyboard"},
            )
        elif job.status == ImageGenerationJobStatus.FAILED.value:
            audit.record(
                series_id=task.series_id,
                event_type=AuditEventType.JOB_FAILED,
                shot_id=str(job.shot_id) if job.shot_id else None,
                job_id=job.id,
                production_run_id=task.production_run_id,
                status=AuditStatus.FAILED,
                attempt=job.attempts,
                metadata={"job_type": JobType.IMAGE_GENERATION.value},
                error_message=job.error_message,
            )

    def _run_video_generation(self, db: Session, task: JobTask) -> None:
        service = VideoGenerationJobService(db)
        job = service._get_job(task.series_id, task.job_id)
        if not ExecutionGuard.is_eligible_for_execution(job):
            return
        request = VideoGenerationRequest(**job.request_payload)
        audit = AuditService(db)
        audit.record(
            series_id=task.series_id,
            event_type=AuditEventType.JOB_STARTED,
            shot_id=str(job.shot_id) if job.shot_id else None,
            job_id=job.id,
            production_run_id=task.production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts + 1,
            metadata={"job_type": JobType.VIDEO_GENERATION.value},
        )
        service.run(job, request)
        asset_id = (job.result_metadata or {}).get("asset_id") if job.result_metadata else None
        if job.status == ImageGenerationJobStatus.SUCCEEDED.value and asset_id:
            audit.record(
                series_id=task.series_id,
                event_type=AuditEventType.JOB_COMPLETED,
                shot_id=str(job.shot_id) if job.shot_id else None,
                asset_id=asset_id,
                job_id=job.id,
                production_run_id=task.production_run_id,
                status=AuditStatus.SUCCESS,
                attempt=job.attempts,
                metadata={"job_type": JobType.VIDEO_GENERATION.value},
            )
            audit.record(
                series_id=task.series_id,
                event_type=AuditEventType.ASSET_CREATED,
                shot_id=str(job.shot_id) if job.shot_id else None,
                asset_id=asset_id,
                job_id=job.id,
                production_run_id=task.production_run_id,
                status=AuditStatus.SUCCESS,
                metadata={"asset_role": "video_clip"},
            )
        elif job.status == ImageGenerationJobStatus.FAILED.value:
            audit.record(
                series_id=task.series_id,
                event_type=AuditEventType.JOB_FAILED,
                shot_id=str(job.shot_id) if job.shot_id else None,
                job_id=job.id,
                production_run_id=task.production_run_id,
                status=AuditStatus.FAILED,
                attempt=job.attempts,
                metadata={"job_type": JobType.VIDEO_GENERATION.value},
                error_message=job.error_message,
            )

    def submit_image_generation(
        self,
        db: Session,
        series_id: str,
        shot_id: str,
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list[str] | None = None,
        production_run_id: str | None = None,
    ) -> ImageGenerationJob:
        """Create a queued image-generation job and enqueue it for execution."""
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)
        job, _shot, _request = service.create(
            series_id,
            shot_id,
            prompt_override=prompt_override,
            reference_asset_ids=reference_asset_ids,
        )
        AuditService(db).record(
            series_id=series_id,
            event_type=AuditEventType.JOB_SUBMITTED,
            shot_id=shot_id,
            job_id=job.id,
            production_run_id=production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"job_type": JobType.IMAGE_GENERATION.value},
        )
        db.commit()
        self._worker.enqueue(
            JobTask(
                job_type=JobType.IMAGE_GENERATION,
                job_id=job.id,
                series_id=series_id,
                production_run_id=production_run_id,
            )
        )
        return job

    def submit_video_generation(
        self,
        db: Session,
        series_id: str,
        shot_id: str,
        storyboard_asset_id: str,
        *,
        prompt_override: str | None = None,
        duration_seconds: int | None = None,
        aspect_ratio: str | None = None,
        motion_description: str | None = None,
        reference_asset_ids: list[str] | None = None,
        production_run_id: str | None = None,
    ) -> VideoGenerationJob:
        """Create a queued video-generation job and enqueue it for execution."""
        service = VideoGenerationJobService(db)
        job, _request = service.create(
            series_id,
            shot_id,
            storyboard_asset_id,
            prompt_override=prompt_override,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            motion_description=motion_description,
            reference_asset_ids=reference_asset_ids,
        )
        AuditService(db).record(
            series_id=series_id,
            event_type=AuditEventType.JOB_SUBMITTED,
            shot_id=shot_id,
            job_id=job.id,
            production_run_id=production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"job_type": JobType.VIDEO_GENERATION.value},
        )
        db.commit()
        self._worker.enqueue(
            JobTask(
                job_type=JobType.VIDEO_GENERATION,
                job_id=job.id,
                series_id=series_id,
                production_run_id=production_run_id,
            )
        )
        return job

    def get_image_generation(self, db: Session, series_id: str, job_id: str) -> ImageGenerationJob:
        """Retrieve an image-generation job."""
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)
        return service._get_job(series_id, job_id)

    def get_video_generation(self, db: Session, series_id: str, job_id: str) -> VideoGenerationJob:
        """Retrieve a video-generation job."""
        service = VideoGenerationJobService(db)
        return service._get_job(series_id, job_id)

    def cancel_image_generation(
        self, db: Session, series_id: str, job_id: str
    ) -> ImageGenerationJob:
        """Cancel an image-generation job."""
        provider = ImageGenerationProviderFactory.create()
        service = ImageGenerationJobService(db, provider)
        return service.cancel(series_id, job_id)

    def cancel_video_generation(
        self, db: Session, series_id: str, job_id: str
    ) -> VideoGenerationJob:
        """Cancel a video-generation job."""
        service = VideoGenerationJobService(db)
        return service.cancel(series_id, job_id)

    def retry_image_generation(
        self,
        db: Session,
        series_id: str,
        job_id: str,
        *,
        production_run_id: str | None = None,
    ) -> ImageGenerationJob:
        """Enqueue a failed image-generation job for retry."""
        job = self.get_image_generation(db, series_id, job_id)
        if job.status != ImageGenerationJobStatus.FAILED.value:
            raise OrchestrationError("Only failed jobs can be retried")
        if job.attempts >= job.max_attempts:
            raise OrchestrationError("Maximum retry attempts exhausted")
        AuditService(db).record(
            series_id=series_id,
            event_type=AuditEventType.JOB_RETRIED,
            shot_id=str(job.shot_id) if job.shot_id else None,
            job_id=job.id,
            production_run_id=production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"job_type": JobType.IMAGE_GENERATION.value},
        )
        db.commit()
        self._worker.enqueue(
            JobTask(
                job_type=JobType.IMAGE_GENERATION,
                job_id=job.id,
                series_id=series_id,
                production_run_id=production_run_id,
            )
        )
        return job

    def retry_video_generation(
        self,
        db: Session,
        series_id: str,
        job_id: str,
        *,
        production_run_id: str | None = None,
    ) -> VideoGenerationJob:
        """Enqueue a failed video-generation job for retry."""
        job = self.get_video_generation(db, series_id, job_id)
        if job.status != ImageGenerationJobStatus.FAILED.value:
            raise OrchestrationError("Only failed jobs can be retried")
        if job.attempts >= job.max_attempts:
            raise OrchestrationError("Maximum retry attempts exhausted")
        AuditService(db).record(
            series_id=series_id,
            event_type=AuditEventType.JOB_RETRIED,
            shot_id=str(job.shot_id) if job.shot_id else None,
            job_id=job.id,
            production_run_id=production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"job_type": JobType.VIDEO_GENERATION.value},
        )
        db.commit()
        self._worker.enqueue(
            JobTask(
                job_type=JobType.VIDEO_GENERATION,
                job_id=job.id,
                series_id=series_id,
                production_run_id=production_run_id,
            )
        )
        return job

    def _resume_job(
        self,
        db: Session,
        series_id: str,
        job_id: str,
        job_type: JobType,
        fetch: Callable[[Session, str, str], Any],
        *,
        production_run_id: str | None = None,
    ) -> Any:
        job = fetch(db, series_id, job_id)
        if not ExecutionGuard.is_recoverable(job):
            raise OrchestrationError(f"Job '{job_id}' is not recoverable")
        if job.status == ImageGenerationJobStatus.RUNNING.value:
            job.status = ImageGenerationJobStatus.QUEUED.value
            db.flush()
        AuditService(db).record(
            series_id=series_id,
            event_type=AuditEventType.JOB_RESUMED,
            shot_id=str(job.shot_id) if job.shot_id else None,
            job_id=job.id,
            production_run_id=production_run_id,
            status=AuditStatus.PENDING,
            attempt=job.attempts,
            metadata={"job_type": job_type.value},
        )
        db.commit()
        self._worker.enqueue(
            JobTask(
                job_type=job_type,
                job_id=job.id,
                series_id=series_id,
                production_run_id=production_run_id,
            )
        )
        return job

    def resume_image_generation(
        self,
        db: Session,
        series_id: str,
        job_id: str,
        *,
        production_run_id: str | None = None,
    ) -> ImageGenerationJob:
        """Recover/continue an image-generation job."""
        return self._resume_job(
            db,
            series_id,
            job_id,
            JobType.IMAGE_GENERATION,
            self.get_image_generation,
            production_run_id=production_run_id,
        )

    def resume_video_generation(
        self,
        db: Session,
        series_id: str,
        job_id: str,
        *,
        production_run_id: str | None = None,
    ) -> VideoGenerationJob:
        """Recover/continue a video-generation job."""
        return self._resume_job(
            db,
            series_id,
            job_id,
            JobType.VIDEO_GENERATION,
            self.get_video_generation,
            production_run_id=production_run_id,
        )

    def wait_for(self, job_id: str, timeout: float | None = None) -> None:
        """Wait for the queued task identified by job_id to complete."""
        self._worker.wait_for(job_id, timeout=timeout)
