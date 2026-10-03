"""Episode end-to-end production pipeline composition service."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.media_generation.image import (
    ImageGenerationJobService,
    ImageGenerationProviderFactory,
)
from app.media_generation.tts import TTSProviderFactory
from app.models import Asset, Episode, Narration, Shot, VideoAssembly, VideoGenerationJob
from app.models.enums import (
    AIQAMode,
    ApprovalStatus,
    AssemblyItemType,
    AssemblyStatus,
    AssemblyTrack,
    AssetStatus,
    AssetType,
    AuditEventType,
    AuditStatus,
    ImageGenerationJobStatus,
    NarrationStatus,
    QAWorkflowStatus,
)
from app.orchestration import Orchestrator
from app.schemas.ai_qa import AIQAFinding
from app.schemas.qa_workflow import QAWorkflowResponse
from app.schemas.video_assembly import AssemblyItemCreate, VideoAssemblyCreate
from app.services.ai_qa_service import AIQAProvider, FakeAIQAProvider
from app.services.audit_service import AuditService
from app.services.final_export_service import FinalExportService
from app.services.narration_generation_service import NarrationGenerationService
from app.services.qa_workflow_service import QAWorkflowService
from app.services.video_assembly_service import VideoAssemblyService
from app.services.video_renderer import FFmpegVideoRenderer
from app.storage import StorageBackend, create_storage_backend


class EpisodeProductionError(Exception):
    """Raised when the episode production pipeline fails."""


class EpisodeProductionStage:
    """Human-readable stage identifiers for the production pipeline."""

    PLANNING = "planning"
    STORYBOARD = "storyboard"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    AUDIO = "audio"
    QA = "qa"
    ASSEMBLY = "assembly"
    EXPORT = "export"
    COMPLETED = "completed"


class EpisodeProductionResult(BaseModel):
    """Result of an episode production run."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    episode_id: UUID
    production_run_id: UUID | None = None
    assembly_id: UUID | None = None
    final_asset_id: UUID | None = None
    stage: str
    status: str
    message: str | None = None
    qa_response: QAWorkflowResponse | None = None
    findings: list[AIQAFinding] = []
    warnings: list[str] = []


