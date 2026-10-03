"""AI visual/narrative QA routes."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.errors import AppError
from app.models.enums import AIQAMode
from app.schemas.ai_qa import AIQAResponse
from app.services.ai_qa_service import (
    AIQANotFoundError,
    AIQAProviderError,
    AIQAService,
    AIQAValidationError,
)

router = APIRouter(prefix="/series", tags=["ai-qa"])


@router.get(
    "/{series_id}/episodes/{episode_id}/qa",
    response_model=AIQAResponse,
)
def evaluate_episode_qa(
    series_id: UUID,
    episode_id: UUID,
    db: DbSession,
    mode: AIQAMode = Query(...),
) -> AIQAResponse:
    """Run AI visual/narrative QA for an episode."""
    service = AIQAService(db)
    try:
        return service.evaluate_episode(str(series_id), str(episode_id), mode)
    except AIQANotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (AIQAProviderError, AIQAValidationError) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc


@router.get(
    "/{series_id}/shots/{shot_id}/qa",
    response_model=AIQAResponse,
)
def evaluate_shot_qa(
    series_id: UUID,
    shot_id: UUID,
    db: DbSession,
    mode: AIQAMode = Query(...),
) -> AIQAResponse:
    """Run AI visual/narrative QA for a shot."""
    service = AIQAService(db)
    try:
        return service.evaluate_shot(str(series_id), str(shot_id), mode)
    except AIQANotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (AIQAProviderError, AIQAValidationError) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
