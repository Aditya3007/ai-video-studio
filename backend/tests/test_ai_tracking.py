"""Tests for prompt/version and model configuration tracking."""

import pytest
from pydantic import ValidationError

from app.ai_tracking import (
    DuplicatePromptVersionError,
    GenerationConfigurationReference,
    InvalidConfigurationVersionError,
    MissingPromptVariableError,
    PromptNotFoundError,
    PromptRegistry,
    PromptRenderer,
    PromptVersion,
    SecretInPromptError,
    compute_configuration_version,
)
from app.model_registry import (
    ModelCapability,
    ModelCapabilityType,
    ModelConfiguration,
    ModelDefinition,
    ModelRegistry,
)
from app.provider_registry import ProviderType


def _analysis_prompt(version: str = "v1") -> PromptVersion:
    return PromptVersion(
        prompt_id="story-analysis",
        version=version,
        content="Analyze story {{ title }} with universe {{ universe }}.",
        purpose="story analysis",
        operation="analyze",
        variables=["title", "universe"],
    )


def _llm_model() -> ModelDefinition:
    return ModelDefinition(
        model_id="fake-llm",
        provider_id="fake",
        provider_type=ProviderType.LLM,
        name="Fake LLM",
        capabilities=[ModelCapability(capability=ModelCapabilityType.TEXT_GENERATION)],
        default_parameters={"temperature": 0.5},
    )


class TestPromptRegistry:
    def test_register_and_resolve(self) -> None:
        registry = PromptRegistry()
        prompt = _analysis_prompt()
        registry.register(prompt)
        resolved = registry.resolve("story-analysis", "v1")
        assert resolved is prompt

    def test_duplicate_version_rejected(self) -> None:
        registry = PromptRegistry()
        registry.register(_analysis_prompt())
        with pytest.raises(DuplicatePromptVersionError):
            registry.register(_analysis_prompt())

    def test_list_versions(self) -> None:
        registry = PromptRegistry()
        registry.register(_analysis_prompt("v1"))
        registry.register(_analysis_prompt("v2"))
        assert registry.list_versions("story-analysis") == ["v1", "v2"]

    def test_get_and_set_current(self) -> None:
        registry = PromptRegistry()
        registry.register(_analysis_prompt("v1"))
        registry.register(_analysis_prompt("v2"))
        assert registry.get_current("story-analysis").version == "v1"
        registry.set_current("story-analysis", "v2")
        assert registry.get_current("story-analysis").version == "v2"

    def test_resolve_unknown_prompt(self) -> None:
        registry = PromptRegistry()
        with pytest.raises(PromptNotFoundError):
            registry.resolve("missing", "v1")

    def test_set_current_unknown_version(self) -> None:
        registry = PromptRegistry()
        registry.register(_analysis_prompt())
        with pytest.raises(PromptNotFoundError):
            registry.set_current("story-analysis", "v99")

    def test_immutability(self) -> None:
        prompt = _analysis_prompt()
        with pytest.raises(ValidationError):
            prompt.content = "mutated"


class TestPromptRenderer:
    def test_render_valid(self) -> None:
        prompt = _analysis_prompt()
        rendered = PromptRenderer.render(prompt, {"title": "My Story", "universe": "My Universe"})
        assert rendered.prompt_id == "story-analysis"
        assert rendered.prompt_version == "v1"
        assert "My Story" in rendered.content
        assert "My Universe" in rendered.content
        assert "{{" not in rendered.content

    def test_missing_variable(self) -> None:
        prompt = _analysis_prompt()
        with pytest.raises(MissingPromptVariableError):
            PromptRenderer.render(prompt, {"title": "My Story"})

    def test_render_does_not_mutate_version(self) -> None:
        prompt = _analysis_prompt()
        original = prompt.content
        PromptRenderer.render(prompt, {"title": "T", "universe": "U"})
        assert prompt.content == original

    def test_registry_render_current(self) -> None:
        registry = PromptRegistry()
        registry.register(_analysis_prompt())
        rendered = registry.render("story-analysis", {"title": "T", "universe": "U"})
        assert "T" in rendered.content

    def test_secret_in_prompt_rejected(self) -> None:
        with pytest.raises(SecretInPromptError):
            PromptVersion(
                prompt_id="bad",
                version="v1",
                content="Use api_key: secret",
                variables=[],
            )


class TestModelConfigurationVersion:
    def test_configuration_identity_is_deterministic(self) -> None:
        config = ModelConfiguration(
            model_id="fake-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            parameters={"temperature": 0.5, "top_p": 0.9},
        )
        first = compute_configuration_version(config)
        second = compute_configuration_version(config)
        assert first.version_id == second.version_id

    def test_equivalent_configuration_stable_identity(self) -> None:
        config_a = ModelConfiguration(
            model_id="fake-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            parameters={"a": 1, "b": 2},
        )
        config_b = ModelConfiguration(
            model_id="fake-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            parameters={"b": 2, "a": 1},
        )
        id_a = compute_configuration_version(config_a).version_id
        id_b = compute_configuration_version(config_b).version_id
        assert id_a == id_b

    def test_different_configuration_different_identity(self) -> None:
        config_a = ModelConfiguration(
            model_id="fake-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            parameters={"temperature": 0.5},
        )
        config_b = ModelConfiguration(
            model_id="fake-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            parameters={"temperature": 0.9},
        )
        id_a = compute_configuration_version(config_a).version_id
        id_b = compute_configuration_version(config_b).version_id
        assert id_a != id_b

    def test_configuration_rejects_secret_keys(self) -> None:
        config = ModelConfiguration.model_construct(
            model_id="fake-llm",
            provider_id="fake",
            provider_type=ProviderType.LLM,
            parameters={"api_key": "secret"},
        )
        with pytest.raises(InvalidConfigurationVersionError):
            compute_configuration_version(config)


class TestIntegration:
    def test_model_registry_configuration_versioning(self) -> None:
        registry = ModelRegistry()
        registry.register(_llm_model())
        config = registry.get_configuration("fake-llm")
        versioned = compute_configuration_version(config)
        assert versioned.configuration.model_id == "fake-llm"
        assert len(versioned.version_id) == 64

    def test_generation_configuration_reference(self) -> None:
        prompt_registry = PromptRegistry()
        prompt_registry.register(_analysis_prompt("v1"))
        model_registry = ModelRegistry()
        model_registry.register(_llm_model())

        rendered = prompt_registry.render(
            "story-analysis", {"title": "T", "universe": "U"}, version="v1"
        )
        config_version = compute_configuration_version(model_registry.get_configuration("fake-llm"))
        ref = GenerationConfigurationReference(
            prompt_id=rendered.prompt_id,
            prompt_version=rendered.prompt_version,
            model_id="fake-llm",
            model_configuration_version=config_version.version_id,
            provider_type=ProviderType.LLM.value,
            provider_id="fake",
        )
        assert ref.prompt_version == "v1"
        assert ref.model_configuration_version == config_version.version_id
