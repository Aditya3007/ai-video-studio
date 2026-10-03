"""Audio cue domain model for music and sound effects."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import AudioCueStatus, AudioCueType

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.episode import Episode
    from app.models.scene import Scene
    from app.models.series import Series
    from app.models.shot import Shot


class AudioCue(Base):
    """Provider-neutral music or sound-effect cue attached to a series/episode/scene/shot."""

    __tablename__ = "audio_cues"
    __table_args__ = (
        UniqueConstraint("series_id", "name"),
        Index("ix_audio_cues_series_id_type", "series_id", "audio_type"),
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
    scene_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("scenes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text)
    audio_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AudioCueType.MUSIC.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AudioCueStatus.PENDING.value,
    )
    prompt: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    start_time_seconds: Mapped[float | None] = mapped_column(Float)
    end_time_seconds: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    loop: Mapped[bool] = mapped_column(Boolean, default=False)
    fade_in: Mapped[bool] = mapped_column(Boolean, default=False)
    fade_out: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    audio_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series")
    episode: Mapped["Episode"] = relationship("Episode")
    scene: Mapped["Scene | None"] = relationship("Scene")
    shot: Mapped["Shot | None"] = relationship("Shot")
    generated_asset: Mapped["Asset | None"] = relationship("Asset")
