"""Production audit event persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.episode import Episode
    from app.models.scene import Scene
    from app.models.series import Series
    from app.models.shot import Shot


class AuditEvent(Base):
    """A single, append-only production audit event."""

    __tablename__ = "audit_events"

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
    scene_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("scenes.id", ondelete="SET NULL"),
        nullable=True,
    )
    shot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    production_run_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    stage: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    attempt: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    event_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    series: Mapped["Series"] = relationship("Series")
    episode: Mapped["Episode | None"] = relationship("Episode")
    scene: Mapped["Scene | None"] = relationship("Scene")
    shot: Mapped["Shot | None"] = relationship("Shot")
    asset: Mapped["Asset | None"] = relationship("Asset")
