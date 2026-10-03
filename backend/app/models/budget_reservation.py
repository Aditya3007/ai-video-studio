"""Budget reservation records for safe concurrent generation planning."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid


class BudgetReservation(Base):
    """A temporary hold against an Episode's generation budget."""

    __tablename__ = "budget_reservations"
    __table_args__ = (UniqueConstraint("series_id", "correlation_id"),)

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
    generation_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RESERVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
