"""Scene CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Episode, Location, Scene
from app.schemas import PaginatedResponse, SceneCreate, SceneResponse, SceneUpdate

router = APIRouter(prefix="/episodes", tags=["scenes"])


def _get_episode(episode_id: UUID, db: DbSession) -> Episode:
    episode = db.get(Episode, str(episode_id))
    if not episode:
        raise AppError("NOT_FOUND", "Episode not found.", status_code=404)
    return episode


def _get_scene(episode_id: UUID, scene_id: UUID, db: DbSession) -> Scene:
    scene = db.get(Scene, str(scene_id))
    if not scene or scene.episode_id != str(episode_id):
        raise AppError("NOT_FOUND", "Scene not found.", status_code=404)
    return scene


def _validate_location(location_id: UUID | None, series_id: str, db: DbSession) -> None:
    if not location_id:
        return
    location = db.get(Location, str(location_id))
    if not location or location.series_id != series_id:
        raise AppError("NOT_FOUND", "Location not found.", status_code=404)


@router.post("/{episode_id}/scenes", status_code=201, response_model=SceneResponse)
def create_scene(episode_id: UUID, data: SceneCreate, db: DbSession) -> Scene:
    """Create a scene within an episode."""
    episode = _get_episode(episode_id, db)
    _validate_location(data.location_id, episode.series_id, db)
    payload = data.model_dump(mode="json")
    scene = Scene(episode_id=str(episode_id), **payload)
    db.add(scene)
    commit_or_409(db)
    db.refresh(scene)
    return scene


@router.get("/{episode_id}/scenes", response_model=PaginatedResponse[SceneResponse])
def list_scenes(
    episode_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[SceneResponse]:
    """List scenes in an episode."""
    _get_episode(episode_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(Scene)
            .where(Scene.episode_id == str(episode_id))
            .order_by(Scene.sequence_order, Scene.scene_number)
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count()).select_from(Scene).where(Scene.episode_id == str(episode_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[SceneResponse](
        items=[SceneResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{episode_id}/scenes/{scene_id}", response_model=SceneResponse)
def get_scene(episode_id: UUID, scene_id: UUID, db: DbSession) -> Scene:
    """Get a scene by ID within an episode."""
    return _get_scene(episode_id, scene_id, db)


@router.patch("/{episode_id}/scenes/{scene_id}", response_model=SceneResponse)
def update_scene(
    episode_id: UUID,
    scene_id: UUID,
    data: SceneUpdate,
    db: DbSession,
) -> Scene:
    """Update a scene."""
    scene = _get_scene(episode_id, scene_id, db)
    payload = data.model_dump(exclude_unset=True, mode="json")
    if "location_id" in payload:
        _validate_location(payload.get("location_id"), scene.episode.series_id, db)
    for key, value in payload.items():
        setattr(scene, key, value)
    commit_or_409(db)
    db.refresh(scene)
    return scene


@router.delete("/{episode_id}/scenes/{scene_id}", status_code=204)
def delete_scene(episode_id: UUID, scene_id: UUID, db: DbSession) -> None:
    """Delete a scene and its shots."""
    scene = _get_scene(episode_id, scene_id, db)
    db.delete(scene)
    commit_or_409(db)
