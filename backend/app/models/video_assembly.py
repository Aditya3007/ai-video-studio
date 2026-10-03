"""Video assembly and timeline domain model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import AssemblyItemType, AssemblyStatus, AssemblyTrack

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.audio_cue import AudioCue
    from app.models.episode import Episode
    from app.models.narration import Narration
    from app.models.scene import Scene
    from app.models.series import Series
    from app.models.shot import Shot


class VideoAssembly(Base):
    """Canonical declarative composition for an episode."""

    __tablename__ = "video_assemblies"

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
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AssemblyStatus.DRAFT.value,
        index=True,
    )
    output_config: Mapped[dict | None] = mapped_column(JSON, default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    assembly_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    final_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series")
    episode: Mapped["Episode"] = relationship("Episode")
    final_asset: Mapped["Asset | None"] = relationship(
        "Asset", foreign_keys="VideoAssembly.final_asset_id"
    )
    items: Mapped[list["AssemblyItem"]] = relationship(
        "AssemblyItem",
        back_populates="assembly",
        order_by="AssemblyItem.sequence_order",
        cascade="all, delete-orphan",
    )


class AssemblyItem(Base):
    """A single timed element on an assembly timeline."""

    __tablename__ = "assembly_items"
    __table_args__ = (UniqueConstraint("assembly_id", "sequence_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    assembly_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("video_assemblies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    item_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AssemblyItemType.VIDEO.value,
    )
    track: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AssemblyTrack.VIDEO.value,
    )
    sequence_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    narration_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("narrations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    audio_cue_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("audio_cues.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    item_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    assembly: Mapped["VideoAssembly"] = relationship("VideoAssembly", back_populates="items")
    series: Mapped["Series"] = relationship("Series")
    episode: Mapped["Episode"] = relationship("Episode")
    scene: Mapped["Scene | None"] = relationship("Scene")
    shot: Mapped["Shot | None"] = relationship("Shot")
    asset: Mapped["Asset | None"] = relationship("Asset")
    narration: Mapped["Narration | None"] = relationship("Narration")
    audio_cue: Mapped["AudioCue | None"] = relationship("AudioCue")
