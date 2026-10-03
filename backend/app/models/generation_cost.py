"""Generation cost accounting records."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid


class GenerationCost(Base):
    """Provider-neutral cost record for an AI/media generation execution."""

    __tablename__ = "generation_costs"
    __table_args__ = (UniqueConstraint("series_id", "correlation_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    episode_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    generation_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cost_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTUAL")
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0)
    usage_components: Mapped[list[dict] | None] = mapped_column(JSON, default=None)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
