"""Audio cue routes for music and sound effects."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.schemas import AudioCueCreate, AudioCueResponse
from app.services.audio_cue_service import (
    AudioCueError,
    AudioCueNotFoundError,
    AudioCueService,
)

router = APIRouter(prefix="/series", tags=["audio-cues"])


@router.post("/{series_id}/audio-cues", status_code=201, response_model=AudioCueResponse)
def create_audio_cue(
    series_id: UUID,
    data: AudioCueCreate,
    db: DbSession,
) -> AudioCueResponse:
    """Create an audio cue within a series."""
    service = AudioCueService(db)
    try:
        cue = service.create(str(series_id), data)
    except AudioCueError as exc:
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    commit_or_409(db)
    return cue


@router.get("/{series_id}/audio-cues", response_model=list[AudioCueResponse])
def list_audio_cues(
    series_id: UUID,
    db: DbSession,
) -> list[AudioCueResponse]:
    """List audio cues within a series."""
    service = AudioCueService(db)
    return service.list(str(series_id))


@router.get(
    "/{series_id}/audio-cues/{audio_cue_id}",
    response_model=AudioCueResponse,
)
def get_audio_cue(
    series_id: UUID,
    audio_cue_id: UUID,
    db: DbSession,
) -> AudioCueResponse:
    """Retrieve an audio cue."""
    service = AudioCueService(db)
    try:
        cue = service.get(str(series_id), str(audio_cue_id))
    except AudioCueNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return cue
