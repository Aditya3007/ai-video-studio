"""Image-to-video workflow routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.media_generation.video import ImageToVideoService, VideoRequestError
from app.schemas import ImageToVideoRequest, ImageToVideoResponse

router = APIRouter(prefix="/series", tags=["image-to-video"])


@router.post(
    "/{series_id}/shots/{shot_id}/image-to-video",
    status_code=201,
    response_model=ImageToVideoResponse,
)
def create_image_to_video(
    series_id: UUID,
    shot_id: UUID,
    data: ImageToVideoRequest,
    db: DbSession,
) -> ImageToVideoResponse:
    """Generate a video from an approved storyboard/keyframe asset."""
    service = ImageToVideoService(db)
    try:
        result = service.generate(
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
    return result
