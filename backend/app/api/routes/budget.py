"""Episode budget API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.deps import DbSession
from app.api.utils import commit_or_409
from app.services.episode_budget_service import (
    BudgetCheckResult,
    BudgetError,
    BudgetUsage,
    EpisodeBudgetResponse,
    EpisodeBudgetService,
    InvalidBudgetError,
)

router = APIRouter(prefix="/series", tags=["budget"])


def _service(db: DbSession) -> EpisodeBudgetService:
    return EpisodeBudgetService(db)


class BudgetConfigure(BaseModel):
    """Request body for configuring an episode budget."""

    model_config = ConfigDict(from_attributes=True)

    budget_amount: str
    cost_currency: str = "USD"
    active: bool = True
    usage_limits: dict | None = None


class BudgetCheckRequest(BaseModel):
    """Request body for checking a proposed generation against the budget."""

    model_config = ConfigDict(from_attributes=True)

    generation_type: str
    estimated_cost: str = "0"
    cost_currency: str = "USD"
    job_id: str | None = None
    correlation_id: str | None = None


@router.put("/{series_id}/episodes/{episode_id}/budget", response_model=EpisodeBudgetResponse)
def configure_budget(
    db: DbSession,
    series_id: UUID,
    episode_id: UUID,
    request: BudgetConfigure,
) -> EpisodeBudgetResponse:
    """Create or update the generation budget for an Episode."""
    try:
        result = _service(db).configure_budget(
            str(series_id),
            str(episode_id),
            request.budget_amount,
            currency=request.cost_currency,
            active=request.active,
            usage_limits=request.usage_limits,
        )
        commit_or_409(db)
        return result
    except InvalidBudgetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BudgetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{series_id}/episodes/{episode_id}/budget", response_model=EpisodeBudgetResponse)
def get_budget(
    db: DbSession,
    series_id: UUID,
    episode_id: UUID,
) -> EpisodeBudgetResponse:
    """Retrieve the configured generation budget for an Episode."""
    try:
        budget = _service(db).get_budget(str(series_id), str(episode_id))
    except BudgetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not configured.")
    return budget


@router.get("/{series_id}/episodes/{episode_id}/budget/usage", response_model=BudgetUsage)
def get_budget_usage(
    db: DbSession,
    series_id: UUID,
    episode_id: UUID,
) -> BudgetUsage:
    """Retrieve current spend, reservations, and status for an Episode budget."""
    try:
        return _service(db).get_usage(str(series_id), str(episode_id))
    except BudgetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{series_id}/episodes/{episode_id}/budget/check",
    response_model=BudgetCheckResult,
)
def check_budget(
    db: DbSession,
    series_id: UUID,
    episode_id: UUID,
    request: BudgetCheckRequest,
) -> BudgetCheckResult:
    """Check whether a proposed generation is allowed under the Episode budget."""
    try:
        result = _service(db).check_and_reserve(
            str(series_id),
            str(episode_id),
            request.generation_type,
            estimated_cost=request.estimated_cost,
            currency=request.cost_currency,
            job_id=request.job_id,
            correlation_id=request.correlation_id,
        )
        commit_or_409(db)
        return result
    except BudgetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidBudgetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
