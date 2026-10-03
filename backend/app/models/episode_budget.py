"""Episode-level generation budget model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid


class EpisodeBudget(Base):
    """Configured generation budget and usage limits for an Episode."""

    __tablename__ = "episode_budgets"
    __table_args__ = (UniqueConstraint("series_id", "episode_id"),)

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
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    usage_limits: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
