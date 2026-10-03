"""Provider-neutral text-to-speech errors."""


class TTSError(Exception):
    """Base class for text-to-speech failures."""


class TTSRequestError(TTSError):
    """Raised when the TTS request is invalid."""


class TTSProviderAuthError(TTSError):
    """Raised when provider authentication/configuration fails."""


class TTSProviderUnavailableError(TTSError):
    """Raised when the provider is unavailable."""


class TTSProviderRateLimitError(TTSError):
    """Raised when a rate limit is hit."""


class TTSSynthesisFailedError(TTSError):
    """Raised when the provider reports a synthesis failure."""


class TTSCapabilityError(TTSError):
    """Raised when the requested capability is not supported by the provider."""
