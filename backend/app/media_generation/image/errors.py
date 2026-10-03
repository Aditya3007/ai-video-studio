"""Provider-neutral image generation errors."""


class ImageGenerationError(Exception):
    """Base class for image-generation failures."""


class ImageRequestError(ImageGenerationError):
    """Raised when the generation request is invalid."""


class ImageProviderAuthError(ImageGenerationError):
    """Raised when provider authentication/configuration fails."""


class ImageProviderUnavailableError(ImageGenerationError):
    """Raised when the provider is unavailable."""


class ImageProviderRateLimitError(ImageGenerationError):
    """Raised when a rate limit is hit."""


class ImageGenerationFailedError(ImageGenerationError):
    """Raised when the provider reports a generation failure."""


class StoryboardError(ImageGenerationError):
    """Raised when a storyboard/keyframe workflow fails."""


class ReferenceConditioningError(StoryboardError):
    """Raised when a canonical reference cannot be conditioned safely."""
