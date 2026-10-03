"""Provider-neutral health checking and fallback strategy."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from app.model_registry import ModelDefinition, ModelRegistry
from app.provider_registry import ProviderType

__all__ = [
    "FallbackPolicy",
    "FallbackSelection",
    "FallbackSelector",
    "HealthChecker",
    "HealthState",
    "HealthStatus",
    "HealthStore",
    "IncompatibleFallbackError",
    "NoFallbackAvailableError",
    "ProviderHealthError",
    "StaticHealthChecker",
    "StoreBackedHealthChecker",
    "UnknownProviderHealthError",
    "get_default_health_store",
]


class ProviderHealthError(Exception):
    """Base error for provider health and fallback failures."""


class UnknownProviderHealthError(ProviderHealthError):
    """Raised when the requested provider/model health is unknown."""


class NoFallbackAvailableError(ProviderHealthError):
    """Raised when no eligible fallback provider/model is available."""


class IncompatibleFallbackError(ProviderHealthError):
    """Raised when a fallback candidate is incompatible with the request."""


class HealthStatus(StrEnum):
    """Provider-neutral health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class HealthState(BaseModel):
    """A provider-neutral health observation."""

    status: HealthStatus
    reason: str | None = None

    model_config = ConfigDict(frozen=True)


class HealthStore:
    """In-memory store for provider/model health state."""

    def __init__(self) -> None:
        self._states: dict[tuple[ProviderType, str, str | None], HealthState] = {}

    def _key(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
    ) -> tuple[ProviderType, str, str | None]:
        return (provider_type, provider_id, model_id)

    def update(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
        state: HealthState,
    ) -> None:
        """Store or overwrite health state for a provider or model."""
        self._states[self._key(provider_type, provider_id, model_id=model_id)] = state

    def get(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
    ) -> HealthState:
        """Return stored health state or UNKNOWN."""
        return self._states.get(
            self._key(provider_type, provider_id, model_id=model_id),
            HealthState(status=HealthStatus.UNKNOWN),
        )

    def is_eligible(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
        allow_degraded: bool = False,
        allow_unknown: bool = False,
    ) -> bool:
        """Return True if the provider/model is eligible under the given policy."""
        state = self.get(provider_type, provider_id, model_id=model_id)
        if state.status == HealthStatus.HEALTHY:
            return True
        if state.status == HealthStatus.DEGRADED and allow_degraded:
            return True
        if state.status == HealthStatus.UNKNOWN and allow_unknown:
            return True
        if state.status == HealthStatus.UNKNOWN:
            # Fall back to provider-level health if model-level is unknown.
            provider_state = self.get(provider_type, provider_id)
            if provider_state.status == HealthStatus.HEALTHY:
                return True
            if provider_state.status == HealthStatus.DEGRADED and allow_degraded:
                return True
        return False


@runtime_checkable
class HealthChecker(Protocol):
    """Provider-neutral contract for checking provider/model health."""

    def check(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
    ) -> HealthState:
        """Return the current health state of the provider or model."""
        ...


class StaticHealthChecker:
    """Deterministic health checker driven by a static mapping."""

    def __init__(
        self,
        states: dict[tuple[ProviderType, str, str | None], HealthState] | None = None,
    ) -> None:
        self._states = states or {}

    def check(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
    ) -> HealthState:
        return self._states.get(
            (provider_type, provider_id, model_id),
            HealthState(status=HealthStatus.UNKNOWN),
        )


class StoreBackedHealthChecker:
    """Health checker backed by a HealthStore."""

    def __init__(self, store: HealthStore) -> None:
        self._store = store

    def check(
        self,
        provider_type: ProviderType,
        provider_id: str,
        *,
        model_id: str | None = None,
    ) -> HealthState:
        return self._store.get(provider_type, provider_id, model_id=model_id)


class FallbackPolicy(BaseModel):
    """Deterministic policy for fallback selection."""

    allow_degraded: bool = False
    allow_unknown: bool = False

    model_config = ConfigDict(frozen=True)


class FallbackSelection(BaseModel):
    """Result of a fallback selection."""

    model_id: str
    provider_id: str
    provider_type: ProviderType
    status: HealthStatus

    model_config = ConfigDict(frozen=True)


class FallbackSelector:
    """Deterministic fallback selector using ModelRegistry and HealthStore."""

    def __init__(self, model_registry: ModelRegistry, health_store: HealthStore) -> None:
        self._model_registry = model_registry
        self._health_store = health_store

    def select(
        self,
        provider_type: ProviderType,
        preferred_model_id: str,
        *,
        required_capabilities: set[str] | None = None,
        policy: FallbackPolicy | None = None,
    ) -> FallbackSelection:
        """Select an eligible model, preferring the requested one."""
        policy = policy or FallbackPolicy()
        required = set(required_capabilities or [])

        preferred = self._model_registry.resolve(preferred_model_id)
        if preferred.provider_type != provider_type:
            raise IncompatibleFallbackError(
                f"Preferred model '{preferred_model_id}' is not a {provider_type} model"
            )
        if not preferred.enabled:
            raise IncompatibleFallbackError(f"Preferred model '{preferred_model_id}' is disabled")
        if not self._model_registry.has_capabilities(preferred_model_id, required):
            raise IncompatibleFallbackError(
                f"Preferred model '{preferred_model_id}' does not satisfy capabilities "
                f"{sorted(required)}"
            )

        candidates = self._model_registry.list_by_capabilities(
            required,
            provider_type=provider_type,
        )
        candidates = [m for m in candidates if m.enabled]
        candidates.sort(key=lambda m: m.model_id)

        if self._is_eligible(preferred, policy):
            status = self._health_store.get(
                preferred.provider_type, preferred.provider_id, model_id=preferred.model_id
            ).status
            return FallbackSelection(
                model_id=preferred.model_id,
                provider_id=preferred.provider_id,
                provider_type=preferred.provider_type,
                status=status,
            )

        for model in candidates:
            if model.model_id == preferred_model_id:
                continue
            if not self._is_eligible(model, policy):
                continue
            status = self._health_store.get(
                model.provider_type, model.provider_id, model_id=model.model_id
            ).status
            return FallbackSelection(
                model_id=model.model_id,
                provider_id=model.provider_id,
                provider_type=model.provider_type,
                status=status,
            )

        raise NoFallbackAvailableError(
            f"No eligible fallback for {provider_type} with capabilities {sorted(required)}"
        )

    def _is_eligible(
        self,
        model: ModelDefinition,
        policy: FallbackPolicy,
    ) -> bool:
        return self._health_store.is_eligible(
            model.provider_type,
            model.provider_id,
            model_id=model.model_id,
            allow_degraded=policy.allow_degraded,
            allow_unknown=policy.allow_unknown,
        )


_default_health_store: HealthStore | None = None


def get_default_health_store() -> HealthStore:
    """Return the process-wide default health store."""
    global _default_health_store
    if _default_health_store is None:
        _default_health_store = HealthStore()
    return _default_health_store
