"""Character CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Character, Series
from app.schemas import CharacterCreate, CharacterResponse, CharacterUpdate, PaginatedResponse

router = APIRouter(prefix="/series", tags=["characters"])


def _assert_series_exists(series_id: UUID, db: DbSession) -> None:
    if not db.get(Series, str(series_id)):
        raise AppError("NOT_FOUND", "Series not found.", status_code=404)


def _get_character(series_id: UUID, character_id: UUID, db: DbSession) -> Character:
    character = db.get(Character, str(character_id))
    if not character or character.series_id != str(series_id):
        raise AppError("NOT_FOUND", "Character not found.", status_code=404)
    return character


@router.post("/{series_id}/characters", status_code=201, response_model=CharacterResponse)
def create_character(series_id: UUID, data: CharacterCreate, db: DbSession) -> Character:
    """Create a character within a series."""
    _assert_series_exists(series_id, db)
    character = Character(series_id=str(series_id), **data.model_dump(mode="json"))
    db.add(character)
    commit_or_409(db)
    db.refresh(character)
    return character


@router.get("/{series_id}/characters", response_model=PaginatedResponse[CharacterResponse])
def list_characters(
    series_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[CharacterResponse]:
    """List characters in a series."""
    _assert_series_exists(series_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(Character)
            .where(Character.series_id == str(series_id))
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count()).select_from(Character).where(Character.series_id == str(series_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[CharacterResponse](
        items=[CharacterResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{series_id}/characters/{character_id}", response_model=CharacterResponse)
def get_character(series_id: UUID, character_id: UUID, db: DbSession) -> Character:
    """Get a character by ID within a series."""
    return _get_character(series_id, character_id, db)


@router.patch("/{series_id}/characters/{character_id}", response_model=CharacterResponse)
def update_character(
    series_id: UUID,
    character_id: UUID,
    data: CharacterUpdate,
    db: DbSession,
) -> Character:
    """Update a character."""
    character = _get_character(series_id, character_id, db)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(character, key, value)
    commit_or_409(db)
    db.refresh(character)
    return character


@router.delete("/{series_id}/characters/{character_id}", status_code=204)
def delete_character(series_id: UUID, character_id: UUID, db: DbSession) -> None:
    """Delete a character and its versions."""
    character = _get_character(series_id, character_id, db)
    db.delete(character)
    commit_or_409(db)
