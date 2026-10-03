"""Publishing workflow job state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid


class PublishingJob(Base):
    """Application-level publishing workflow state."""

    __tablename__ = "publishing_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index("ix_publishing_jobs_status", "status"),
        Index("ix_publishing_jobs_scheduled_at", "scheduled_at"),
        Index("ix_publishing_jobs_idempotency_key", "idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    episode_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thumbnail_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    metadata_snapshot: Mapped[dict | None] = mapped_column(JSON, default=None)
    provider_id: Mapped[str] = mapped_column(String(50), nullable=False, default="fake")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_publication_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
