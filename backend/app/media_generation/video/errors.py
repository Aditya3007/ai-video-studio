"""Provider-neutral video generation errors."""


class VideoGenerationError(Exception):
    """Base class for video-generation failures."""


class VideoRequestError(VideoGenerationError):
    """Raised when the generation request is invalid."""


class VideoProviderAuthError(VideoGenerationError):
    """Raised when provider authentication/configuration fails."""


class VideoProviderUnavailableError(VideoGenerationError):
    """Raised when the provider is unavailable."""


class VideoProviderRateLimitError(VideoGenerationError):
    """Raised when a rate limit is hit."""


class VideoGenerationFailedError(VideoGenerationError):
    """Raised when the provider reports a generation failure."""


class VideoCapabilityError(VideoGenerationError):
    """Raised when the requested capability is not supported by the provider."""


class VideoValidationError(VideoGenerationError):
    """Raised when a generated video clip fails application validation."""
