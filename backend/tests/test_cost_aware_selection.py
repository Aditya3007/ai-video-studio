"""Focused tests for P14-T04 cost-aware provider/model selection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import load_settings
from app.media_generation.image.factory import ImageGenerationProviderFactory
from app.media_generation.image.fake import FakeImageGenerationProvider
from app.media_generation.image.provider import ImageGenerationRequest
from app.media_generation.tts.fake import FakeTTSProvider
from app.media_generation.tts.provider import TTSRequest
from app.media_generation.video.fake import FakeVideoGenerationProvider
from app.media_generation.video.provider import VideoGenerationRequest
from app.model_registry import (
    ModelCapability,
    ModelCapabilityType,
    ModelDefinition,
    ModelRegistry,
)
from app.provider_health import HealthState, HealthStatus, HealthStore
from app.provider_registry import ProviderRegistry, ProviderType
from app.services.cost_aware_selector import (
    CostAwareSelector,
    NoCostAwareCandidateError,
)


def _make_registry() -> tuple[ProviderRegistry, ModelRegistry, HealthStore]:
    provider_registry = ProviderRegistry()
    provider_registry.register(ProviderType.IMAGE_GENERATION, "fake", FakeImageGenerationProvider())
    provider_registry.register(
        ProviderType.IMAGE_GENERATION,
        "fake-premium",
        FakeImageGenerationProvider(provider="fake-premium", model="fake-premium-image"),
    )
    provider_registry.register(
        ProviderType.IMAGE_GENERATION,
        "fake-cheap",
        FakeImageGenerationProvider(provider="fake-cheap", model="fake-cheap-image"),
    )
    provider_registry.register(
        ProviderType.IMAGE_GENERATION,
        "fake-incapable",
        FakeImageGenerationProvider(provider="fake-incapable", model="fake-incapable"),
    )
    provider_registry.register(ProviderType.TTS, "fake", FakeTTSProvider())
    provider_registry.register(
        ProviderType.TTS,
        "fake-tts-cheap",
        FakeTTSProvider(provider="fake-tts-cheap"),
    )
    provider_registry.register(ProviderType.VIDEO_GENERATION, "fake", FakeVideoGenerationProvider())
    provider_registry.register(
        ProviderType.VIDEO_GENERATION,
        "fake-video-cheap",
        FakeVideoGenerationProvider(provider="fake-video-cheap"),
    )

    model_registry = ModelRegistry(provider_registry)
    health_store = HealthStore()
    return provider_registry, model_registry, health_store


def _image_model(model_id: str, provider_id: str, price: str | None = None) -> ModelDefinition:
    pricing = (
        {"unit": "image", "unit_price": price, "currency": "USD"} if price is not None else None
    )
    return ModelDefinition(
        model_id=model_id,
        provider_id=provider_id,
        provider_type=ProviderType.IMAGE_GENERATION,
        name=model_id,
        capabilities=[ModelCapability(capability=ModelCapabilityType.IMAGE_GENERATION.value)],
        pricing=pricing,
    )


def _tts_model(model_id: str, provider_id: str, price: str | None = None) -> ModelDefinition:
    pricing = (
        {"unit": "character", "unit_price": price, "currency": "USD"} if price is not None else None
    )
    return ModelDefinition(
        model_id=model_id,
        provider_id=provider_id,
        provider_type=ProviderType.TTS,
        name=model_id,
        capabilities=[ModelCapability(capability=ModelCapabilityType.SPEECH_SYNTHESIS.value)],
        pricing=pricing,
    )


def _video_model(model_id: str, provider_id: str, price: str | None = None) -> ModelDefinition:
    pricing = (
        {"unit": "second", "unit_price": price, "currency": "USD"} if price is not None else None
    )
    return ModelDefinition(
        model_id=model_id,
        provider_id=provider_id,
        provider_type=ProviderType.VIDEO_GENERATION,
        name=model_id,
        capabilities=[ModelCapability(capability=ModelCapabilityType.IMAGE_TO_VIDEO.value)],
        pricing=pricing,
    )


def test_selects_cheapest_image_model() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("cheap", "fake-cheap", "0.01"))
    model_registry.register(_image_model("premium", "fake-premium", "0.10"))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    selection = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert selection.model_id == "cheap"
    assert selection.provider_id == "fake-cheap"
    assert selection.estimated_cost == "0.01"
    assert selection.currency == "USD"


def test_capability_filter_excludes_incapable_model() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("capable", "fake-cheap", "0.01"))
    incapable = ModelDefinition(
        model_id="incapable",
        provider_id="fake-incapable",
        provider_type=ProviderType.IMAGE_GENERATION,
        name="incapable",
        capabilities=[ModelCapability(capability="unknown_capability")],
        pricing={"unit": "image", "unit_price": "0.001", "currency": "USD"},
    )
    model_registry.register(incapable)

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    selection = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert selection.model_id == "capable"


def test_unhealthy_cheaper_model_is_excluded() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("sick-cheap", "fake-cheap", "0.01"))
    model_registry.register(_image_model("healthy-expensive", "fake-premium", "0.10"))
    health_store.update(
        ProviderType.IMAGE_GENERATION,
        "fake-cheap",
        model_id="sick-cheap",
        state=HealthState(status=HealthStatus.UNAVAILABLE),
    )
    health_store.update(
        ProviderType.IMAGE_GENERATION,
        "fake-premium",
        model_id="healthy-expensive",
        state=HealthState(status=HealthStatus.HEALTHY),
    )

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    selection = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert selection.model_id == "healthy-expensive"
    assert selection.health_status == HealthStatus.HEALTHY


def test_deterministic_tie_breaker() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("alpha", "fake-cheap", "0.05"))
    model_registry.register(_image_model("beta", "fake-premium", "0.05"))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    first = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    second = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert first.model_id == second.model_id == "alpha"


def test_unknown_cost_excluded_by_default() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("known", "fake-cheap", "0.01"))
    model_registry.register(_image_model("unknown", "fake-premium", price=None))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    selection = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert selection.model_id == "known"


def test_all_unknown_cost_raises_when_not_allowed() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("unknown-a", "fake-cheap", price=None))
    model_registry.register(_image_model("unknown-b", "fake-premium", price=None))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    with pytest.raises(NoCostAwareCandidateError):
        selector.select(
            ProviderType.IMAGE_GENERATION,
            {ModelCapabilityType.IMAGE_GENERATION.value},
            cost_context={"num_images": 1},
        )


def test_allow_unknown_cost_uses_penalty_and_tie_breaks() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("known", "fake-cheap", "0.01"))
    model_registry.register(_image_model("zeta-unknown", "fake-premium", price=None))
    model_registry.register(_image_model("alpha-unknown", "fake", price=None))

    selector = CostAwareSelector(
        model_registry,
        health_store,
        provider_registry,
        allow_unknown_cost=True,
    )
    selection = selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert selection.model_id == "known"

    # When only unknown-cost candidates remain, the penalty is applied equally and
    # selection falls back to deterministic model_id ordering.
    # Remove known candidate to leave only unknown-cost models.
    model_registry = ModelRegistry(provider_registry)
    model_registry.register(
        ModelDefinition(
            model_id="zeta",
            provider_id="fake-premium",
            provider_type=ProviderType.IMAGE_GENERATION,
            name="zeta",
            capabilities=[ModelCapability(capability=ModelCapabilityType.IMAGE_GENERATION.value)],
        )
    )
    model_registry.register(
        ModelDefinition(
            model_id="alpha",
            provider_id="fake",
            provider_type=ProviderType.IMAGE_GENERATION,
            name="alpha",
            capabilities=[ModelCapability(capability=ModelCapabilityType.IMAGE_GENERATION.value)],
        )
    )
    all_unknown_selector = CostAwareSelector(
        model_registry,
        health_store,
        provider_registry,
        allow_unknown_cost=True,
    )
    selection = all_unknown_selector.select(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert selection.model_id == "alpha"


def test_select_provider_resolves_instance() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("cheap", "fake-cheap", "0.01"))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    provider = selector.select_provider(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": 1},
    )
    assert isinstance(provider, FakeImageGenerationProvider)


def test_image_factory_cost_aware_selection() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_image_model("cheap", "fake-cheap", "0.01"))
    model_registry.register(_image_model("premium", "fake-premium", "0.10"))

    # Use the same registries so the selector sees the registered models.
    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    request = ImageGenerationRequest(prompt="test", num_images=1)
    provider = selector.select_provider(
        ProviderType.IMAGE_GENERATION,
        {ModelCapabilityType.IMAGE_GENERATION.value},
        cost_context={"num_images": request.num_images},
    )
    assert isinstance(provider, FakeImageGenerationProvider)
    assert provider._provider == "fake-cheap"


def test_tts_factory_cost_aware_selection() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_tts_model("cheap-tts", "fake-tts-cheap", "0.0001"))
    model_registry.register(_tts_model("default-tts", "fake", "0.001"))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    request = TTSRequest(text="hello world", voice_id="v1")
    provider = selector.select_provider(
        ProviderType.TTS,
        {ModelCapabilityType.SPEECH_SYNTHESIS.value},
        cost_context={"character_count": len(request.text)},
    )
    assert provider._provider == "fake-tts-cheap"


def test_video_factory_cost_aware_selection() -> None:
    provider_registry, model_registry, health_store = _make_registry()
    model_registry.register(_video_model("cheap-video", "fake-video-cheap", "0.05"))
    model_registry.register(_video_model("default-video", "fake", "0.20"))

    selector = CostAwareSelector(model_registry, health_store, provider_registry)
    request = VideoGenerationRequest(
        prompt="test",
        duration=5.0,
    )
    provider = selector.select_provider(
        ProviderType.VIDEO_GENERATION,
        {ModelCapabilityType.IMAGE_TO_VIDEO.value},
        cost_context={"duration_seconds": request.duration},
    )
    assert provider._provider == "fake-video-cheap"


def test_default_factory_mode_ignores_cost() -> None:
    settings = load_settings({"IMAGE_GENERATION_PROVIDER": "fake"})
    provider = ImageGenerationProviderFactory.create(settings=settings)
    assert isinstance(provider, FakeImageGenerationProvider)
    assert provider._provider == "fake"


def test_cost_estimator_respects_unit_and_quantity() -> None:
    from app.services.cost_aware_selector import CostEstimator

    model = _image_model("m", "fake", "0.02")
    estimate = CostEstimator.estimate(model, {"num_images": 3})
    assert estimate is not None
    cost, currency = estimate
    assert cost == Decimal("0.06")
    assert currency == "USD"


def test_missing_pricing_returns_none() -> None:
    from app.services.cost_aware_selector import CostEstimator

    model = _image_model("m", "fake", price=None)
    assert CostEstimator.estimate(model, {"num_images": 1}) is None
