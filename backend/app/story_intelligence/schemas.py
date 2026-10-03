"""Provider-neutral structured story analysis schemas."""

from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnalysisStatus = Literal["PENDING", "ANALYZING", "COMPLETED", "FAILED", "REVIEW_REQUIRED"]
BeatType = Literal[
    "SETUP",
    "INCITING_INCIDENT",
    "CONFLICT",
    "ESCALATION",
    "MIDPOINT",
    "TURNING_POINT",
    "CLIMAX",
    "RESOLUTION",
    "OTHER",
]
EntityResolutionStatus = Literal["MATCHED", "AMBIGUOUS", "UNRESOLVED"]


class SourceReference(BaseModel):
    """Traceability back to the original source material."""

    source_version_id: UUID
    chapter: str | None = None
    paragraph: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    excerpt: str | None = None
    extra: dict | None = None


class StoryMetadata(BaseModel):
    """High-level story metadata."""

    title: str | None = None
    logline: str | None = None
    premise: str | None = None
    theme: str | None = None
    genre: str | None = None
    tone: str | None = None
    target_audience: str | None = None
    language: str | None = None
    extra: dict | None = None


class CharacterReference(BaseModel):
    """A character as it appears in the analyzed story."""

    name: str = Field(..., min_length=1)
    aliases: list[str] = []
    role: str | None = None
    description: str | None = None
    personality: str | None = None
    motivations: list[str] = []
    goals: list[str] = []
    conflicts: list[str] = []
    relationships: list[dict] = []
    character_arc: str | None = None
    appearance_notes: str | None = None
    dialogue_style: str | None = None
    canonical_character_id: UUID | None = None
    status: EntityResolutionStatus = "UNRESOLVED"
    source_refs: list[SourceReference] = []
    extra: dict | None = None


class LocationReference(BaseModel):
    """A location as it appears in the analyzed story."""

    name: str = Field(..., min_length=1)
    description: str | None = None
    significance: str | None = None
    atmosphere: str | None = None
    time_context: str | None = None
    canonical_location_id: UUID | None = None
    status: EntityResolutionStatus = "UNRESOLVED"
    source_refs: list[SourceReference] = []
    extra: dict | None = None


class ObjectReference(BaseModel):
    """An important object as it appears in the analyzed story."""

    name: str = Field(..., min_length=1)
    description: str | None = None
    significance: str | None = None
    ownership_context: str | None = None
    canonical_object_id: UUID | None = None
    status: EntityResolutionStatus = "UNRESOLVED"
    source_refs: list[SourceReference] = []
    extra: dict | None = None


class Event(BaseModel):
    """A narrative event."""

    id: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=0)
    summary: str = Field(..., min_length=1)
    description: str | None = None
    involved_characters: list[str] = []
    location: str | None = None
    cause: str | None = None
    consequence: str | None = None
    emotional_significance: str | None = None
    time_context: str | None = None
    source_refs: list[SourceReference] = []
    extra: dict | None = None


class DialogueLine(BaseModel):
    """A line of dialogue preserved from the source."""

    speaker: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=0)
    context: str | None = None
    associated_event_id: str | None = None
    source_refs: list[SourceReference] = []
    extra: dict | None = None


class NarrativeBeat(BaseModel):
    """An important narrative beat."""

    id: str = Field(..., min_length=1)
    type: BeatType
    summary: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=0)
    involved_characters: list[str] = []
    event_ids: list[str] = []
    emotional_state: str | None = None
    importance: str | None = None
    source_refs: list[SourceReference] = []
    extra: dict | None = None


class NarrativeStructure(BaseModel):
    """Structural overview of the narrative."""

    acts: list[dict] = []
    beginning: str | None = None
    inciting_incident: str | None = None
    rising_action: list[str] = []
    midpoint: str | None = None
    climax: str | None = None
    resolution: str | None = None
    plot_beats: list[NarrativeBeat] = []
    extra: dict | None = None


class StoryAnalysisResult(BaseModel):
    """Top-level provider-neutral story analysis result."""

    model_config = ConfigDict(extra="allow")

    story_id: UUID
    story_version_id: UUID
    status: AnalysisStatus
    metadata: StoryMetadata = StoryMetadata()
    narrative: NarrativeStructure = NarrativeStructure()
    characters: list[CharacterReference] = []
    locations: list[LocationReference] = []
    objects: list[ObjectReference] = []
    events: list[Event] = []
    dialogue: list[DialogueLine] = []
    beats: list[NarrativeBeat] = []
    source_refs: list[SourceReference] = []
    warnings: list[str] = []
    unresolved_entities: list[dict] = []
    extra: dict | None = None

    @model_validator(mode="after")
    def _unique_identifiers(self) -> "StoryAnalysisResult":
        """Ensure event and beat identifiers are unique within a result."""
        event_ids = [event.id for event in self.events]
        beat_ids = [beat.id for beat in self.beats]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("Event ids must be unique within the analysis result.")
        if len(set(beat_ids)) != len(beat_ids):
            raise ValueError("Beat ids must be unique within the analysis result.")
        return self


class ResolutionResult(BaseModel):
    """Result of resolving a story entity to a canonical universe entity."""

    canonical_id: UUID | None = None
    status: EntityResolutionStatus = "UNRESOLVED"
    confidence: float = Field(..., ge=0.0, le=1.0)
    alternatives: list[UUID] = []
    reason: str | None = None


class Screenplay(BaseModel):
    """Boundary output for future screenplay generation."""

    title: str | None = None
    logline: str | None = None
    scenes: list[dict] = []
    extra: dict | None = None


class StoryAnalyzer(Protocol):
    """Provider-neutral analyzer contract."""

    def analyze(
        self,
        story: Any,
        story_version: Any,
        universe_context: Any,
    ) -> StoryAnalysisResult:
        """Analyze a StoryVersion and return a structured result."""
        ...


class ScreenplayGenerator(Protocol):
    """Provider-neutral screenplay generator contract."""

    def generate(
        self,
        analysis: StoryAnalysisResult,
        universe_context: Any,
    ) -> Screenplay:
        """Generate a screenplay from an analysis result."""
        ...
