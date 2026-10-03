"""Asset domain service with canonical reference validation."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Asset,
    Character,
    Location,
    Series,
    Shot,
    StoryObject,
)
from app.schemas.asset import AssetCreate, AssetUpdate


class AssetError(Exception):
    """Raised when asset validation fails."""


class AssetNotFoundError(Exception):
    """Raised when an asset cannot be found for the given series."""


class AssetService:
    """Manages asset lifecycle and canonical references within a series."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_series(self, series_id: str) -> Series:
        series = self._db.get(Series, series_id)
        if not series:
            raise AssetNotFoundError("Series not found.")
        return series

    def _assert_shot_in_series(self, shot_id: str, series_id: str) -> Shot:
        shot = self._db.get(Shot, shot_id)
        if not shot or str(shot.scene.episode.series_id) != series_id:
            raise AssetError("Shot not found or does not belong to this series.")
        return shot

    def _validate_canonical_refs(
        self,
        series_id: str,
        *,
        character_ids: list[str] | None = None,
        location_ids: list[str] | None = None,
        object_ids: list[str] | None = None,
    ) -> tuple[list[Character], list[Location], list[StoryObject]]:
        characters: list[Character] = []
        locations: list[Location] = []
        objects: list[StoryObject] = []

        for cid in character_ids or []:
            character = self._db.get(Character, cid)
            if not character or str(character.series_id) != series_id:
                raise AssetError("Invalid character reference.")
            characters.append(character)

        for lid in location_ids or []:
            location = self._db.get(Location, lid)
            if not location or str(location.series_id) != series_id:
                raise AssetError("Invalid location reference.")
            locations.append(location)

        for oid in object_ids or []:
            obj = self._db.get(StoryObject, oid)
            if not obj or str(obj.series_id) != series_id:
                raise AssetError("Invalid object reference.")
            objects.append(obj)

        return characters, locations, objects

    def _apply_update(self, asset: Asset, data: AssetCreate | AssetUpdate) -> None:
        payload = data.model_dump(exclude_unset=True, mode="json")
        char_ids = payload.pop("character_ids", None)
        loc_ids = payload.pop("location_ids", None)
        obj_ids = payload.pop("object_ids", None)

        for key, value in payload.items():
            setattr(asset, key, value)

        if char_ids is not None or loc_ids is not None or obj_ids is not None:
            characters, locations, objects = self._validate_canonical_refs(
                asset.series_id,
                character_ids=char_ids,
                location_ids=loc_ids,
                object_ids=obj_ids,
            )
            if char_ids is not None:
                asset.characters = characters
            if loc_ids is not None:
                asset.locations = locations
            if obj_ids is not None:
                asset.objects = objects

    def create_asset(self, series_id: str, data: AssetCreate) -> Asset:
        """Create an asset and validate all canonical references."""
        self._assert_series(series_id)

        if data.shot_id:
            self._assert_shot_in_series(str(data.shot_id), series_id)

        characters, locations, objects = self._validate_canonical_refs(
            series_id,
            character_ids=[str(cid) for cid in data.character_ids],
            location_ids=[str(lid) for lid in data.location_ids],
            object_ids=[str(oid) for oid in data.object_ids],
        )

        payload = data.model_dump(
            exclude={"character_ids", "location_ids", "object_ids"},
            mode="json",
        )
        asset = Asset(series_id=series_id, **payload)
        asset.characters = characters
        asset.locations = locations
        asset.objects = objects

        self._db.add(asset)
        self._db.flush()
        self._db.refresh(asset)
        return asset

    def get_asset(self, series_id: str, asset_id: str) -> Asset:
        """Return an asset if it belongs to the series."""
        asset = self._db.get(Asset, asset_id)
        if not asset or asset.series_id != series_id:
            raise AssetNotFoundError("Asset not found.")
        return asset

    def list_assets(
        self,
        series_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        asset_type: str | None = None,
    ) -> tuple[list[Asset], int]:
        """Return assets within the series."""
        self._assert_series(series_id)
        query = select(Asset).where(Asset.series_id == series_id)
        if asset_type:
            query = query.where(Asset.asset_type == asset_type)
        query = (
            query.options(
                selectinload(Asset.characters),
                selectinload(Asset.locations),
                selectinload(Asset.objects),
            )
            .order_by(Asset.created_at)
            .offset(offset)
            .limit(limit)
        )
        items = list(self._db.execute(query).scalars().all())
        count_query = select(func.count(Asset.id)).where(Asset.series_id == series_id)
        if asset_type:
            count_query = count_query.where(Asset.asset_type == asset_type)
        total = self._db.execute(count_query).scalar() or 0
        return items, total

    def update_asset(self, series_id: str, asset_id: str, data: AssetUpdate) -> Asset:
        """Update an asset within a series."""
        asset = self.get_asset(series_id, asset_id)

        if data.shot_id:
            self._assert_shot_in_series(str(data.shot_id), series_id)

        self._apply_update(asset, data)
        self._db.flush()
        self._db.refresh(asset)
        return asset

    def delete_asset(self, series_id: str, asset_id: str) -> None:
        """Delete an asset within a series."""
        asset = self.get_asset(series_id, asset_id)
        self._db.delete(asset)
