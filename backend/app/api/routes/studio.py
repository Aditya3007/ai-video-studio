"""Studio production workflow backend routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.schemas.studio import (
    StudioEpisodeProductionResponse,
    StudioSceneProductionResponse,
    StudioSeriesOverviewResponse,
    StudioShotProductionResponse,
)
from app.services.studio_service import StudioNotFoundError, StudioService

router = APIRouter(prefix="/series", tags=["studio"])


@router.get("/{series_id}/studio", response_model=StudioSeriesOverviewResponse)
def get_series_studio(series_id: UUID, db: DbSession) -> StudioSeriesOverviewResponse:
    """Return a production overview for a Series."""
    service = StudioService(db)
    try:
        return service.get_series_overview(str(series_id))
    except StudioNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc


@router.get(
    "/{series_id}/episodes/{episode_id}/studio",
    response_model=StudioEpisodeProductionResponse,
)
def get_episode_studio(
    series_id: UUID,
    episode_id: UUID,
    db: DbSession,
) -> StudioEpisodeProductionResponse:
    """Return production state for an Episode."""
    service = StudioService(db)
    try:
        return service.get_episode_production(str(series_id), str(episode_id))
    except StudioNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc


@router.get(
    "/{series_id}/episodes/{episode_id}/scenes/{scene_id}/studio",
    response_model=StudioSceneProductionResponse,
)
def get_scene_studio(
    series_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    db: DbSession,
) -> StudioSceneProductionResponse:
    """Return production state for a Scene."""
    service = StudioService(db)
    try:
        return service.get_scene_production(str(series_id), str(episode_id), str(scene_id))
    except StudioNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc


@router.get(
    "/{series_id}/shots/{shot_id}/studio",
    response_model=StudioShotProductionResponse,
)
def get_shot_studio(
    series_id: UUID,
    shot_id: UUID,
    db: DbSession,
) -> StudioShotProductionResponse:
    """Return production state for a Shot."""
    service = StudioService(db)
    try:
        return service.get_shot_production(str(series_id), str(shot_id))
    except StudioNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
