"""Narration/dialogue routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.schemas import NarrationCreate, NarrationResponse
from app.services.narration_generation_service import (
    NarrationGenerationError,
    NarrationGenerationService,
)
from app.services.narration_service import (
    NarrationError,
    NarrationNotFoundError,
    NarrationService,
)

router = APIRouter(prefix="/series", tags=["narrations"])


@router.post(
    "/{series_id}/narrations",
    status_code=201,
    response_model=NarrationResponse,
)
def create_narration(
    series_id: UUID,
    data: NarrationCreate,
    db: DbSession,
) -> NarrationResponse:
    """Create a narration item within a series."""
    service = NarrationService(db)
    try:
        narration = service.create(str(series_id), data)
    except NarrationError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return narration


@router.get("/{series_id}/narrations", response_model=list[NarrationResponse])
def list_narrations(
    series_id: UUID,
    db: DbSession,
) -> list[NarrationResponse]:
    """List narrations within a series."""
    service = NarrationService(db)
    return service.list(str(series_id))


@router.get(
    "/{series_id}/narrations/{narration_id}",
    response_model=NarrationResponse,
)
def get_narration(
    series_id: UUID,
    narration_id: UUID,
    db: DbSession,
) -> NarrationResponse:
    """Retrieve a narration item."""
    service = NarrationService(db)
    try:
        narration = service.get(str(series_id), str(narration_id))
    except NarrationNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return narration


@router.post(
    "/{series_id}/narrations/{narration_id}/generate",
    response_model=NarrationResponse,
)
def generate_narration(
    series_id: UUID,
    narration_id: UUID,
    db: DbSession,
) -> NarrationResponse:
    """Generate audio for a narration item."""
    service = NarrationGenerationService(db)
    try:
        narration = service.generate(str(series_id), str(narration_id))
    except NarrationGenerationError as exc:
        commit_or_409(db)
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return narration
