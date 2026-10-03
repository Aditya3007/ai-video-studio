"""Series model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.audio_bible import AudioBible
    from app.models.character import Character
    from app.models.episode import Episode
    from app.models.location import Location
    from app.models.story import Story
    from app.models.story_object import StoryObject
    from app.models.visual_bible import VisualBible
    from app.models.world import World


class Series(Base):
    """Top-level ownership boundary for a story universe/project."""

    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    genre: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), default="en")
    target_audience: Mapped[str | None] = mapped_column(String(255))
    episode_duration_seconds: Mapped[int] = mapped_column(default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    world: Mapped["World | None"] = relationship(
        "World", back_populates="series", uselist=False, cascade="all, delete-orphan"
    )
    visual_bible: Mapped["VisualBible | None"] = relationship(
        "VisualBible", back_populates="series", uselist=False, cascade="all, delete-orphan"
    )
    audio_bible: Mapped["AudioBible | None"] = relationship(
        "AudioBible", back_populates="series", uselist=False, cascade="all, delete-orphan"
    )
    characters: Mapped[list["Character"]] = relationship(
        "Character", back_populates="series", cascade="all, delete-orphan"
    )
    locations: Mapped[list["Location"]] = relationship(
        "Location", back_populates="series", cascade="all, delete-orphan"
    )
    objects: Mapped[list["StoryObject"]] = relationship(
        "StoryObject", back_populates="series", cascade="all, delete-orphan"
    )
    stories: Mapped[list["Story"]] = relationship(
        "Story", back_populates="series", cascade="all, delete-orphan"
    )
    episodes: Mapped[list["Episode"]] = relationship(
        "Episode", back_populates="series", cascade="all, delete-orphan"
    )
