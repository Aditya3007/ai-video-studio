"""QA workflow orchestration routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.schemas.qa_workflow import QAWorkflowRequest, QAWorkflowResponse
from app.services.ai_qa_service import AIQAProviderError, AIQAValidationError
from app.services.qa_workflow_service import (
    QAWorkflowNotFoundError,
    QAWorkflowService,
)

router = APIRouter(prefix="/series", tags=["qa-workflow"])


@router.post(
    "/{series_id}/episodes/{episode_id}/qa-workflow",
    response_model=QAWorkflowResponse,
)
def evaluate_episode_workflow(
    series_id: UUID,
    episode_id: UUID,
    request: QAWorkflowRequest,
    db: DbSession,
) -> QAWorkflowResponse:
    """Run deterministic continuity + optional AI QA for an episode."""
    service = QAWorkflowService(db)
    try:
        return service.evaluate_episode(str(series_id), str(episode_id), request.ai_modes)
    except QAWorkflowNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (AIQAProviderError, AIQAValidationError) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc


@router.post(
    "/{series_id}/shots/{shot_id}/qa-workflow",
    response_model=QAWorkflowResponse,
)
def evaluate_shot_workflow(
    series_id: UUID,
    shot_id: UUID,
    request: QAWorkflowRequest,
    db: DbSession,
) -> QAWorkflowResponse:
    """Run deterministic continuity + optional AI QA for a shot."""
    service = QAWorkflowService(db)
    try:
        return service.evaluate_shot(str(series_id), str(shot_id), request.ai_modes)
    except QAWorkflowNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except (AIQAProviderError, AIQAValidationError) as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
