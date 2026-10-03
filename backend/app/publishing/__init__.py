"""Provider-neutral YouTube publishing abstraction."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PublishingStatus


class PublishingError(Exception):
    """Raised when a publishing operation fails."""


class PublishingRequest(BaseModel):
    """Provider-neutral request to publish a completed episode asset."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    series_id: UUID
    episode_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=100)
    visibility: str = Field(default="public")
    category: str | None = None
    is_shorts: bool = True
    scheduled_publish_time: datetime | None = None
    idempotency_key: str | None = None


class PublishingResult(BaseModel):
    """Provider-neutral result of a publishing operation."""

    model_config = ConfigDict(from_attributes=True)

    publication_id: str
    status: PublishingStatus
    provider: str
    url: str | None = None
    requested_at: datetime
    published_at: datetime | None = None
    error_message: str | None = None
    metadata: dict | None = None


@runtime_checkable
class PublishingProvider(Protocol):
    """Provider-neutral contract for publishing a video."""

    @property
    def provider_id(self) -> str:
        """Return the stable provider identifier."""
        ...

    def publish(self, request: PublishingRequest) -> PublishingResult:
        """Publish the requested asset and return a normalized result."""
        ...

    def get_status(self, publication_id: str) -> PublishingResult:
        """Return the current status of a publication."""
        ...

    def cancel(self, publication_id: str) -> PublishingResult:
        """Cancel a publication if its lifecycle allows cancellation."""
        ...


class FakePublishingProvider:
    """Deterministic fake publishing provider for local tests."""

    provider_id: str = "fake"

    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self._state: dict[str, PublishingResult] = {}

    def _deterministic_id(self, request: PublishingRequest) -> str:
        key = request.idempotency_key or str(request.asset_id)
        return f"fake-publication-{key}"

    def publish(self, request: PublishingRequest) -> PublishingResult:
        publication_id = self._deterministic_id(request)
        requested_at = datetime.now(UTC)
        if self._should_fail:
            result = PublishingResult(
                publication_id=publication_id,
                status=PublishingStatus.FAILED,
                provider=self.provider_id,
                requested_at=requested_at,
                error_message="Fake provider simulated failure.",
            )
            self._state[publication_id] = result
            return result

        result = PublishingResult(
            publication_id=publication_id,
            status=PublishingStatus.PUBLISHED,
            provider=self.provider_id,
            url=f"https://example.com/watch/{publication_id}",
            requested_at=requested_at,
            published_at=requested_at,
            metadata={
                "asset_id": str(request.asset_id),
                "title": request.title,
                "visibility": request.visibility,
            },
        )
        self._state[publication_id] = result
        return result

    def get_status(self, publication_id: str) -> PublishingResult:
        if publication_id not in self._state:
            raise PublishingError(f"Publication '{publication_id}' not found.")
        return self._state[publication_id]

    def cancel(self, publication_id: str) -> PublishingResult:
        if publication_id not in self._state:
            raise PublishingError(f"Publication '{publication_id}' not found.")
        current = self._state[publication_id]
        if current.status == PublishingStatus.PUBLISHED.value:
            raise PublishingError("Cannot cancel an already published video.")
        cancelled = current.model_copy(update={"status": PublishingStatus.CANCELLED.value})
        self._state[publication_id] = cancelled
        return cancelled
