"""P8-T02 FFmpeg rendering pipeline tests."""

import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import (
    AssemblyItem,
    Asset,
    AudioCue,
    Episode,
    Narration,
    Scene,
    Series,
    Shot,
    Voice,
)
from app.models.enums import (
    ApprovalStatus,
    AssemblyItemType,
    AssemblyStatus,
    AssemblyTrack,
    AssetRole,
    AssetStatus,
    AssetType,
    AudioCueStatus,
    AudioCueType,
    NarrationStatus,
    NarrationType,
)
from app.schemas.video_assembly import (
    AssemblyItemCreate,
    VideoAssemblyCreate,
)
from app.services.video_assembly_service import VideoAssemblyService
from app.services.video_renderer import (
    FFmpegCommandRunner,
    FFmpegExecutionError,
    FFmpegNotAvailableError,
    FFmpegVideoRenderer,
    InvalidTimelineError,
    MediaNotFoundError,
    RenderOutputError,
    VideoRenderError,
)
from app.storage.base import StorageBackend, StorageObject
from app.storage.filesystem import FilesystemStorage


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


def _memory_db() -> tuple[Session, object]:
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
    return session, engine


@pytest.fixture
def db():
    session, engine = _memory_db()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


class RecordingRunner:
    """Records FFmpeg arguments and optionally returns a configured response."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.last_args: list[str] | None = None

    def run(self, args: list[str]) -> tuple[int, str, str]:
        self.last_args = args
        return self.returncode, self.stdout, self.stderr


def _seed(
    db: Session,
    storage: StorageBackend,
    video_data: bytes,
    audio_data: bytes,
) -> tuple[Series, Episode, Scene, Shot, Asset, Asset, Narration, AudioCue, object]:
    series = Series(name="Render Series")
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

    scene = Scene(
        episode_id=episode.id,
        scene_number=1,
        sequence_order=0,
        title="Scene 1",
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)

    shot = Shot(
        scene_id=scene.id,
        shot_number=1,
        sequence_order=0,
        description="Shot 1",
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)

    video_asset = Asset(
        series_id=series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        approval_status=ApprovalStatus.PENDING.value,
        storage_backend="fake",
        storage_key="renders/video.mp4",
        name="Generated video",
        shot_id=shot.id,
    )
    storage.put("renders/video.mp4", video_data, content_type="video/mp4")
    db.add(video_asset)

    audio_asset = Asset(
        series_id=series.id,
        asset_type=AssetType.AUDIO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        approval_status=ApprovalStatus.PENDING.value,
        storage_backend="fake",
        storage_key="renders/audio.mp3",
        name="Generated audio",
    )
    storage.put("renders/audio.mp3", audio_data, content_type="audio/mpeg")
    db.add(audio_asset)
    db.commit()
    db.refresh(video_asset)
    db.refresh(audio_asset)

    voice = Voice(series_id=series.id, name="Narrator")
    db.add(voice)
    db.commit()
    db.refresh(voice)

    narration = Narration(
        series_id=series.id,
        episode_id=episode.id,
        scene_id=scene.id,
        shot_id=shot.id,
        source_text="Hello",
        voice_id=voice.id,
        narration_type=NarrationType.NARRATION.value,
        status=NarrationStatus.GENERATED.value,
        generated_asset_id=audio_asset.id,
    )
    db.add(narration)
    db.commit()
    db.refresh(narration)

    music_cue = AudioCue(
        series_id=series.id,
        episode_id=episode.id,
        name="Background music",
        audio_type=AudioCueType.MUSIC.value,
        status=AudioCueStatus.GENERATED.value,
        prompt="Upbeat",
        generated_asset_id=audio_asset.id,
        volume=0.5,
        fade_in=True,
        fade_out=True,
        loop=True,
    )
    db.add(music_cue)
    db.commit()
    db.refresh(music_cue)

    assembly = VideoAssemblyCreate(episode_id=episode.id)
    assembly_service = VideoAssemblyService(db)
    created = assembly_service.create(str(series.id), assembly)
    db.commit()

    return series, episode, scene, shot, video_asset, audio_asset, narration, music_cue, created


def _add_video_item(db: Session, assembly, video_asset, scene, shot, sequence: int = 0) -> None:
    service = VideoAssemblyService(db)
    service.add_item(
        str(assembly.series_id),
        assembly.id,
        AssemblyItemCreate(
            scene_id=scene.id,
            shot_id=shot.id,
            item_type=AssemblyItemType.VIDEO,
            track=AssemblyTrack.VIDEO,
            sequence_order=sequence,
            start_time_seconds=0.0,
            duration_seconds=2.0,
            asset_id=video_asset.id,
        ),
    )
    db.commit()


def _add_music_item(db: Session, assembly, audio_asset, music_cue, sequence: int = 1) -> None:
    service = VideoAssemblyService(db)
    service.add_item(
        str(assembly.series_id),
        assembly.id,
        AssemblyItemCreate(
            item_type=AssemblyItemType.MUSIC,
            track=AssemblyTrack.MUSIC,
            sequence_order=sequence,
            start_time_seconds=0.0,
            duration_seconds=2.0,
            asset_id=audio_asset.id,
            audio_cue_id=music_cue.id,
        ),
    )
    db.commit()


class TestFFmpegVideoRenderer:
    def test_assembly_not_found(self, db: Session) -> None:
        storage = InMemoryStorage()
        renderer = FFmpegVideoRenderer(db, storage, command_runner=RecordingRunner())
        with pytest.raises(VideoRenderError):
            renderer.render("does-not-exist", "does-not-exist", "/tmp/out.mp4")

    def test_empty_assembly_rejected(self, db: Session) -> None:
        storage = InMemoryStorage()
        series = Series(name="S")
        db.add(series)
        db.commit()
        db.refresh(series)
        episode = Episode(series_id=series.id, title="E", episode_number=1, source_type="TOPIC")
        db.add(episode)
        db.commit()
        db.refresh(episode)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))
        db.commit()

        renderer = FFmpegVideoRenderer(db, storage, command_runner=RecordingRunner())
        with pytest.raises(InvalidTimelineError):
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")

    def test_overlapping_video_rejected(self, db: Session) -> None:
        storage = InMemoryStorage()
        series, episode, scene, shot, video_asset, _, _, _, assembly = _seed(
            db, storage, b"video", b"audio"
        )
        service = VideoAssemblyService(db)
        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO,
                track=AssemblyTrack.VIDEO,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=2.0,
                asset_id=video_asset.id,
            ),
        )
        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO,
                track=AssemblyTrack.VIDEO,
                sequence_order=1,
                start_time_seconds=1.0,
                duration_seconds=2.0,
                asset_id=video_asset.id,
            ),
        )
        db.commit()

        renderer = FFmpegVideoRenderer(db, storage, command_runner=RecordingRunner())
        with pytest.raises(InvalidTimelineError):
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")

    def test_missing_media_rejected(self, db: Session) -> None:
        storage = InMemoryStorage()
        series, episode, scene, shot, video_asset, _, _, _, assembly = _seed(
            db, storage, b"video", b"audio"
        )
        _add_video_item(db, assembly, video_asset, scene, shot)
        video_asset.storage_key = "renders/missing.mp4"
        db.commit()

        renderer = FFmpegVideoRenderer(db, storage, command_runner=RecordingRunner())
        with pytest.raises(MediaNotFoundError):
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")

    def test_command_construction(self, db: Session) -> None:
        storage = InMemoryStorage()
        series, episode, scene, shot, video_asset, audio_asset, _, music_cue, assembly = _seed(
            db, storage, b"video", b"audio"
        )
        _add_video_item(db, assembly, video_asset, scene, shot)
        _add_music_item(db, assembly, audio_asset, music_cue)

        runner = RecordingRunner()
        renderer = FFmpegVideoRenderer(db, storage, command_runner=runner)
        with pytest.raises(RenderOutputError):
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")

        assert runner.last_args is not None
        assert "-filter_complex" in runner.last_args
        assert "libx264" in runner.last_args
        assert "1080" in "".join(runner.last_args) or "1080x1920" in "".join(runner.last_args)

    def test_ffmpeg_failure(self, db: Session) -> None:
        storage = InMemoryStorage()
        series, episode, scene, shot, video_asset, _, _, _, assembly = _seed(
            db, storage, b"video", b"audio"
        )
        _add_video_item(db, assembly, video_asset, scene, shot)

        runner = RecordingRunner(returncode=1, stderr="codec not found")
        renderer = FFmpegVideoRenderer(db, storage, command_runner=runner)
        with pytest.raises(FFmpegExecutionError):
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")

    def test_ffmpeg_not_available(self) -> None:
        with pytest.raises(FFmpegNotAvailableError):
            FFmpegCommandRunner("/nonexistent/ffmpeg")

    def test_series_isolation_for_asset(self, db: Session) -> None:
        storage = InMemoryStorage()
        series, episode, scene, shot, video_asset, _, _, _, assembly = _seed(
            db, storage, b"video", b"audio"
        )
        other_series = Series(name="Other")
        db.add(other_series)
        db.commit()
        db.refresh(other_series)

        other_asset = Asset(
            series_id=other_series.id,
            asset_type=AssetType.VIDEO.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            storage_backend="fake",
            storage_key="renders/other.mp4",
            name="Other video",
        )
        storage.put("renders/other.mp4", b"video2")
        db.add(other_asset)
        db.commit()
        db.refresh(other_asset)

        db.add(
            AssemblyItem(
                assembly_id=assembly.id,
                series_id=series.id,
                episode_id=episode.id,
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO.value,
                track=AssemblyTrack.VIDEO.value,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=2.0,
                asset_id=other_asset.id,
            )
        )
        db.commit()

        renderer = FFmpegVideoRenderer(db, storage, command_runner=RecordingRunner())
        with pytest.raises(MediaNotFoundError):
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg not available"
)
class TestFFmpegIntegration:
    def test_full_render_9_16(self, db: Session) -> None:
        with tempfile.TemporaryDirectory(prefix="aivs_render_int_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            video_path = tmpdir_path / "input_video.mp4"
            audio_path = tmpdir_path / "input_audio.mp3"
            output_path = tmpdir_path / "output.mp4"

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=red:s=640x480:r=30:d=2.0",
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
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=2.0",
                    "-c:a",
                    "libmp3lame",
                    "-t",
                    "2.0",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            fs_storage = FilesystemStorage(tmpdir_path / "storage")

            (
                series,
                episode,
                scene,
                shot,
                video_asset,
                audio_asset,
                narration,
                music_cue,
                assembly,
            ) = _seed(db, fs_storage, b"", b"")
            fs_storage.put("renders/video.mp4", video_path.read_bytes(), content_type="video/mp4")
            fs_storage.put("renders/audio.mp3", audio_path.read_bytes(), content_type="audio/mpeg")

            _add_video_item(db, assembly, video_asset, scene, shot)
            _add_music_item(db, assembly, audio_asset, music_cue)

            renderer = FFmpegVideoRenderer(db, fs_storage)
            result = renderer.render(str(series.id), assembly.id, output_path)

            assert result.width == 1080
            assert result.height == 1920
            assert result.has_video_stream
            assert result.has_audio_stream
            assert result.size_bytes > 0
            assert "mp4" in result.container_format

    def test_render_status_transitions(self, db: Session) -> None:
        with tempfile.TemporaryDirectory(prefix="aivs_render_int_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            video_path = tmpdir_path / "input_video.mp4"
            output_path = tmpdir_path / "output.mp4"

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=red:s=1080x1920:r=30:d=2.0",
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

            fs_storage = FilesystemStorage(tmpdir_path / "storage")

            series, episode, scene, shot, video_asset, _, _, _, assembly = _seed(
                db, fs_storage, b"", b""
            )
            fs_storage.put("renders/video.mp4", video_path.read_bytes(), content_type="video/mp4")
            _add_video_item(db, assembly, video_asset, scene, shot)

            assert assembly.status == AssemblyStatus.DRAFT.value
            renderer = FFmpegVideoRenderer(db, fs_storage)
            renderer.render(str(series.id), assembly.id, output_path)
            assert assembly.status == AssemblyStatus.READY.value
