"""Image-to-video workflow from a storyboard/keyframe Asset."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.media_generation.image.reference_resolver import ReferenceAssetResolver
from app.media_generation.video.errors import VideoRequestError
from app.media_generation.video.factory import VideoGenerationProviderFactory
from app.media_generation.video.provider import (
    VideoGenerationProvider,
    VideoGenerationRequest,
    VideoGenerationResult,
)
from app.media_generation.video.service import VideoGenerationService
from app.models import Asset, Series, Shot
from app.models.enums import ApprovalStatus, AssetStatus, AssetType


class ImageToVideoService:
    """Builds a provider-neutral video generation request from a storyboard/keyframe."""

    _ELIGIBLE_TYPES = {AssetType.STORYBOARD.value, AssetType.KEYFRAME.value}

    def __init__(self, db: Session, provider: VideoGenerationProvider | None = None) -> None:
        self._db = db
        self._provider = provider

    def _assert_shot_in_series(self, series_id: str, shot_id: str) -> Shot:
        shot = self._db.get(Shot, shot_id)
        if not shot:
            raise VideoRequestError("Shot not found.")
        if str(shot.scene.episode.series_id) != series_id:
            raise VideoRequestError("Shot does not belong to this series.")
        return shot

    def _validate_storyboard_asset(self, series_id: str, asset_id: str) -> Asset:
        asset = self._db.get(Asset, asset_id)
        if not asset:
            raise VideoRequestError("Storyboard asset not found.")
        if str(asset.series_id) != series_id:
            raise VideoRequestError("Storyboard asset does not belong to this series.")
        if asset.asset_type not in self._ELIGIBLE_TYPES:
            raise VideoRequestError("Asset must be a storyboard or keyframe.")
        if asset.status != AssetStatus.AVAILABLE.value:
            raise VideoRequestError("Storyboard asset is not available.")
        if asset.approval_status != ApprovalStatus.APPROVED.value:
            raise VideoRequestError("Storyboard asset must be approved before video generation.")
        return asset

    @staticmethod
    def _build_prompt(shot_spec) -> str:
        fields = [
            "intent",
            "visual_direction",
            "subject_notes",
            "camera_notes",
            "composition",
            "framing",
        ]
        parts = [str(getattr(shot_spec, field) or "").strip() for field in fields]
        prompt = " ".join(p for p in parts if p)
        return prompt or "Generate video from the provided storyboard."

    def build_video_request(
        self,
        series_id: str,
        shot_id: str,
        storyboard_asset_id: str,
        *,
        prompt_override: str | None = None,
        duration_seconds: int | None = None,
        aspect_ratio: str | None = None,
        motion_description: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> VideoGenerationRequest:
        """Build a provider-neutral video generation request from a storyboard/keyframe."""
        series = self._db.get(Series, series_id)
        if not series:
            raise VideoRequestError("Series not found.")

        shot = self._assert_shot_in_series(series_id, shot_id)
        shot_spec = shot.specification
        if shot_spec is None:
            raise VideoRequestError("Shot has no specification.")

        storyboard = self._validate_storyboard_asset(series_id, storyboard_asset_id)

        spec_dict = {
            "character_refs": shot_spec.character_refs or [],
            "location_refs": shot_spec.location_refs or [],
            "object_refs": shot_spec.object_refs or [],
        }
        resolved_refs = ReferenceAssetResolver(self._db).resolve_from_shot_spec(
            series_id, spec_dict, strict=False
        )
        explicit_refs = reference_asset_ids or []
        combined_refs = [UUID(aid) for aid in resolved_refs + explicit_refs]

        prompt = prompt_override or self._build_prompt(shot_spec)
        motion = motion_description or (
            str(shot_spec.camera_movement or "").strip()
            or str(shot_spec.camera_notes or "").strip()
            or None
        )
        output_constraints = shot_spec.output_constraints or {}

        return VideoGenerationRequest(
            prompt=prompt,
            aspect_ratio=aspect_ratio or shot_spec.aspect_ratio or "9:16",
            width=output_constraints.get("width"),
            height=output_constraints.get("height"),
            duration=(
                float(duration_seconds)
                if duration_seconds is not None
                else (
                    float(shot_spec.duration_seconds)
                    if shot_spec.duration_seconds is not None
                    else None
                )
            ),
            canonical_character_ids=shot_spec.character_refs or [],
            canonical_location_ids=shot_spec.location_refs or [],
            canonical_object_ids=shot_spec.object_refs or [],
            keyframe_asset_ids=[UUID(storyboard.id)],
            reference_asset_ids=combined_refs,
            motion_description=motion,
            output_constraints=output_constraints,
            options=shot_spec.extra,
        )

    def execute_request(
        self, series_id: str, request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """Execute a provider-neutral video generation request."""
        provider = self._provider or VideoGenerationProviderFactory.create(request=request)
        video_service = VideoGenerationService(self._db, provider)
        return video_service.generate(series_id, request)

    def generate(
        self,
        series_id: str,
        shot_id: str,
        storyboard_asset_id: str,
        *,
        prompt_override: str | None = None,
        duration_seconds: int | None = None,
        aspect_ratio: str | None = None,
        motion_description: str | None = None,
        reference_asset_ids: list[str] | None = None,
    ) -> dict:
        """Generate a video from an approved storyboard/keyframe asset."""
        request = self.build_video_request(
            series_id,
            shot_id,
            storyboard_asset_id,
            prompt_override=prompt_override,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            motion_description=motion_description,
            reference_asset_ids=reference_asset_ids,
        )
        result = self.execute_request(series_id, request)
        return result.model_dump()
