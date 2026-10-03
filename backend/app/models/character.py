"""Character and character version models."""

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
    from app.models.series import Series


class Character(Base):
    """Canonical reusable character within a series."""

    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(String(255))
    voice_reference: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    series: Mapped["Series"] = relationship("Series", back_populates="characters")
    versions: Mapped[list["CharacterVersion"]] = relationship(
        "CharacterVersion", back_populates="character", cascade="all, delete-orphan"
    )


class CharacterVersion(Base):
    """Version of a character's visual/story definition."""

    __tablename__ = "character_versions"
    __table_args__ = (UniqueConstraint("character_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    appearance: Mapped[str | None] = mapped_column(Text)
    clothing: Mapped[str | None] = mapped_column(Text)
    personality_details: Mapped[str | None] = mapped_column(Text)
    visual_description: Mapped[str | None] = mapped_column(Text)
    reference_asset_id: Mapped[str | None] = mapped_column(String(36))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    character: Mapped["Character"] = relationship("Character", back_populates="versions")
