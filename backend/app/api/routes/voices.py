"""Voice routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.schemas import VoiceCreate, VoiceResponse
from app.services.voice_service import VoiceError, VoiceNotFoundError, VoiceService

router = APIRouter(prefix="/series", tags=["voices"])


@router.post("/{series_id}/voices", status_code=201, response_model=VoiceResponse)
def create_voice(
    series_id: UUID,
    data: VoiceCreate,
    db: DbSession,
) -> VoiceResponse:
    """Create a voice within a series."""
    service = VoiceService(db)
    try:
        voice = service.create(str(series_id), data)
    except VoiceError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return voice


@router.get("/{series_id}/voices", response_model=list[VoiceResponse])
def list_voices(
    series_id: UUID,
    db: DbSession,
) -> list[VoiceResponse]:
    """List voices within a series."""
    service = VoiceService(db)
    return service.list(str(series_id))


@router.get("/{series_id}/voices/{voice_id}", response_model=VoiceResponse)
def get_voice(
    series_id: UUID,
    voice_id: UUID,
    db: DbSession,
) -> VoiceResponse:
    """Retrieve a voice."""
    service = VoiceService(db)
    try:
        voice = service.get(str(series_id), str(voice_id))
    except VoiceNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return voice
