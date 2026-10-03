"""Unit economics / monetization analytics API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import DbSession
from app.services.unit_economics_service import (
    EconomicsFilter,
    EpisodeEconomicsResponse,
    SeriesEconomicsResponse,
    UnitEconomicsService,
)

router = APIRouter(prefix="/series", tags=["economics"])


def _filter(
    generation_type: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> EconomicsFilter:
    return EconomicsFilter(
        generation_type=generation_type,
        provider=provider,
        model=model_name,
        start=start,
        end=end,
    )


@router.get("/{series_id}/economics", response_model=SeriesEconomicsResponse)
def get_series_economics(
    db: DbSession,
    series_id: UUID,
    filters: EconomicsFilter = Depends(_filter),
) -> SeriesEconomicsResponse:
    """Return cost-side unit economics for a Series."""
    try:
        return UnitEconomicsService(db).get_series_economics(str(series_id), filters)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{series_id}/episodes/{episode_id}/economics", response_model=EpisodeEconomicsResponse)
def get_episode_economics(
    db: DbSession,
    series_id: UUID,
    episode_id: UUID,
    filters: EconomicsFilter = Depends(_filter),
) -> EpisodeEconomicsResponse:
    """Return cost-side unit economics for an Episode."""
    try:
        return UnitEconomicsService(db).get_episode_economics(
            str(series_id), str(episode_id), filters
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
