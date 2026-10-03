"""Provider-neutral LLM errors."""


class LLMProviderError(Exception):
    """Raised when an LLM provider fails or returns unusable output."""
