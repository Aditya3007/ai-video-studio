"""Studio production workflow API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import QAWorkflowStatus
from app.schemas.asset import AssetResponse
from app.schemas.episode import EpisodeResponse
from app.schemas.scene import SceneResponse
from app.schemas.series import SeriesResponse
from app.schemas.shot import ShotResponse
from app.schemas.shot_specification import ShotSpecificationResponse
from app.schemas.story import StoryResponse


class StudioEpisodeSummary(BaseModel):
    """Compact episode summary for the series Studio overview."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    episode_number: int
    status: str
    scene_count: int
    shot_count: int
    assembly_status: str | None = None
    final_asset_id: UUID | None = None


class StudioShotSummary(BaseModel):
    """Compact shot summary for Studio production views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shot_number: int
    description: str | None = None
    duration_seconds: int | None = None
    action: str | None = None
    has_specification: bool
    asset_count: int = 0


class StudioSceneSummary(BaseModel):
    """Compact scene summary with nested shots."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scene_number: int
    title: str | None = None
    description: str | None = None
    location_id: UUID | None = None
    shot_count: int
    shots: list[StudioShotSummary] = []


class StudioVideoAssemblySummary(BaseModel):
    """Compact video assembly summary for the Studio."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    status: str | None = None
    duration_seconds: float | None = None
    final_asset_id: UUID | None = None
    rendered_at: datetime | None = None
    item_count: int = 0


class StudioSeriesOverviewResponse(BaseModel):
    """Series-level Studio production overview."""

    model_config = ConfigDict(from_attributes=True)

    series: SeriesResponse
    counts: dict[str, int]
    episodes: list[StudioEpisodeSummary] = []


class StudioEpisodeProductionResponse(BaseModel):
    """Episode-level Studio production state."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    episode: EpisodeResponse
    story: StoryResponse | None = None
    scenes: list[StudioSceneSummary] = []
    assembly: StudioVideoAssemblySummary
    qa_status: QAWorkflowStatus | None = None


class StudioSceneProductionResponse(BaseModel):
    """Scene-level Studio production state."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    episode_id: UUID
    scene: SceneResponse
    shots: list[StudioShotSummary] = []
    assembly_item_count: int = 0


class StudioShotProductionResponse(BaseModel):
    """Shot-level Studio production state."""

    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    episode_id: UUID
    scene_id: UUID
    shot: ShotResponse
    specification: ShotSpecificationResponse | None = None
    assets: list[AssetResponse] = []
    assembly_item_count: int = 0
    qa_status: QAWorkflowStatus | None = None
