"""Cost-aware provider/model selection for P14-T04."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.model_registry import ModelDefinition, ModelRegistry, get_default_model_registry
from app.provider_health import HealthStatus, HealthStore, get_default_health_store
from app.provider_registry import ProviderRegistry, ProviderType, get_default_registry


class NoCostAwareCandidateError(Exception):
    """Raised when no cost-aware eligible candidate can be selected."""


class CostAwareSelection(BaseModel):
    """Result of a cost-aware provider/model selection."""

    model_config = ConfigDict(from_attributes=True)

    model_id: str
    provider_id: str
    provider_type: ProviderType
    health_status: HealthStatus
    estimated_cost: str | None
    currency: str | None


class CostEstimator:
    """Provider-neutral cost estimation from model pricing and request context."""

    @staticmethod
    def _to_decimal(value) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _quantity(context: dict[str, Any], unit: str) -> Decimal | None:
        if unit in {"image", "fixed"}:
            return Decimal(context.get("num_images", 1))
        if unit == "second":
            value = context.get("duration_seconds") or context.get("seconds")
            if value is None:
                return None
            return Decimal(str(value))
        if unit == "character":
            value = context.get("character_count") or context.get("text_length")
            if value is None:
                return None
            return Decimal(str(value))
        if unit == "token":
            input_tokens = Decimal(context.get("input_tokens", 0))
            output_tokens = Decimal(context.get("output_tokens", 0))
            return input_tokens + output_tokens
        return None

    @classmethod
    def estimate(
        cls,
        model: ModelDefinition,
        cost_context: dict[str, Any] | None = None,
    ) -> tuple[Decimal, str] | None:
        """Return (estimated_cost, currency) for a model given usage context."""
        pricing = (cost_context or {}).get("pricing_override") if cost_context else None
        if pricing is None:
            pricing = model.pricing if model else None
            if pricing is None and getattr(model, "configuration", None):
                pricing = model.configuration.get("pricing")
        if not pricing or not isinstance(pricing, dict):
            return None

        unit_price = cls._to_decimal(pricing.get("unit_price"))
        if unit_price is None:
            return None
        unit = pricing.get("unit", "fixed")
        currency = pricing.get("currency", "USD")
        quantity = cls._quantity(cost_context or {}, unit)
        if quantity is None:
            # If the pricing unit cannot be satisfied by the context, treat as unknown.
            return None
        return (unit_price * quantity, currency)


class CostAwareSelector:
    """Provider-neutral, deterministic cost-aware provider/model selector."""

    def __init__(
        self,
        model_registry: ModelRegistry | None = None,
        health_store: HealthStore | None = None,
        provider_registry: ProviderRegistry | None = None,
        *,
        allow_unknown_cost: bool = False,
        unknown_cost_penalty: str | Decimal = "Infinity",
    ) -> None:
        self._model_registry = model_registry or get_default_model_registry()
        self._health_store = health_store or get_default_health_store()
        self._provider_registry = provider_registry or get_default_registry()
        self._allow_unknown_cost = allow_unknown_cost
        self._unknown_penalty = Decimal(str(unknown_cost_penalty))

    def _is_eligible(self, model: ModelDefinition) -> bool:
        return self._health_store.is_eligible(
            model.provider_type,
            model.provider_id,
            model_id=model.model_id,
            allow_degraded=False,
            allow_unknown=True,
        )

    def _resolve_provider(self, provider_type: ProviderType, provider_id: str) -> Any:
        return self._provider_registry.resolve(provider_type, provider_id)

    def select(
        self,
        provider_type: ProviderType,
        required_capabilities: set[str],
        cost_context: dict[str, Any] | None = None,
    ) -> CostAwareSelection:
        """Select the cheapest healthy, capable candidate."""
        candidates = self._model_registry.list_by_capabilities(
            required_capabilities,
            provider_type=provider_type,
        )
        candidates = [m for m in candidates if m.enabled and self._is_eligible(m)]

        scored: list[tuple[Decimal, str | None, str, ModelDefinition]] = []
        for model in candidates:
            estimate = CostEstimator.estimate(model, cost_context)
            if estimate is None:
                if not self._allow_unknown_cost:
                    continue
                # Unknown cost candidates receive a deterministic penalty.
                # Currency is irrelevant because they will only win if all candidates are unknown.
                scored.append((self._unknown_penalty, None, model.model_id, model))
            else:
                cost, currency = estimate
                scored.append((cost, currency, model.model_id, model))

        if not scored:
            raise NoCostAwareCandidateError(
                f"No eligible cost-aware candidate for {provider_type} "
                f"with capabilities {sorted(required_capabilities)}"
            )

        # Sort by estimated cost ascending, then model_id for deterministic tie-breaking.
        scored.sort(key=lambda x: (x[0], x[2]))
        _, currency, _, selected = scored[0]
        health_state = self._health_store.get(
            selected.provider_type, selected.provider_id, model_id=selected.model_id
        )
        estimated_cost, _ = CostEstimator.estimate(selected, cost_context) or (None, None)

        return CostAwareSelection(
            model_id=selected.model_id,
            provider_id=selected.provider_id,
            provider_type=selected.provider_type,
            health_status=health_state.status,
            estimated_cost=str(estimated_cost) if estimated_cost is not None else None,
            currency=currency,
        )

    def select_provider(
        self,
        provider_type: ProviderType,
        required_capabilities: set[str],
        cost_context: dict[str, Any] | None = None,
    ) -> Any:
        """Select a candidate and resolve its provider instance."""
        selection = self.select(provider_type, required_capabilities, cost_context)
        return self._resolve_provider(selection.provider_type, selection.provider_id)
