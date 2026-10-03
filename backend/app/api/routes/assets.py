"""Asset CRUD routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Asset, Series
from app.schemas import AssetCreate, AssetResponse, AssetUpdate, PaginatedResponse
from app.services.asset_service import AssetError, AssetNotFoundError, AssetService

router = APIRouter(prefix="/series", tags=["assets"])


def _assert_series_exists(series_id: UUID, db: DbSession) -> None:
    if not db.get(Series, str(series_id)):
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)


@router.post("/{series_id}/assets", status_code=201, response_model=AssetResponse)
def create_asset(series_id: UUID, data: AssetCreate, db: DbSession) -> Asset:
    """Create an asset within a series."""
    _assert_series_exists(series_id, db)
    try:
        asset = AssetService(db).create_asset(str(series_id), data)
    except AssetNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except AssetError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return asset


@router.get("/{series_id}/assets", response_model=PaginatedResponse[AssetResponse])
def list_assets(
    series_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
    asset_type: str | None = None,
) -> PaginatedResponse[AssetResponse]:
    """List assets in a series."""
    _assert_series_exists(series_id, db)
    limit = min(limit, 100)
    items, total = AssetService(db).list_assets(
        str(series_id), limit=limit, offset=offset, asset_type=asset_type
    )
    return PaginatedResponse[AssetResponse](
        items=[AssetResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{series_id}/assets/{asset_id}", response_model=AssetResponse)
def get_asset(series_id: UUID, asset_id: UUID, db: DbSession) -> Asset:
    """Get an asset within a series."""
    try:
        return AssetService(db).get_asset(str(series_id), str(asset_id))
    except AssetNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc


@router.patch("/{series_id}/assets/{asset_id}", response_model=AssetResponse)
def update_asset(
    series_id: UUID,
    asset_id: UUID,
    data: AssetUpdate,
    db: DbSession,
) -> Asset:
    """Update an asset within a series."""
    try:
        asset = AssetService(db).update_asset(str(series_id), str(asset_id), data)
    except AssetNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except AssetError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return asset


@router.delete("/{series_id}/assets/{asset_id}", status_code=204)
def delete_asset(series_id: UUID, asset_id: UUID, db: DbSession) -> None:
    """Delete an asset within a series."""
    try:
        AssetService(db).delete_asset(str(series_id), str(asset_id))
    except AssetNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    commit_or_409(db)
