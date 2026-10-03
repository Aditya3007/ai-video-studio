"""Shot CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Scene, Shot, ShotSpecification
from app.schemas import (
    PaginatedResponse,
    ShotCreate,
    ShotResponse,
    ShotSpecificationCreate,
    ShotSpecificationResponse,
    ShotSpecificationUpdate,
    ShotUpdate,
)

router = APIRouter(prefix="/scenes", tags=["shots"])


def _get_scene(scene_id: UUID, db: DbSession) -> Scene:
    scene = db.get(Scene, str(scene_id))
    if not scene:
        raise AppError("NOT_FOUND", "Scene not found.", status_code=404)
    return scene


def _get_shot(scene_id: UUID, shot_id: UUID, db: DbSession) -> Shot:
    shot = db.get(Shot, str(shot_id))
    if not shot or shot.scene_id != str(scene_id):
        raise AppError("NOT_FOUND", "Shot not found.", status_code=404)
    return shot


@router.post("/{scene_id}/shots", status_code=201, response_model=ShotResponse)
def create_shot(scene_id: UUID, data: ShotCreate, db: DbSession) -> Shot:
    """Create a shot within a scene."""
    _get_scene(scene_id, db)
    shot = Shot(scene_id=str(scene_id), **data.model_dump(mode="json"))
    db.add(shot)
    commit_or_409(db)
    db.refresh(shot)
    return shot


@router.get("/{scene_id}/shots", response_model=PaginatedResponse[ShotResponse])
def list_shots(
    scene_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[ShotResponse]:
    """List shots in a scene."""
    _get_scene(scene_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(Shot)
            .where(Shot.scene_id == str(scene_id))
            .order_by(Shot.sequence_order, Shot.shot_number)
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count()).select_from(Shot).where(Shot.scene_id == str(scene_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[ShotResponse](
        items=[ShotResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{scene_id}/shots/{shot_id}", response_model=ShotResponse)
def get_shot(scene_id: UUID, shot_id: UUID, db: DbSession) -> Shot:
    """Get a shot by ID within a scene."""
    return _get_shot(scene_id, shot_id, db)


@router.patch("/{scene_id}/shots/{shot_id}", response_model=ShotResponse)
def update_shot(
    scene_id: UUID,
    shot_id: UUID,
    data: ShotUpdate,
    db: DbSession,
) -> Shot:
    """Update a shot."""
    shot = _get_shot(scene_id, shot_id, db)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(shot, key, value)
    commit_or_409(db)
    db.refresh(shot)
    return shot


@router.delete("/{scene_id}/shots/{shot_id}", status_code=204)
def delete_shot(scene_id: UUID, shot_id: UUID, db: DbSession) -> None:
    """Delete a shot."""
    shot = _get_shot(scene_id, shot_id, db)
    db.delete(shot)
    commit_or_409(db)


@router.post(
    "/{scene_id}/shots/{shot_id}/specification",
    status_code=201,
    response_model=ShotSpecificationResponse,
)
def create_shot_specification(
    scene_id: UUID,
    shot_id: UUID,
    data: ShotSpecificationCreate,
    db: DbSession,
) -> ShotSpecification:
    """Create a provider-neutral specification for a shot."""
    _get_shot(scene_id, shot_id, db)
    spec = ShotSpecification(shot_id=str(shot_id), **data.model_dump(mode="json"))
    db.add(spec)
    commit_or_409(db)
    db.refresh(spec)
    return spec


@router.get(
    "/{scene_id}/shots/{shot_id}/specification",
    response_model=ShotSpecificationResponse,
)
def get_shot_specification(scene_id: UUID, shot_id: UUID, db: DbSession) -> ShotSpecification:
    """Get a shot's specification."""
    shot = _get_shot(scene_id, shot_id, db)
    if shot.specification is None:
        raise AppError("NOT_FOUND", "Shot specification not found.", status_code=404)
    return shot.specification


@router.patch(
    "/{scene_id}/shots/{shot_id}/specification",
    response_model=ShotSpecificationResponse,
)
def update_shot_specification(
    scene_id: UUID,
    shot_id: UUID,
    data: ShotSpecificationUpdate,
    db: DbSession,
) -> ShotSpecification:
    """Update a shot's specification."""
    shot = _get_shot(scene_id, shot_id, db)
    if shot.specification is None:
        raise AppError("NOT_FOUND", "Shot specification not found.", status_code=404)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(shot.specification, key, value)
    commit_or_409(db)
    db.refresh(shot.specification)
    return shot.specification
