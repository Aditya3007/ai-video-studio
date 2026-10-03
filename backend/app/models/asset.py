"""Asset domain model and canonical reference associations."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import ApprovalStatus, AssetRole, AssetStatus

if TYPE_CHECKING:
    from app.models.character import Character
    from app.models.location import Location
    from app.models.series import Series
    from app.models.shot import Shot
    from app.models.story_object import StoryObject


asset_characters = Table(
    "asset_characters",
    Base.metadata,
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "character_id",
        String(36),
        ForeignKey("characters.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

asset_locations = Table(
    "asset_locations",
    Base.metadata,
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        String(36),
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

asset_objects = Table(
    "asset_objects",
    Base.metadata,
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "object_id",
        String(36),
        ForeignKey("story_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Asset(Base):
    """Provider-neutral production asset."""

    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_series_id_type", "series_id", "asset_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=AssetRole.CANONICAL.value)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AssetStatus.PENDING.value
    )
    approval_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=ApprovalStatus.PENDING.value
    )
    storage_backend: Mapped[str | None] = mapped_column(String(50), default="default")
    storage_key: Mapped[str | None] = mapped_column(String(512))
    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    asset_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    shot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series")
    shot: Mapped["Shot | None"] = relationship("Shot")
    characters: Mapped[list["Character"]] = relationship("Character", secondary=asset_characters)
    locations: Mapped[list["Location"]] = relationship("Location", secondary=asset_locations)
    objects: Mapped[list["StoryObject"]] = relationship("StoryObject", secondary=asset_objects)

    @property
    def character_ids(self) -> list[str]:
        return [str(c.id) for c in self.characters]

    @property
    def location_ids(self) -> list[str]:
        return [str(loc.id) for loc in self.locations]

    @property
    def object_ids(self) -> list[str]:
        return [str(o.id) for o in self.objects]
