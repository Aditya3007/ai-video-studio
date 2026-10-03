"""Shot model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.scene import Scene
    from app.models.shot_specification import ShotSpecification


class Shot(Base):
    """Atomic production planning unit within a scene."""

    __tablename__ = "shots"
    __table_args__ = (UniqueConstraint("scene_id", "shot_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    camera: Mapped[str | None] = mapped_column(String(255))
    camera_movement: Mapped[str | None] = mapped_column(String(255))
    lighting: Mapped[str | None] = mapped_column(String(255))
    mood: Mapped[str | None] = mapped_column(String(255))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    dialogue: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    scene: Mapped["Scene"] = relationship("Scene", back_populates="shots")
    specification: Mapped["ShotSpecification | None"] = relationship(
        "ShotSpecification",
        back_populates="shot",
        uselist=False,
        cascade="all, delete-orphan",
    )
