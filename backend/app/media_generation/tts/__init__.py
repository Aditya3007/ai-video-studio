"""Text-to-speech provider boundary for AI Video Studio."""

from app.media_generation.tts.errors import (
    TTSCapabilityError,
    TTSError,
    TTSProviderAuthError,
    TTSProviderRateLimitError,
    TTSProviderUnavailableError,
    TTSRequestError,
    TTSSynthesisFailedError,
)
from app.media_generation.tts.factory import TTSProviderFactory
from app.media_generation.tts.fake import FakeTTSProvider
from app.media_generation.tts.provider import (
    TTSProvider,
    TTSReference,
    TTSRequest,
    TTSResult,
    TTSUsage,
)

__all__ = [
    "FakeTTSProvider",
    "TTSCapabilityError",
    "TTSError",
    "TTSProvider",
    "TTSProviderAuthError",
    "TTSProviderFactory",
    "TTSProviderRateLimitError",
    "TTSProviderUnavailableError",
    "TTSReference",
    "TTSRequest",
    "TTSRequestError",
    "TTSResult",
    "TTSSynthesisFailedError",
    "TTSUsage",
]
