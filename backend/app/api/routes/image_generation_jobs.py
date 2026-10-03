"""Image generation job orchestration routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.media_generation.image import (
    ImageGenerationJobService,
    ImageGenerationProviderFactory,
    StoryboardError,
)
from app.schemas import ImageGenerationJobCreate, ImageGenerationJobResponse

router = APIRouter(prefix="/series", tags=["image-generation-jobs"])


@router.post(
    "/{series_id}/shots/{shot_id}/image-generation-jobs",
    status_code=201,
    response_model=ImageGenerationJobResponse,
)
def create_and_run_job(
    series_id: UUID,
    shot_id: UUID,
    data: ImageGenerationJobCreate,
    db: DbSession,
) -> ImageGenerationJobResponse:
    """Create and synchronously execute an image generation job."""
    provider = ImageGenerationProviderFactory.create()
    service = ImageGenerationJobService(db, provider)
    try:
        job = service.create_and_run(
            str(series_id),
            str(shot_id),
            prompt_override=data.prompt_override,
            reference_asset_ids=[str(aid) for aid in data.reference_asset_ids],
        )
    except StoryboardError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job


@router.get(
    "/{series_id}/image-generation-jobs/{job_id}",
    response_model=ImageGenerationJobResponse,
)
def get_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> ImageGenerationJobResponse:
    """Retrieve an image generation job."""
    provider = ImageGenerationProviderFactory.create()
    service = ImageGenerationJobService(db, provider)
    try:
        job = service._get_job(str(series_id), str(job_id))
    except StoryboardError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return job


@router.post(
    "/{series_id}/image-generation-jobs/{job_id}/approve",
    response_model=ImageGenerationJobResponse,
)
def approve_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> ImageGenerationJobResponse:
    """Approve a succeeded image generation job."""
    provider = ImageGenerationProviderFactory.create()
    service = ImageGenerationJobService(db, provider)
    try:
        job = service.approve(str(series_id), str(job_id))
    except StoryboardError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job


@router.post(
    "/{series_id}/image-generation-jobs/{job_id}/reject",
    response_model=ImageGenerationJobResponse,
)
def reject_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> ImageGenerationJobResponse:
    """Reject a succeeded image generation job."""
    provider = ImageGenerationProviderFactory.create()
    service = ImageGenerationJobService(db, provider)
    try:
        job = service.reject(str(series_id), str(job_id))
    except StoryboardError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job


@router.post(
    "/{series_id}/image-generation-jobs/{job_id}/retry",
    response_model=ImageGenerationJobResponse,
)
def retry_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> ImageGenerationJobResponse:
    """Retry a failed image generation job."""
    provider = ImageGenerationProviderFactory.create()
    service = ImageGenerationJobService(db, provider)
    try:
        job = service.retry(str(series_id), str(job_id))
    except StoryboardError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job
