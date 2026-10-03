"""Story and story version models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.episode import Episode
    from app.models.series import Series
    from app.models.story_analysis import StoryAnalysis


class Story(Base):
    """User-provided story or story idea belonging to a series."""

    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series", back_populates="stories")
    versions: Mapped[list["StoryVersion"]] = relationship(
        "StoryVersion", back_populates="story", cascade="all, delete-orphan"
    )
    episodes: Mapped[list["Episode"]] = relationship("Episode", back_populates="story")
    analyses: Mapped[list["StoryAnalysis"]] = relationship(
        "StoryAnalysis", back_populates="story", cascade="all, delete-orphan"
    )


class StoryVersion(Base):
    """Versioned content for a story."""

    __tablename__ = "story_versions"
    __table_args__ = (UniqueConstraint("story_id", "version_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    story: Mapped["Story"] = relationship("Story", back_populates="versions")
    analyses: Mapped[list["StoryAnalysis"]] = relationship(
        "StoryAnalysis", back_populates="story_version", cascade="all, delete-orphan"
    )
