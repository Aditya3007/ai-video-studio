"""Scene → shot breakdown plan schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.shot import ShotResponse


class ShotPlan(BaseModel):
    """A planned Shot before it is persisted."""

    shot_number: int
    sequence_order: int
    description: str | None = None
    action: str | None = None


class ScenePlanResponse(BaseModel):
    """Response returned after scene shot planning is applied."""

    model_config = ConfigDict(from_attributes=True)

    episode_id: UUID
    scene_id: UUID
    shots_planned: int
    replaced_existing: bool
    shots: list[ShotResponse]
