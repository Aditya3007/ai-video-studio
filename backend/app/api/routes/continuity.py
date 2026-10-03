"""Continuity rules engine API routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.schemas.continuity import (
    ContinuityEvaluationResponse,
    ContinuityShotEvaluationResponse,
)
from app.services.continuity_service import ContinuityNotFoundError, ContinuityService

router = APIRouter(prefix="/series", tags=["continuity"])


@router.get(
    "/{series_id}/episodes/{episode_id}/continuity",
    response_model=ContinuityEvaluationResponse,
)
def evaluate_episode_continuity(
    series_id: UUID,
    episode_id: UUID,
    db: DbSession,
) -> ContinuityEvaluationResponse:
    """Evaluate deterministic continuity rules for an episode."""
    service = ContinuityService(db)
    try:
        findings = service.check_episode(str(series_id), str(episode_id))
    except ContinuityNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return ContinuityEvaluationResponse(
        series_id=series_id,
        episode_id=episode_id,
        findings=findings,
    )


@router.get(
    "/{series_id}/shots/{shot_id}/continuity",
    response_model=ContinuityShotEvaluationResponse,
)
def evaluate_shot_continuity(
    series_id: UUID,
    shot_id: UUID,
    db: DbSession,
) -> ContinuityShotEvaluationResponse:
    """Evaluate deterministic continuity rules for a single shot."""
    service = ContinuityService(db)
    try:
        findings = service.check_shot(str(series_id), str(shot_id))
    except ContinuityNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return ContinuityShotEvaluationResponse(
        series_id=series_id,
        shot_id=shot_id,
        findings=findings,
    )
