"""Video generation job lifecycle and retry service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.media_generation.video.clip_storage_service import VideoClipStorageService
from app.media_generation.video.errors import VideoRequestError
from app.media_generation.video.image_to_video_service import ImageToVideoService
from app.media_generation.video.provider import (
    VideoGenerationProvider,
    VideoGenerationRequest,
)
from app.models import Shot, VideoGenerationJob
from app.models.enums import VideoGenerationJobStatus
from app.storage.base import StorageBackend


class VideoGenerationJobService:
    """Persistent video generation job lifecycle with bounded retries."""

    def __init__(
        self,
        db: Session,
        provider: VideoGenerationProvider | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._db = db
        self._image_to_video = ImageToVideoService(db, provider)
        self._clip_storage = VideoClipStorageService(db, storage)

    def _get_job(self, series_id: str, job_id: str) -> VideoGenerationJob:
        job = self._db.get(VideoGenerationJob, job_id)
        if not job or job.series_id != series_id:
            raise VideoRequestError("Job not found.")
        return job

    def create(
        self,
        series_id: str,
        shot_id: str,
        storyboard_asset_id: str,
        *,
        prompt_override: str | None = None,
        duration_seconds: int | None = None,
        aspect_ratio: str | None = None,
        motion_description: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> tuple[VideoGenerationJob, VideoGenerationRequest]:
        """Create a queued job and return it along with the resolved request."""
        request = self._image_to_video.build_video_request(
            series_id,
            shot_id,
            storyboard_asset_id,
            prompt_override=prompt_override,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            motion_description=motion_description,
            reference_asset_ids=reference_asset_ids,
        )

        job = VideoGenerationJob(
            series_id=series_id,
            shot_id=shot_id,
            source_asset_id=storyboard_asset_id,
            request_payload=request.model_dump(mode="json"),
            status=VideoGenerationJobStatus.QUEUED.value,
            attempts=0,
            max_attempts=3,
        )
        self._db.add(job)
        self._db.flush()

        return job, request

    def create_and_run(
        self,
        series_id: str,
        shot_id: str,
        storyboard_asset_id: str,
        *,
        prompt_override: str | None = None,
        duration_seconds: int | None = None,
        aspect_ratio: str | None = None,
        motion_description: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> VideoGenerationJob:
        """Create a queued job, run it synchronously, and persist the result."""
        job, request = self.create(
            series_id,
            shot_id,
            storyboard_asset_id,
            prompt_override=prompt_override,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            motion_description=motion_description,
            reference_asset_ids=reference_asset_ids,
        )
        return self.run(job, request)

    def run(self, job: VideoGenerationJob, request: VideoGenerationRequest) -> VideoGenerationJob:
        """Execute a queued or failed video generation job and persist the result."""
        if job.status not in {
            VideoGenerationJobStatus.QUEUED.value,
            VideoGenerationJobStatus.FAILED.value,
        }:
            raise VideoRequestError("Job cannot be executed from its current state.")

        if job.attempts >= job.max_attempts:
            job.status = VideoGenerationJobStatus.FAILED.value
            job.error_message = "Maximum retry attempts exceeded."
            self._db.flush()
            return job

        job.attempts += 1
        job.status = VideoGenerationJobStatus.RUNNING.value
        job.error_message = None
        self._db.flush()

        reservation_id: str | None = None
        try:
            from app.models import Scene
            from app.services.episode_budget_service import (
                BudgetExceededError,
                EpisodeBudgetService,
            )
            from app.services.generation_cost_service import GenerationCostService

            shot = self._db.get(Shot, str(job.shot_id)) if job.shot_id else None
            scene = self._db.get(Scene, str(shot.scene_id)) if shot and shot.scene_id else None
            episode_id = str(scene.episode_id) if scene and scene.episode_id else None
            budget_result = EpisodeBudgetService(self._db).check_and_reserve(
                job.series_id,
                episode_id,
                "VIDEO",
                estimated_cost=0,
                currency="USD",
                job_id=str(job.id),
            )
            if not budget_result.allowed:
                raise BudgetExceededError(budget_result.reason)
            reservation_id = budget_result.reservation_id

            result = self._image_to_video.execute_request(job.series_id, request)
            asset = self._clip_storage.process_result(job, result)
            GenerationCostService(self._db).record_from_video_result(
                job.series_id,
                result,
                episode_id=episode_id,
                job_id=str(job.id),
                asset_id=str(asset.id),
            )
            if reservation_id:
                EpisodeBudgetService(self._db).settle_reservation(reservation_id)
            job.provider = result.provider
            job.model = result.model
            job.status = VideoGenerationJobStatus.SUCCEEDED.value
        except Exception as exc:
            if reservation_id:
                from app.services.episode_budget_service import EpisodeBudgetService

                EpisodeBudgetService(self._db).release_reservation(reservation_id)
            job.status = VideoGenerationJobStatus.FAILED.value
            job.error_message = str(exc)

        self._db.flush()
        self._db.refresh(job)
        return job

    def retry(self, series_id: str, job_id: str) -> VideoGenerationJob:
        """Retry a failed video generation job."""
        job = self._get_job(series_id, job_id)
        if job.status != VideoGenerationJobStatus.FAILED.value:
            raise VideoRequestError("Only failed jobs can be retried.")
        if job.attempts >= job.max_attempts:
            raise VideoRequestError("Maximum retry attempts have been exhausted.")

        request = VideoGenerationRequest(**job.request_payload)
        return self.run(job, request)

    def cancel(self, series_id: str, job_id: str) -> VideoGenerationJob:
        """Cancel a queued or running video generation job."""
        job = self._get_job(series_id, job_id)
        if job.status not in {
            VideoGenerationJobStatus.QUEUED.value,
            VideoGenerationJobStatus.RUNNING.value,
        }:
            raise VideoRequestError("Job cannot be cancelled in its current state.")
        job.status = VideoGenerationJobStatus.CANCELLED.value
        self._db.flush()
        self._db.refresh(job)
        return job
