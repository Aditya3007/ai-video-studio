"""Tests for provider-neutral fallback strategy."""

import pytest

from app.model_registry import (
    ModelCapability,
    ModelCapabilityType,
    ModelDefinition,
    ModelRegistry,
)
from app.provider_health import (
    FallbackPolicy,
    FallbackSelector,
    HealthState,
    HealthStatus,
    HealthStore,
    IncompatibleFallbackError,
    NoFallbackAvailableError,
)
from app.provider_registry import ProviderType


def _image_model(model_id: str, capabilities: list[str], enabled: bool = True) -> ModelDefinition:
    return ModelDefinition(
        model_id=model_id,
        provider_id="fake",
        provider_type=ProviderType.IMAGE_GENERATION,
        name=model_id,
        capabilities=[ModelCapability(capability=c) for c in capabilities],
        enabled=enabled,
    )


def _llm_model(model_id: str) -> ModelDefinition:
    return ModelDefinition(
        model_id=model_id,
        provider_id="fake",
        provider_type=ProviderType.LLM,
        name=model_id,
        capabilities=[ModelCapability(capability=ModelCapabilityType.TEXT_GENERATION)],
    )


def _selector() -> tuple[FallbackSelector, HealthStore]:
    registry = ModelRegistry()
    registry.register(_image_model("image-a", [ModelCapabilityType.IMAGE_GENERATION]))
    registry.register(_image_model("image-b", [ModelCapabilityType.IMAGE_GENERATION]))
    registry.register(
        _image_model("image-wide", [ModelCapabilityType.IMAGE_GENERATION], enabled=False)
    )
    registry.register(_llm_model("llm-a"))
    store = HealthStore()
    return FallbackSelector(registry, store), store


class TestFallbackSelector:
    def test_selects_preferred_when_healthy(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        selection = selector.select(ProviderType.IMAGE_GENERATION, "image-a")
        assert selection.model_id == "image-a"
        assert selection.status == HealthStatus.HEALTHY

    def test_falls_back_when_preferred_unavailable(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.UNAVAILABLE),
        )
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-b",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        selection = selector.select(ProviderType.IMAGE_GENERATION, "image-a")
        assert selection.model_id == "image-b"

    def test_degraded_preferred_with_policy(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.DEGRADED),
        )
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-b",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        selection = selector.select(
            ProviderType.IMAGE_GENERATION,
            "image-a",
            policy=FallbackPolicy(allow_degraded=False),
        )
        assert selection.model_id == "image-b"

    def test_multiple_candidates_are_deterministic(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.UNAVAILABLE),
        )
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-b",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        # Run multiple times to ensure deterministic order.
        for _ in range(3):
            selection = selector.select(ProviderType.IMAGE_GENERATION, "image-a")
            assert selection.model_id == "image-b"

    def test_incompatible_capability_rejected(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        with pytest.raises(IncompatibleFallbackError):
            selector.select(
                ProviderType.IMAGE_GENERATION,
                "image-a",
                required_capabilities={ModelCapabilityType.TEXT_TO_VIDEO},
            )

    def test_disabled_model_rejected(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-wide",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        with pytest.raises(IncompatibleFallbackError):
            selector.select(ProviderType.IMAGE_GENERATION, "image-wide")

    def test_wrong_provider_type_rejected(self) -> None:
        selector, store = _selector()
        with pytest.raises(IncompatibleFallbackError):
            selector.select(ProviderType.TTS, "image-a")

    def test_no_candidate_raises(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.UNAVAILABLE),
        )
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-b",
            state=HealthState(status=HealthStatus.UNAVAILABLE),
        )
        with pytest.raises(NoFallbackAvailableError):
            selector.select(ProviderType.IMAGE_GENERATION, "image-a")

    def test_unknown_health_without_policy_raises(self) -> None:
        selector, _ = _selector()
        with pytest.raises(NoFallbackAvailableError):
            selector.select(ProviderType.IMAGE_GENERATION, "image-a")

    def test_unknown_health_allowed_by_policy(self) -> None:
        selector, _ = _selector()
        selection = selector.select(
            ProviderType.IMAGE_GENERATION,
            "image-a",
            policy=FallbackPolicy(allow_unknown=True),
        )
        assert selection.model_id == "image-a"
        assert selection.status == HealthStatus.UNKNOWN

    def test_category_isolation(self) -> None:
        selector, store = _selector()
        store.update(
            ProviderType.IMAGE_GENERATION,
            "fake",
            model_id="image-a",
            state=HealthState(status=HealthStatus.HEALTHY),
        )
        # LLM model exists but is not an image-generation candidate.
        with pytest.raises(IncompatibleFallbackError):
            selector.select(ProviderType.IMAGE_GENERATION, "llm-a")

    def test_no_secrets_in_fallback_error(self) -> None:
        selector, store = _selector()
        with pytest.raises(NoFallbackAvailableError) as exc:
            selector.select(ProviderType.IMAGE_GENERATION, "image-a")
        message = str(exc.value)
        assert "api_key" not in message.lower()
        assert "token" not in message.lower()
