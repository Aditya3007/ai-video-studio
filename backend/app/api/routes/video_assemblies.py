"""Video assembly and timeline routes."""

import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession, StorageDep
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.core.config import get_settings
from app.schemas import (
    AssemblyItemCreate,
    AssemblyItemResponse,
    AssemblyItemUpdate,
    AssetResponse,
    FinalExportResponse,
    VideoAssemblyCreate,
    VideoAssemblyResponse,
    VideoAssemblyUpdate,
)
from app.services.final_export_service import FinalExportError, FinalExportService
from app.services.video_assembly_service import (
    AssemblyItemError,
    AssemblyItemNotFoundError,
    VideoAssemblyError,
    VideoAssemblyNotFoundError,
    VideoAssemblyService,
)
from app.services.video_renderer import (
    FFmpegExecutionError,
    FFmpegNotAvailableError,
    FFmpegVideoRenderer,
    InvalidTimelineError,
    MediaNotFoundError,
    RenderOutputError,
    RenderResult,
    VideoRenderError,
)

router = APIRouter(prefix="/series", tags=["video-assemblies"])


@router.post(
    "/{series_id}/video-assemblies",
    status_code=201,
    response_model=VideoAssemblyResponse,
)
def create_video_assembly(
    series_id: UUID,
    data: VideoAssemblyCreate,
    db: DbSession,
) -> VideoAssemblyResponse:
    """Create a video assembly for an episode."""
    service = VideoAssemblyService(db)
    try:
        assembly = service.create(str(series_id), data)
    except VideoAssemblyError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return assembly


@router.get(
    "/{series_id}/video-assemblies/{assembly_id}",
    response_model=VideoAssemblyResponse,
)
def get_video_assembly(
    series_id: UUID,
    assembly_id: UUID,
    db: DbSession,
) -> VideoAssemblyResponse:
    """Retrieve a video assembly."""
    service = VideoAssemblyService(db)
    try:
        assembly = service.get(str(series_id), str(assembly_id))
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return assembly


@router.patch(
    "/{series_id}/video-assemblies/{assembly_id}",
    response_model=VideoAssemblyResponse,
)
def update_video_assembly(
    series_id: UUID,
    assembly_id: UUID,
    data: VideoAssemblyUpdate,
    db: DbSession,
) -> VideoAssemblyResponse:
    """Update a video assembly."""
    service = VideoAssemblyService(db)
    try:
        assembly = service.update(str(series_id), str(assembly_id), data)
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except VideoAssemblyError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return assembly


@router.post(
    "/{series_id}/video-assemblies/{assembly_id}/items",
    status_code=201,
    response_model=AssemblyItemResponse,
)
def add_assembly_item(
    series_id: UUID,
    assembly_id: UUID,
    data: AssemblyItemCreate,
    db: DbSession,
) -> AssemblyItemResponse:
    """Add a timeline item to a video assembly."""
    service = VideoAssemblyService(db)
    try:
        item = service.add_item(str(series_id), str(assembly_id), data)
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except AssemblyItemError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return item


@router.get(
    "/{series_id}/video-assemblies/{assembly_id}/items",
    response_model=list[AssemblyItemResponse],
)
def list_assembly_items(
    series_id: UUID,
    assembly_id: UUID,
    db: DbSession,
) -> list[AssemblyItemResponse]:
    """List timeline items for a video assembly."""
    service = VideoAssemblyService(db)
    try:
        return service.list_items(str(series_id), str(assembly_id))
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc


@router.get(
    "/{series_id}/video-assemblies/{assembly_id}/items/{item_id}",
    response_model=AssemblyItemResponse,
)
def get_assembly_item(
    series_id: UUID,
    assembly_id: UUID,
    item_id: UUID,
    db: DbSession,
) -> AssemblyItemResponse:
    """Retrieve a timeline item."""
    service = VideoAssemblyService(db)
    try:
        item = service.get_item(str(series_id), str(assembly_id), str(item_id))
    except AssemblyItemNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return item


@router.patch(
    "/{series_id}/video-assemblies/{assembly_id}/items/{item_id}",
    response_model=AssemblyItemResponse,
)
def update_assembly_item(
    series_id: UUID,
    assembly_id: UUID,
    item_id: UUID,
    data: AssemblyItemUpdate,
    db: DbSession,
) -> AssemblyItemResponse:
    """Update a timeline item."""
    service = VideoAssemblyService(db)
    try:
        item = service.update_item(str(series_id), str(assembly_id), str(item_id), data)
    except (VideoAssemblyNotFoundError, AssemblyItemNotFoundError) as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except AssemblyItemError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return item


@router.delete(
    "/{series_id}/video-assemblies/{assembly_id}/items/{item_id}",
    status_code=204,
)
def remove_assembly_item(
    series_id: UUID,
    assembly_id: UUID,
    item_id: UUID,
    db: DbSession,
) -> None:
    """Remove a timeline item."""
    service = VideoAssemblyService(db)
    try:
        service.remove_item(str(series_id), str(assembly_id), str(item_id))
    except (VideoAssemblyNotFoundError, AssemblyItemNotFoundError) as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    commit_or_409(db)


@router.post(
    "/{series_id}/video-assemblies/{assembly_id}/render",
    response_model=RenderResult,
)
def render_video_assembly(
    series_id: UUID,
    assembly_id: UUID,
    db: DbSession,
    storage: StorageDep,
) -> RenderResult:
    """Render a video assembly to a transient working MP4 using FFmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        output_path = Path(tmp.name)

    renderer = FFmpegVideoRenderer(db, storage)
    try:
        result = renderer.render(str(series_id), str(assembly_id), output_path)
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (
        FFmpegNotAvailableError,
        FFmpegExecutionError,
        InvalidTimelineError,
        MediaNotFoundError,
        RenderOutputError,
        VideoRenderError,
    ) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return result


@router.post(
    "/{series_id}/video-assemblies/{assembly_id}/export",
    response_model=FinalExportResponse,
)
def export_video_assembly(
    series_id: UUID,
    assembly_id: UUID,
    db: DbSession,
    storage: StorageDep,
) -> FinalExportResponse:
    """Render and persist the final MP4 export for a video assembly."""
    settings = get_settings()
    service = FinalExportService(db, storage, settings.storage_backend)
    try:
        assembly = service.export(str(series_id), str(assembly_id))
    except VideoAssemblyNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (FinalExportError, VideoRenderError) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc

    asset = assembly.final_asset
    if asset is None:
        raise AppError("INTERNAL_ERROR", "Final export asset was not created.", status_code=500)

    response = FinalExportResponse(
        assembly=VideoAssemblyResponse.model_validate(assembly),
        asset=AssetResponse.model_validate(asset),
    )
    commit_or_409(db)
    return response
