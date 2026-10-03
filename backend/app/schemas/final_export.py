"""Final MP4 export response schema."""

from pydantic import BaseModel

from app.schemas.asset import AssetResponse
from app.schemas.video_assembly import VideoAssemblyResponse


class FinalExportResponse(BaseModel):
    """Result of exporting a video assembly to a persistent MP4 Asset."""

    assembly: VideoAssemblyResponse
    asset: AssetResponse
