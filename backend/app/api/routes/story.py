"""Story intake and version routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.schemas import (
    PaginatedResponse,
    StoryCreate,
    StoryResponse,
    StoryUpdate,
    StoryVersionCreate,
    StoryVersionResponse,
)
from app.services.story import StoryNotFoundError, StoryService

router = APIRouter(prefix="/series/{series_id}/stories", tags=["stories"])


def _service(db: DbSession) -> StoryService:
    return StoryService(db)


@router.post("", status_code=201, response_model=StoryResponse)
def create_story(series_id: UUID, data: StoryCreate, db: DbSession) -> "StoryResponse":
    """Create a story and its initial version 1."""
    try:
        story = _service(db).create(str(series_id), data)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    commit_or_409(db)
    db.refresh(story)
    return story


@router.get("", response_model=PaginatedResponse[StoryResponse])
def list_stories(
    series_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[StoryResponse]:
    """List stories for a series."""
    try:
        items, total = _service(db).list_stories(str(series_id), limit, offset)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return PaginatedResponse[StoryResponse](
        items=[StoryResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(series_id: UUID, story_id: UUID, db: DbSession) -> "StoryResponse":
    """Get a story by ID."""
    try:
        story = _service(db).get_story(str(series_id), str(story_id))
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return story


@router.patch("/{story_id}", response_model=StoryResponse)
def update_story(
    series_id: UUID, story_id: UUID, data: StoryUpdate, db: DbSession
) -> "StoryResponse":
    """Update mutable story metadata."""
    try:
        story = _service(db).update(str(series_id), str(story_id), data)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    commit_or_409(db)
    db.refresh(story)
    return story


@router.delete("/{story_id}", status_code=204)
def delete_story(series_id: UUID, story_id: UUID, db: DbSession) -> None:
    """Delete a story and its versions."""
    try:
        story = _service(db).delete(str(series_id), str(story_id))
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    db.delete(story)
    commit_or_409(db)


@router.post("/{story_id}/versions", status_code=201, response_model=StoryVersionResponse)
def create_version(
    series_id: UUID, story_id: UUID, data: StoryVersionCreate, db: DbSession
) -> StoryVersionResponse:
    """Create a new story version."""
    try:
        version = _service(db).create_version(str(series_id), str(story_id), data)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    commit_or_409(db)
    db.refresh(version)
    return version


@router.get("/{story_id}/versions", response_model=PaginatedResponse[StoryVersionResponse])
def list_versions(
    series_id: UUID,
    story_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[StoryVersionResponse]:
    """List versions for a story."""
    try:
        items, total = _service(db).list_versions(str(series_id), str(story_id), limit, offset)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return PaginatedResponse[StoryVersionResponse](
        items=[StoryVersionResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{story_id}/versions/{version_id}", response_model=StoryVersionResponse)
def get_version(
    series_id: UUID, story_id: UUID, version_id: UUID, db: DbSession
) -> StoryVersionResponse:
    """Get a story version by ID."""
    try:
        version = _service(db).get_version(str(series_id), str(story_id), str(version_id))
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return version
