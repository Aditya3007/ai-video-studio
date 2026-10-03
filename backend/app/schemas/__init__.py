"""Pydantic schemas for API requests and responses."""

from app.schemas.ai_qa import (
    AIQAFinding,
    AIQAMode,
    AIQARequest,
    AIQAResponse,
    AIQAResult,
    MediaReference,
)
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.schemas.audio_bible import (
    AudioBibleCreate,
    AudioBibleResponse,
    AudioBibleUpdate,
)
from app.schemas.audio_cue import (
    AudioCueCreate,
    AudioCueResponse,
    AudioCueUpdate,
)
from app.schemas.caption import (
    CaptionCreate,
    CaptionResponse,
    CaptionStyle,
    CaptionUpdate,
)
from app.schemas.character import (
    CharacterCreate,
    CharacterResponse,
    CharacterUniverseResponse,
    CharacterUpdate,
    CharacterVersionCreate,
    CharacterVersionResponse,
    CharacterVersionUpdate,
)
from app.schemas.common import PaginatedResponse
from app.schemas.continuity import (
    ContinuityEvaluationResponse,
    ContinuityFinding,
    ContinuityShotEvaluationResponse,
)
from app.schemas.episode import EpisodeCreate, EpisodeResponse, EpisodeUpdate
from app.schemas.final_export import FinalExportResponse
from app.schemas.image_generation_job import (
    ImageGenerationJobCreate,
    ImageGenerationJobResponse,
)
from app.schemas.image_to_video import (
    ImageToVideoRequest,
    ImageToVideoResponse,
)
from app.schemas.location import (
    LocationCreate,
    LocationResponse,
    LocationUniverseResponse,
    LocationUpdate,
    LocationVersionCreate,
    LocationVersionResponse,
    LocationVersionUpdate,
)
from app.schemas.narration import (
    NarrationCreate,
    NarrationResponse,
    NarrationUpdate,
)
from app.schemas.qa_workflow import (
    QAWorkflowCounts,
    QAWorkflowRequest,
    QAWorkflowResponse,
)
from app.schemas.scene import SceneCreate, SceneResponse, SceneUpdate
from app.schemas.scene_plan import EpisodePlanResponse, ScenePlan
from app.schemas.series import SeriesCreate, SeriesResponse, SeriesUpdate
from app.schemas.shot import ShotCreate, ShotResponse, ShotUpdate
from app.schemas.shot_plan import ScenePlanResponse, ShotPlan
from app.schemas.shot_specification import (
    ShotSpecificationCreate,
    ShotSpecificationResponse,
    ShotSpecificationUpdate,
)
from app.schemas.story import (
    StoryCreate,
    StoryResponse,
    StoryUpdate,
    StoryVersionCreate,
    StoryVersionResponse,
)
from app.schemas.story_analysis import StoryAnalysisResponse
from app.schemas.story_object import StoryObjectCreate, StoryObjectResponse, StoryObjectUpdate
from app.schemas.storyboard import StoryboardGenerationRequest
from app.schemas.studio import (
    StudioEpisodeProductionResponse,
    StudioEpisodeSummary,
    StudioSceneProductionResponse,
    StudioSceneSummary,
    StudioSeriesOverviewResponse,
    StudioShotProductionResponse,
    StudioShotSummary,
    StudioVideoAssemblySummary,
)
from app.schemas.universe import TimelineResponse, UniverseContextResponse
from app.schemas.video_assembly import (
    AssemblyItemCreate,
    AssemblyItemResponse,
    AssemblyItemUpdate,
    VideoAssemblyCreate,
    VideoAssemblyResponse,
    VideoAssemblyUpdate,
)
from app.schemas.video_generation_job import (
    VideoGenerationJobCreate,
    VideoGenerationJobResponse,
)
from app.schemas.visual_bible import (
    VisualBibleCreate,
    VisualBibleResponse,
    VisualBibleUpdate,
)
from app.schemas.voice import (
    VoiceCreate,
    VoiceResponse,
    VoiceUpdate,
)
from app.schemas.world import WorldCreate, WorldResponse, WorldUpdate

__all__ = [
    "AssemblyItemCreate",
    "AssemblyItemResponse",
    "AssemblyItemUpdate",
    "AssetCreate",
    "AssetResponse",
    "AssetUpdate",
    "AIQAFinding",
    "AIQAMode",
    "AIQARequest",
    "AIQAResponse",
    "AIQAResult",
    "MediaReference",
    "AudioBibleCreate",
    "AudioBibleResponse",
    "AudioBibleUpdate",
    "AudioCueCreate",
    "AudioCueResponse",
    "AudioCueUpdate",
    "CaptionCreate",
    "CaptionResponse",
    "CaptionStyle",
    "CaptionUpdate",
    "CharacterCreate",
    "CharacterResponse",
    "CharacterUniverseResponse",
    "CharacterUpdate",
    "CharacterVersionCreate",
    "CharacterVersionResponse",
    "CharacterVersionUpdate",
    "ContinuityEvaluationResponse",
    "ContinuityFinding",
    "ContinuityShotEvaluationResponse",
    "EpisodeCreate",
    "EpisodeResponse",
    "EpisodeUpdate",
    "FinalExportResponse",
    "LocationCreate",
    "LocationResponse",
    "LocationUniverseResponse",
    "LocationUpdate",
    "LocationVersionCreate",
    "LocationVersionResponse",
    "LocationVersionUpdate",
    "EpisodePlanResponse",
    "ImageGenerationJobCreate",
    "ImageGenerationJobResponse",
    "ImageToVideoRequest",
    "ImageToVideoResponse",
    "NarrationCreate",
    "NarrationResponse",
    "NarrationUpdate",
    "VideoGenerationJobCreate",
    "VideoGenerationJobResponse",
    "VoiceCreate",
    "VoiceResponse",
    "VoiceUpdate",
    "PaginatedResponse",
    "QAWorkflowCounts",
    "QAWorkflowRequest",
    "QAWorkflowResponse",
    "StudioEpisodeProductionResponse",
    "StudioEpisodeSummary",
    "StudioSceneProductionResponse",
    "StudioSceneSummary",
    "StudioSeriesOverviewResponse",
    "StudioShotProductionResponse",
    "StudioShotSummary",
    "StudioVideoAssemblySummary",
    "SceneCreate",
    "ScenePlan",
    "SceneResponse",
    "SceneUpdate",
    "SeriesCreate",
    "SeriesResponse",
    "SeriesUpdate",
    "ScenePlanResponse",
    "ShotCreate",
    "ShotPlan",
    "ShotResponse",
    "ShotSpecificationCreate",
    "ShotSpecificationResponse",
    "ShotSpecificationUpdate",
    "ShotUpdate",
    "StoryAnalysisResponse",
    "StoryboardGenerationRequest",
    "StoryCreate",
    "StoryObjectCreate",
    "StoryObjectResponse",
    "StoryObjectUpdate",
    "StoryResponse",
    "StoryUpdate",
    "StoryVersionCreate",
    "StoryVersionResponse",
    "TimelineResponse",
    "UniverseContextResponse",
    "VideoAssemblyCreate",
    "VideoAssemblyResponse",
    "VideoAssemblyUpdate",
    "VisualBibleCreate",
    "VisualBibleResponse",
    "VisualBibleUpdate",
    "WorldCreate",
    "WorldResponse",
    "WorldUpdate",
]
