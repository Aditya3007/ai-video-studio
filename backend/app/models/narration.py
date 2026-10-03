"""Narration/dialogue domain model for audio production."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import NarrationStatus, NarrationType

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.character import Character
    from app.models.episode import Episode
    from app.models.scene import Scene
    from app.models.series import Series
    from app.models.shot import Shot
    from app.models.voice import Voice


class Narration(Base):
    """Provider-neutral narration or dialogue item awaiting or resulting from TTS generation."""

    __tablename__ = "narrations"

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
    voice_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("voices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    character_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("characters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    narration_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=NarrationType.NARRATION.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=NarrationStatus.PENDING.value,
    )
    generated_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float)
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
    voice: Mapped["Voice | None"] = relationship("Voice")
    character: Mapped["Character | None"] = relationship("Character")
    generated_asset: Mapped["Asset | None"] = relationship("Asset")
