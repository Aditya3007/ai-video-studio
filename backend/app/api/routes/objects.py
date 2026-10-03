"""StoryObject CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Series, StoryObject
from app.schemas import PaginatedResponse, StoryObjectCreate, StoryObjectResponse, StoryObjectUpdate

router = APIRouter(prefix="/series", tags=["objects"])


def _assert_series_exists(series_id: UUID, db: DbSession) -> None:
    if not db.get(Series, str(series_id)):
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)


def _get_object(series_id: UUID, object_id: UUID, db: DbSession) -> StoryObject:
    obj = db.get(StoryObject, str(object_id))
    if not obj or obj.series_id != str(series_id):
        raise AppError("NOT_FOUND", "Object not found.", status_code=404)
    return obj


@router.post("/{series_id}/objects", status_code=201, response_model=StoryObjectResponse)
def create_object(series_id: UUID, data: StoryObjectCreate, db: DbSession) -> StoryObject:
    """Create an object within a series."""
    _assert_series_exists(series_id, db)
    obj = StoryObject(series_id=str(series_id), **data.model_dump(mode="json"))
    db.add(obj)
    commit_or_409(db)
    db.refresh(obj)
    return obj


@router.get("/{series_id}/objects", response_model=PaginatedResponse[StoryObjectResponse])
def list_objects(
    series_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[StoryObjectResponse]:
    """List objects in a series."""
    _assert_series_exists(series_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(StoryObject)
            .where(StoryObject.series_id == str(series_id))
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count())
            .select_from(StoryObject)
            .where(StoryObject.series_id == str(series_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[StoryObjectResponse](
        items=[StoryObjectResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{series_id}/objects/{object_id}", response_model=StoryObjectResponse)
def get_object(series_id: UUID, object_id: UUID, db: DbSession) -> StoryObject:
    """Get an object by ID within a series."""
    return _get_object(series_id, object_id, db)


@router.patch("/{series_id}/objects/{object_id}", response_model=StoryObjectResponse)
def update_object(
    series_id: UUID,
    object_id: UUID,
    data: StoryObjectUpdate,
    db: DbSession,
) -> StoryObject:
    """Update an object."""
    obj = _get_object(series_id, object_id, db)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(obj, key, value)
    commit_or_409(db)
    db.refresh(obj)
    return obj


@router.delete("/{series_id}/objects/{object_id}", status_code=204)
def delete_object(series_id: UUID, object_id: UUID, db: DbSession) -> None:
    """Delete an object."""
    obj = _get_object(series_id, object_id, db)
    db.delete(obj)
    commit_or_409(db)
