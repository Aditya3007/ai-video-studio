"""Episode model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import EpisodeSourceType, EpisodeStatus

if TYPE_CHECKING:
    from app.models.scene import Scene
    from app.models.series import Series
    from app.models.story import Story


class Episode(Base):
    """Episode/story within a series."""

    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("series_id", "episode_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=EpisodeStatus.DRAFT.value, nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(20), default=EpisodeSourceType.TOPIC.value, nullable=False
    )
    source_text: Mapped[str | None] = mapped_column(Text)
    story_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series", back_populates="episodes")
    story: Mapped["Story | None"] = relationship("Story", back_populates="episodes")
    scenes: Mapped[list["Scene"]] = relationship(
        "Scene", back_populates="episode", cascade="all, delete-orphan"
    )
