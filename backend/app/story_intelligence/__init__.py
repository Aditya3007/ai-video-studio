"""Story Intelligence domain: analysis contracts, deterministic plumbing, and future AI boundary."""

from app.story_intelligence.ai_analyzer import AIStoryAnalyzer
from app.story_intelligence.analyzer import DeterministicStoryAnalyzer
from app.story_intelligence.llm import (
    FakeLLMProvider,
    LLMProvider,
    LLMProviderError,
    LLMProviderFactory,
    LLMResponse,
)
from app.story_intelligence.resolver import ResolutionResult, StoryEntityResolver
from app.story_intelligence.schemas import (
    AnalysisStatus,
    BeatType,
    CharacterReference,
    DialogueLine,
    Event,
    LocationReference,
    NarrativeBeat,
    NarrativeStructure,
    ObjectReference,
    Screenplay,
    ScreenplayGenerator,
    SourceReference,
    StoryAnalysisResult,
    StoryAnalyzer,
    StoryMetadata,
)

__all__ = [
    "AIStoryAnalyzer",
    "AnalysisStatus",
    "BeatType",
    "CharacterReference",
    "DeterministicStoryAnalyzer",
    "DialogueLine",
    "Event",
    "FakeLLMProvider",
    "LLMProvider",
    "LLMProviderError",
    "LLMProviderFactory",
    "LLMResponse",
    "LocationReference",
    "NarrativeBeat",
    "NarrativeStructure",
    "ObjectReference",
    "ResolutionResult",
    "Screenplay",
    "ScreenplayGenerator",
    "SourceReference",
    "StoryAnalysisResult",
    "StoryAnalyzer",
    "StoryEntityResolver",
    "StoryMetadata",
]
