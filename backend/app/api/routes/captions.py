"""Caption/subtitle routes for video assemblies."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.schemas import CaptionCreate, CaptionResponse, CaptionUpdate
from app.services.caption_service import CaptionError, CaptionNotFoundError, CaptionService
from app.services.video_assembly_service import VideoAssemblyNotFoundError

router = APIRouter(prefix="/series", tags=["captions"])


@router.get(
    "/{series_id}/video-assemblies/{assembly_id}/captions",
    response_model=list[CaptionResponse],
)
def list_captions(
    series_id: UUID,
    assembly_id: UUID,
    db: DbSession,
) -> list[CaptionResponse]:
    """List captions for a video assembly."""
    service = CaptionService(db)
    try:
        captions = service.list_for_assembly(str(series_id), str(assembly_id))
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return [CaptionResponse.model_validate(c) for c in captions]


@router.post(
    "/{series_id}/video-assemblies/{assembly_id}/captions",
    response_model=CaptionResponse,
    status_code=201,
)
def create_caption(
    series_id: UUID,
    assembly_id: UUID,
    data: CaptionCreate,
    db: DbSession,
) -> CaptionResponse:
    """Create a caption for a video assembly."""
    service = CaptionService(db)
    try:
        caption = service.create(str(series_id), data)
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except CaptionError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return CaptionResponse.model_validate(caption)


@router.get(
    "/{series_id}/video-assemblies/{assembly_id}/captions/{caption_id}",
    response_model=CaptionResponse,
)
def get_caption(
    series_id: UUID,
    assembly_id: UUID,
    caption_id: UUID,
    db: DbSession,
) -> CaptionResponse:
    """Retrieve a caption."""
    service = CaptionService(db)
    try:
        caption = service.get(str(series_id), str(caption_id))
    except CaptionNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    if str(caption.assembly_id) != str(assembly_id):
        raise AppError("NOT_FOUND", "Caption not found.", status_code=404)
    return CaptionResponse.model_validate(caption)


@router.patch(
    "/{series_id}/video-assemblies/{assembly_id}/captions/{caption_id}",
    response_model=CaptionResponse,
)
def update_caption(
    series_id: UUID,
    assembly_id: UUID,
    caption_id: UUID,
    data: CaptionUpdate,
    db: DbSession,
) -> CaptionResponse:
    """Update a caption."""
    service = CaptionService(db)
    try:
        caption = service.get(str(series_id), str(caption_id))
        if str(caption.assembly_id) != str(assembly_id):
            raise AppError("NOT_FOUND", "Caption not found.", status_code=404)
        caption = service.update(str(series_id), str(caption_id), data)
    except CaptionNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (CaptionError, VideoAssemblyNotFoundError) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return CaptionResponse.model_validate(caption)


@router.delete(
    "/{series_id}/video-assemblies/{assembly_id}/captions/{caption_id}",
    status_code=204,
)
def delete_caption(
    series_id: UUID,
    assembly_id: UUID,
    caption_id: UUID,
    db: DbSession,
) -> None:
    """Delete a caption."""
    service = CaptionService(db)
    try:
        caption = service.get(str(series_id), str(caption_id))
        if str(caption.assembly_id) != str(assembly_id):
            raise AppError("NOT_FOUND", "Caption not found.", status_code=404)
        service.remove(str(series_id), str(caption_id))
    except CaptionNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    commit_or_409(db)
