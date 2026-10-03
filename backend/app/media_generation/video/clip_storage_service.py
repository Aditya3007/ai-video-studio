"""Video clip storage and Asset persistence for validated generated videos."""

from __future__ import annotations

from app.core.config import get_settings
from app.media_generation.video.clip_validator import VideoClipValidator
from app.media_generation.video.errors import VideoValidationError
from app.media_generation.video.provider import (
    VideoGenerationRequest,
    VideoGenerationResult,
)
from app.models import Asset, VideoGenerationJob
from app.models.enums import ApprovalStatus, AssetRole, AssetStatus, AssetType
from app.storage.factory import create_storage_backend


class VideoClipStorageService:
    """Validate, store, and persist a generated video clip as an Asset."""

    def __init__(self, db, storage=None) -> None:
        self._db = db
        self._storage = storage or create_storage_backend(get_settings())

    def _generate_key(self, job: VideoGenerationJob, index: int) -> str:
        return f"videos/{job.series_id}/{job.id}/{index}.mp4"

    def process_result(self, job: VideoGenerationJob, result: VideoGenerationResult) -> Asset:
        """Validate, store, and persist the result; return the created Asset."""
        if job.result_metadata and job.result_metadata.get("asset_id"):
            existing = self._db.get(Asset, job.result_metadata["asset_id"])
            if existing:
                return existing

        request = VideoGenerationRequest(**job.request_payload)
        VideoClipValidator.validate(request, result)

        video = result.videos[0]
        if not video.data:
            raise VideoValidationError("Video reference contains no artifact data.")

        key = self._generate_key(job, 0)
        storage_object = self._storage.put(
            key,
            video.data,
            content_type=video.content_type,
            metadata={
                "series_id": str(job.series_id),
                "job_id": str(job.id),
                "shot_id": str(job.shot_id) if job.shot_id else "",
                "source_asset_id": str(job.source_asset_id) if job.source_asset_id else "",
                "provider": result.provider,
                "model": result.model,
            },
        )

        asset = Asset(
            series_id=job.series_id,
            asset_type=AssetType.VIDEO.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            approval_status=ApprovalStatus.PENDING.value,
            storage_backend=get_settings().storage_backend,
            storage_key=storage_object.key,
            name=f"Generated video for shot {job.shot_id}",
            asset_metadata={
                "video_generation_job_id": str(job.id),
                "source_asset_id": str(job.source_asset_id) if job.source_asset_id else None,
                "shot_id": str(job.shot_id) if job.shot_id else None,
                "provider": result.provider,
                "model": result.model,
                "width": video.width,
                "height": video.height,
                "duration": video.duration,
                "content_type": video.content_type,
                "request_id": result.request_id,
            },
            shot_id=job.shot_id,
        )
        self._db.add(asset)
        self._db.flush()

        job.result_metadata = {
            **result.model_dump(mode="json"),
            "asset_id": asset.id,
            "validation": {"valid": True},
        }
        self._db.flush()
        self._db.refresh(asset)
        return asset
