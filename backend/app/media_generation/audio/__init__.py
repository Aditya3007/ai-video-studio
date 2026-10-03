"""Music and sound-effect generation provider boundary."""

from app.media_generation.audio.errors import (
    AudioCapabilityError,
    AudioGenerationError,
    AudioGenerationFailedError,
    AudioProviderAuthError,
    AudioProviderRateLimitError,
    AudioProviderUnavailableError,
    AudioRequestError,
)
from app.media_generation.audio.factory import AudioGenerationProviderFactory
from app.media_generation.audio.fake import FakeAudioGenerationProvider
from app.media_generation.audio.provider import (
    AudioGenerationProvider,
    AudioGenerationRequest,
    AudioGenerationResult,
    AudioReference,
    AudioUsage,
)

__all__ = [
    "AudioCapabilityError",
    "AudioGenerationError",
    "AudioGenerationFailedError",
    "AudioGenerationProvider",
    "AudioGenerationProviderFactory",
    "AudioGenerationRequest",
    "AudioGenerationResult",
    "AudioProviderAuthError",
    "AudioProviderRateLimitError",
    "AudioProviderUnavailableError",
    "AudioReference",
    "AudioRequestError",
    "AudioUsage",
    "FakeAudioGenerationProvider",
]
