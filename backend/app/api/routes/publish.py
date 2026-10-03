"""Minimal publishing API endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, StorageDep
from app.provider_registry import get_default_registry
from app.publishing import PublishingRequest, PublishingResult
from app.services.publishing_service import PublishingService

router = APIRouter(prefix="/publish", tags=["publish"])


@router.post("", response_model=PublishingResult)
def publish_video(
    db: DbSession, storage: StorageDep, request: PublishingRequest
) -> PublishingResult:
    """Publish a completed episode video through the configured provider."""
    service = PublishingService(
        db,
        storage,
        registry=get_default_registry(),
        provider_id="fake",
    )
    return service.publish(request)
