"""QA workflow orchestration schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AIQAMode, QAWorkflowStatus
from app.schemas.ai_qa import AIQAFinding


class QAWorkflowRequest(BaseModel):
    """Request options for a QA workflow evaluation."""

    ai_modes: list[AIQAMode] = []


class QAWorkflowCounts(BaseModel):
    """Summary counts for a QA workflow result."""

    total: int
    error: int
    warning: int
    info: int
    deterministic: int
    ai: int


class QAWorkflowResponse(BaseModel):
    """Aggregated QA workflow result for an episode or shot."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    scope_type: str
    scope_id: UUID
    status: QAWorkflowStatus
    findings: list[AIQAFinding]
    counts: QAWorkflowCounts
    ai_failed: bool = False
    ai_error: str | None = None
    metadata: dict | None = None
