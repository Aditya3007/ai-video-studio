"""Application service for generating narration audio through the TTS boundary."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import generate_uuid
from app.media_generation.tts import (
    TTSError,
    TTSProvider,
    TTSProviderFactory,
    TTSRequest,
    TTSResult,
)
from app.models import Asset, Narration, Voice
from app.models.enums import (
    ApprovalStatus,
    AssetRole,
    AssetStatus,
    AssetType,
    NarrationStatus,
)
from app.services.generation_cost_service import GenerationCostService
from app.storage import StorageBackend, StorageError, create_storage_backend


class NarrationGenerationError(Exception):
    """Raised when narration audio generation fails."""


class NarrationGenerationService:
    """Generates audio for a narration using the provider-neutral TTS boundary."""

    def __init__(
        self,
        db: Session,
        provider: TTSProvider | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._db = db
        self._provider = provider
        self._storage = storage or create_storage_backend(get_settings())

    def _get_narration(self, series_id: str, narration_id: str) -> Narration:
        narration = self._db.get(Narration, narration_id)
        if not narration or narration.series_id != series_id:
            raise NarrationGenerationError("Narration not found.")
        return narration

    def _validate_eligible(self, narration: Narration) -> None:
        if not narration.source_text or not narration.source_text.strip():
            raise NarrationGenerationError("Narration text is required for generation.")
        if narration.status == NarrationStatus.GENERATED.value and narration.generated_asset_id:
            raise NarrationGenerationError("Narration already has a generated asset.")
        if not narration.voice_id:
            raise NarrationGenerationError("Narration requires a voice for generation.")

    def _resolve_voice(self, series_id: str, voice_id: str) -> Voice:
        voice = self._db.get(Voice, voice_id)
        if not voice or voice.series_id != series_id:
            raise NarrationGenerationError("Voice not found.")
        return voice

    def _build_tts_request(self, narration: Narration, voice: Voice) -> TTSRequest:
        return TTSRequest(
            text=narration.source_text,
            voice_id=str(voice.id),
            voice_metadata=voice.voice_metadata or {},
            options=narration.audio_metadata or {},
        )

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        provider = self._provider or TTSProviderFactory.create(request=request)
        try:
            return provider.synthesize(request)
        except (TTSError, ValueError, NotImplementedError) as exc:
            raise NarrationGenerationError(str(exc)) from exc

    def _validate_result(self, result: TTSResult) -> None:
        if result.audio is None:
            raise NarrationGenerationError("Provider returned no audio reference.")
        if not result.audio.data:
            raise NarrationGenerationError("Provider returned empty audio payload.")
        if not result.audio.content_type:
            raise NarrationGenerationError("Provider returned no content type.")
        if not result.audio.audio_format:
            raise NarrationGenerationError("Provider returned no audio format.")

    def _generate_key(self, narration: Narration, result: TTSResult) -> str:
        request_id = result.request_id or "generated"
        return (
            f"audio/{narration.series_id}/{narration.id}/{request_id}.{result.audio.audio_format}"
        )

    def _store_and_create_asset(self, narration: Narration, result: TTSResult) -> Asset:
        key = self._generate_key(narration, result)
        try:
            storage_object = self._storage.put(
                key,
                result.audio.data,
                content_type=result.audio.content_type,
                metadata={
                    "series_id": str(narration.series_id),
                    "narration_id": str(narration.id),
                    "provider": result.provider,
                    "model": result.model,
                    "request_id": result.request_id or "",
                    "content_type": result.audio.content_type,
                    "audio_format": result.audio.audio_format,
                    "duration": (
                        str(result.audio.duration) if result.audio.duration is not None else ""
                    ),
                },
            )
        except StorageError as exc:
            raise NarrationGenerationError(f"Storage failed: {exc}") from exc

        asset = Asset(
            id=generate_uuid(),
            series_id=narration.series_id,
            asset_type=AssetType.AUDIO.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            approval_status=ApprovalStatus.PENDING.value,
            storage_backend=get_settings().storage_backend,
            storage_key=storage_object.key,
            name=f"Generated audio for narration {narration.id}",
            asset_metadata={
                "narration_id": str(narration.id),
                "provider": result.provider,
                "model": result.model,
                "content_type": result.audio.content_type,
                "audio_format": result.audio.audio_format,
                "duration": result.audio.duration,
                "request_id": result.request_id,
                "language": (
                    result.audio.metadata.get("language") if result.audio.metadata else None
                ),
            },
            shot_id=narration.shot_id,
        )
        self._db.add(asset)
        return asset

    def _link_success(self, narration: Narration, asset: Asset, result: TTSResult) -> None:
        narration.generated_asset_id = asset.id
        narration.status = NarrationStatus.GENERATED.value
        narration.duration_seconds = result.audio.duration
        narration.audio_metadata = {
            "provider": result.provider,
            "model": result.model,
            "content_type": result.audio.content_type,
            "audio_format": result.audio.audio_format,
            "duration": result.audio.duration,
            "request_id": result.request_id,
            "storage_key": asset.storage_key,
        }

    def _mark_failed(self, narration: Narration, message: str) -> None:
        narration.status = NarrationStatus.FAILED.value
        narration.audio_metadata = {"error": message}

    def generate(self, series_id: str, narration_id: str) -> Narration:
        """Generate audio for a narration and persist it as an AUDIO asset."""
        narration = self._get_narration(series_id, narration_id)
        self._validate_eligible(narration)
        voice = self._resolve_voice(series_id, str(narration.voice_id))
        request = self._build_tts_request(narration, voice)

        reservation_id: str | None = None
        try:
            from app.services.episode_budget_service import EpisodeBudgetService

            budget_result = EpisodeBudgetService(self._db).check_and_reserve(
                series_id,
                str(narration.episode_id),
                "TTS",
                estimated_cost=0,
                currency="USD",
                job_id=str(narration.id),
            )
            if not budget_result.allowed:
                raise NarrationGenerationError(budget_result.reason)
            reservation_id = budget_result.reservation_id

            result = self._synthesize(request)
            self._validate_result(result)
            asset = self._store_and_create_asset(narration, result)
            self._link_success(narration, asset, result)
            GenerationCostService(self._db).record_from_tts_result(
                series_id,
                result,
                episode_id=str(narration.episode_id),
                job_id=str(narration.id),
                asset_id=str(asset.id),
            )
            if reservation_id:
                EpisodeBudgetService(self._db).settle_reservation(reservation_id)
            self._db.flush()
            self._db.refresh(narration)
        except NarrationGenerationError as exc:
            if reservation_id:
                EpisodeBudgetService(self._db).release_reservation(reservation_id)
            self._mark_failed(narration, str(exc))
            self._db.flush()
            raise

        return narration
