"""Video generation job lifecycle model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import VideoGenerationJobStatus

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.series import Series
    from app.models.shot import Shot


class VideoGenerationJob(Base):
    """Provider-neutral video generation job lifecycle."""

    __tablename__ = "video_generation_jobs"

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
    source_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VideoGenerationJobStatus.QUEUED.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    result_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series")
    shot: Mapped["Shot | None"] = relationship("Shot")
    source_asset: Mapped["Asset | None"] = relationship("Asset")
