"""Provider-neutral generation cost tracking service."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.media_generation.audio.provider import AudioGenerationResult
from app.media_generation.image.provider import ImageGenerationResult
from app.media_generation.tts.provider import TTSResult
from app.media_generation.video.provider import VideoGenerationResult
from app.models import GenerationCost
from app.models.enums import AuditEventType, AuditStatus, CostStatus, GenerationType
from app.services.audit_service import AuditService
from app.story_intelligence.llm.provider import LLMResponse


class CostComponent(BaseModel):
    """One normalized usage component used to calculate generation cost."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def _decimal_like(cls, value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))


class GenerationCostService:
    """Records, calculates, and aggregates provider-neutral generation costs."""

    def __init__(self, db: Session, audit_service: AuditService | None = None) -> None:
        self._db = db
        self._audit = audit_service or AuditService(db)

    @staticmethod
    def _normalize_status(value: CostStatus | str) -> str:
        return value.value if isinstance(value, CostStatus) else str(value)

    @staticmethod
    def _normalize_type(value: GenerationType | str) -> str:
        return value.value if isinstance(value, GenerationType) else str(value)

    @staticmethod
    def _calculate_total(components: list[CostComponent] | None) -> Decimal:
        if not components:
            return Decimal("0")
        return sum(
            (component.quantity * component.unit_price).quantize(Decimal("0.000001"))
            for component in components
        )

    def _existing(self, series_id: str, correlation_id: str | None) -> GenerationCost | None:
        if not correlation_id:
            return None
        return (
            self._db.query(GenerationCost)
            .filter(
                GenerationCost.series_id == series_id,
                GenerationCost.correlation_id == correlation_id,
            )
            .first()
        )

    def record(
        self,
        series_id: str,
        generation_type: GenerationType | str,
        provider: str,
        model: str,
        components: list[CostComponent] | None = None,
        *,
        episode_id: str | None = None,
        job_id: str | None = None,
        asset_id: str | None = None,
        cost_status: CostStatus | str = CostStatus.ACTUAL,
        currency: str = "USD",
        correlation_id: str | None = None,
        request_id: str | None = None,
        audit_metadata: dict[str, Any] | None = None,
    ) -> GenerationCost:
        """Create or return an existing generation cost record."""
        if correlation_id:
            existing = self._existing(series_id, correlation_id)
            if existing:
                return existing

        normalized_components = components or []
        total = self._calculate_total(normalized_components)

        cost = GenerationCost(
            series_id=series_id,
            episode_id=episode_id,
            generation_type=self._normalize_type(generation_type),
            job_id=job_id,
            asset_id=asset_id,
            provider=provider,
            model=model,
            cost_status=self._normalize_status(cost_status),
            cost_currency=currency,
            total_cost=total,
            usage_components=[
                component.model_dump(mode="json") for component in normalized_components
            ],
            correlation_id=correlation_id,
            request_id=request_id,
        )
        self._db.add(cost)
        self._db.flush()
        self._audit.record(
            series_id=series_id,
            episode_id=episode_id,
            event_type=AuditEventType.GENERATION_COST_RECORDED,
            job_id=job_id,
            asset_id=asset_id,
            status=AuditStatus.SUCCESS,
            metadata={
                "generation_type": cost.generation_type,
                "provider": provider,
                "model": model,
                "cost": str(total),
                "currency": currency,
                "cost_status": cost.cost_status,
                **(audit_metadata or {}),
            },
        )
        return cost

    @staticmethod
    def _usage_to_components(usage: Any) -> list[CostComponent]:
        """Best-effort conversion of provider usage objects to normalized components."""
        if usage is None:
            return []
        components: list[CostComponent] = []

        if isinstance(usage, dict):
            for key in ("input_tokens", "output_tokens"):
                value = usage.get(key)
                if value is not None:
                    components.append(
                        CostComponent(
                            name=key,
                            quantity=Decimal(str(value)),
                            unit="token",
                            unit_price=Decimal("0"),
                        )
                    )
            if "cost_usd" in usage:
                components.append(
                    CostComponent(
                        name="cost",
                        quantity=Decimal("1"),
                        unit="usd",
                        unit_price=Decimal(str(usage["cost_usd"])),
                    )
                )
            return components

        cost_usd = getattr(usage, "cost_usd", None)
        credits = getattr(usage, "credits", None)
        if cost_usd is not None:
            components.append(
                CostComponent(
                    name="cost",
                    quantity=Decimal("1"),
                    unit="usd",
                    unit_price=Decimal(str(cost_usd)),
                )
            )
        if credits is not None:
            components.append(
                CostComponent(
                    name="credits",
                    quantity=Decimal(str(credits)),
                    unit="credit",
                    unit_price=Decimal("0"),
                )
            )
        return components

    def record_from_image_result(
        self,
        series_id: str,
        result: ImageGenerationResult,
        *,
        episode_id: str | None = None,
        job_id: str | None = None,
        asset_id: str | None = None,
        cost_status: CostStatus | str = CostStatus.ACTUAL,
        correlation_id: str | None = None,
    ) -> GenerationCost | None:
        """Record a cost from an image generation result."""
        components = self._usage_to_components(result.usage)
        return self.record(
            series_id=series_id,
            generation_type=GenerationType.IMAGE,
            provider=result.provider,
            model=result.model,
            components=components,
            episode_id=episode_id,
            job_id=job_id,
            asset_id=asset_id,
            cost_status=cost_status,
            correlation_id=correlation_id or result.request_id,
            request_id=result.request_id,
        )

    def record_from_video_result(
        self,
        series_id: str,
        result: VideoGenerationResult,
        *,
        episode_id: str | None = None,
        job_id: str | None = None,
        asset_id: str | None = None,
        cost_status: CostStatus | str = CostStatus.ACTUAL,
        correlation_id: str | None = None,
    ) -> GenerationCost | None:
        """Record a cost from a video generation result."""
        components = self._usage_to_components(result.usage)
        return self.record(
            series_id=series_id,
            generation_type=GenerationType.VIDEO,
            provider=result.provider,
            model=result.model,
            components=components,
            episode_id=episode_id,
            job_id=job_id,
            asset_id=asset_id,
            cost_status=cost_status,
            correlation_id=correlation_id or result.request_id,
            request_id=result.request_id,
        )

    def record_from_tts_result(
        self,
        series_id: str,
        result: TTSResult,
        *,
        episode_id: str | None = None,
        job_id: str | None = None,
        asset_id: str | None = None,
        cost_status: CostStatus | str = CostStatus.ACTUAL,
        correlation_id: str | None = None,
    ) -> GenerationCost | None:
        """Record a cost from a TTS result."""
        components = self._usage_to_components(result.usage)
        return self.record(
            series_id=series_id,
            generation_type=GenerationType.TTS,
            provider=result.provider,
            model=result.model,
            components=components,
            episode_id=episode_id,
            job_id=job_id,
            asset_id=asset_id,
            cost_status=cost_status,
            correlation_id=correlation_id or result.request_id,
            request_id=result.request_id,
        )

    def record_from_audio_result(
        self,
        series_id: str,
        result: AudioGenerationResult,
        *,
        episode_id: str | None = None,
        job_id: str | None = None,
        asset_id: str | None = None,
        cost_status: CostStatus | str = CostStatus.ACTUAL,
        correlation_id: str | None = None,
    ) -> GenerationCost | None:
        """Record a cost from a music/sound-effect generation result."""
        components = self._usage_to_components(result.usage)
        return self.record(
            series_id=series_id,
            generation_type=(
                GenerationType.SFX
                if (result.audio.metadata or {}).get("audio_type") == "SOUND_EFFECT"
                else GenerationType.MUSIC
            ),
            provider=result.provider,
            model=result.model,
            components=components,
            episode_id=episode_id,
            job_id=job_id,
            asset_id=asset_id,
            cost_status=cost_status,
            correlation_id=correlation_id or result.request_id,
            request_id=result.request_id,
        )

    def record_from_llm_response(
        self,
        series_id: str,
        response: LLMResponse,
        *,
        episode_id: str | None = None,
        job_id: str | None = None,
        cost_status: CostStatus | str = CostStatus.ACTUAL,
        correlation_id: str | None = None,
    ) -> GenerationCost | None:
        """Record a cost from an LLM response when usage is reported."""
        components = self._usage_to_components(response.usage)
        if not components:
            return None
        return self.record(
            series_id=series_id,
            generation_type=GenerationType.TEXT,
            provider=response.provider or "unknown",
            model=response.model or "unknown",
            components=components,
            episode_id=episode_id,
            job_id=job_id,
            cost_status=cost_status,
            correlation_id=correlation_id,
            request_id=response.metadata.get("request_id") if response.metadata else None,
        )

    def get_by_id(self, cost_id: str, series_id: str) -> GenerationCost | None:
        """Retrieve a single cost record enforcing Series scope."""
        return (
            self._db.query(GenerationCost)
            .filter(GenerationCost.id == cost_id, GenerationCost.series_id == series_id)
            .first()
        )

    def list_by_series(
        self,
        series_id: str,
        *,
        generation_type: str | None = None,
        cost_status: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[GenerationCost]:
        """List cost records for a Series with optional filters."""
        query = self._db.query(GenerationCost).filter(GenerationCost.series_id == series_id)
        if generation_type:
            query = query.filter(GenerationCost.generation_type == generation_type)
        if cost_status:
            query = query.filter(GenerationCost.cost_status == cost_status)
        if provider:
            query = query.filter(GenerationCost.provider == provider)
        if model:
            query = query.filter(GenerationCost.model == model)
        if start:
            query = query.filter(GenerationCost.recorded_at >= start)
        if end:
            query = query.filter(GenerationCost.recorded_at <= end)
        return query.order_by(GenerationCost.recorded_at.desc()).all()

    def _series_total_query(self, series_id: str) -> Any:
        return self._db.query(func.sum(GenerationCost.total_cost)).filter(
            GenerationCost.series_id == series_id
        )

    def get_total_by_series(
        self,
        series_id: str,
        *,
        generation_type: str | None = None,
        cost_status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Decimal:
        """Return the total cost for a Series, optionally filtered."""
        query = self._series_total_query(series_id)
        if generation_type:
            query = query.filter(GenerationCost.generation_type == generation_type)
        if cost_status:
            query = query.filter(GenerationCost.cost_status == cost_status)
        if start:
            query = query.filter(GenerationCost.recorded_at >= start)
        if end:
            query = query.filter(GenerationCost.recorded_at <= end)
        total = query.scalar()
        return Decimal(total or 0)

    def get_total_by_episode(
        self,
        series_id: str,
        episode_id: str,
        *,
        generation_type: str | None = None,
        cost_status: str | None = None,
    ) -> Decimal:
        """Return the total cost for an Episode."""
        query = self._db.query(func.sum(GenerationCost.total_cost)).filter(
            GenerationCost.series_id == series_id,
            GenerationCost.episode_id == episode_id,
        )
        if generation_type:
            query = query.filter(GenerationCost.generation_type == generation_type)
        if cost_status:
            query = query.filter(GenerationCost.cost_status == cost_status)
        total = query.scalar()
        return Decimal(total or 0)

    def get_by_generation_type(self, series_id: str, generation_type: str) -> list[GenerationCost]:
        """Return cost records for a generation type."""
        return self.list_by_series(series_id, generation_type=generation_type)

    def get_by_provider(self, series_id: str, provider: str) -> list[GenerationCost]:
        """Return cost records for a provider."""
        return self.list_by_series(series_id, provider=provider)

    def get_by_model(self, series_id: str, model: str) -> list[GenerationCost]:
        """Return cost records for a model."""
        return self.list_by_series(series_id, model=model)

    def get_time_range(
        self,
        series_id: str,
        start: datetime,
        end: datetime,
    ) -> list[GenerationCost]:
        """Return cost records within a time range."""
        return self.list_by_series(series_id, start=start, end=end)

    def get_by_job(self, series_id: str, job_id: str) -> list[GenerationCost]:
        """Return cost records for a generation job."""
        return (
            self._db.query(GenerationCost)
            .filter(
                GenerationCost.series_id == series_id,
                GenerationCost.job_id == job_id,
            )
            .order_by(GenerationCost.recorded_at.desc())
            .all()
        )

    def aggregate_by_generation_type(self, series_id: str) -> dict[str, Decimal]:
        """Return total cost per generation type for a Series."""
        rows = (
            self._db.query(
                GenerationCost.generation_type,
                func.sum(GenerationCost.total_cost),
            )
            .filter(GenerationCost.series_id == series_id)
            .group_by(GenerationCost.generation_type)
            .all()
        )
        return {row[0]: Decimal(row[1] or 0) for row in rows}

    def aggregate_by_provider(self, series_id: str) -> dict[str, Decimal]:
        """Return total cost per provider for a Series."""
        rows = (
            self._db.query(
                GenerationCost.provider,
                func.sum(GenerationCost.total_cost),
            )
            .filter(GenerationCost.series_id == series_id)
            .group_by(GenerationCost.provider)
            .all()
        )
        return {row[0]: Decimal(row[1] or 0) for row in rows}

    def aggregate_by_model(self, series_id: str) -> dict[str, Decimal]:
        """Return total cost per model for a Series."""
        rows = (
            self._db.query(
                GenerationCost.model,
                func.sum(GenerationCost.total_cost),
            )
            .filter(GenerationCost.series_id == series_id)
            .group_by(GenerationCost.model)
            .all()
        )
        return {row[0]: Decimal(row[1] or 0) for row in rows}
