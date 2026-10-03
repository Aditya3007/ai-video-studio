"""Location CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Location, Series
from app.schemas import LocationCreate, LocationResponse, LocationUpdate, PaginatedResponse

router = APIRouter(prefix="/series", tags=["locations"])


def _assert_series_exists(series_id: UUID, db: DbSession) -> None:
    if not db.get(Series, str(series_id)):
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)


def _get_location(series_id: UUID, location_id: UUID, db: DbSession) -> Location:
    location = db.get(Location, str(location_id))
    if not location or location.series_id != str(series_id):
        raise AppError("NOT_FOUND", "Location not found.", status_code=404)
    return location


@router.post("/{series_id}/locations", status_code=201, response_model=LocationResponse)
def create_location(series_id: UUID, data: LocationCreate, db: DbSession) -> Location:
    """Create a location within a series."""
    _assert_series_exists(series_id, db)
    location = Location(series_id=str(series_id), **data.model_dump(mode="json"))
    db.add(location)
    commit_or_409(db)
    db.refresh(location)
    return location


@router.get("/{series_id}/locations", response_model=PaginatedResponse[LocationResponse])
def list_locations(
    series_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[LocationResponse]:
    """List locations in a series."""
    _assert_series_exists(series_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(Location).where(Location.series_id == str(series_id)).offset(offset).limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count()).select_from(Location).where(Location.series_id == str(series_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[LocationResponse](
        items=[LocationResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{series_id}/locations/{location_id}", response_model=LocationResponse)
def get_location(series_id: UUID, location_id: UUID, db: DbSession) -> Location:
    """Get a location by ID within a series."""
    return _get_location(series_id, location_id, db)


@router.patch("/{series_id}/locations/{location_id}", response_model=LocationResponse)
def update_location(
    series_id: UUID,
    location_id: UUID,
    data: LocationUpdate,
    db: DbSession,
) -> Location:
    """Update a location."""
    location = _get_location(series_id, location_id, db)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(location, key, value)
    commit_or_409(db)
    db.refresh(location)
    return location


@router.delete("/{series_id}/locations/{location_id}", status_code=204)
def delete_location(series_id: UUID, location_id: UUID, db: DbSession) -> None:
    """Delete a location and its versions."""
    location = _get_location(series_id, location_id, db)
    db.delete(location)
    commit_or_409(db)
