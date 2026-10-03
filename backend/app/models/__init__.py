"""Register all ORM models for Base.metadata."""

from app.models.asset import Asset
from app.models.audio_bible import AudioBible
from app.models.audio_cue import AudioCue
from app.models.audit_event import AuditEvent
from app.models.budget_reservation import BudgetReservation
from app.models.caption import Caption
from app.models.character import Character, CharacterVersion
from app.models.episode import Episode
from app.models.episode_budget import EpisodeBudget
from app.models.generation_cost import GenerationCost
from app.models.image_generation_job import ImageGenerationJob
from app.models.location import Location, LocationVersion
from app.models.narration import Narration
from app.models.publishing_job import PublishingJob
from app.models.qa_issue import QAIssue, QAResolutionAction
from app.models.scene import Scene
from app.models.series import Series
from app.models.shot import Shot
from app.models.shot_specification import ShotSpecification
from app.models.story import Story, StoryVersion
from app.models.story_analysis import StoryAnalysis
from app.models.story_object import StoryObject
from app.models.video_assembly import AssemblyItem, VideoAssembly
from app.models.video_generation_job import VideoGenerationJob
from app.models.visual_bible import VisualBible
from app.models.voice import Voice
from app.models.world import World

__all__ = [
    "Asset",
    "AudioBible",
    "AuditEvent",
    "AudioCue",
    "AssemblyItem",
    "BudgetReservation",
    "Caption",
    "Character",
    "CharacterVersion",
    "Episode",
    "EpisodeBudget",
    "GenerationCost",
    "ImageGenerationJob",
    "Location",
    "LocationVersion",
    "Narration",
    "PublishingJob",
    "QAIssue",
    "QAResolutionAction",
    "Scene",
    "Series",
    "Shot",
    "ShotSpecification",
    "Story",
    "StoryAnalysis",
    "StoryObject",
    "StoryVersion",
    "VideoAssembly",
    "VideoGenerationJob",
    "VisualBible",
    "Voice",
    "World",
]
