"""Provider-neutral music/sound-effect generation errors."""


class AudioGenerationError(Exception):
    """Base class for music/sound-effect generation failures."""


class AudioRequestError(AudioGenerationError):
    """Raised when the generation request is invalid."""


class AudioProviderAuthError(AudioGenerationError):
    """Raised when provider authentication/configuration fails."""


class AudioProviderUnavailableError(AudioGenerationError):
    """Raised when the provider is unavailable."""


class AudioProviderRateLimitError(AudioGenerationError):
    """Raised when a rate limit is hit."""


class AudioGenerationFailedError(AudioGenerationError):
    """Raised when the provider reports a generation failure."""


class AudioCapabilityError(AudioGenerationError):
    """Raised when the requested capability is not supported by the provider."""
