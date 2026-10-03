"""AI-assisted visual/narrative QA schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AIQAMode
from app.schemas.continuity import ContinuityFinding


class AIQAFinding(ContinuityFinding):
    """A continuity finding produced by an AI QA provider."""

    confidence: float | None = Field(None, ge=0.0, le=1.0)
    source: str = "ai"


class MediaReference(BaseModel):
    """Reference to a stored visual/media asset for AI QA."""

    asset_id: UUID
    asset_type: str
    storage_backend: str
    storage_key: str
    description: str | None = None


class AIQAContext(BaseModel):
    """Canonical and production context sent to an AI QA provider."""

    series: dict
    episode: dict | None = None
    scene: dict | None = None
    shot: dict | None = None
    canonical_characters: list[dict] = []
    canonical_locations: list[dict] = []
    canonical_objects: list[dict] = []
    asset_refs: list[MediaReference] = []


class AIQARequest(BaseModel):
    """Provider-neutral request for AI visual/narrative QA."""

    mode: AIQAMode
    scope_type: str
    scope_id: UUID
    series_id: UUID
    context: AIQAContext


class AIQAResult(BaseModel):
    """Provider-neutral result from AI visual/narrative QA."""

    model_config = ConfigDict(from_attributes=True)

    findings: list[AIQAFinding] = []
    provider: str
    model: str | None = None
    usage: dict | None = None
    metadata: dict | None = None


class AIQAResponse(BaseModel):
    """API response for an AI QA evaluation."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    scope_type: str
    scope_id: UUID
    mode: AIQAMode
    findings: list[AIQAFinding]
    provider: str
    model: str | None = None
