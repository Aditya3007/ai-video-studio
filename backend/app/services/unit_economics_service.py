"""Unit economics / monetization analytics service for P14-T03."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func

from app.models import BudgetReservation, Episode, EpisodeBudget, GenerationCost, Series
from app.models.enums import BudgetReservationStatus
from app.services.episode_budget_service import EpisodeBudgetService
from app.services.generation_cost_service import GenerationCostService


class EconomicsFilter(BaseModel):
    """Optional filters for cost-side analytics queries."""

    model_config = ConfigDict(from_attributes=True)

    generation_type: str | None = None
    provider: str | None = None
    model: str | None = None
    start: datetime | None = None
    end: datetime | None = None


class CostBreakdown(BaseModel):
    """Cost and count for a single dimension value."""

    model_config = ConfigDict(from_attributes=True)

    value: str
    total_cost: str
    generation_count: int


class EpisodeSummary(BaseModel):
    """Economics summary for one episode."""

    model_config = ConfigDict(from_attributes=True)

    episode_id: str
    title: str
    actual_spend: str
    generation_count: int
    budget_amount: str | None
    budget_currency: str | None
    budget_status: str
    remaining_budget: str | None
    utilization: str


class SeriesEconomicsResponse(BaseModel):
    """Provider-neutral unit economics view of a Series."""

    model_config = ConfigDict(from_attributes=True)

    series_id: str
    total_actual_cost: str
    generation_count: int
    episode_count: int
    average_cost_per_generation: str
    cost_by_generation_type: list[CostBreakdown]
    cost_by_provider: list[CostBreakdown]
    cost_by_model: list[CostBreakdown]
    total_configured_budget: str
    total_actual_spend: str
    total_reserved: str
    total_remaining_budget: str
    budget_utilization: str
    budget_currency: str | None
    episode_summaries: list[EpisodeSummary]


class EpisodeEconomicsResponse(BaseModel):
    """Provider-neutral unit economics view of an Episode."""

    model_config = ConfigDict(from_attributes=True)

    series_id: str
    episode_id: str
    title: str
    actual_spend: str
    generation_count: int
    average_cost_per_generation: str
    cost_by_generation_type: list[CostBreakdown]
    cost_by_provider: list[CostBreakdown]
    cost_by_model: list[CostBreakdown]
    generation_count_by_type: dict[str, int]
    budget_amount: str | None
    budget_currency: str | None
    budget_status: str
    active_reservation: str
    remaining_budget: str | None
    available_budget: str | None
    utilization: str
    usage_limits: dict | None


class UnitEconomicsService:
    """Derives cost-side unit economics from existing P14-T01/T02 data."""

    def __init__(self, db) -> None:
        self._db = db
        self._costs = GenerationCostService(db)
        self._budgets = EpisodeBudgetService(db)

    @staticmethod
    def _to_decimal(value) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _format(value: Decimal | int | str | None) -> str:
        if value is None:
            return "0"
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return format(value.normalize(), "f")

    @staticmethod
    def _build_breakdown(costs: list[GenerationCost], key_attr: str) -> list[CostBreakdown]:
        totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        counts: dict[str, int] = defaultdict(int)
        for cost in costs:
            key = getattr(cost, key_attr, None)
            if not key:
                continue
            totals[key] += cost.total_cost or Decimal("0")
            counts[key] += 1
        return [
            CostBreakdown(
                value=key,
                total_cost=UnitEconomicsService._format(totals[key]),
                generation_count=counts[key],
            )
            for key in sorted(totals.keys())
        ]

    def _query_costs(
        self,
        series_id: str,
        episode_id: str | None = None,
        filters: EconomicsFilter | None = None,
    ) -> list[GenerationCost]:
        query = self._db.query(GenerationCost).filter(GenerationCost.series_id == series_id)
        if episode_id:
            query = query.filter(GenerationCost.episode_id == episode_id)
        if filters:
            if filters.generation_type:
                query = query.filter(GenerationCost.generation_type == filters.generation_type)
            if filters.provider:
                query = query.filter(GenerationCost.provider == filters.provider)
            if filters.model:
                query = query.filter(GenerationCost.model == filters.model)
            if filters.start:
                query = query.filter(GenerationCost.recorded_at >= filters.start)
            if filters.end:
                query = query.filter(GenerationCost.recorded_at <= filters.end)
        return query.order_by(GenerationCost.recorded_at.desc()).all()

    def _assert_series(self, series_id: str) -> Series:
        series = self._db.get(Series, str(series_id))
        if not series:
            raise ValueError("Series not found.")
        return series

    def _assert_episode(self, series_id: str, episode_id: str) -> Episode:
        episode = self._db.get(Episode, str(episode_id))
        if not episode or str(episode.series_id) != str(series_id):
            raise ValueError("Episode not found in this Series.")
        return episode

    def _series_budget_totals(self, series_id: str) -> tuple[Decimal, Decimal, Decimal, str | None]:
        budgets = (
            self._db.query(EpisodeBudget)
            .filter(EpisodeBudget.series_id == series_id, EpisodeBudget.active.is_(True))
            .all()
        )
        if not budgets:
            return Decimal("0"), Decimal("0"), Decimal("0"), None
        currency = budgets[0].cost_currency
        total_budget = sum(b.budget_amount for b in budgets)
        reserved = (
            self._db.query(func.sum(BudgetReservation.estimated_cost))
            .filter(
                BudgetReservation.series_id == series_id,
                BudgetReservation.status == BudgetReservationStatus.RESERVED.value,
            )
            .scalar()
        )
        reserved = self._to_decimal(reserved)
        return total_budget, Decimal("0"), reserved, currency

    def get_series_economics(
        self,
        series_id: str,
        filters: EconomicsFilter | None = None,
    ) -> SeriesEconomicsResponse:
        """Return cost-side unit economics for a Series."""
        series = self._assert_series(series_id)
        costs = self._query_costs(series_id, filters=filters)
        total_cost = sum((c.total_cost or Decimal("0") for c in costs), Decimal("0"))
        count = len(costs)
        episodes_with_costs = {c.episode_id for c in costs if c.episode_id}

        total_budget, _, total_reserved, budget_currency = self._series_budget_totals(series_id)
        # Actual spend in the analytics view is the filtered cost total.
        total_actual_spend = total_cost
        total_remaining = total_budget - total_actual_spend - total_reserved
        if total_remaining < 0:
            total_remaining = Decimal("0")
        budget_utilization = (
            (total_actual_spend / total_budget).quantize(Decimal("0.0001"))
            if total_budget > 0
            else Decimal("0")
        )

        # Per-episode summaries for all episodes in the series.
        episodes = (
            self._db.query(Episode)
            .filter(Episode.series_id == series_id)
            .order_by(Episode.episode_number)
            .all()
        )
        summaries = []
        for episode in episodes:
            ep_costs = self._query_costs(series_id, episode_id=episode.id, filters=filters)
            ep_spend = sum((c.total_cost or Decimal("0") for c in ep_costs), Decimal("0"))
            ep_count = len(ep_costs)
            usage = self._budgets.get_usage(series_id, episode.id)
            summaries.append(
                EpisodeSummary(
                    episode_id=episode.id,
                    title=episode.title,
                    actual_spend=self._format(ep_spend),
                    generation_count=ep_count,
                    budget_amount=usage.budget,
                    budget_currency=usage.currency,
                    budget_status=usage.status,
                    remaining_budget=usage.remaining,
                    utilization=usage.utilization,
                )
            )

        return SeriesEconomicsResponse(
            series_id=str(series.id),
            total_actual_cost=self._format(total_cost),
            generation_count=count,
            episode_count=len(episodes_with_costs),
            average_cost_per_generation=self._format(total_cost / count) if count > 0 else "0",
            cost_by_generation_type=self._build_breakdown(costs, "generation_type"),
            cost_by_provider=self._build_breakdown(costs, "provider"),
            cost_by_model=self._build_breakdown(costs, "model"),
            total_configured_budget=self._format(total_budget),
            total_actual_spend=self._format(total_actual_spend),
            total_reserved=self._format(total_reserved),
            total_remaining_budget=self._format(total_remaining),
            budget_utilization=self._format(budget_utilization),
            budget_currency=budget_currency,
            episode_summaries=summaries,
        )

    def get_episode_economics(
        self,
        series_id: str,
        episode_id: str,
        filters: EconomicsFilter | None = None,
    ) -> EpisodeEconomicsResponse:
        """Return cost-side unit economics for a single Episode."""
        episode = self._assert_episode(series_id, episode_id)
        costs = self._query_costs(series_id, episode_id=episode_id, filters=filters)
        total_cost = sum((c.total_cost or Decimal("0") for c in costs), Decimal("0"))
        count = len(costs)

        usage = self._budgets.get_usage(series_id, episode_id)
        budget = self._budgets.get_budget(series_id, episode_id)

        generation_count_by_type: dict[str, int] = defaultdict(int)
        for cost in costs:
            generation_count_by_type[cost.generation_type] += 1

        return EpisodeEconomicsResponse(
            series_id=str(series_id),
            episode_id=str(episode.id),
            title=episode.title,
            actual_spend=self._format(total_cost),
            generation_count=count,
            average_cost_per_generation=self._format(total_cost / count) if count > 0 else "0",
            cost_by_generation_type=self._build_breakdown(costs, "generation_type"),
            cost_by_provider=self._build_breakdown(costs, "provider"),
            cost_by_model=self._build_breakdown(costs, "model"),
            generation_count_by_type=dict(generation_count_by_type),
            budget_amount=usage.budget,
            budget_currency=usage.currency,
            budget_status=usage.status,
            active_reservation=usage.reserved,
            remaining_budget=usage.remaining,
            available_budget=usage.available,
            utilization=usage.utilization,
            usage_limits=budget.usage_limits if budget else None,
        )
