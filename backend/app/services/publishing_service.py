"""Application publishing service for provider-neutral video publishing."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import Asset
from app.models.enums import AssetStatus, AssetType
from app.provider_registry import ProviderRegistry, ProviderType
from app.publishing import (
    FakePublishingProvider,
    PublishingError,
    PublishingProvider,
    PublishingRequest,
    PublishingResult,
)
from app.storage import StorageBackend


class PublishingServiceError(Exception):
    """Raised when the publishing service cannot process a request."""


class PublishingService:
    """Validate and execute publishing requests through a provider-neutral boundary."""

    MAX_SHORTS_DURATION_SECONDS = 60
    ASPECT_RATIO_TOLERANCE = 0.05

    def __init__(
        self,
        db: Session,
        storage: StorageBackend,
        *,
        provider: PublishingProvider | None = None,
        registry: ProviderRegistry | None = None,
        provider_id: str = "fake",
    ) -> None:
        self._db = db
        self._storage = storage
        self._registry = registry
        if provider is not None:
            self._provider = provider
        elif registry is not None:
            self._provider = registry.resolve(ProviderType.PUBLISHING, provider_id)
        else:
            self._provider = FakePublishingProvider()

    @staticmethod
    def _sanitize_error(value: str | None) -> str | None:
        if not value:
            return value
        patterns = [
            (r"(Bearer\s+)[A-Za-z0-9_\-]+", r"\1***REDACTED***"),
            (r"(?i)(api[_-]?key\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
            (r"(?i)(token\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
            (r"(?i)(password\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
        ]
        for pattern, repl in patterns:
            value = re.sub(pattern, repl, value)
        return value

    def _load_asset(self, series_id: str, asset_id: str) -> Asset:
        asset = self._db.get(Asset, asset_id)
        if not asset:
            raise PublishingServiceError("Asset not found.")
        if str(asset.series_id) != series_id:
            raise PublishingServiceError("Asset does not belong to the requested Series.")
        return asset

    def _validate_publishable(self, asset: Asset) -> None:
        if asset.asset_type != AssetType.VIDEO.value:
            raise PublishingServiceError("Only video assets can be published.")
        if asset.status != AssetStatus.AVAILABLE.value:
            raise PublishingServiceError("Asset is not available for publishing.")
        if not asset.storage_key:
            raise PublishingServiceError("Asset has no storage key.")
        if not self._storage.exists(asset.storage_key):
            raise PublishingServiceError("Asset is not available in storage.")

    def _validate_shorts_constraints(self, asset: Asset) -> None:
        metadata = asset.asset_metadata or {}
        width = metadata.get("width")
        height = metadata.get("height")
        duration = metadata.get("duration_seconds")

        if width is None or height is None or duration is None:
            raise PublishingServiceError("Asset metadata missing width, height, or duration.")

        if width <= 0 or height <= 0:
            raise PublishingServiceError("Invalid asset dimensions.")

        aspect_ratio = width / height
        target = 9 / 16
        if abs(aspect_ratio - target) > self.ASPECT_RATIO_TOLERANCE:
            raise PublishingServiceError(f"Aspect ratio {aspect_ratio:.3f} is not 9:16.")

        if duration > self.MAX_SHORTS_DURATION_SECONDS:
            raise PublishingServiceError(
                f"Duration {duration}s exceeds Shorts maximum of "
                f"{self.MAX_SHORTS_DURATION_SECONDS}s."
            )

    def publish(self, request: PublishingRequest) -> PublishingResult:
        """Validate the request and invoke the configured publishing provider."""
        asset = self._load_asset(str(request.series_id), str(request.asset_id))
        self._validate_publishable(asset)
        if request.is_shorts:
            self._validate_shorts_constraints(asset)

        try:
            result = self._provider.publish(request)
        except PublishingError:
            raise
        except Exception as exc:
            raise PublishingServiceError(f"Publishing provider failed: {exc}") from exc

        if result.error_message:
            result = result.model_copy(
                update={"error_message": self._sanitize_error(result.error_message)}
            )
        return result

    def get_status(self, publication_id: str) -> PublishingResult:
        """Return the current status of a publication."""
        try:
            return self._provider.get_status(publication_id)
        except PublishingError:
            raise
        except Exception as exc:
            raise PublishingServiceError(f"Status lookup failed: {exc}") from exc

    def cancel(self, publication_id: str) -> PublishingResult:
        """Cancel a publication if the provider allows it."""
        try:
            return self._provider.cancel(publication_id)
        except PublishingError:
            raise
        except Exception as exc:
            raise PublishingServiceError(f"Cancel failed: {exc}") from exc
