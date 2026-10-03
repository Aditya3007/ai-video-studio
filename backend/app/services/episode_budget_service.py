"""Episode-level generation budget control service."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BudgetReservation, Episode, EpisodeBudget, GenerationCost, Series
from app.models.enums import (
    AuditEventType,
    AuditStatus,
    BudgetReservationStatus,
    BudgetStatus,
    GenerationType,
)
from app.services.audit_service import AuditService
from app.services.generation_cost_service import GenerationCostService


class BudgetError(Exception):
    """Base exception for budget control failures."""


class BudgetExceededError(BudgetError):
    """Raised when a generation request exceeds the configured budget or usage limits."""


class InvalidBudgetError(BudgetError):
    """Raised when a budget amount or currency is invalid."""


class BudgetCheckResult(BaseModel):
    """Result of a pre-generation budget check."""

    model_config = ConfigDict(from_attributes=True)

    allowed: bool
    reason: str
    estimated_cost: str
    budget: str | None
    spent: str
    reserved: str
    available: str | None
    reservation_id: str | None
    currency: str | None


class BudgetUsage(BaseModel):
    """Current budget usage for an episode."""

    model_config = ConfigDict(from_attributes=True)

    budget: str | None
    spent: str
    reserved: str
    remaining: str
    available: str | None
    utilization: str
    status: str
    currency: str | None


class EpisodeBudgetResponse(BaseModel):
    """Public representation of an episode budget."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    series_id: str
    episode_id: str
    budget_amount: str
    cost_currency: str
    active: bool
    usage_limits: dict | None


