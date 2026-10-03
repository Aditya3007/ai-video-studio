"""Final MP4 export and artifact lifecycle service."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Asset, VideoAssembly
from app.models.enums import AssemblyStatus, AssetRole, AssetStatus, AssetType
from app.services.video_assembly_service import VideoAssemblyService
from app.services.video_renderer import FFmpegVideoRenderer, RenderResult, VideoRenderError
from app.storage import StorageBackend, StorageError


class FinalExportError(Exception):
    """Raised when final MP4 export/persistence fails."""


class FinalExportService:
    """Exports a transient render to a persistent final MP4 Asset."""

    CONTENT_TYPE = "video/mp4"
    ASSET_TYPE = AssetType.VIDEO.value
    ASSET_ROLE = AssetRole.GENERATED.value
    ASSET_STATUS = AssetStatus.AVAILABLE.value

    def __init__(
        self,
        db: Session,
        storage: StorageBackend,
        storage_backend_name: str,
        renderer: FFmpegVideoRenderer | None = None,
    ) -> None:
        self._db = db
        self._storage = storage
        self._storage_backend_name = storage_backend_name
        self._renderer = renderer or FFmpegVideoRenderer(db, storage)

    def export(self, series_id: str, assembly_id: str) -> VideoAssembly:
        """Render and persist the final MP4 for an assembly."""
        assembly_service = VideoAssemblyService(self._db)
        assembly = assembly_service.get(series_id, assembly_id)

        if assembly.status == AssemblyStatus.RENDERING.value:
            raise FinalExportError("Assembly is already rendering.")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            result = self._renderer.render(series_id, assembly_id, output_path)
            asset = self._persist_output(assembly, output_path, result)
        except StorageError as exc:
            assembly.status = AssemblyStatus.FAILED.value
            self._db.flush()
            raise FinalExportError(f"Storage persistence failed: {exc}") from exc
        except VideoRenderError:
            assembly.status = AssemblyStatus.FAILED.value
            self._db.flush()
            raise
        finally:
            if output_path.exists():
                output_path.unlink(missing_ok=True)

        assembly.final_asset_id = asset.id
        assembly.status = AssemblyStatus.RENDERED.value
        assembly.rendered_at = datetime.now(UTC)
        self._db.flush()
        self._db.refresh(assembly)
        return assembly

    def _persist_output(
        self,
        assembly: VideoAssembly,
        output_path: Path,
        result: RenderResult,
    ) -> Asset:
        """Store the rendered MP4 and create/update the final Asset row."""
        storage_key = f"exports/{assembly.series_id}/{assembly.id}/final.mp4"

        with output_path.open("rb") as stream:
            self._storage.put(
                storage_key,
                stream,
                content_type=self.CONTENT_TYPE,
                metadata={
                    "series_id": str(assembly.series_id),
                    "episode_id": str(assembly.episode_id),
                    "assembly_id": str(assembly.id),
                },
            )

        asset = self._resolve_asset(assembly)
        asset.series_id = assembly.series_id
        asset.asset_type = self.ASSET_TYPE
        asset.role = self.ASSET_ROLE
        asset.status = self.ASSET_STATUS
        asset.storage_backend = self._storage_backend_name
        asset.storage_key = storage_key
        asset.name = f"Final export for assembly {assembly.id}"
        asset.asset_metadata = {
            "width": result.width,
            "height": result.height,
            "duration_seconds": result.duration_seconds,
            "has_audio_stream": result.has_audio_stream,
            "has_video_stream": result.has_video_stream,
            "container_format": result.container_format,
            "size_bytes": result.size_bytes,
            "assembly_id": str(assembly.id),
        }
        self._db.flush()
        self._db.refresh(asset)
        return asset

    def _resolve_asset(self, assembly: VideoAssembly) -> Asset:
        """Reuse the existing final export asset when re-rendering."""
        if assembly.final_asset_id:
            asset = self._db.get(Asset, assembly.final_asset_id)
            if asset:
                return asset
        asset = Asset()
        self._db.add(asset)
        return asset
