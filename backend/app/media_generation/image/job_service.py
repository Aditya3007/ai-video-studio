"""Image generation job orchestration and approval service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.media_generation.image.errors import StoryboardError
from app.media_generation.image.provider import ImageGenerationProvider
from app.media_generation.image.service import ImageGenerationService
from app.media_generation.image.storyboard_service import StoryboardService
from app.models import Asset, ImageGenerationJob
from app.models.enums import ApprovalStatus, ImageGenerationJobStatus


class ImageGenerationJobService:
    """Orchestrates image generation with persistent jobs and approval."""

    def __init__(self, db: Session, provider: ImageGenerationProvider) -> None:
        self._db = db
        self._provider = provider
        self._storyboard = StoryboardService(db, provider)
        self._image = ImageGenerationService(db, provider)

    def _get_job(self, series_id: str, job_id: str) -> ImageGenerationJob:
        job = self._db.get(ImageGenerationJob, job_id)
        if not job or job.series_id != series_id:
            raise StoryboardError("Job not found.")
        return job

    def create(
        self,
        series_id: str,
        shot_id: str,
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> tuple[ImageGenerationJob, Any, Any]:
        """Create a queued job and return it along with the resolved shot/request."""
        shot, request = self._storyboard.build_image_request(
            series_id,
            shot_id,
            prompt_override=prompt_override,
            reference_asset_ids=reference_asset_ids,
        )

        job = ImageGenerationJob(
            series_id=series_id,
            shot_id=shot_id,
            request_payload=request.model_dump(mode="json"),
            status=ImageGenerationJobStatus.QUEUED.value,
            approval_status=ApprovalStatus.PENDING.value,
            attempts=0,
            max_attempts=3,
        )
        self._db.add(job)
        self._db.flush()

        return job, shot, request

    def create_and_run(
        self,
        series_id: str,
        shot_id: str,
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> ImageGenerationJob:
        """Create a queued job, run it synchronously, and persist the result."""
        job, shot, request = self.create(
            series_id,
            shot_id,
            prompt_override=prompt_override,
            reference_asset_ids=reference_asset_ids,
        )
        return self.run(job, shot, request)

    def run(
        self,
        job: ImageGenerationJob,
        shot,
        request,
    ) -> ImageGenerationJob:
        """Execute a queued or failed job and persist the result."""
        if job.status not in {
            ImageGenerationJobStatus.QUEUED.value,
            ImageGenerationJobStatus.FAILED.value,
        }:
            raise StoryboardError("Job cannot be executed from its current state.")

        job.attempts += 1
        if job.attempts > job.max_attempts:
            job.status = ImageGenerationJobStatus.FAILED.value
            job.error_message = "Maximum retry attempts exceeded."
            self._db.flush()
            return job

        job.status = ImageGenerationJobStatus.RUNNING.value
        job.error_message = None
        self._db.flush()

        reservation_id: str | None = None
        try:
            from app.core.config import get_settings
            from app.media_generation.image.factory import ImageGenerationProviderFactory

            settings = get_settings()
            provider = self._provider
            if settings.provider_selection_mode == "cost_aware":
                provider = ImageGenerationProviderFactory.create(settings=settings, request=request)

            from app.models import Scene
            from app.services.episode_budget_service import (
                BudgetExceededError,
                EpisodeBudgetService,
            )
            from app.services.generation_cost_service import GenerationCostService

            image_service = ImageGenerationService(self._db, provider)
            storyboard_service = StoryboardService(self._db, provider)

            scene = self._db.get(Scene, str(shot.scene_id)) if shot.scene_id else None
            episode_id = str(scene.episode_id) if scene and scene.episode_id else None
            budget_result = EpisodeBudgetService(self._db).check_and_reserve(
                job.series_id,
                episode_id,
                "IMAGE",
                estimated_cost=0,
                currency="USD",
                job_id=str(job.id),
            )
            if not budget_result.allowed:
                raise BudgetExceededError(budget_result.reason)
            reservation_id = budget_result.reservation_id

            result = image_service.generate(job.series_id, request)
            asset = storyboard_service.persist_asset(
                shot, request.prompt, result, approval_status=ApprovalStatus.PENDING
            )
            GenerationCostService(self._db).record_from_image_result(
                job.series_id,
                result,
                episode_id=episode_id,
                job_id=str(job.id),
                asset_id=str(asset.id),
            )
            if reservation_id:
                EpisodeBudgetService(self._db).settle_reservation(reservation_id)
            job.result_asset_ids = [asset.id]
            job.status = ImageGenerationJobStatus.SUCCEEDED.value
            job.approval_status = ApprovalStatus.PENDING.value
        except Exception as exc:
            if reservation_id:
                from app.services.episode_budget_service import EpisodeBudgetService

                EpisodeBudgetService(self._db).release_reservation(reservation_id)
            job.status = ImageGenerationJobStatus.FAILED.value
            job.error_message = str(exc)
            job.approval_status = ApprovalStatus.PENDING.value

        self._db.flush()
        self._db.refresh(job)
        return job

    def retry(self, series_id: str, job_id: str) -> ImageGenerationJob:
        """Retry a failed job."""
        job = self._get_job(series_id, job_id)
        if job.status != ImageGenerationJobStatus.FAILED.value:
            raise StoryboardError("Only failed jobs can be retried.")

        shot, request = self._storyboard.build_image_request(
            job.series_id,
            str(job.shot_id),
            prompt_override=None,
            reference_asset_ids=[
                str(aid) for aid in (job.request_payload or {}).get("reference_asset_ids", [])
            ],
        )
        return self.run(job, shot, request)

    def cancel(self, series_id: str, job_id: str) -> ImageGenerationJob:
        """Cancel a queued or running job."""
        job = self._get_job(series_id, job_id)
        if job.status not in {
            ImageGenerationJobStatus.QUEUED.value,
            ImageGenerationJobStatus.RUNNING.value,
        }:
            raise StoryboardError("Job cannot be cancelled in its current state.")
        job.status = ImageGenerationJobStatus.CANCELLED.value
        self._db.flush()
        self._db.refresh(job)
        return job

    def _set_approval(
        self, series_id: str, job_id: str, approval_status: ApprovalStatus
    ) -> ImageGenerationJob:
        job = self._get_job(series_id, job_id)
        if job.status != ImageGenerationJobStatus.SUCCEEDED.value:
            raise StoryboardError("Only succeeded jobs can be approved or rejected.")
        if job.approval_status != ApprovalStatus.PENDING.value:
            raise StoryboardError("Job approval has already been decided.")

        job.approval_status = approval_status.value
        if job.result_asset_ids:
            for asset_id in job.result_asset_ids:
                asset = self._db.get(Asset, asset_id)
                if asset:
                    asset.approval_status = approval_status.value
        self._db.flush()
        self._db.refresh(job)
        return job

    def approve(self, series_id: str, job_id: str) -> ImageGenerationJob:
        """Approve a succeeded generation job and its assets."""
        return self._set_approval(series_id, job_id, ApprovalStatus.APPROVED)

    def reject(self, series_id: str, job_id: str) -> ImageGenerationJob:
        """Reject a succeeded generation job and its assets."""
        return self._set_approval(series_id, job_id, ApprovalStatus.REJECTED)
