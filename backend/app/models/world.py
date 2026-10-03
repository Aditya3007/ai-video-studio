"""World model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.series import Series


class World(Base):
    """Persistent world/universe associated with a series."""

    __tablename__ = "worlds"
    __table_args__ = (UniqueConstraint("series_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    setting: Mapped[str | None] = mapped_column(Text)
    era: Mapped[str | None] = mapped_column(String(255))
    geography: Mapped[str | None] = mapped_column(Text)
    technology: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[str | None] = mapped_column(Text)
    cultural_context: Mapped[str | None] = mapped_column(Text)
    current_era: Mapped[str | None] = mapped_column(String(255))
    history_context: Mapped[str | None] = mapped_column(Text)
    social_structure: Mapped[str | None] = mapped_column(Text)
    timeline_notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series", back_populates="world")
