"""Generation cost API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.deps import DbSession
from app.models import Episode
from app.services.generation_cost_service import GenerationCostService

router = APIRouter(prefix="/costs", tags=["costs"])


class CostComponentResponse(BaseModel):
    """One usage component returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    quantity: str
    unit: str
    unit_price: str


class GenerationCostResponse(BaseModel):
    """Public cost record representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    episode_id: UUID | None
    generation_type: str
    provider: str
    model: str
    cost_status: str
    cost_currency: str
    total_cost: str
    usage_components: list[CostComponentResponse] | None
    job_id: UUID | None
    asset_id: UUID | None
    request_id: str | None
    recorded_at: datetime | None


class GenerationCostListResponse(BaseModel):
    """List of cost records with a Series-scoped total."""

    total: str
    costs: list[GenerationCostResponse]


def _to_component(data: dict) -> CostComponentResponse:
    return CostComponentResponse(
        name=data["name"],
        quantity=str(data["quantity"]),
        unit=data["unit"],
        unit_price=str(data["unit_price"]),
    )


def _to_response(cost) -> GenerationCostResponse:
    return GenerationCostResponse(
        id=UUID(cost.id),
        series_id=UUID(cost.series_id),
        episode_id=UUID(cost.episode_id) if cost.episode_id else None,
        generation_type=cost.generation_type,
        provider=cost.provider,
        model=cost.model,
        cost_status=cost.cost_status,
        cost_currency=cost.cost_currency,
        total_cost=str(cost.total_cost),
        usage_components=[_to_component(c) for c in (cost.usage_components or [])],
        job_id=UUID(cost.job_id) if cost.job_id else None,
        asset_id=UUID(cost.asset_id) if cost.asset_id else None,
        request_id=cost.request_id,
        recorded_at=cost.recorded_at,
    )


def _service(db: DbSession) -> GenerationCostService:
    return GenerationCostService(db)


@router.get("/{series_id}", response_model=GenerationCostListResponse)
def list_series_costs(
    db: DbSession,
    series_id: UUID,
    generation_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    cost_status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> GenerationCostListResponse:
    """List generation costs for a Series, optionally filtered."""
    service = _service(db)
    costs = service.list_by_series(
        str(series_id),
        generation_type=generation_type,
        provider=provider,
        model=model,
        cost_status=cost_status,
        start=start,
        end=end,
    )
    total = service.get_total_by_series(
        str(series_id),
        generation_type=generation_type,
        cost_status=cost_status,
        start=start,
        end=end,
    )
    return GenerationCostListResponse(total=str(total), costs=[_to_response(c) for c in costs])


@router.get("/{series_id}/episodes/{episode_id}", response_model=GenerationCostListResponse)
def list_episode_costs(
    db: DbSession,
    series_id: UUID,
    episode_id: UUID,
    generation_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    cost_status: str | None = None,
) -> GenerationCostListResponse:
    """List generation costs for an Episode within a Series."""
    episode = db.get(Episode, str(episode_id))
    if not episode or str(episode.series_id) != str(series_id):
        raise HTTPException(status_code=404, detail="Episode not found in this Series.")

    service = _service(db)
    costs = service.list_by_series(
        str(series_id),
        generation_type=generation_type,
        provider=provider,
        model=model,
        cost_status=cost_status,
    )
    costs = [c for c in costs if c.episode_id == str(episode_id)]
    total = service.get_total_by_episode(
        str(series_id),
        str(episode_id),
        generation_type=generation_type,
        cost_status=cost_status,
    )
    return GenerationCostListResponse(total=str(total), costs=[_to_response(c) for c in costs])
