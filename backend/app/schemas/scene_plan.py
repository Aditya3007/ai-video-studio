"""Episode → scene breakdown plan schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.scene import SceneResponse


class ScenePlan(BaseModel):
    """A planned Scene before it is persisted."""

    scene_number: int
    sequence_order: int
    title: str | None = None
    description: str | None = None
    location_id: UUID | None = None
    source_excerpt: str | None = None


class EpisodePlanResponse(BaseModel):
    """Response returned after episode scene planning is applied."""

    model_config = ConfigDict(from_attributes=True)

    episode_id: UUID
    scenes_planned: int
    replaced_existing: bool
    scenes: list[SceneResponse]
