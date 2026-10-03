"""Asset domain schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ApprovalStatus, AssetRole, AssetStatus, AssetType


class AssetBase(BaseModel):
    """Common Asset fields."""

    asset_type: AssetType
    role: AssetRole = AssetRole.CANONICAL
    status: AssetStatus = AssetStatus.PENDING
    approval_status: ApprovalStatus | None = ApprovalStatus.PENDING
    storage_backend: str = "default"
    storage_key: str | None = None
    name: str | None = None
    description: str | None = None
    asset_metadata: dict | None = None
    shot_id: UUID | None = None
    character_ids: list[UUID] = []
    location_ids: list[UUID] = []
    object_ids: list[UUID] = []


class AssetCreate(AssetBase):
    """Fields required to create an Asset."""


class AssetUpdate(BaseModel):
    """Fields allowed for partial Asset updates."""

    asset_type: AssetType | None = None
    role: AssetRole | None = None
    status: AssetStatus | None = None
    approval_status: ApprovalStatus | None = None
    storage_backend: str | None = None
    storage_key: str | None = None
    name: str | None = None
    description: str | None = None
    asset_metadata: dict | None = None
    shot_id: UUID | None = None
    character_ids: list[UUID] | None = None
    location_ids: list[UUID] | None = None
    object_ids: list[UUID] | None = None


class AssetResponse(AssetBase):
    """Asset response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    created_at: datetime
    updated_at: datetime
