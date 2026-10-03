"""Continuity rules engine schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ContinuitySeverity


class ContinuityFinding(BaseModel):
    """A single deterministic continuity finding."""

    model_config = ConfigDict(from_attributes=True)

    severity: ContinuitySeverity
    rule_id: str
    category: str
    message: str
    entity_type: str
    entity_id: UUID
    related_entity_ids: list[UUID] = []
    expected: str | None = None
    actual: str | None = None
    metadata: dict | None = None


class ContinuityEvaluationResponse(BaseModel):
    """Response from evaluating continuity for an Episode."""

    series_id: UUID
    episode_id: UUID
    findings: list[ContinuityFinding]


class ContinuityShotEvaluationResponse(BaseModel):
    """Response from evaluating continuity for a Shot."""

    series_id: UUID
    shot_id: UUID
    findings: list[ContinuityFinding]
