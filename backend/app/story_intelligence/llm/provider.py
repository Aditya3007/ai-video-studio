"""Provider-neutral LLM contract."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Provider-neutral response from any LLM provider."""

    content: str
    parsed: dict[str, Any] | None = None
    model: str | None = None
    provider: str | None = None
    usage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract contract for all LLM provider adapters."""

    def generate(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Generate a provider-neutral response."""
        ...
