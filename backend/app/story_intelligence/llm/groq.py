"""Groq LLM provider adapter."""

import os
from typing import Any

from pydantic import BaseModel

from app.story_intelligence.llm.errors import LLMProviderError
from app.story_intelligence.llm.provider import LLMResponse


class GroqLLMProvider:
    """Groq LLM provider adapter."""

    def __init__(
        self,
        *,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize Groq provider.

        Args:
            model: Groq model identifier.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            api_key: Groq API key. If None, reads from GROQ_API_KEY environment variable.
        """
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._api_key = api_key or os.getenv("GROQ_API_KEY")

        if not self._api_key:
            raise LLMProviderError(
                "Groq API key is required. Set GROQ_API_KEY environment "
                "variable or pass api_key parameter."
            )

        try:
            from groq import Groq as GroqClient

            self._client = GroqClient(api_key=self._api_key)
        except ImportError as exc:
            raise LLMProviderError(
                "Groq SDK is not installed. Install with: pip install groq"
            ) from exc

    def generate(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Generate text using Groq.

        Args:
            system_prompt: Optional system prompt.
            user_prompt: User prompt.
            response_model: Optional Pydantic model for structured output.

        Returns:
            Provider-neutral LLM response.

        Raises:
            LLMProviderError: If generation fails.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            content = completion.choices[0].message.content or ""
            parsed: dict[str, Any] | None = None

            if response_model is not None:
                try:
                    parsed = response_model.model_validate_json(content)
                except Exception as exc:
                    raise LLMProviderError(
                        f"Failed to parse response as {response_model.__name__}: {exc}"
                    ) from exc

            return LLMResponse(
                content=content,
                parsed=parsed,
                model=self._model,
                provider="groq",
                usage={
                    "prompt_tokens": completion.usage.prompt_tokens if completion.usage else None,
                    "completion_tokens": completion.usage.completion_tokens
                    if completion.usage
                    else None,
                    "total_tokens": completion.usage.total_tokens if completion.usage else None,
                },
                metadata={
                    "finish_reason": completion.choices[0].finish_reason,
                    "id": completion.id,
                },
            )
        except Exception as exc:
            raise LLMProviderError(f"Groq generation failed: {exc}") from exc
