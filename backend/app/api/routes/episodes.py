"""Episode CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Episode, Series
from app.schemas import (
    EpisodeCreate,
    EpisodePlanResponse,
    EpisodeResponse,
    EpisodeUpdate,
    PaginatedResponse,
    ScenePlanResponse,
)
from app.services.episode_planning import (
    EpisodeNotFoundError as PlanningEpisodeNotFoundError,
)
from app.services.episode_planning import (
    EpisodePlanningError,
    EpisodePlanningService,
)
from app.services.shot_planning import (
    SceneNotFoundError as PlanningSceneNotFoundError,
)
from app.services.shot_planning import (
    ShotPlanningError,
    ShotPlanningService,
)

router = APIRouter(prefix="/series", tags=["episodes"])


def _assert_series_exists(series_id: UUID, db: DbSession) -> None:
    if not db.get(Series, str(series_id)):
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)


def _get_episode(series_id: UUID, episode_id: UUID, db: DbSession) -> Episode:
    episode = db.get(Episode, str(episode_id))
    if not episode or episode.series_id != str(series_id):
        raise AppError("NOT_FOUND", "Episode not found.", status_code=404)
    return episode


@router.post("/{series_id}/episodes", status_code=201, response_model=EpisodeResponse)
def create_episode(series_id: UUID, data: EpisodeCreate, db: DbSession) -> Episode:
    """Create an episode within a series."""
    _assert_series_exists(series_id, db)
    payload = data.model_dump(mode="json")
    episode = Episode(series_id=str(series_id), **payload)
    db.add(episode)
    commit_or_409(db)
    db.refresh(episode)
    return episode


@router.get("/{series_id}/episodes", response_model=PaginatedResponse[EpisodeResponse])
def list_episodes(
    series_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[EpisodeResponse]:
    """List episodes in a series."""
    _assert_series_exists(series_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(Episode).where(Episode.series_id == str(series_id)).offset(offset).limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count()).select_from(Episode).where(Episode.series_id == str(series_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[EpisodeResponse](
        items=[EpisodeResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{series_id}/episodes/{episode_id}", response_model=EpisodeResponse)
def get_episode(series_id: UUID, episode_id: UUID, db: DbSession) -> Episode:
    """Get an episode by ID within a series."""
    return _get_episode(series_id, episode_id, db)


@router.patch("/{series_id}/episodes/{episode_id}", response_model=EpisodeResponse)
def update_episode(
    series_id: UUID,
    episode_id: UUID,
    data: EpisodeUpdate,
    db: DbSession,
) -> Episode:
    """Update an episode."""
    episode = _get_episode(series_id, episode_id, db)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(episode, key, value)
    commit_or_409(db)
    db.refresh(episode)
    return episode


@router.delete("/{series_id}/episodes/{episode_id}", status_code=204)
def delete_episode(series_id: UUID, episode_id: UUID, db: DbSession) -> None:
    """Delete an episode and its scenes/shots."""
    episode = _get_episode(series_id, episode_id, db)
    db.delete(episode)
    commit_or_409(db)


@router.post(
    "/{series_id}/episodes/{episode_id}/plan-scenes",
    status_code=201,
    response_model=EpisodePlanResponse,
)
def plan_scenes(
    series_id: UUID,
    episode_id: UUID,
    db: DbSession,
    replace: bool = False,
) -> EpisodePlanResponse:
    """Generate a deterministic scene breakdown for an episode."""
    _assert_series_exists(series_id, db)
    try:
        result = EpisodePlanningService(db).plan_and_create(
            str(series_id), str(episode_id), replace=replace
        )
    except PlanningEpisodeNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except EpisodePlanningError as exc:
        raise AppError("CONFLICT", str(exc), status_code=409) from exc
    commit_or_409(db)
    return result


@router.post(
    "/{series_id}/episodes/{episode_id}/scenes/{scene_id}/plan-shots",
    status_code=201,
    response_model=ScenePlanResponse,
)
def plan_shots(
    series_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    db: DbSession,
    replace: bool = False,
) -> ScenePlanResponse:
    """Generate a deterministic shot breakdown for a scene."""
    _assert_series_exists(series_id, db)
    try:
        result = ShotPlanningService(db).plan_and_create(
            str(series_id), str(episode_id), str(scene_id), replace=replace
        )
    except PlanningSceneNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except ShotPlanningError as exc:
        raise AppError("CONFLICT", str(exc), status_code=409) from exc
    commit_or_409(db)
    return result
