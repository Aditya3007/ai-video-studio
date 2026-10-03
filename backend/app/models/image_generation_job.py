"""Image generation job orchestration model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import ApprovalStatus, ImageGenerationJobStatus

if TYPE_CHECKING:
    from app.models.series import Series
    from app.models.shot import Shot


class ImageGenerationJob(Base):
    """Provider-neutral image generation job lifecycle."""

    __tablename__ = "image_generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ImageGenerationJobStatus.QUEUED.value,
        index=True,
    )
    approval_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=ApprovalStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    result_asset_ids: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series")
    shot: Mapped["Shot | None"] = relationship("Shot")
