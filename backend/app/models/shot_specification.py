"""Shot specification model — provider-neutral production constraints for a Shot."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.shot import Shot


class ShotSpecification(Base):
    """Provider-neutral production specification for a single shot."""

    __tablename__ = "shot_specifications"
    __table_args__ = (UniqueConstraint("shot_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    shot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    intent: Mapped[str | None] = mapped_column(Text)
    framing: Mapped[str | None] = mapped_column(Text)
    composition: Mapped[str | None] = mapped_column(Text)
    camera_notes: Mapped[str | None] = mapped_column(Text)
    camera_movement: Mapped[str | None] = mapped_column(Text)
    subject_notes: Mapped[str | None] = mapped_column(Text)
    visual_direction: Mapped[str | None] = mapped_column(Text)
    aspect_ratio: Mapped[str | None] = mapped_column(String(20))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    character_refs: Mapped[list[str] | None] = mapped_column(JSON)
    location_refs: Mapped[list[str] | None] = mapped_column(JSON)
    object_refs: Mapped[list[str] | None] = mapped_column(JSON)
    output_constraints: Mapped[dict | None] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    shot: Mapped["Shot"] = relationship("Shot", back_populates="specification")
