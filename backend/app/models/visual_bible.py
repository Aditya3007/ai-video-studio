"""Visual bible model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.series import Series


class VisualBible(Base):
    """Canonical visual style guide for a series."""

    __tablename__ = "visual_bibles"
    __table_args__ = (UniqueConstraint("series_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    art_style: Mapped[str | None] = mapped_column(Text)
    color_palette: Mapped[str | None] = mapped_column(Text)
    lighting_style: Mapped[str | None] = mapped_column(Text)
    camera_style: Mapped[str | None] = mapped_column(Text)
    lens_style: Mapped[str | None] = mapped_column(Text)
    composition_style: Mapped[str | None] = mapped_column(Text)
    environment_style: Mapped[str | None] = mapped_column(Text)
    character_rendering_style: Mapped[str | None] = mapped_column(Text)
    aspect_ratio: Mapped[str | None] = mapped_column(String(20))
    visual_notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series", back_populates="visual_bible")
