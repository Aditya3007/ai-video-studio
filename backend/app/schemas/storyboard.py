"""Storyboard/keyframe generation request schema."""

from uuid import UUID

from pydantic import BaseModel


class StoryboardGenerationRequest(BaseModel):
    """Optional overrides for storyboard/keyframe generation."""

    prompt_override: str | None = None
    reference_asset_ids: list[UUID] = []
