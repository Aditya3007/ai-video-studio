"""Tests for provider-neutral health checking."""

from app.provider_health import (
    HealthState,
    HealthStatus,
    HealthStore,
    StaticHealthChecker,
    StoreBackedHealthChecker,
)
from app.provider_registry import ProviderType


def _image_provider_key() -> tuple[ProviderType, str, str | None]:
    return (ProviderType.IMAGE_GENERATION, "fake", None)


class TestHealthStore:
    def test_store_and_retrieve_state(self) -> None:
        store = HealthStore()
        state = HealthState(status=HealthStatus.HEALTHY)
        store.update(ProviderType.IMAGE_GENERATION, "fake", model_id="fake-model", state=state)
        retrieved = store.get(ProviderType.IMAGE_GENERATION, "fake", model_id="fake-model")
        assert retrieved == state

    def test_missing_state_is_unknown(self) -> None:
        store = HealthStore()
        state = store.get(ProviderType.IMAGE_GENERATION, "missing")
        assert state.status == HealthStatus.UNKNOWN

    def test_eligibility_healthy(self) -> None:
        store = HealthStore()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="fake-model",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        assert store.is_eligible(ProviderType.IMAGE_GENERATION, "fake", model_id="fake-model")

    def test_eligibility_degraded_policy(self) -> None:
        store = HealthStore()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="fake-model",
            state=HealthState(status=HealthStatus.DEGRADED),
        )
        assert not store.is_eligible(ProviderType.IMAGE_GENERATION, "fake", model_id="fake-model")
        assert store.is_eligible(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="fake-model",
            allow_degraded=True,
        )

    def test_eligibility_unknown_policy(self) -> None:
        store = HealthStore()
        assert not store.is_eligible(ProviderType.IMAGE_GENERATION, "fake", model_id="fake-model")
        assert store.is_eligible(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="fake-model",
            allow_unknown=True,
        )

    def test_provider_level_fallback_for_unknown_model(self) -> None:
        store = HealthStore()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        assert store.is_eligible(ProviderType.IMAGE_GENERATION, "fake", model_id="unknown-model")

    def test_isolated_stores(self) -> None:
        first = HealthStore()
        second = HealthStore()
        first.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        assert first.is_eligible(ProviderType.IMAGE_GENERATION, "fake")
        assert not second.is_eligible(ProviderType.IMAGE_GENERATION, "fake")

    def test_state_does_not_contain_secrets(self) -> None:
        state = HealthState(status=HealthStatus.UNAVAILABLE, reason="Provider timeout")
        assert "api_key" not in state.reason.lower()
        assert "token" not in state.reason.lower()


class TestStaticHealthChecker:
    def test_static_checker_returns_configured_state(self) -> None:
        checker = StaticHealthChecker(
            states={
                (ProviderType.IMAGE_GENERATION, "fake", None): HealthState(
                    status=HealthStatus.DEGRADED
                )
            }
        )
        state = checker.check(ProviderType.IMAGE_GENERATION, "fake")
        assert state.status == HealthStatus.DEGRADED

    def test_static_checker_returns_unknown_for_missing(self) -> None:
        checker = StaticHealthChecker()
        state = checker.check(ProviderType.IMAGE_GENERATION, "missing")
        assert state.status == HealthStatus.UNKNOWN


class TestStoreBackedHealthChecker:
    def test_checker_reads_store(self) -> None:
        store = HealthStore()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        checker = StoreBackedHealthChecker(store)
        assert checker.check(ProviderType.IMAGE_GENERATION, "fake").status == HealthStatus.HEALTHY
