"""Offline fake LLM provider for local testing and development."""

import json
from typing import Any

from pydantic import BaseModel

from app.story_intelligence.llm.errors import LLMProviderError
from app.story_intelligence.llm.provider import LLMResponse

_DEFAULT_RESPONSE: dict[str, Any] = {
    "status": "COMPLETED",
    "metadata": {},
    "narrative": {},
    "characters": [],
    "locations": [],
    "objects": [],
    "events": [],
    "dialogue": [],
    "beats": [],
    "source_refs": [],
    "warnings": ["Fake provider response."],
    "unresolved_entities": [],
}


class FakeLLMProvider:
    """Deterministic fake provider that never makes network requests."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        text: str | None = None,
        *,
        fail: bool = False,
        provider: str = "fake",
        model: str = "fake-model",
    ) -> None:
        self._response = response
        self._text = text
        self._fail = fail
        self._provider = provider
        self._model = model

    def generate(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str = "",
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Return a deterministic fake response."""
        if self._fail:
            raise LLMProviderError("Simulated LLM provider failure.")

        if self._text is not None:
            return LLMResponse(
                content=self._text,
                parsed=None,
                provider=self._provider,
                model=self._model,
            )

        response = self._response if self._response is not None else _DEFAULT_RESPONSE
        if response_model is not None:
            try:
                response_model(**response)
            except Exception as exc:
                raise LLMProviderError(
                    f"Fake response failed response model validation: {exc}"
                ) from exc

        return LLMResponse(
            content=json.dumps(response),
            parsed=response,
            provider=self._provider,
            model=self._model,
        )
