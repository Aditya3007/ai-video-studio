"""Provider-neutral model capability and configuration registry."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.provider_registry import ProviderRegistry, ProviderType, get_default_registry

__all__ = [
    "DuplicateModelError",
    "IncompatibleModelError",
    "InvalidModelConfigurationError",
    "ModelCapability",
    "ModelCapabilityType",
    "ModelConfiguration",
    "ModelDefinition",
    "ModelNotFoundError",
    "ModelRegistry",
    "ModelRegistryError",
]


class ModelRegistryError(Exception):
    """Base error for model registry failures."""


class ModelNotFoundError(ModelRegistryError):
    """Raised when a requested model is not registered."""


class DuplicateModelError(ModelRegistryError):
    """Raised when a model ID is registered more than once without override."""


class IncompatibleModelError(ModelRegistryError):
    """Raised when a model is incompatible with its provider or category."""


class InvalidModelConfigurationError(ModelRegistryError):
    """Raised when a model configuration is invalid or contains secrets."""


_SECRET_KEY_SUBSTRINGS = ("api_key", "token", "secret", "password", "credential")


def _contains_secret_key(parameters: dict[str, Any]) -> bool:
    """Return True if any parameter key looks like a secret."""
    return any(
        substring in key.lower() for key in parameters for substring in _SECRET_KEY_SUBSTRINGS
    )


def _validate_no_secrets(parameters: dict[str, Any]) -> None:
    """Reject parameters that store secret-like keys."""
    if _contains_secret_key(parameters):
        raise InvalidModelConfigurationError(
            "Model parameters must not contain secret keys such as api_key, token, or password"
        )


class ModelCapabilityType(StrEnum):
    """Stable capability identifiers."""

    TEXT_GENERATION = "text_generation"
    STRUCTURED_OUTPUT = "structured_output"
    IMAGE_GENERATION = "image_generation"
    IMAGE_TO_VIDEO = "image_to_video"
    TEXT_TO_VIDEO = "text_to_video"
    SPEECH_SYNTHESIS = "speech_synthesis"
    MUSIC_GENERATION = "music_generation"
    SOUND_EFFECT_GENERATION = "sound_effect_generation"
    NARRATIVE_QA = "narrative_qa"
    VISUAL_QA = "visual_qa"
    REFERENCE_IMAGE_CONDITIONING = "reference_image_conditioning"


class ModelCapability(BaseModel):
    """A provider-neutral capability with optional constraints."""

    capability: str
    constraints: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelDefinition(BaseModel):
    """Provider-neutral model metadata."""

    model_id: str
    provider_id: str
    provider_type: ProviderType
    name: str
    capabilities: list[ModelCapability] = Field(default_factory=list)
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    pricing: dict[str, Any] | None = None
    enabled: bool = True

    @field_validator("model_id", "provider_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value:
            raise ValueError("identifier must be non-empty")
        return value

    @field_validator("default_parameters")
    @classmethod
    def _no_secrets_in_defaults(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_no_secrets(value)
        return value


class ModelConfiguration(BaseModel):
    """Provider-neutral runtime configuration for a model."""

    model_id: str
    provider_id: str
    provider_type: ProviderType
    parameters: dict[str, Any] = Field(default_factory=dict)
    pricing: dict[str, Any] | None = None
    enabled: bool = True

    @field_validator("model_id", "provider_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value:
            raise ValueError("identifier must be non-empty")
        return value

    @field_validator("parameters")
    @classmethod
    def _no_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_no_secrets(value)
        return value


class ModelRegistry:
    """Registers and resolves provider-neutral model definitions and configurations."""

    def __init__(self, provider_registry: ProviderRegistry | None = None) -> None:
        self._provider_registry = provider_registry
        self._models: dict[str, ModelDefinition] = {}
        self._configurations: dict[str, ModelConfiguration] = {}

    def _validate_provider(self, model: ModelDefinition) -> None:
        if not model.provider_id:
            raise IncompatibleModelError("provider_id must be non-empty")
        if self._provider_registry is not None:
            if not self._provider_registry.has(model.provider_type, model.provider_id):
                raise IncompatibleModelError(
                    f"Provider '{model.provider_id}' is not registered for {model.provider_type}"
                )

    def register(
        self,
        model: ModelDefinition,
        *,
        override: bool = False,
    ) -> None:
        """Register a model definition."""
        if not override and model.model_id in self._models:
            raise DuplicateModelError(f"Model '{model.model_id}' is already registered")
        self._validate_provider(model)
        self._models[model.model_id] = model
        # Clear any stale configuration when a model is re-registered.
        if model.model_id in self._configurations:
            del self._configurations[model.model_id]

    def has(self, model_id: str) -> bool:
        """Return True if the model is registered."""
        return model_id in self._models

    def resolve(self, model_id: str) -> ModelDefinition:
        """Return the model definition for the given ID."""
        if model_id not in self._models:
            raise ModelNotFoundError(f"Model '{model_id}' not found")
        return self._models[model_id]

    def list(
        self,
        provider_type: ProviderType | None = None,
        enabled_only: bool = False,
    ) -> list[ModelDefinition]:
        """List registered models, optionally filtered."""
        models = self._models.values()
        if provider_type is not None:
            models = (m for m in models if m.provider_type == provider_type)
        if enabled_only:
            models = (m for m in models if m.enabled)
        return sorted(models, key=lambda m: m.model_id)

    def list_by_capabilities(
        self,
        capabilities: set[str],
        provider_type: ProviderType | None = None,
    ) -> list[ModelDefinition]:
        """List models that expose all of the requested capabilities."""
        return [
            m
            for m in self.list(provider_type=provider_type)
            if self.has_capabilities(m.model_id, capabilities)
        ]

    def list_by_capability(
        self,
        capability: str,
        provider_type: ProviderType | None = None,
    ) -> list[ModelDefinition]:
        """List models that expose a single capability."""
        return self.list_by_capabilities({capability}, provider_type=provider_type)

    def has_capabilities(self, model_id: str, capabilities: set[str]) -> bool:
        """Return True if the model exposes all requested capabilities."""
        if not capabilities:
            return True
        model = self.resolve(model_id)
        model_caps = {c.capability for c in model.capabilities}
        return capabilities.issubset(model_caps)

    def has_capability(self, model_id: str, capability: str) -> bool:
        """Return True if the model exposes the given capability."""
        return self.has_capabilities(model_id, {capability})

    def get_configuration(self, model_id: str) -> ModelConfiguration:
        """Return explicit or default configuration for the model."""
        if model_id in self._configurations:
            return self._configurations[model_id]
        model = self.resolve(model_id)
        return ModelConfiguration(
            model_id=model.model_id,
            provider_id=model.provider_id,
            provider_type=model.provider_type,
            parameters=dict(model.default_parameters),
            pricing=model.pricing,
            enabled=model.enabled,
        )

    def set_configuration(self, configuration: ModelConfiguration) -> None:
        """Store runtime configuration for a model."""
        model = self.resolve(configuration.model_id)
        if (
            configuration.provider_id != model.provider_id
            or configuration.provider_type != model.provider_type
        ):
            raise InvalidModelConfigurationError(
                "Configuration provider does not match model provider"
            )
        _validate_no_secrets(configuration.parameters)
        if configuration.pricing is not None:
            _validate_no_secrets(configuration.pricing)
        self._configurations[configuration.model_id] = configuration


_default_model_registry: ModelRegistry | None = None


def get_default_model_registry() -> ModelRegistry:
    """Return the process-wide default model registry."""
    global _default_model_registry
    if _default_model_registry is None:
        _default_model_registry = ModelRegistry(get_default_registry())
    return _default_model_registry
