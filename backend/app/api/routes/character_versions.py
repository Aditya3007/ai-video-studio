"""Character version CRUD routes."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.models import Character, CharacterVersion
from app.schemas import (
    CharacterVersionCreate,
    CharacterVersionResponse,
    CharacterVersionUpdate,
    PaginatedResponse,
)

router = APIRouter(prefix="/characters", tags=["character-versions"])


def _get_character(character_id: UUID, db: DbSession) -> Character:
    character = db.get(Character, str(character_id))
    if not character:
        raise AppError("NOT_FOUND", "Character not found.", status_code=404)
    return character


def _get_version(character_id: UUID, version_id: UUID, db: DbSession) -> CharacterVersion:
    version = db.get(CharacterVersion, str(version_id))
    if not version or version.character_id != str(character_id):
        raise AppError("NOT_FOUND", "Character version not found.", status_code=404)
    return version


@router.post("/{character_id}/versions", status_code=201, response_model=CharacterVersionResponse)
def create_character_version(
    character_id: UUID,
    data: CharacterVersionCreate,
    db: DbSession,
) -> CharacterVersion:
    """Create a version for a character."""
    _get_character(character_id, db)
    existing = db.execute(
        select(CharacterVersion).where(
            CharacterVersion.character_id == str(character_id),
            CharacterVersion.version == data.version,
        )
    ).scalar_one_or_none()
    if existing:
        raise AppError(
            "CONFLICT",
            "Version number already exists for this character.",
            status_code=409,
        )

    payload = data.model_dump(mode="json")
    if payload.get("reference_asset_id"):
        payload["reference_asset_id"] = str(payload["reference_asset_id"])
    version = CharacterVersion(character_id=str(character_id), **payload)
    db.add(version)
    commit_or_409(db)
    db.refresh(version)
    return version


@router.get("/{character_id}/versions", response_model=PaginatedResponse[CharacterVersionResponse])
def list_character_versions(
    character_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[CharacterVersionResponse]:
    """List versions for a character."""
    _get_character(character_id, db)
    limit = min(limit, 100)
    items = (
        db.execute(
            select(CharacterVersion)
            .where(CharacterVersion.character_id == str(character_id))
            .order_by(CharacterVersion.version)
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.execute(
            select(func.count())
            .select_from(CharacterVersion)
            .where(CharacterVersion.character_id == str(character_id))
        ).scalar()
        or 0
    )
    return PaginatedResponse[CharacterVersionResponse](
        items=[CharacterVersionResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{character_id}/versions/{version_id}", response_model=CharacterVersionResponse)
def get_character_version(
    character_id: UUID,
    version_id: UUID,
    db: DbSession,
) -> CharacterVersion:
    """Get a character version."""
    return _get_version(character_id, version_id, db)


@router.patch("/{character_id}/versions/{version_id}", response_model=CharacterVersionResponse)
def update_character_version(
    character_id: UUID,
    version_id: UUID,
    data: CharacterVersionUpdate,
    db: DbSession,
) -> CharacterVersion:
    """Update a character version."""
    version = _get_version(character_id, version_id, db)
    payload = data.model_dump(exclude_unset=True, mode="json")
    if "reference_asset_id" in payload and payload["reference_asset_id"]:
        payload["reference_asset_id"] = str(payload["reference_asset_id"])
    for key, value in payload.items():
        setattr(version, key, value)
    commit_or_409(db)
    db.refresh(version)
    return version


@router.delete("/{character_id}/versions/{version_id}", status_code=204)
def delete_character_version(
    character_id: UUID,
    version_id: UUID,
    db: DbSession,
) -> None:
    """Delete a character version."""
    version = _get_version(character_id, version_id, db)
    db.delete(version)
    commit_or_409(db)
