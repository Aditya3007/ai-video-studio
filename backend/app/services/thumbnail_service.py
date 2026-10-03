"""Thumbnail preparation and validation for YouTube Shorts publishing."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models import Asset
from app.models.enums import AssetStatus, AssetType
from app.storage import StorageBackend


class ThumbnailError(Exception):
    """Raised when thumbnail preparation fails."""


class ThumbnailSelection(BaseModel):
    """Provider-neutral thumbnail selection for a Short."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    series_id: UUID
    episode_id: UUID | None = None
    storage_backend: str | None = None
    storage_key: str | None = None
    alt_text: str | None = Field(default=None, max_length=500)


class ThumbnailService:
    """Validate and prepare an existing image Asset as a thumbnail candidate."""

    _ELIGIBLE_TYPES = {
        AssetType.IMAGE.value,
        AssetType.STORYBOARD.value,
        AssetType.KEYFRAME.value,
        AssetType.THUMBNAIL.value,
    }

    def __init__(self, db: Session, storage: StorageBackend) -> None:
        self._db = db
        self._storage = storage

    def select(
        self,
        series_id: str,
        episode_id: str | None,
        asset_id: str,
        *,
        alt_text: str | None = None,
    ) -> ThumbnailSelection:
        """Validate the candidate asset and return a thumbnail selection."""
        asset = self._db.get(Asset, asset_id)
        if not asset:
            raise ThumbnailError("Thumbnail asset not found.")
        if str(asset.series_id) != series_id:
            raise ThumbnailError("Thumbnail asset does not belong to the requested Series.")
        if asset.asset_type not in self._ELIGIBLE_TYPES:
            raise ThumbnailError("Thumbnail must be an image-type asset.")
        if asset.status != AssetStatus.AVAILABLE.value:
            raise ThumbnailError("Thumbnail asset is not available.")
        if not asset.storage_key:
            raise ThumbnailError("Thumbnail asset has no storage key.")
        if not self._storage.exists(asset.storage_key):
            raise ThumbnailError("Thumbnail asset is not available in storage.")

        return ThumbnailSelection(
            asset_id=UUID(asset.id),
            series_id=UUID(asset.series_id),
            episode_id=UUID(episode_id) if episode_id else None,
            storage_backend=asset.storage_backend,
            storage_key=asset.storage_key,
            alt_text=alt_text,
        )
