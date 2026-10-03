"""Tests for the provider-neutral model capability/configuration registry."""

import pytest

from app.model_registry import (
    DuplicateModelError,
    IncompatibleModelError,
    InvalidModelConfigurationError,
    ModelCapability,
    ModelCapabilityType,
    ModelConfiguration,
    ModelDefinition,
    ModelNotFoundError,
    ModelRegistry,
)
from app.provider_registry import ProviderType, get_default_registry


def _fake_llm_model() -> ModelDefinition:
    return ModelDefinition(
        model_id="fake-llm",
        provider_id="fake",
        provider_type=ProviderType.LLM,
        name="Fake LLM",
        capabilities=[ModelCapability(capability=ModelCapabilityType.TEXT_GENERATION)],
        default_parameters={"temperature": 0.5},
    )


def _fake_image_model() -> ModelDefinition:
    return ModelDefinition(
        model_id="fake-image",
        provider_id="fake",
        provider_type=ProviderType.IMAGE_GENERATION,
        name="Fake Image",
        capabilities=[
            ModelCapability(
                capability=ModelCapabilityType.IMAGE_GENERATION,
                constraints={"aspect_ratios": ["16:9", "4:3"]},
            )
        ],
    )


class TestModelRegistry:
    def test_register_and_resolve(self) -> None:
        registry = ModelRegistry()
        model = _fake_llm_model()
        registry.register(model)
        resolved = registry.resolve("fake-llm")
        assert resolved is model

    def test_has_and_list(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        registry.register(_fake_image_model())
        assert registry.has("fake-llm")
        assert not registry.has("missing")
        assert [m.model_id for m in registry.list()] == ["fake-image", "fake-llm"]

    def test_list_by_provider_type(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        registry.register(_fake_image_model())
        llm_models = registry.list(provider_type=ProviderType.LLM)
        assert len(llm_models) == 1
        assert llm_models[0].model_id == "fake-llm"

    def test_unknown_model_raises(self) -> None:
        registry = ModelRegistry()
        with pytest.raises(ModelNotFoundError):
            registry.resolve("missing")

    def test_duplicate_registration(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        with pytest.raises(DuplicateModelError):
            registry.register(_fake_llm_model())

    def test_override_registration(self) -> None:
        registry = ModelRegistry()
        first = _fake_llm_model()
        second = first.model_copy(update={"name": "Updated Fake LLM"})
        registry.register(first)
        registry.register(second, override=True)
        assert registry.resolve("fake-llm").name == "Updated Fake LLM"

    def test_invalid_provider_association(self) -> None:
        registry = ModelRegistry(provider_registry=get_default_registry())
        bad = ModelDefinition(
            model_id="bad-llm",
            provider_id="openai",
            provider_type=ProviderType.LLM,
            name="Bad LLM",
        )
        with pytest.raises(IncompatibleModelError):
            registry.register(bad)

    def test_list_by_capability(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        registry.register(_fake_image_model())
        text_models = registry.list_by_capability(ModelCapabilityType.TEXT_GENERATION)
        assert [m.model_id for m in text_models] == ["fake-llm"]

    def test_has_capability(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        assert registry.has_capability("fake-llm", ModelCapabilityType.TEXT_GENERATION)
        assert not registry.has_capability("fake-llm", ModelCapabilityType.IMAGE_GENERATION)

    def test_default_configuration(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        config = registry.get_configuration("fake-llm")
        assert config.model_id == "fake-llm"
        assert config.parameters == {"temperature": 0.5}
        assert config.enabled is True

    def test_set_configuration(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        registry.set_configuration(
            ModelConfiguration(
                model_id="fake-llm",
                provider_id="fake",
                provider_type=ProviderType.LLM,
                parameters={"temperature": 0.9},
            )
        )
        config = registry.get_configuration("fake-llm")
        assert config.parameters == {"temperature": 0.9}

    def test_configuration_rejects_provider_mismatch(self) -> None:
        registry = ModelRegistry()
        registry.register(_fake_llm_model())
        with pytest.raises(InvalidModelConfigurationError):
            registry.set_configuration(
                ModelConfiguration(
                    model_id="fake-llm",
                    provider_id="other",
                    provider_type=ProviderType.LLM,
                )
            )

    def test_configuration_rejects_secrets(self) -> None:
        registry = ModelRegistry()
        with pytest.raises(InvalidModelConfigurationError):
            registry.register(
                ModelDefinition(
                    model_id="bad",
                    provider_id="fake",
                    provider_type=ProviderType.LLM,
                    name="Bad",
                    default_parameters={"api_key": "secret"},
                )
            )

    def test_isolated_registries(self) -> None:
        first = ModelRegistry()
        second = ModelRegistry()
        first.register(_fake_llm_model())
        assert first.has("fake-llm")
        assert not second.has("fake-llm")

    def test_enabled_filter(self) -> None:
        registry = ModelRegistry()
        enabled = _fake_llm_model()
        disabled = ModelDefinition(
            model_id="disabled-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            name="Disabled",
            enabled=False,
        )
        registry.register(enabled)
        registry.register(disabled)
        assert [m.model_id for m in registry.list(enabled_only=True)] == ["fake-llm"]