class EpisodeBudgetService:
    """Controls per-episode generation budgets and usage limits."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._costs = GenerationCostService(db)
        self._audit = AuditService(db)

    @staticmethod
    def _to_decimal(value) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise InvalidBudgetError("Invalid monetary value.") from exc

    @staticmethod
    def _to_str(value: Decimal | None) -> str:
        if value is None:
            return "0"
        return format(value.normalize(), "f")

    def _assert_ownership(self, series_id: str, episode_id: str) -> None:
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != str(series_id):
            raise BudgetError("Episode not found in this Series.")
        series = self._db.get(Series, series_id)
        if not series:
            raise BudgetError("Series not found.")

    def configure_budget(
        self,
        series_id: str,
        episode_id: str,
        amount,
        *,
        currency: str = "USD",
        active: bool = True,
        usage_limits: dict | None = None,
    ) -> EpisodeBudgetResponse:
        """Create or update an episode's generation budget."""
        self._assert_ownership(series_id, episode_id)
        if not currency or len(currency) != 3:
            raise InvalidBudgetError("Currency must be a 3-character code.")
        value = self._to_decimal(amount)
        if value < 0:
            raise InvalidBudgetError("Budget amount cannot be negative.")

        budget = (
            self._db.execute(
                select(EpisodeBudget).where(
                    EpisodeBudget.series_id == series_id,
                    EpisodeBudget.episode_id == episode_id,
                )
            )
            .scalars()
            .first()
        )
        if budget is None:
            budget = EpisodeBudget(
                series_id=series_id,
                episode_id=episode_id,
                budget_amount=value,
                cost_currency=currency.upper(),
                active=active,
                usage_limits=usage_limits,
            )
            self._db.add(budget)
        else:
            budget.budget_amount = value
            budget.cost_currency = currency.upper()
            budget.active = active
            budget.usage_limits = usage_limits

        self._db.flush()
        self._db.refresh(budget)
        self._audit.record(
            series_id=series_id,
            episode_id=episode_id,
            event_type=AuditEventType.BUDGET_CONFIGURED,
            status=AuditStatus.SUCCESS,
            metadata={"budget_amount": str(value), "currency": currency.upper(), "active": active},
        )
        return self._to_response(budget)

    def get_budget(self, series_id: str, episode_id: str) -> EpisodeBudgetResponse | None:
        """Retrieve the configured budget for an episode."""
        self._assert_ownership(series_id, episode_id)
        budget = (
            self._db.execute(
                select(EpisodeBudget).where(
                    EpisodeBudget.series_id == series_id,
                    EpisodeBudget.episode_id == episode_id,
                )
            )
            .scalars()
            .first()
        )
        return self._to_response(budget) if budget else None

    def get_usage(self, series_id: str, episode_id: str) -> BudgetUsage:
        """Calculate current spend, reservations, and budget status."""
        self._assert_ownership(series_id, episode_id)
        budget = (
            self._db.execute(
                select(EpisodeBudget).where(
                    EpisodeBudget.series_id == series_id,
                    EpisodeBudget.episode_id == episode_id,
                )
            )
            .scalars()
            .first()
        )
        spent = self._costs.get_total_by_episode(series_id, episode_id)
        reserved = self._reserved_amount(series_id, episode_id)

        if budget is None or not budget.active:
            return BudgetUsage(
                budget=None,
                spent=self._to_str(spent),
                reserved=self._to_str(reserved),
                remaining=self._to_str(-spent),
                available=None,
                utilization="0",
                status=BudgetStatus.UNCONFIGURED.value,
                currency=None,
            )

        budget_amount = budget.budget_amount
        remaining = budget_amount - spent
        available = budget_amount - spent - reserved
        if spent > budget_amount:
            status = BudgetStatus.OVER_BUDGET.value
        elif spent == budget_amount:
            status = BudgetStatus.EXHAUSTED.value
        else:
            status = BudgetStatus.WITHIN_BUDGET.value
        utilization = (
            str((spent / budget_amount).quantize(Decimal("0.0001"))) if budget_amount > 0 else "0"
        )
        return BudgetUsage(
            budget=self._to_str(budget_amount),
            spent=self._to_str(spent),
            reserved=self._to_str(reserved),
            remaining=self._to_str(remaining),
            available=self._to_str(available),
            utilization=utilization,
            status=status,
            currency=budget.cost_currency,
        )

    def _reserved_amount(self, series_id: str, episode_id: str) -> Decimal:
        result = self._db.execute(
            select(func.coalesce(func.sum(BudgetReservation.estimated_cost), 0)).where(
                BudgetReservation.series_id == series_id,
                BudgetReservation.episode_id == episode_id,
                BudgetReservation.status == BudgetReservationStatus.RESERVED.value,
            )
        ).scalar()
        return self._to_decimal(result)

    def _usage_limit_check(
        self,
        budget: EpisodeBudget | None,
        generation_type: str,
        episode_id: str,
    ) -> bool:
        if budget is None or budget.usage_limits is None:
            return True
        limits = budget.usage_limits.get(generation_type) or budget.usage_limits.get(
            generation_type.value
            if isinstance(generation_type, GenerationType)
            else generation_type
        )
        if not limits:
            return True
        max_generations = limits.get("max_generations")
        if max_generations is None:
            return True
        actual = (
            self._db.execute(
                select(func.count(GenerationCost.id)).where(
                    GenerationCost.series_id == budget.series_id,
                    GenerationCost.episode_id == episode_id,
                    GenerationCost.generation_type == str(generation_type),
                )
            ).scalar()
            or 0
        )
        reserved = (
            self._db.execute(
                select(func.count(BudgetReservation.id)).where(
                    BudgetReservation.series_id == budget.series_id,
                    BudgetReservation.episode_id == episode_id,
                    BudgetReservation.generation_type == str(generation_type),
                    BudgetReservation.status == BudgetReservationStatus.RESERVED.value,
                )
            ).scalar()
            or 0
        )
        return (actual + reserved) < int(max_generations)

    def check_and_reserve(
        self,
        series_id: str,
        episode_id: str,
        generation_type: str,
        *,
        estimated_cost=None,
        currency: str = "USD",
        job_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BudgetCheckResult:
        """Check whether a generation is allowed and reserve estimated cost if applicable."""
        self._assert_ownership(series_id, episode_id)
        estimated = self._to_decimal(estimated_cost or 0)
        if not currency or len(currency) != 3:
            raise InvalidBudgetError("Currency must be a 3-character code.")

        spent = self._costs.get_total_by_episode(series_id, episode_id)
        budget = (
            self._db.execute(
                select(EpisodeBudget).where(
                    EpisodeBudget.series_id == series_id,
                    EpisodeBudget.episode_id == episode_id,
                )
            )
            .scalars()
            .first()
        )

        if budget is None or not budget.active:
            return BudgetCheckResult(
                allowed=True,
                reason="NO_BUDGET_CONFIGURED",
                estimated_cost=self._to_str(estimated),
                budget=None,
                spent=self._to_str(spent),
                reserved=self._to_str(self._reserved_amount(series_id, episode_id)),
                available=None,
                reservation_id=None,
                currency=None,
            )

        if budget.cost_currency.upper() != currency.upper():
            self._audit.record(
                series_id=series_id,
                episode_id=episode_id,
                event_type=AuditEventType.BUDGET_EXCEEDED,
                status=AuditStatus.FAILED,
                metadata={"reason": "CURRENCY_MISMATCH", "currency": currency},
            )
            return BudgetCheckResult(
                allowed=False,
                reason="CURRENCY_MISMATCH",
                estimated_cost=self._to_str(estimated),
                budget=self._to_str(budget.budget_amount),
                spent=self._to_str(spent),
                reserved=self._to_str(self._reserved_amount(series_id, episode_id)),
                available=self._to_str(
                    budget.budget_amount - spent - self._reserved_amount(series_id, episode_id)
                ),
                reservation_id=None,
                currency=budget.cost_currency,
            )

        if not self._usage_limit_check(budget, generation_type, episode_id):
            self._audit.record(
                series_id=series_id,
                episode_id=episode_id,
                event_type=AuditEventType.BUDGET_EXCEEDED,
                status=AuditStatus.FAILED,
                metadata={
                    "reason": "USAGE_LIMIT_EXCEEDED",
                    "generation_type": str(generation_type),
                },
            )
            return BudgetCheckResult(
                allowed=False,
                reason="USAGE_LIMIT_EXCEEDED",
                estimated_cost=self._to_str(estimated),
                budget=self._to_str(budget.budget_amount),
                spent=self._to_str(spent),
                reserved=self._to_str(self._reserved_amount(series_id, episode_id)),
                available=self._to_str(
                    budget.budget_amount - spent - self._reserved_amount(series_id, episode_id)
                ),
                reservation_id=None,
                currency=budget.cost_currency,
            )

        reserved = self._reserved_amount(series_id, episode_id)
        available = budget.budget_amount - spent - reserved

        if estimated > available:
            self._audit.record(
                series_id=series_id,
                episode_id=episode_id,
                event_type=AuditEventType.BUDGET_EXCEEDED,
                status=AuditStatus.FAILED,
                metadata={
                    "reason": "BUDGET_EXCEEDED",
                    "estimated_cost": str(estimated),
                    "available": str(available),
                    "generation_type": str(generation_type),
                },
            )
            return BudgetCheckResult(
                allowed=False,
                reason="BUDGET_EXCEEDED",
                estimated_cost=self._to_str(estimated),
                budget=self._to_str(budget.budget_amount),
                spent=self._to_str(spent),
                reserved=self._to_str(reserved),
                available=self._to_str(available),
                reservation_id=None,
                currency=budget.cost_currency,
            )

        correlation = correlation_id or str(uuid4())
        reservation = self._create_or_update_reservation(
            budget,
            generation_type,
            estimated,
            currency,
            job_id,
            correlation,
        )

        self._audit.record(
            series_id=series_id,
            episode_id=episode_id,
            event_type=AuditEventType.BUDGET_CHECKED,
            status=AuditStatus.SUCCESS,
            metadata={
                "allowed": True,
                "estimated_cost": str(estimated),
                "available": str(available),
                "generation_type": str(generation_type),
                "reservation_id": reservation.id,
            },
        )
        return BudgetCheckResult(
            allowed=True,
            reason="WITHIN_BUDGET",
            estimated_cost=self._to_str(estimated),
            budget=self._to_str(budget.budget_amount),
            spent=self._to_str(spent),
            reserved=self._to_str(self._reserved_amount(series_id, episode_id)),
            available=self._to_str(
                budget.budget_amount - spent - self._reserved_amount(series_id, episode_id)
            ),
            reservation_id=reservation.id,
            currency=budget.cost_currency,
        )

    def _create_or_update_reservation(
        self,
        budget: EpisodeBudget,
        generation_type: str,
        estimated_cost: Decimal,
        currency: str,
        job_id: str | None,
        correlation_id: str,
    ) -> BudgetReservation:
        existing = (
            self._db.execute(
                select(BudgetReservation).where(
                    BudgetReservation.series_id == budget.series_id,
                    BudgetReservation.correlation_id == correlation_id,
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            if existing.status != BudgetReservationStatus.RESERVED.value:
                existing.status = BudgetReservationStatus.RESERVED.value
                existing.estimated_cost = estimated_cost
                existing.cost_currency = currency.upper()
                existing.generation_type = str(generation_type)
                existing.job_id = job_id
            self._db.flush()
            return existing

        reservation = BudgetReservation(
            series_id=budget.series_id,
            episode_id=budget.episode_id,
            generation_type=str(generation_type),
            job_id=job_id,
            correlation_id=correlation_id,
            estimated_cost=estimated_cost,
            cost_currency=currency.upper(),
            status=BudgetReservationStatus.RESERVED.value,
        )
        self._db.add(reservation)
        try:
            self._db.flush()
        except IntegrityError as exc:
            self._db.rollback()
            raise BudgetError("Duplicate reservation correlation_id.") from exc

        self._audit.record(
            series_id=budget.series_id,
            episode_id=budget.episode_id,
            event_type=AuditEventType.BUDGET_RESERVATION_CREATED,
            status=AuditStatus.SUCCESS,
            metadata={
                "reservation_id": reservation.id,
                "estimated_cost": str(estimated_cost),
                "currency": currency.upper(),
                "generation_type": str(generation_type),
            },
        )
        return reservation

    def release_reservation(self, reservation_id: str) -> None:
        """Release a reservation (e.g., after a failed generation)."""
        reservation = self._db.get(BudgetReservation, reservation_id)
        if not reservation:
            return
        if reservation.status != BudgetReservationStatus.RESERVED.value:
            return
        reservation.status = BudgetReservationStatus.RELEASED.value
        self._db.flush()
        self._audit.record(
            series_id=reservation.series_id,
            episode_id=reservation.episode_id,
            event_type=AuditEventType.BUDGET_RESERVATION_RELEASED,
            status=AuditStatus.SUCCESS,
            metadata={"reservation_id": reservation_id},
        )

    def settle_reservation(self, reservation_id: str, actual_cost=None) -> None:
        """Settle a reservation (e.g., after a successful generation)."""
        reservation = self._db.get(BudgetReservation, reservation_id)
        if not reservation:
            return
        if reservation.status != BudgetReservationStatus.RESERVED.value:
            return
        reservation.status = BudgetReservationStatus.SETTLED.value
        if actual_cost is not None:
            reservation.actual_cost = self._to_decimal(actual_cost)
        self._db.flush()
        self._audit.record(
            series_id=reservation.series_id,
            episode_id=reservation.episode_id,
            event_type=AuditEventType.BUDGET_RESERVATION_SETTLED,
            status=AuditStatus.SUCCESS,
            metadata={
                "reservation_id": reservation_id,
                "actual_cost": str(reservation.actual_cost or 0),
            },
        )

    @staticmethod
    def _to_response(budget: EpisodeBudget) -> EpisodeBudgetResponse:
        return EpisodeBudgetResponse(
            id=str(budget.id),
            series_id=str(budget.series_id),
            episode_id=str(budget.episode_id),
            budget_amount=EpisodeBudgetService._to_str(budget.budget_amount),
            cost_currency=budget.cost_currency,
            active=budget.active,
            usage_limits=budget.usage_limits,
        )
