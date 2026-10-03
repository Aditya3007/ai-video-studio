"""Provider-neutral prompt versioning and model configuration tracking."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.model_registry import ModelConfiguration

__all__ = [
    "AITrackingError",
    "compute_configuration_version",
    "DuplicatePromptVersionError",
    "GenerationConfigurationReference",
    "MissingPromptVariableError",
    "ModelConfigurationVersion",
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptRenderer",
    "PromptVersion",
    "RenderedPrompt",
    "SecretInPromptError",
]

_SECRET_SUBSTRINGS = ("api_key", "token", "secret", "password", "credential")

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _contains_secret(value: str) -> bool:
    """Return True if the value contains a secret-like substring."""
    lower = value.lower()
    return any(substring in lower for substring in _SECRET_SUBSTRINGS)


def _validate_no_secrets(value: str) -> None:
    """Raise SecretInPromptError if the value appears to contain secrets."""
    if _contains_secret(value):
        raise SecretInPromptError(
            "Prompt content must not contain secret-like values such as api_key, token, or password"
        )


class AITrackingError(Exception):
    """Base error for AI tracking failures."""


class PromptNotFoundError(AITrackingError):
    """Raised when a prompt or prompt version cannot be found."""


class DuplicatePromptVersionError(AITrackingError):
    """Raised when a prompt version is registered more than once."""


class MissingPromptVariableError(AITrackingError):
    """Raised when a required prompt variable is missing during rendering."""


class SecretInPromptError(AITrackingError):
    """Raised when prompt content or metadata appears to contain secrets."""


class InvalidConfigurationVersionError(AITrackingError):
    """Raised when a configuration version cannot be computed."""


class PromptVersion(BaseModel):
    """Immutable version of a provider-neutral prompt."""

    prompt_id: str
    version: str
    content: str
    purpose: str | None = None
    operation: str | None = None
    description: str | None = None
    variables: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    @field_validator("prompt_id", "version")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("identifier must be non-empty")
        return value

    @field_validator("content")
    @classmethod
    def _no_secrets_in_content(cls, value: str) -> str:
        _validate_no_secrets(value)
        return value

    @field_validator("metadata")
    @classmethod
    def _no_secrets_in_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key in value:
            if isinstance(value[key], str):
                _validate_no_secrets(value[key])
        return value


class RenderedPrompt(BaseModel):
    """Runtime-rendered prompt with traceability back to the source version."""

    prompt_id: str
    prompt_version: str
    content: str

    model_config = ConfigDict(frozen=True)


class PromptRenderer:
    """Render a PromptVersion by substituting {{ variable }} placeholders."""

    @staticmethod
    def render(version: PromptVersion, variables: dict[str, str]) -> RenderedPrompt:
        """Return a RenderedPrompt with substituted variables."""
        required = set(version.variables)
        missing = required - variables.keys()
        if missing:
            raise MissingPromptVariableError(
                f"Missing required prompt variables: {sorted(missing)}"
            )

        def _replacer(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in variables:
                return variables[name]
            # Preserve unmatched placeholders.
            return match.group(0)

        rendered = _PLACEHOLDER_RE.sub(_replacer, version.content)
        return RenderedPrompt(
            prompt_id=version.prompt_id,
            prompt_version=version.version,
            content=rendered,
        )


class PromptRegistry:
    """Registry for immutable prompt versions and current/active selection."""

    def __init__(self) -> None:
        self._versions: dict[str, dict[str, PromptVersion]] = {}
        self._current: dict[str, str] = {}

    def register(
        self,
        version: PromptVersion,
        *,
        set_current: bool = False,
    ) -> None:
        """Register an immutable prompt version."""
        if version.prompt_id not in self._versions:
            self._versions[version.prompt_id] = {}
        if version.version in self._versions[version.prompt_id]:
            raise DuplicatePromptVersionError(
                f"Prompt version '{version.version}' for '{version.prompt_id}' already exists"
            )
        self._versions[version.prompt_id][version.version] = version
        if set_current or version.prompt_id not in self._current:
            self._current[version.prompt_id] = version.version

    def resolve(self, prompt_id: str, version: str) -> PromptVersion:
        """Return a specific prompt version."""
        if prompt_id not in self._versions:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")
        if version not in self._versions[prompt_id]:
            raise PromptNotFoundError(f"Version '{version}' of prompt '{prompt_id}' not found")
        return self._versions[prompt_id][version]

    def has(self, prompt_id: str, version: str | None = None) -> bool:
        """Return True if the prompt/version is registered."""
        if prompt_id not in self._versions:
            return False
        if version is None:
            return True
        return version in self._versions[prompt_id]

    def list_versions(self, prompt_id: str) -> list[str]:
        """Return all registered versions for a prompt in registration order."""
        if prompt_id not in self._versions:
            return []
        return list(self._versions[prompt_id].keys())

    def get_current(self, prompt_id: str) -> PromptVersion:
        """Return the currently active prompt version."""
        if prompt_id not in self._current:
            raise PromptNotFoundError(f"No current version set for prompt '{prompt_id}'")
        return self.resolve(prompt_id, self._current[prompt_id])

    def set_current(self, prompt_id: str, version: str) -> None:
        """Set the active version for a prompt."""
        if not self.has(prompt_id, version):
            raise PromptNotFoundError(
                f"Cannot set current: version '{version}' of prompt '{prompt_id}' not found"
            )
        self._current[prompt_id] = version

    def render(
        self,
        prompt_id: str,
        variables: dict[str, str],
        *,
        version: str | None = None,
    ) -> RenderedPrompt:
        """Render the current or specified prompt version with variables."""
        if version is not None:
            prompt_version = self.resolve(prompt_id, version)
        else:
            prompt_version = self.get_current(prompt_id)
        return PromptRenderer.render(prompt_version, variables)


class ModelConfigurationVersion(BaseModel):
    """Deterministic, immutable identity for a ModelConfiguration snapshot."""

    configuration: ModelConfiguration
    version_id: str

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_configuration(cls, configuration: ModelConfiguration) -> ModelConfigurationVersion:
        """Compute a stable version identity from a ModelConfiguration."""
        # Re-validate that no secrets are present before computing identity.
        for key in configuration.parameters:
            if any(substring in key.lower() for substring in _SECRET_SUBSTRINGS):
                raise InvalidConfigurationVersionError(
                    "Configuration identity cannot include secret keys"
                )
        canonical = json.dumps(
            configuration.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        version_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(configuration=configuration, version_id=version_id)


def compute_configuration_version(
    configuration: ModelConfiguration,
) -> ModelConfigurationVersion:
    """Compute a deterministic ModelConfigurationVersion."""
    return ModelConfigurationVersion.from_configuration(configuration)


class GenerationConfigurationReference(BaseModel):
    """Stable reference to the prompt/model configuration used for an AI operation."""

    prompt_id: str
    prompt_version: str
    model_id: str
    model_configuration_version: str
    provider_type: str
    provider_id: str

    model_config = ConfigDict(frozen=True)
