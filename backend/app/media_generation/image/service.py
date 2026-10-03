"""Application service for provider-neutral image generation."""

from sqlalchemy.orm import Session

from app.media_generation.image.errors import ImageRequestError
from app.media_generation.image.provider import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from app.models import Asset, Character, Location, Series, StoryObject


class ImageGenerationService:
    """Validates ownership and dispatches image generation to a provider."""

    def __init__(self, db: Session, provider: ImageGenerationProvider) -> None:
        self._db = db
        self._provider = provider

    def _validate_series(self, series_id: str) -> None:
        series = self._db.get(Series, series_id)
        if not series:
            raise ImageRequestError("Series not found.")

    def _validate_canonical_refs(self, series_id: str, request: ImageGenerationRequest) -> None:
        for entity_cls, ids in (
            (Character, request.canonical_character_ids),
            (Location, request.canonical_location_ids),
            (StoryObject, request.canonical_object_ids),
        ):
            for entity_id in ids:
                entity = self._db.get(entity_cls, str(entity_id))
                if not entity or str(entity.series_id) != series_id:
                    raise ImageRequestError(f"Invalid {entity_cls.__name__.lower()} reference.")

    def _validate_reference_assets(self, series_id: str, request: ImageGenerationRequest) -> None:
        for asset_id in request.reference_asset_ids:
            asset = self._db.get(Asset, str(asset_id))
            if not asset or asset.series_id != series_id:
                raise ImageRequestError("Invalid reference asset.")

    def generate(self, series_id: str, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Validate the request and dispatch to the configured provider."""
        self._validate_series(series_id)
        self._validate_canonical_refs(series_id, request)
        self._validate_reference_assets(series_id, request)
        return self._provider.generate(request)

    def generate_from_shot_specification(
        self,
        series_id: str,
        shot_spec: dict,
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list | None = None,
    ) -> ImageGenerationResult:
        """Map a shot specification to a request and generate."""
        request = ImageGenerationRequest.from_shot_specification(
            shot_spec,
            prompt_override=prompt_override,
            reference_asset_ids=reference_asset_ids or [],
        )
        return self.generate(series_id, request)
