"""Storyboard/keyframe generation workflow built on the image provider boundary."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.media_generation.image.errors import StoryboardError
from app.media_generation.image.provider import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from app.media_generation.image.reference_resolver import ReferenceAssetResolver
from app.media_generation.image.service import ImageGenerationService
from app.models import Asset, Series, Shot
from app.models.enums import ApprovalStatus, AssetRole, AssetStatus, AssetType


class StoryboardService:
    """Generates storyboard/keyframe assets for a planned shot."""

    def __init__(self, db: Session, provider: ImageGenerationProvider) -> None:
        self._db = db
        self._provider = provider

    def _assert_shot_in_series(self, series_id: str, shot_id: str) -> Shot:
        shot = self._db.get(Shot, shot_id)
        if not shot:
            raise StoryboardError("Shot not found.")
        if str(shot.scene.episode.series_id) != series_id:
            raise StoryboardError("Shot does not belong to this series.")
        return shot

    @staticmethod
    def _build_prompt(shot_spec: dict) -> str:
        fields = [
            "intent",
            "subject_notes",
            "visual_direction",
            "composition",
            "framing",
            "camera_notes",
        ]
        parts = [str(shot_spec.get(field) or "").strip() for field in fields]
        prompt = " ".join(p for p in parts if p)
        return prompt or "Storyboard image for the shot."

    def build_image_request(
        self,
        series_id: str,
        shot_id: str,
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> tuple[Shot, ImageGenerationRequest]:
        """Validate and build a provider-neutral image generation request."""
        series = self._db.get(Series, series_id)
        if not series:
            raise StoryboardError("Series not found.")

        shot = self._assert_shot_in_series(series_id, shot_id)
        shot_spec = shot.specification
        if shot_spec is None:
            raise StoryboardError("Shot has no specification.")

        spec_dict = {
            "intent": shot_spec.intent,
            "framing": shot_spec.framing,
            "composition": shot_spec.composition,
            "camera_notes": shot_spec.camera_notes,
            "camera_movement": shot_spec.camera_movement,
            "subject_notes": shot_spec.subject_notes,
            "visual_direction": shot_spec.visual_direction,
            "aspect_ratio": shot_spec.aspect_ratio,
            "output_constraints": shot_spec.output_constraints,
            "extra": shot_spec.extra,
            "character_refs": shot_spec.character_refs or [],
            "location_refs": shot_spec.location_refs or [],
            "object_refs": shot_spec.object_refs or [],
        }

        prompt = prompt_override or self._build_prompt(spec_dict)
        output_constraints = spec_dict["output_constraints"] or {}

        resolved_refs = ReferenceAssetResolver(self._db).resolve_from_shot_spec(
            series_id, spec_dict, strict=False
        )
        explicit_refs = reference_asset_ids or []
        combined_refs = [UUID(aid) for aid in resolved_refs + explicit_refs]

        request = ImageGenerationRequest(
            prompt=prompt,
            aspect_ratio=spec_dict["aspect_ratio"] or "9:16",
            width=output_constraints.get("width"),
            height=output_constraints.get("height"),
            num_images=1,
            canonical_character_ids=spec_dict["character_refs"],
            canonical_location_ids=spec_dict["location_refs"],
            canonical_object_ids=spec_dict["object_refs"],
            reference_asset_ids=combined_refs,
            output_constraints=spec_dict["output_constraints"],
            options=spec_dict["extra"],
        )
        return shot, request

    def persist_asset(
        self,
        shot: Shot,
        prompt: str,
        result: ImageGenerationResult,
        *,
        approval_status: ApprovalStatus = ApprovalStatus.PENDING,
    ) -> Asset:
        """Persist a generated image as a storyboard Asset."""
        asset = Asset(
            series_id=shot.scene.episode.series_id,
            asset_type=AssetType.STORYBOARD.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            approval_status=approval_status.value,
            shot_id=shot.id,
            name=f"Storyboard for shot {shot.shot_number}",
            description=prompt,
            storage_backend="image-provider",
            storage_key=result.images[0].uri if result.images else None,
            asset_metadata={
                "images": [image.model_dump() for image in result.images],
                "provider": result.provider,
                "model": result.model,
                "request_id": result.request_id,
                "prompt": prompt,
            },
        )
        self._db.add(asset)
        self._db.flush()
        self._db.refresh(asset)
        return asset

    def generate_storyboard(
        self,
        series_id: str,
        shot_id: str,
        *,
        prompt_override: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> Asset:
        """Generate a storyboard asset from the shot's specification."""
        shot, request = self.build_image_request(
            series_id,
            shot_id,
            prompt_override=prompt_override,
            reference_asset_ids=reference_asset_ids,
        )
        image_service = ImageGenerationService(self._db, self._provider)
        result = image_service.generate(series_id, request)
        return self.persist_asset(shot, request.prompt, result)