class EpisodeProductionService:
    """Provider-neutral orchestrator for producing an Episode end-to-end."""

    def __init__(
        self,
        db: Session,
        *,
        orchestrator: Orchestrator | None = None,
        storage: StorageBackend | None = None,
        storage_backend_name: str | None = None,
        renderer: Any | None = None,
        ai_provider: AIQAProvider | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._db = db
        self._orchestrator = orchestrator or Orchestrator()
        self._storage = storage or create_storage_backend(get_settings())
        self._storage_backend_name = storage_backend_name or get_settings().storage_backend
        self._renderer = renderer or FFmpegVideoRenderer(db, self._storage)
        self._ai_provider = ai_provider or FakeAIQAProvider()
        self._audit = audit_service or AuditService(db)

    def _load_episode(self, series_id: str, episode_id: str) -> Episode:
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise EpisodeProductionError("Episode not found in this series.")
        return episode

    def _emit(
        self,
        event_type: AuditEventType,
        *,
        stage: str | None = None,
        episode_id: str | None = None,
        shot_id: str | None = None,
        asset_id: str | None = None,
        job_id: str | None = None,
        status: AuditStatus | str | None = None,
        attempt: int | None = None,
        metadata: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        try:
            self._audit.record(
                series_id=self._series_id,
                event_type=event_type,
                episode_id=episode_id,
                shot_id=shot_id,
                asset_id=asset_id,
                job_id=job_id,
                production_run_id=self._run_id,
                stage=stage,
                status=status,
                attempt=attempt,
                metadata=metadata,
                error_message=error_message,
            )
        except Exception as exc:
            self._audit_warnings.append(f"Audit event failed: {exc}")

    def _existing_storyboard_asset(self, series_id: str, shot: Shot) -> Asset | None:
        return (
            self._db.query(Asset)
            .filter_by(
                series_id=series_id,
                shot_id=shot.id,
                asset_type=AssetType.STORYBOARD.value,
                status=AssetStatus.AVAILABLE.value,
            )
            .first()
        )

    def _ensure_storyboard(self, series_id: str, shot: Shot) -> Asset:
        existing = self._existing_storyboard_asset(series_id, shot)
        if existing:
            self._emit(
                AuditEventType.ASSET_REUSED,
                episode_id=str(shot.scene.episode_id),
                shot_id=shot.id,
                asset_id=existing.id,
                status=AuditStatus.SUCCESS,
                metadata={"asset_role": "storyboard"},
            )
            return existing
        job = self._orchestrator.submit_image_generation(
            self._db, series_id, shot.id, production_run_id=self._run_id
        )
        self._db.refresh(job)
        if job.status != ImageGenerationJobStatus.SUCCEEDED.value:
            raise EpisodeProductionError(f"Storyboard generation failed for shot {shot.id}")
        asset = self._db.get(Asset, job.result_asset_ids[0])
        if not asset:
            raise EpisodeProductionError(f"Storyboard asset missing for shot {shot.id}")
        if asset.approval_status != ApprovalStatus.APPROVED.value:
            image_service = ImageGenerationJobService(
                self._db, ImageGenerationProviderFactory.create()
            )
            image_service.approve(series_id, job.id)
            self._db.refresh(asset)
        self._emit(
            AuditEventType.ASSET_CREATED,
            episode_id=str(shot.scene.episode_id),
            shot_id=shot.id,
            asset_id=asset.id,
            job_id=job.id,
            status=AuditStatus.SUCCESS,
            metadata={"asset_role": "storyboard"},
        )
        return asset

    def _existing_video_job(self, series_id: str, shot: Shot) -> VideoGenerationJob | None:
        return (
            self._db.query(VideoGenerationJob)
            .filter_by(
                series_id=series_id,
                shot_id=shot.id,
                status=ImageGenerationJobStatus.SUCCEEDED.value,
            )
            .first()
        )

    def _video_asset_id(self, job: VideoGenerationJob) -> str | None:
        metadata = job.result_metadata or {}
        return metadata.get("asset_id")

    def _ensure_video(self, series_id: str, shot: Shot, storyboard_asset_id: str) -> Asset:
        existing_job = self._existing_video_job(series_id, shot)
        if existing_job:
            asset_id = self._video_asset_id(existing_job)
            if asset_id:
                asset = self._db.get(Asset, asset_id)
                if asset:
                    self._emit(
                        AuditEventType.ASSET_REUSED,
                        episode_id=str(shot.scene.episode_id),
                        shot_id=shot.id,
                        asset_id=asset.id,
                        status=AuditStatus.SUCCESS,
                        metadata={"asset_role": "video_clip"},
                    )
                    return asset
        job = self._orchestrator.submit_video_generation(
            self._db, series_id, shot.id, storyboard_asset_id, production_run_id=self._run_id
        )
        self._db.refresh(job)
        if job.status != ImageGenerationJobStatus.SUCCEEDED.value:
            raise EpisodeProductionError(f"Video generation failed for shot {shot.id}")
        asset_id = self._video_asset_id(job)
        if not asset_id:
            raise EpisodeProductionError(
                f"Video generation did not produce an asset for shot {shot.id}"
            )
        asset = self._db.get(Asset, asset_id)
        if not asset:
            raise EpisodeProductionError(f"Video asset missing for shot {shot.id}")
        self._emit(
            AuditEventType.ASSET_CREATED,
            episode_id=str(shot.scene.episode_id),
            shot_id=shot.id,
            asset_id=asset.id,
            job_id=job.id,
            status=AuditStatus.SUCCESS,
            metadata={"asset_role": "video_clip"},
        )
        return asset

    def _ensure_shot_media(self, series_id: str, shot: Shot) -> dict[str, Any]:
        storyboard = self._ensure_storyboard(series_id, shot)
        video_asset = self._ensure_video(series_id, shot, str(storyboard.id))
        duration = video_asset.asset_metadata.get("duration") or 5.0
        return {
            "shot": shot,
            "storyboard": storyboard,
            "video_asset": video_asset,
            "duration_seconds": float(duration),
        }

    def _ensure_media(self, series_id: str, episode: Episode) -> list[dict[str, Any]]:
        media: list[dict[str, Any]] = []
        for scene in episode.scenes:
            for shot in scene.shots:
                if shot.specification is None:
                    raise EpisodeProductionError(f"Shot {shot.id} has no production specification")
                media.append(self._ensure_shot_media(series_id, shot))
        return media

    def _ensure_narrations(self, series_id: str, episode_id: str) -> list[tuple[Narration, Asset]]:
        narrations = (
            self._db.query(Narration).filter_by(series_id=series_id, episode_id=episode_id).all()
        )
        pairs: list[tuple[Narration, Asset]] = []
        if not narrations:
            return pairs
        tts = NarrationGenerationService(
            self._db,
            provider=TTSProviderFactory.create(),
            storage=self._storage,
        )
        for narration in narrations:
            if not narration.voice_id or not narration.source_text:
                continue
            if narration.status == NarrationStatus.GENERATED.value and narration.generated_asset_id:
                asset = self._db.get(Asset, narration.generated_asset_id)
                if asset:
                    self._emit(
                        AuditEventType.ASSET_REUSED,
                        episode_id=episode_id,
                        asset_id=asset.id,
                        status=AuditStatus.SUCCESS,
                        metadata={"asset_role": "narration_audio"},
                    )
                    pairs.append((narration, asset))
                    continue
            try:
                generated = tts.generate(series_id, narration.id)
            except Exception as exc:
                raise EpisodeProductionError(
                    f"Narration generation failed for {narration.id}: {exc}"
                ) from exc
            asset = self._db.get(Asset, generated.generated_asset_id)
            if not asset:
                raise EpisodeProductionError(f"Narration asset missing for {narration.id}")
            self._emit(
                AuditEventType.ASSET_CREATED,
                episode_id=episode_id,
                asset_id=asset.id,
                status=AuditStatus.SUCCESS,
                metadata={"asset_role": "narration_audio"},
            )
            pairs.append((narration, asset))
        return pairs

    def _run_qa(self, series_id: str, episode_id: str) -> QAWorkflowResponse:
        qa_service = QAWorkflowService(self._db, ai_provider=self._ai_provider)
        return qa_service.evaluate_episode(series_id, episode_id, ai_modes=[AIQAMode.NARRATIVE])

    def _build_assembly(
        self,
        series_id: str,
        episode_id: str,
        shot_media: list[dict[str, Any]],
        narration_pairs: list[tuple[Narration, Asset]],
    ) -> VideoAssembly:
        assembly_service = VideoAssemblyService(self._db)
        existing = assembly_service.get_by_episode(series_id, episode_id)
        if existing:
            assembly = existing
        else:
            total_duration = sum(m["duration_seconds"] for m in shot_media)
            assembly = assembly_service.create(
                series_id,
                VideoAssemblyCreate(
                    episode_id=UUID(episode_id),
                    status=AssemblyStatus.READY,
                    duration_seconds=total_duration,
                ),
            )

        # Only add items when the assembly is new; existing items are reused.
        if not existing:
            start_time = 0.0
            for index, media in enumerate(shot_media):
                shot = media["shot"]
                video_asset = media["video_asset"]
                assembly_service.add_item(
                    series_id,
                    str(assembly.id),
                    AssemblyItemCreate(
                        scene_id=UUID(str(shot.scene_id)),
                        shot_id=UUID(str(shot.id)),
                        item_type=AssemblyItemType.VIDEO,
                        track=AssemblyTrack.VIDEO,
                        sequence_order=index,
                        start_time_seconds=start_time,
                        duration_seconds=media["duration_seconds"],
                        asset_id=UUID(str(video_asset.id)),
                    ),
                )
                start_time += media["duration_seconds"]

            for index, (narration, asset) in enumerate(narration_pairs):
                assembly_service.add_item(
                    series_id,
                    str(assembly.id),
                    AssemblyItemCreate(
                        item_type=AssemblyItemType.NARRATION,
                        track=AssemblyTrack.DIALOGUE,
                        sequence_order=len(shot_media) + index,
                        start_time_seconds=0.0,
                        duration_seconds=asset.asset_metadata.get("duration") or 5.0,
                        asset_id=UUID(str(asset.id)),
                        narration_id=UUID(str(narration.id)),
                    ),
                )

        assembly.status = AssemblyStatus.READY.value
        self._db.flush()
        self._db.refresh(assembly)
        return assembly

    def _stage_started(self, stage: str, episode_id: str) -> None:
        self._emit(
            AuditEventType.STAGE_STARTED,
            episode_id=episode_id,
            stage=stage,
            status=AuditStatus.PENDING,
            metadata={"stage": stage},
        )

    def _stage_completed(self, stage: str, episode_id: str, metadata: dict | None = None) -> None:
        self._emit(
            AuditEventType.STAGE_COMPLETED,
            episode_id=episode_id,
            stage=stage,
            status=AuditStatus.SUCCESS,
            metadata=metadata or {"stage": stage},
        )

    def _stage_failed(self, stage: str, episode_id: str, error_message: str) -> None:
        self._emit(
            AuditEventType.STAGE_FAILED,
            episode_id=episode_id,
            stage=stage,
            status=AuditStatus.FAILED,
            error_message=error_message,
            metadata={"stage": stage},
        )

    def produce(self, series_id: str, episode_id: str) -> EpisodeProductionResult:
        """Execute the full episode production pipeline."""
        self._series_id = series_id
        self._run_id = str(uuid.uuid4())
        self._audit_warnings: list[str] = []

        episode = self._load_episode(series_id, episode_id)

        if not episode.scenes:
            self._stage_started(EpisodeProductionStage.PLANNING, episode_id)
            self._stage_failed(
                EpisodeProductionStage.PLANNING,
                episode_id,
                "Episode has no scenes; planning is required first.",
            )
            self._emit(
                AuditEventType.PRODUCTION_FAILED,
                episode_id=episode_id,
                status=AuditStatus.FAILED,
                error_message="Episode has no scenes; planning is required first.",
            )
            return EpisodeProductionResult(
                series_id=UUID(series_id),
                episode_id=UUID(episode_id),
                production_run_id=UUID(self._run_id),
                stage=EpisodeProductionStage.PLANNING,
                status="failed",
                message="Episode has no scenes; planning is required first.",
                warnings=self._audit_warnings,
            )

        stage = EpisodeProductionStage.STORYBOARD
        try:
            self._emit(
                AuditEventType.PRODUCTION_STARTED,
                episode_id=episode_id,
                status=AuditStatus.PENDING,
                metadata={"episode_title": episode.title},
            )

            self._stage_started(stage, episode_id)
            shot_media = self._ensure_media(series_id, episode)
            self._stage_completed(stage, episode_id)

            stage = EpisodeProductionStage.AUDIO
            self._stage_started(stage, episode_id)
            narration_assets = self._ensure_narrations(series_id, episode_id)
            self._stage_completed(stage, episode_id)

            stage = EpisodeProductionStage.QA
            self._stage_started(stage, episode_id)
            qa = self._run_qa(series_id, episode_id)
            self._emit(
                AuditEventType.QA_COMPLETED,
                episode_id=episode_id,
                status=str(qa.status),
                metadata=qa.counts.model_dump(mode="json") if qa.counts else {},
            )
            self._stage_completed(stage, episode_id)
            if qa.status in {QAWorkflowStatus.FAIL, QAWorkflowStatus.DEGRADED}:
                self._stage_failed(stage, episode_id, "QA gate failed.")
                self._emit(
                    AuditEventType.PRODUCTION_FAILED,
                    episode_id=episode_id,
                    status=AuditStatus.FAILED,
                    error_message="QA gate failed.",
                )
                return EpisodeProductionResult(
                    series_id=UUID(series_id),
                    episode_id=UUID(episode_id),
                    production_run_id=UUID(self._run_id),
                    stage=stage,
                    status="failed",
                    message="QA gate failed.",
                    qa_response=qa,
                    findings=qa.findings,
                    warnings=self._audit_warnings,
                )

            stage = EpisodeProductionStage.ASSEMBLY
            self._stage_started(stage, episode_id)
            assembly = self._build_assembly(series_id, episode_id, shot_media, narration_assets)
            self._stage_completed(stage, episode_id, metadata={"assembly_id": str(assembly.id)})

            stage = EpisodeProductionStage.EXPORT
            self._stage_started(stage, episode_id)
            exporter = FinalExportService(
                self._db,
                self._storage,
                self._storage_backend_name,
                self._renderer,
            )
            assembly = exporter.export(series_id, str(assembly.id))
            self._emit(
                AuditEventType.EXPORT_COMPLETED,
                episode_id=episode_id,
                asset_id=assembly.final_asset_id,
                status=AuditStatus.SUCCESS,
                metadata={
                    "assembly_id": str(assembly.id),
                    "final_asset_id": str(assembly.final_asset_id),
                },
            )
            self._stage_completed(
                stage, episode_id, metadata={"final_asset_id": str(assembly.final_asset_id)}
            )

            self._emit(
                AuditEventType.PRODUCTION_COMPLETED,
                episode_id=episode_id,
                asset_id=assembly.final_asset_id,
                status=AuditStatus.SUCCESS,
                metadata={
                    "assembly_id": str(assembly.id),
                    "final_asset_id": str(assembly.final_asset_id),
                },
            )

            return EpisodeProductionResult(
                series_id=UUID(series_id),
                episode_id=UUID(episode_id),
                production_run_id=UUID(self._run_id),
                assembly_id=UUID(str(assembly.id)),
                final_asset_id=(
                    UUID(str(assembly.final_asset_id)) if assembly.final_asset_id else None
                ),
                stage=EpisodeProductionStage.COMPLETED,
                status="completed",
                message="Episode production completed.",
                qa_response=qa,
                findings=qa.findings,
                warnings=self._audit_warnings,
            )
        except Exception as exc:
            self._stage_failed(stage, episode_id, str(exc))
            self._emit(
                AuditEventType.PRODUCTION_FAILED,
                episode_id=episode_id,
                status=AuditStatus.FAILED,
                error_message=str(exc),
            )
            return EpisodeProductionResult(
                series_id=UUID(series_id),
                episode_id=UUID(episode_id),
                production_run_id=UUID(self._run_id),
                stage=stage,
                status="failed",
                message=str(exc),
                warnings=self._audit_warnings,
            )
