"""Publishing workflow API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.deps import DbSession, StorageDep
from app.models.publishing_job import PublishingJob
from app.services.publishing_workflow_service import (
    PublishingWorkflowError,
    PublishingWorkflowResult,
    PublishingWorkflowService,
)

router = APIRouter(prefix="/publishing", tags=["publishing"])


class PublishingWorkflowCreate(BaseModel):
    """Request body for creating a publishing workflow job."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    episode_id: UUID
    asset_id: UUID
    thumbnail_asset_id: UUID | None = None
    scheduled_at: datetime | None = None
    idempotency_key: str | None = None
    provider_id: str = "fake"
    metadata: dict | None = None


class PublishingWorkflowResponse(PublishingWorkflowResult):
    """Public response model for a publishing workflow job."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    episode_id: UUID
    asset_id: UUID
    thumbnail_asset_id: UUID | None = None
    scheduled_at: datetime | None = None
    provider_id: str
    correlation_id: str | None = None


def _to_response(job: PublishingJob) -> PublishingWorkflowResponse:
    return PublishingWorkflowResponse(
        job_id=UUID(job.id),
        series_id=UUID(job.series_id),
        episode_id=UUID(job.episode_id),
        asset_id=UUID(job.asset_id),
        thumbnail_asset_id=UUID(job.thumbnail_asset_id) if job.thumbnail_asset_id else None,
        status=job.status,
        scheduled_at=job.scheduled_at,
        provider_id=job.provider_id,
        external_publication_id=job.external_publication_id,
        external_url=job.external_url,
        attempts=job.attempts,
        error_message=job.error_message,
        correlation_id=job.correlation_id,
    )


def _service(db: DbSession, storage: StorageDep) -> PublishingWorkflowService:
    return PublishingWorkflowService(db, storage)


@router.post("", response_model=PublishingWorkflowResponse)
def create_publishing(
    db: DbSession,
    storage: StorageDep,
    request: PublishingWorkflowCreate,
) -> PublishingWorkflowResponse:
    """Request a new episode publication, either immediate or scheduled."""
    service = _service(db, storage)
    try:
        job = service.request_publication(
            str(request.series_id),
            str(request.episode_id),
            str(request.asset_id),
            thumbnail_asset_id=(
                str(request.thumbnail_asset_id) if request.thumbnail_asset_id else None
            ),
            scheduled_at=request.scheduled_at,
            idempotency_key=request.idempotency_key,
            provider_id=request.provider_id,
        )
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(job)
    return _to_response(job)


@router.get("/{series_id}/{job_id}", response_model=PublishingWorkflowResponse)
def get_publishing(
    db: DbSession,
    storage: StorageDep,
    series_id: UUID,
    job_id: UUID,
) -> PublishingWorkflowResponse:
    """Retrieve a publishing job by Series and job ID."""
    service = _service(db, storage)
    try:
        job = service.get(str(series_id), str(job_id))
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(job)


@router.post("/{series_id}/{job_id}/cancel", response_model=PublishingWorkflowResponse)
def cancel_publishing(
    db: DbSession,
    storage: StorageDep,
    series_id: UUID,
    job_id: UUID,
) -> PublishingWorkflowResponse:
    """Cancel a scheduled/ready publishing job."""
    service = _service(db, storage)
    try:
        result = service.cancel(str(series_id), str(job_id))
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(result)


@router.post("/{series_id}/{job_id}/retry", response_model=PublishingWorkflowResponse)
def retry_publishing(
    db: DbSession,
    storage: StorageDep,
    series_id: UUID,
    job_id: UUID,
) -> PublishingWorkflowResponse:
    """Retry a failed publishing job."""
    service = _service(db, storage)
    try:
        job = service.retry(str(series_id), str(job_id))
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(job)
