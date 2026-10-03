"""Video generation job lifecycle routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.media_generation.video import VideoGenerationJobService, VideoRequestError
from app.schemas import VideoGenerationJobCreate, VideoGenerationJobResponse

router = APIRouter(prefix="/series", tags=["video-generation-jobs"])


@router.post(
    "/{series_id}/shots/{shot_id}/video-generation-jobs",
    status_code=201,
    response_model=VideoGenerationJobResponse,
)
def create_and_run_job(
    series_id: UUID,
    shot_id: UUID,
    data: VideoGenerationJobCreate,
    db: DbSession,
) -> VideoGenerationJobResponse:
    """Create and synchronously execute a video generation job."""
    service = VideoGenerationJobService(db)
    try:
        job = service.create_and_run(
            str(series_id),
            str(shot_id),
            str(data.storyboard_asset_id),
            prompt_override=data.prompt_override,
            duration_seconds=data.duration_seconds,
            aspect_ratio=data.aspect_ratio,
            motion_description=data.motion_description,
            reference_asset_ids=[str(aid) for aid in data.reference_asset_ids],
        )
    except VideoRequestError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job


@router.get(
    "/{series_id}/video-generation-jobs/{job_id}",
    response_model=VideoGenerationJobResponse,
)
def get_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> VideoGenerationJobResponse:
    """Retrieve a video generation job."""
    service = VideoGenerationJobService(db)
    try:
        job = service._get_job(str(series_id), str(job_id))
    except VideoRequestError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return job


@router.post(
    "/{series_id}/video-generation-jobs/{job_id}/retry",
    response_model=VideoGenerationJobResponse,
)
def retry_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> VideoGenerationJobResponse:
    """Retry a failed video generation job."""
    service = VideoGenerationJobService(db)
    try:
        job = service.retry(str(series_id), str(job_id))
    except VideoRequestError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job


@router.post(
    "/{series_id}/video-generation-jobs/{job_id}/cancel",
    response_model=VideoGenerationJobResponse,
)
def cancel_job(
    series_id: UUID,
    job_id: UUID,
    db: DbSession,
) -> VideoGenerationJobResponse:
    """Cancel a video generation job."""
    service = VideoGenerationJobService(db)
    try:
        job = service.cancel(str(series_id), str(job_id))
    except VideoRequestError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return job
