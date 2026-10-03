"""Application service for provider-neutral video generation."""

from sqlalchemy.orm import Session

from app.media_generation.video.errors import VideoRequestError
from app.media_generation.video.provider import (
    VideoGenerationProvider,
    VideoGenerationRequest,
    VideoGenerationResult,
)
from app.models import Asset, Character, Location, Series, StoryObject


class VideoGenerationService:
    """Validates ownership and dispatches video generation to a provider."""

    def __init__(self, db: Session, provider: VideoGenerationProvider) -> None:
        self._db = db
        self._provider = provider

    def _validate_series(self, series_id: str) -> None:
        series = self._db.get(Series, series_id)
        if not series:
            raise VideoRequestError("Series not found.")

    def _validate_canonical_refs(self, series_id: str, request: VideoGenerationRequest) -> None:
        for entity_cls, ids in (
            (Character, request.canonical_character_ids),
            (Location, request.canonical_location_ids),
            (StoryObject, request.canonical_object_ids),
        ):
            for entity_id in ids:
                entity = self._db.get(entity_cls, str(entity_id))
                if not entity or str(entity.series_id) != series_id:
                    raise VideoRequestError(f"Invalid {entity_cls.__name__.lower()} reference.")

    def _validate_reference_assets(self, series_id: str, request: VideoGenerationRequest) -> None:
        for asset_id in request.reference_asset_ids:
            asset = self._db.get(Asset, str(asset_id))
            if not asset or asset.series_id != series_id:
                raise VideoRequestError("Invalid reference asset.")
        for asset_id in request.keyframe_asset_ids:
            asset = self._db.get(Asset, str(asset_id))
            if not asset or asset.series_id != series_id:
                raise VideoRequestError("Invalid keyframe asset.")

    def generate(self, series_id: str, request: VideoGenerationRequest) -> VideoGenerationResult:
        """Validate the request and dispatch to the configured provider."""
        self._validate_series(series_id)
        self._validate_canonical_refs(series_id, request)
        self._validate_reference_assets(series_id, request)
        return self._provider.generate(request)
