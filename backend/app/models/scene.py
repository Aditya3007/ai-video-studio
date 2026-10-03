"""Scene model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.episode import Episode
    from app.models.location import Location
    from app.models.shot import Shot


class Scene(Base):
    """Scene within an episode."""

    __tablename__ = "scenes"
    __table_args__ = (UniqueConstraint("episode_id", "scene_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    episode_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    time_of_day: Mapped[str | None] = mapped_column(String(255))
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    episode: Mapped["Episode"] = relationship("Episode", back_populates="scenes")
    location: Mapped["Location | None"] = relationship("Location", back_populates="scenes")
    shots: Mapped[list["Shot"]] = relationship(
        "Shot", back_populates="scene", cascade="all, delete-orphan"
    )
