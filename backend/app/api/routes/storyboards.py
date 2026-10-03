"""Storyboard/keyframe generation routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.media_generation.image import (
    ImageGenerationError,
    ImageGenerationProviderFactory,
    StoryboardError,
    StoryboardService,
)
from app.schemas import AssetResponse, StoryboardGenerationRequest

router = APIRouter(prefix="/series", tags=["storyboards"])


@router.post(
    "/{series_id}/shots/{shot_id}/storyboard",
    status_code=201,
    response_model=AssetResponse,
)
def generate_storyboard(
    series_id: UUID,
    shot_id: UUID,
    data: StoryboardGenerationRequest,
    db: DbSession,
) -> AssetResponse:
    """Generate a storyboard/keyframe asset for a shot."""
    provider = ImageGenerationProviderFactory.create()
    service = StoryboardService(db, provider)
    try:
        asset = service.generate_storyboard(
            str(series_id),
            str(shot_id),
            prompt_override=data.prompt_override,
            reference_asset_ids=[str(aid) for aid in data.reference_asset_ids],
        )
    except StoryboardError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    except ImageGenerationError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return asset
