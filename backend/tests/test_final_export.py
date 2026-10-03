"""P8-T04 final MP4 export and artifact lifecycle tests."""

import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import Episode, Series
from app.models.enums import AssemblyStatus, AssetStatus
from app.schemas.video_assembly import VideoAssemblyCreate
from app.services.final_export_service import FinalExportError, FinalExportService
from app.services.video_assembly_service import VideoAssemblyNotFoundError, VideoAssemblyService
from app.services.video_renderer import RenderResult, VideoRenderError
from app.storage.base import StorageBackend, StorageObject
from app.storage.exceptions import StorageError
from app.storage.filesystem import FilesystemStorage
from tests.test_video_renderer import _add_video_item
from tests.test_video_renderer import _seed as _video_renderer_seed


class InMemoryStorage:
    """In-memory storage backend for tests."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        body = data.read() if hasattr(data, "read") else data
        self._objects[key] = body if isinstance(body, bytes) else body.encode()
        return StorageObject(
            key=key,
            size=len(self._objects[key]),
            content_type=content_type or "application/octet-stream",
        )

    def get(self, key: str) -> BinaryIO:
        if key not in self._objects:
            raise FileNotFoundError(key)
        return io.BytesIO(self._objects[key])

    def exists(self, key: str) -> bool:
        return key in self._objects

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def get_metadata(self, key: str) -> StorageObject:
        if key not in self._objects:
            raise FileNotFoundError(key)
        return StorageObject(
            key=key, size=len(self._objects[key]), content_type="application/octet-stream"
        )


class BrokenStorage(StorageBackend):
    """Storage backend that always fails on put."""

    def put(self, key, data, content_type=None, metadata=None):
        raise StorageError("storage is down")

    def get(self, key):
        raise StorageError("storage is down")

    def exists(self, key):
        return False

    def delete(self, key):
        raise StorageError("storage is down")

    def get_metadata(self, key):
        raise StorageError("storage is down")


class FakeRenderer:
    """Renderer that writes a fake MP4 without calling FFmpeg."""

    def __init__(self, video_data: bytes = b"FAKE_MP4", raise_on_render: bool = False):
        self.video_data = video_data
        self.raise_on_render = raise_on_render

    def render(
        self,
        series_id: str,
        assembly_id: str,
        output_path: str | Path | None = None,
    ) -> RenderResult:
        if self.raise_on_render:
            raise VideoRenderError("render failed")
        output = Path(output_path) if output_path else Path("/tmp/fake.mp4")
        output.write_bytes(self.video_data)
        return RenderResult(
            output_path=str(output),
            duration_seconds=2.0,
            width=1080,
            height=1920,
            has_video_stream=True,
            has_audio_stream=False,
            container_format="mov,mp4,m4a,3gp,3g2,mj2",
            size_bytes=len(self.video_data),
            metadata={},
        )


def _memory_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return session


@pytest.fixture
def db():
    session = _memory_db()
    try:
        yield session
    finally:
        session.close()


def _seed(db: Session) -> tuple[Series, Episode, object]:
    series = Series(name="Export Series")
    db.add(series)
    db.commit()
    db.refresh(series)

    episode = Episode(
        series_id=series.id,
        title="Episode 1",
        episode_number=1,
        source_type="TOPIC",
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)

    assembly_service = VideoAssemblyService(db)
    assembly = assembly_service.create(
        str(series.id),
        VideoAssemblyCreate(episode_id=episode.id, duration_seconds=2.0),
    )
    db.commit()
    db.refresh(assembly)
    return series, episode, assembly


class TestFinalExportService:
    def test_successful_export_creates_asset_and_sets_rendered(self, db: Session) -> None:
        series, episode, assembly = _seed(db)
        storage = InMemoryStorage()
        renderer = FakeRenderer(video_data=b"FINAL_MP4")
        service = FinalExportService(db, storage, "memory", renderer=renderer)

        assembly = service.export(str(series.id), assembly.id)

        assert assembly.status == AssemblyStatus.RENDERED.value
        assert assembly.final_asset_id is not None
        assert assembly.rendered_at is not None
        asset = assembly.final_asset
        assert asset is not None
        assert asset.asset_type == "VIDEO"
        assert asset.status == AssetStatus.AVAILABLE.value
        assert asset.storage_backend == "memory"
        assert asset.storage_key.startswith("exports/")
        assert asset.asset_metadata["width"] == 1080
        assert storage.exists(asset.storage_key)
        assert storage.get(asset.storage_key).read() == b"FINAL_MP4"

    def test_re_render_reuses_existing_asset(self, db: Session) -> None:
        series, episode, assembly = _seed(db)
        storage = InMemoryStorage()
        renderer = FakeRenderer(video_data=b"FIRST")
        service = FinalExportService(db, storage, "memory", renderer=renderer)

        service.export(str(series.id), assembly.id)
        first_asset_id = assembly.final_asset_id
        first_rendered_at = assembly.rendered_at

        renderer.video_data = b"SECOND"
        assembly = service.export(str(series.id), assembly.id)

        assert assembly.final_asset_id == first_asset_id
        assert assembly.rendered_at != first_rendered_at
        assert storage.get(assembly.final_asset.storage_key).read() == b"SECOND"

    def test_render_failure_leaves_failed_status(self, db: Session) -> None:
        series, episode, assembly = _seed(db)
        storage = InMemoryStorage()
        renderer = FakeRenderer(raise_on_render=True)
        service = FinalExportService(db, storage, "memory", renderer=renderer)

        with pytest.raises(VideoRenderError):
            service.export(str(series.id), assembly.id)

        assert assembly.status == AssemblyStatus.FAILED.value
        assert assembly.final_asset_id is None

    def test_persistence_failure_does_not_mark_rendered(self, db: Session) -> None:
        series, episode, assembly = _seed(db)
        renderer = FakeRenderer(video_data=b"FINAL_MP4")
        service = FinalExportService(db, BrokenStorage(), "memory", renderer=renderer)

        with pytest.raises(FinalExportError):
            service.export(str(series.id), assembly.id)

        assert assembly.status != AssemblyStatus.RENDERED.value
        assert assembly.final_asset_id is None

    def test_export_not_found(self, db: Session) -> None:
        storage = InMemoryStorage()
        renderer = FakeRenderer()
        service = FinalExportService(db, storage, "memory", renderer=renderer)

        with pytest.raises(VideoAssemblyNotFoundError):
            service.export(str(uuid4()), str(uuid4()))

    def test_export_wrong_series(self, db: Session) -> None:
        series, episode, assembly = _seed(db)
        other = Series(name="Other")
        db.add(other)
        db.commit()

        storage = InMemoryStorage()
        renderer = FakeRenderer()
        service = FinalExportService(db, storage, "memory", renderer=renderer)

        with pytest.raises(VideoAssemblyNotFoundError):
            service.export(str(other.id), assembly.id)

    def test_already_rendering_is_rejected(self, db: Session) -> None:
        series, episode, assembly = _seed(db)
        assembly.status = AssemblyStatus.RENDERING.value
        db.commit()

        storage = InMemoryStorage()
        renderer = FakeRenderer()
        service = FinalExportService(db, storage, "memory", renderer=renderer)

        with pytest.raises(FinalExportError):
            service.export(str(series.id), assembly.id)


class TestFinalExportRealFFmpeg:
    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg not available")
    def test_real_end_to_end_export(self, db: Session) -> None:
        with tempfile.TemporaryDirectory(prefix="aivs_export_int_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            video_path = tmpdir_path / "input_video.mp4"
            storage_root = tmpdir_path / "storage"

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=blue:s=1080x1920:r=30:d=2.0",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000:d=2.0",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-t",
                    "2.0",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            fs_storage = FilesystemStorage(storage_root)
            (
                series,
                _episode,
                scene,
                shot,
                video_asset,
                _audio_asset,
                _narration,
                _music_cue,
                assembly,
            ) = _video_renderer_seed(db, fs_storage, b"", b"")
            fs_storage.put("renders/video.mp4", video_path.read_bytes(), content_type="video/mp4")
            _add_video_item(db, assembly, video_asset, scene, shot)

            service = FinalExportService(db, fs_storage, "filesystem")
            assembly = service.export(str(series.id), assembly.id)

            assert assembly.status == AssemblyStatus.RENDERED.value
            assert assembly.final_asset_id is not None
            assert fs_storage.exists(assembly.final_asset.storage_key)
            assert assembly.final_asset.asset_metadata["width"] == 1080
            assert assembly.final_asset.asset_metadata["height"] == 1920


class TestFinalExportAPI:
    def test_export_not_found(self, client) -> None:
        zero = str(UUID(int=0))
        response = client.post(f"/api/v1/series/{zero}/video-assemblies/{zero}/export")
        assert response.status_code == 404
