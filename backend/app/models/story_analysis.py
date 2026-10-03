"""Story analysis result persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.story import Story, StoryVersion


class StoryAnalysis(Base):
    """Persisted provider-neutral story analysis result for a specific StoryVersion."""

    __tablename__ = "story_analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    story_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("story_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    warnings: Mapped[list | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    story: Mapped["Story"] = relationship("Story", back_populates="analyses")
    story_version: Mapped["StoryVersion"] = relationship("StoryVersion", back_populates="analyses")
