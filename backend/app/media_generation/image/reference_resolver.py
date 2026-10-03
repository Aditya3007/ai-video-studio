"""Canonical entity → visual reference Asset resolution for image generation."""

from uuid import UUID

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.media_generation.image.errors import ReferenceConditioningError
from app.models import Asset, Character, Location, StoryObject
from app.models.enums import AssetStatus, AssetType


class ReferenceAssetResolver:
    """Resolves canonical Character/Location/StoryObject refs to visual Assets."""

    _ELIGIBLE_TYPES: tuple[AssetType, ...] = (
        AssetType.REFERENCE,
        AssetType.IMAGE,
        AssetType.STORYBOARD,
        AssetType.KEYFRAME,
        AssetType.THUMBNAIL,
    )

    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _as_str_list(value: list[str] | list[UUID] | None) -> list[str]:
        if value is None:
            return []
        return [str(v) for v in value]

    def _resolve_entity_type(
        self,
        series_id: str,
        entity_cls: type[Character | Location | StoryObject],
        entity_id: str,
        asset_attr: str,
    ) -> str | None:
        entity = self._db.get(entity_cls, entity_id)
        if entity is None:
            raise ReferenceConditioningError(f"{entity_cls.__name__} reference not found.")
        if str(entity.series_id) != series_id:
            raise ReferenceConditioningError(
                f"{entity_cls.__name__} reference does not belong to this series."
            )

        asset = (
            self._db.query(Asset)
            .filter(getattr(Asset, asset_attr).any(entity_cls.id == entity_id))
            .filter(Asset.series_id == series_id)
            .filter(Asset.asset_type.in_([t.value for t in self._ELIGIBLE_TYPES]))
            .filter(Asset.status != AssetStatus.FAILED.value)
            .filter(Asset.status != AssetStatus.ARCHIVED.value)
            .order_by(asc(Asset.created_at), asc(Asset.id))
            .first()
        )
        return str(asset.id) if asset else None

    def resolve(
        self,
        series_id: str,
        character_ids: list[str] | list[UUID] | None = None,
        location_ids: list[str] | list[UUID] | None = None,
        object_ids: list[str] | list[UUID] | None = None,
        *,
        strict: bool = False,
    ) -> list[str]:
        """Resolve canonical refs to eligible visual Asset IDs.

        Ordering: characters, then locations, then objects, in the order supplied.
        When ``strict`` is ``True``, a canonical reference with no eligible asset
        raises ``ReferenceConditioningError``. When ``False``, missing eligible
        assets are skipped so the workflow can continue without conditioning.
        """
        resolved: list[str] = []

        for entity_cls, ids, asset_attr in (
            (Character, character_ids, "characters"),
            (Location, location_ids, "locations"),
            (StoryObject, object_ids, "objects"),
        ):
            for entity_id in self._as_str_list(ids):
                asset_id = self._resolve_entity_type(series_id, entity_cls, entity_id, asset_attr)
                if asset_id is None:
                    if strict:
                        entity_name = entity_cls.__name__
                        raise ReferenceConditioningError(
                            f"No eligible visual reference asset for {entity_name} {entity_id}."
                        )
                    continue
                resolved.append(asset_id)

        return resolved

    def resolve_from_shot_spec(
        self, series_id: str, shot_spec: dict, *, strict: bool = False
    ) -> list[str]:
        """Resolve references declared in a shot specification dictionary."""
        return self.resolve(
            series_id,
            character_ids=shot_spec.get("character_refs"),
            location_ids=shot_spec.get("location_refs"),
            object_ids=shot_spec.get("object_refs"),
            strict=strict,
        )
