"""Series CRUD and universe routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import AudioBible, Series, VisualBible
from app.schemas import (
    AudioBibleCreate,
    AudioBibleResponse,
    AudioBibleUpdate,
    PaginatedResponse,
    SeriesCreate,
    SeriesResponse,
    SeriesUpdate,
    UniverseContextResponse,
    VisualBibleCreate,
    VisualBibleResponse,
    VisualBibleUpdate,
)
from app.services.universe import UniverseContextService

router = APIRouter(prefix="/series", tags=["series"])


def _assert_series(series_id: UUID, db: DbSession) -> Series:
    """Load a Series or raise a 404 error."""
    series = db.get(Series, str(series_id))
    if not series:
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)
    return series


@router.post("", status_code=201, response_model=SeriesResponse)
def create_series(data: SeriesCreate, db: DbSession) -> Series:
    """Create a new series."""
    series = Series(**data.model_dump(mode="json"))
    db.add(series)
    commit_or_409(db)
    db.refresh(series)
    return series


@router.get("", response_model=PaginatedResponse[SeriesResponse])
def list_series(
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[SeriesResponse]:
    """List series with pagination."""
    limit = min(limit, 100)
    items = db.execute(select(Series).offset(offset).limit(limit)).scalars().all()
    total = db.execute(select(func.count()).select_from(Series)).scalar() or 0
    return PaginatedResponse[SeriesResponse](
        items=[SeriesResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{series_id}", response_model=SeriesResponse)
def get_series(series_id: UUID, db: DbSession) -> Series:
    """Get a series by ID."""
    return _assert_series(series_id, db)


@router.patch("/{series_id}", response_model=SeriesResponse)
def update_series(series_id: UUID, data: SeriesUpdate, db: DbSession) -> Series:
    """Update a series."""
    series = _assert_series(series_id, db)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(series, key, value)
    commit_or_409(db)
    db.refresh(series)
    return series


@router.delete("/{series_id}", status_code=204)
def delete_series(series_id: UUID, db: DbSession) -> None:
    """Delete a series and its owned children."""
    series = _assert_series(series_id, db)
    db.delete(series)
    commit_or_409(db)


@router.get("/{series_id}/universe", response_model=UniverseContextResponse)
def get_universe(series_id: UUID, db: DbSession) -> UniverseContextResponse:
    """Return the canonical universe context for a series."""
    series = _assert_series(series_id, db)
    return UniverseContextService(db).get_context(series)


def _existing_bible(series_id: str, model: type, db: DbSession):
    """Return an existing bible model for a series, if any."""
    return db.execute(select(model).where(model.series_id == series_id)).scalar_one_or_none()


@router.post("/{series_id}/visual-bible", status_code=201, response_model=VisualBibleResponse)
def create_visual_bible(series_id: UUID, data: VisualBibleCreate, db: DbSession) -> VisualBible:
    """Create the canonical Visual Bible for a series."""
    series = _assert_series(series_id, db)
    if _existing_bible(series.id, VisualBible, db):
        raise AppError("CONFLICT", "Visual Bible already exists for this series.", status_code=409)
    bible = VisualBible(series_id=series.id, **data.model_dump(mode="json"))
    db.add(bible)
    commit_or_409(db)
    db.refresh(bible)
    return bible


@router.get("/{series_id}/visual-bible", response_model=VisualBibleResponse)
def get_visual_bible(series_id: UUID, db: DbSession) -> VisualBible:
    """Get the Visual Bible for a series."""
    series = _assert_series(series_id, db)
    bible = _existing_bible(series.id, VisualBible, db)
    if not bible:
        raise AppError("NOT_FOUND", "Visual Bible not found.", status_code=404)
    return bible


@router.patch("/{series_id}/visual-bible", response_model=VisualBibleResponse)
def update_visual_bible(series_id: UUID, data: VisualBibleUpdate, db: DbSession) -> VisualBible:
    """Update the Visual Bible for a series."""
    series = _assert_series(series_id, db)
    bible = _existing_bible(series.id, VisualBible, db)
    if not bible:
        raise AppError("NOT_FOUND", "Visual Bible not found.", status_code=404)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(bible, key, value)
    commit_or_409(db)
    db.refresh(bible)
    return bible


@router.post("/{series_id}/audio-bible", status_code=201, response_model=AudioBibleResponse)
def create_audio_bible(series_id: UUID, data: AudioBibleCreate, db: DbSession) -> AudioBible:
    """Create the canonical Audio Bible for a series."""
    series = _assert_series(series_id, db)
    if _existing_bible(series.id, AudioBible, db):
        raise AppError("CONFLICT", "Audio Bible already exists for this series.", status_code=409)
    bible = AudioBible(series_id=series.id, **data.model_dump(mode="json"))
    db.add(bible)
    commit_or_409(db)
    db.refresh(bible)
    return bible


@router.get("/{series_id}/audio-bible", response_model=AudioBibleResponse)
def get_audio_bible(series_id: UUID, db: DbSession) -> AudioBible:
    """Get the Audio Bible for a series."""
    series = _assert_series(series_id, db)
    bible = _existing_bible(series.id, AudioBible, db)
    if not bible:
        raise AppError("NOT_FOUND", "Audio Bible not found.", status_code=404)
    return bible


@router.patch("/{series_id}/audio-bible", response_model=AudioBibleResponse)
def update_audio_bible(series_id: UUID, data: AudioBibleUpdate, db: DbSession) -> AudioBible:
    """Update the Audio Bible for a series."""
    series = _assert_series(series_id, db)
    bible = _existing_bible(series.id, AudioBible, db)
    if not bible:
        raise AppError("NOT_FOUND", "Audio Bible not found.", status_code=404)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(bible, key, value)
    commit_or_409(db)
    db.refresh(bible)
    return bible
