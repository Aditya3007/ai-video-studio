"""Persistent QA issue and resolution action models for P9-T04."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid
from app.models.enums import (
    QAIssueSource,
    QAIssueStatus,
    ResolutionActionStatus,
    ResolutionActionType,
)

if TYPE_CHECKING:
    pass


class QAIssue(Base):
    """A structured, actionable QA finding that can drive controlled regeneration."""

    __tablename__ = "qa_issues"
    __table_args__ = (
        Index("ix_qa_issues_series_episode", "series_id", "episode_id"),
        Index("ix_qa_issues_status", "status"),
        Index("ix_qa_issues_series_shot", "series_id", "shot_id"),
    )

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
    )
    scene_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("scenes.id", ondelete="CASCADE"),
        nullable=True,
    )
    shot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="CASCADE"),
        nullable=True,
    )
    asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )

    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QAIssueSource.CONTINUITY.value
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QAIssueStatus.OPEN.value,
    )
    resolution_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    regenerated_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )

    qa_finding_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    resolution_actions: Mapped[list[QAResolutionAction]] = relationship(
        "QAResolutionAction",
        back_populates="issue",
        cascade="all, delete-orphan",
        order_by="QAResolutionAction.attempt_number.asc()",
    )


class QAResolutionAction(Base):
    """A single controlled resolution attempt for a QA issue."""

    __tablename__ = "qa_resolution_actions"
    __table_args__ = (
        Index("ix_qa_resolution_actions_issue", "issue_id"),
        Index("ix_qa_resolution_actions_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qa_issues.id", ondelete="CASCADE"),
        nullable=False,
    )
    series_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ResolutionActionType.RE_RUN_QA.value,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ResolutionActionStatus.PENDING.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_job_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    issue: Mapped[QAIssue] = relationship("QAIssue", back_populates="resolution_actions")
