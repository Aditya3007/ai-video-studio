"""World CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Series, World
from app.schemas import WorldCreate, WorldResponse, WorldUpdate

router = APIRouter(tags=["worlds"])


@router.post("/series/{series_id}/world", status_code=201, response_model=WorldResponse)
def create_world(series_id: UUID, data: WorldCreate, db: DbSession) -> World:
    """Create the world for a series."""
    series = db.get(Series, str(series_id))
    if not series:
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)

    existing = db.execute(
        select(World).where(World.series_id == str(series_id))
    ).scalar_one_or_none()
    if existing:
        raise AppError("CONFLICT", "A world already exists for this series.", status_code=409)

    world = World(series_id=str(series_id), **data.model_dump(mode="json"))
    db.add(world)
    commit_or_409(db)
    db.refresh(world)
    return world


@router.get("/series/{series_id}/world", response_model=WorldResponse)
def get_world_by_series(series_id: UUID, db: DbSession) -> World:
    """Get the world associated with a series."""
    series = db.get(Series, str(series_id))
    if not series:
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)

    world = db.execute(select(World).where(World.series_id == str(series_id))).scalar_one_or_none()
    if not world:
        raise AppError("NOT_FOUND", "World not found for this series.", status_code=404)
    return world


@router.get("/worlds/{world_id}", response_model=WorldResponse)
def get_world(world_id: UUID, db: DbSession) -> World:
    """Get a world by ID."""
    world = db.get(World, str(world_id))
    if not world:
        raise AppError("NOT_FOUND", "World not found.", status_code=404)
    return world


@router.patch("/worlds/{world_id}", response_model=WorldResponse)
def update_world(world_id: UUID, data: WorldUpdate, db: DbSession) -> World:
    """Update a world."""
    world = db.get(World, str(world_id))
    if not world:
        raise AppError("NOT_FOUND", "World not found.", status_code=404)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(world, key, value)
    commit_or_409(db)
    db.refresh(world)
    return world


@router.delete("/worlds/{world_id}", status_code=204)
def delete_world(world_id: UUID, db: DbSession) -> None:
    """Delete a world."""
    world = db.get(World, str(world_id))
    if not world:
        raise AppError("NOT_FOUND", "World not found.", status_code=404)
    db.delete(world)
    commit_or_409(db)
