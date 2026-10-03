"""Caption/subtitle domain model for timed text in video assembly."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.episode import Episode
    from app.models.narration import Narration
    from app.models.scene import Scene
    from app.models.series import Series
    from app.models.shot import Shot
    from app.models.video_assembly import VideoAssembly


class Caption(Base):
    """Timed caption/subtitle entry associated with a video assembly."""

    __tablename__ = "captions"
    __table_args__ = (
        Index("ix_captions_assembly_id", "assembly_id"),
        Index("ix_captions_series_id", "series_id"),
        Index("ix_captions_episode_id", "episode_id"),
        Index("ix_captions_narration_id", "narration_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
    )
    episode_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    assembly_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("video_assemblies.id", ondelete="CASCADE"),
        nullable=False,
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
    narration_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("narrations.id", ondelete="SET NULL"),
        nullable=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    style: Mapped[dict | None] = mapped_column(JSON, default=None)
    locale: Mapped[str | None] = mapped_column(String(10))
    caption_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series")
    episode: Mapped["Episode"] = relationship("Episode")
    assembly: Mapped["VideoAssembly"] = relationship("VideoAssembly")
    scene: Mapped["Scene | None"] = relationship("Scene")
    shot: Mapped["Shot | None"] = relationship("Shot")
    narration: Mapped["Narration | None"] = relationship("Narration")
