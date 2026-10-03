"""Location version CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Location, LocationVersion
from app.schemas import (
    LocationVersionCreate,
    LocationVersionResponse,
    LocationVersionUpdate,
    PaginatedResponse,
)

router = APIRouter(prefix="/locations", tags=["location-versions"])


def _get_location(location_id: UUID, db: DbSession) -> Location:
    location = db.get(Location, str(location_id))
    if not location:
        raise AppError("NOT_FOUND", "Location not found.", status_code=404)
    return location


def _get_version(location_id: UUID, version_id: UUID, db: DbSession) -> LocationVersion:
    version = db.get(LocationVersion, str(version_id))
    if not version or version.location_id != str(location_id):
        raise AppError("NOT_FOUND", "Location version not found.", status_code=404)
    return version


@router.post("/{location_id}/versions", status_code=201, response_model=LocationVersionResponse)
def create_location_version(
    location_id: UUID,
    data: LocationVersionCreate,
    db: DbSession,
) -> LocationVersion:
    """Create a version for a location."""
    _get_location(location_id, db)
    existing = db.execute(
        select(LocationVersion).where(
            LocationVersion.location_id == str(location_id),
            LocationVersion.version == data.version,
        )
    ).scalar_one_or_none()
    if existing:
        raise AppError(
            "CONFLICT",
            "Version number already exists for this location.",
            status_code=409,
        )

    payload = data.model_dump(mode="json")
    if payload.get("reference_asset_id"):
        payload["reference_asset_id"] = str(payload["reference_asset_id"])
    version = LocationVersion(location_id=str(location_id), **payload)
    db.add(version)
    commit_or_409(db)
    db.refresh(version)
    return version


@router.get("/{location_id}/versions", response_model=PaginatedResponse[LocationVersionResponse])
def list_location_versions(
    location_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[LocationVersionResponse]:
    """List versions for a location."""
    _get_location(location_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(LocationVersion)
            .where(LocationVersion.location_id == str(location_id))
            .order_by(LocationVersion.version)
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count())
            .select_from(LocationVersion)
            .where(LocationVersion.location_id == str(location_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[LocationVersionResponse](
        items=[LocationVersionResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{location_id}/versions/{version_id}", response_model=LocationVersionResponse)
def get_location_version(
    location_id: UUID,
    version_id: UUID,
    db: DbSession,
) -> LocationVersion:
    """Get a location version."""
    return _get_version(location_id, version_id, db)


@router.patch("/{location_id}/versions/{version_id}", response_model=LocationVersionResponse)
def update_location_version(
    location_id: UUID,
    version_id: UUID,
    data: LocationVersionUpdate,
    db: DbSession,
) -> LocationVersion:
    """Update a location version."""
    version = _get_version(location_id, version_id, db)
    payload = data.model_dump(exclude_unset=True, mode="json")
    if "reference_asset_id" in payload and payload["reference_asset_id"]:
        payload["reference_asset_id"] = str(payload["reference_asset_id"])
    for key, value in payload.items():
        setattr(version, key, value)
    commit_or_409(db)
    db.refresh(version)
    return version


@router.delete("/{location_id}/versions/{version_id}", status_code=204)
def delete_location_version(
    location_id: UUID,
    version_id: UUID,
    db: DbSession,
) -> None:
    """Delete a location version."""
    version = _get_version(location_id, version_id, db)
    db.delete(version)
    commit_or_409(db)
