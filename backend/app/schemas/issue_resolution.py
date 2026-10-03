"""P9-T04 issue resolution API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    QAIssueSource,
    ResolutionActionType,
)


class QAIssueCreateRequest(BaseModel):
    """Request to create a structured issue from a QA finding."""

    episode_id: UUID
    scene_id: UUID | None = None
    shot_id: UUID | None = None
    asset_id: UUID | None = None
    category: str
    severity: str
    message: str
    rule_id: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    source: QAIssueSource = QAIssueSource.CONTINUITY
    qa_finding_metadata: dict | None = None
    max_attempts: int = Field(default=3, ge=1, le=10)


class QAIssueResponse(BaseModel):
    """API response for a QA issue."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    episode_id: UUID
    scene_id: UUID | None = None
    shot_id: UUID | None = None
    asset_id: UUID | None = None
    category: str
    severity: str
    rule_id: str | None = None
    message: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    source: str
    status: str
    resolution_type: str | None = None
    max_attempts: int
    attempt_count: int
    regenerated_asset_id: UUID | None = None
    qa_finding_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class QAIssueListResponse(BaseModel):
    """Paginated list of QA issues."""

    issues: list[QAIssueResponse]


class ResolutionActionRequest(BaseModel):
    """Request a resolution action for an issue."""

    action_type: ResolutionActionType
    action_metadata: dict | None = None


class ResolutionActionResponse(BaseModel):
    """API response for a resolution action."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    issue_id: UUID
    series_id: UUID
    action_type: str
    attempt_number: int
    status: str
    error_message: str | None = None
    generated_asset_id: UUID | None = None
    generated_job_id: str | None = None
    action_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class ManualResolutionRequest(BaseModel):
    """Request to manually resolve a QA issue."""

    resolution_note: str | None = None


class ExecuteActionResponse(BaseModel):
    """Response after executing a resolution action."""

    action: ResolutionActionResponse
    issue: QAIssueResponse
