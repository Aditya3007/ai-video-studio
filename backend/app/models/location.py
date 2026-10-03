"""Location and location version models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.scene import Scene
    from app.models.series import Series


class Location(Base):
    """Canonical reusable location within a series."""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location_type: Mapped[str | None] = mapped_column(String(255))
    atmosphere: Mapped[str | None] = mapped_column(Text)
    visual_characteristics: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series", back_populates="locations")
    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="location")
    versions: Mapped[list["LocationVersion"]] = relationship(
        "LocationVersion", back_populates="location", cascade="all, delete-orphan"
    )


class LocationVersion(Base):
    """Version of a location's visual/environmental definition."""

    __tablename__ = "location_versions"
    __table_args__ = (UniqueConstraint("location_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    architecture: Mapped[str | None] = mapped_column(Text)
    lighting: Mapped[str | None] = mapped_column(Text)
    visual_description: Mapped[str | None] = mapped_column(Text)
    reference_asset_id: Mapped[str | None] = mapped_column(String(36))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    location: Mapped["Location"] = relationship("Location", back_populates="versions")
