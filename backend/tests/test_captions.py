"""Caption/subtitle domain, API and rendering tests."""

import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import (
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
    AssetRole,
    AssetStatus,
    AssetType,
    AudioCueStatus,
    AudioCueType,
    NarrationStatus,
    NarrationType,
)
from app.schemas.caption import CaptionCreate, CaptionStyle, CaptionUpdate
from app.schemas.video_assembly import VideoAssemblyCreate
from app.services.caption_service import CaptionError, CaptionNotFoundError, CaptionService
from app.services.video_assembly_service import VideoAssemblyService
from app.services.video_renderer import FFmpegVideoRenderer
from app.storage.base import StorageObject
from app.storage.filesystem import FilesystemStorage


def _enable_sqlite_fk(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_fk)
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_factory()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(db: Session) -> tuple[Any, ...]:
    series = Series(name="S")
    db.add(series)
    db.commit()
    db.refresh(series)
    episode = Episode(series_id=series.id, title="E", episode_number=1, source_type="TOPIC")
    db.add(episode)
    db.commit()
    db.refresh(episode)
    scene = Scene(episode_id=episode.id, scene_number=1, title="Scene")
    db.add(scene)
    db.commit()
    db.refresh(scene)
    shot = Shot(scene_id=scene.id, shot_number=1, description="Shot")
    db.add(shot)
    db.commit()
    db.refresh(shot)

    voice = Voice(series_id=series.id, name="V")
    db.add(voice)
    db.commit()
    db.refresh(voice)
    narration = Narration(
        series_id=series.id,
        episode_id=episode.id,
        voice_id=voice.id,
        source_text="Hello world",
        narration_type=NarrationType.NARRATION.value,
        status=NarrationStatus.GENERATED.value,
    )
    db.add(narration)
    db.commit()
    db.refresh(narration)

    video_asset = Asset(
        series_id=series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="fake",
        storage_key="renders/video.mp4",
        name="video",
    )
    audio_asset = Asset(
        series_id=series.id,
        asset_type=AssetType.AUDIO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="fake",
        storage_key="renders/audio.mp3",
        name="audio",
    )
    music_cue = AudioCue(
        series_id=series.id,
        episode_id=episode.id,
        audio_type=AudioCueType.MUSIC.value,
        status=AudioCueStatus.GENERATED.value,
        name="music",
        generated_asset_id=audio_asset.id,
    )
    db.add_all([video_asset, audio_asset, music_cue])
    db.commit()
    db.refresh(video_asset)
    db.refresh(audio_asset)
    db.refresh(music_cue)

    service = VideoAssemblyService(db)
    assembly = service.create(
        str(series.id),
        VideoAssemblyCreate(episode_id=episode.id, duration_seconds=10.0),
    )
    db.commit()
    db.refresh(assembly)
    return series, episode, scene, shot, video_asset, audio_asset, narration, music_cue, assembly


class TestCaptionStyle:
    def test_default_style(self) -> None:
        style = CaptionStyle()
        assert style.alignment == 2
        assert style.font_size == 60

    def test_invalid_color_rejected(self) -> None:
        with pytest.raises(ValueError):
            CaptionStyle(primary_color="white")

    def test_invalid_font_size_rejected(self) -> None:
        with pytest.raises(ValueError):
            CaptionStyle(font_size=0)


class TestCaptionService:
    def test_create_and_get(self, db: Session) -> None:
        series, episode, scene, shot, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        caption = service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                scene_id=scene.id,
                shot_id=shot.id,
                text="Hello world",
                start_time_seconds=0.0,
                end_time_seconds=3.0,
                sequence_order=1,
            ),
        )
        assert caption.text == "Hello world"
        assert caption.start_time_seconds == 0.0
        assert caption.end_time_seconds == 3.0

    def test_empty_text_rejected(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        with pytest.raises(CaptionError):
            service.create(
                str(series.id),
                CaptionCreate(
                    assembly_id=assembly.id,
                    episode_id=episode.id,
                    text="   ",
                    start_time_seconds=0.0,
                    end_time_seconds=3.0,
                ),
            )

    def test_end_before_start_rejected(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        with pytest.raises(ValueError):
            service.create(
                str(series.id),
                CaptionCreate(
                    assembly_id=assembly.id,
                    episode_id=episode.id,
                    text="Oops",
                    start_time_seconds=3.0,
                    end_time_seconds=1.0,
                ),
            )

    def test_exceeds_duration_rejected(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        with pytest.raises(CaptionError):
            service.create(
                str(series.id),
                CaptionCreate(
                    assembly_id=assembly.id,
                    episode_id=episode.id,
                    text="Too long",
                    start_time_seconds=0.0,
                    end_time_seconds=15.0,
                ),
            )

    def test_unicode_accepted(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        caption = service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                text="Héllo 世界 🌍",
                start_time_seconds=1.0,
                end_time_seconds=3.0,
            ),
        )
        assert "世界" in caption.text

    def test_deterministic_ordering(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                text="Second",
                start_time_seconds=2.0,
                end_time_seconds=3.0,
                sequence_order=2,
            ),
        )
        service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                text="First",
                start_time_seconds=1.0,
                end_time_seconds=2.0,
                sequence_order=1,
            ),
        )
        captions = service.list_for_assembly(str(series.id), assembly.id)
        assert [c.text for c in captions] == ["First", "Second"]

    def test_cross_series_narration_rejected(self, db: Session) -> None:
        series, episode, _, _, _, _, narration, _, assembly = _seed(db)
        other_series = Series(name="Other")
        db.add(other_series)
        db.commit()
        db.refresh(other_series)
        other_episode = Episode(
            series_id=other_series.id, title="E2", episode_number=1, source_type="TOPIC"
        )
        db.add(other_episode)
        db.commit()
        db.refresh(other_episode)
        other_narration = Narration(
            series_id=other_series.id,
            episode_id=other_episode.id,
            voice_id=narration.voice_id,
            source_text="Other",
            narration_type=NarrationType.NARRATION.value,
            status=NarrationStatus.GENERATED.value,
        )
        db.add(other_narration)
        db.commit()
        db.refresh(other_narration)

        service = CaptionService(db)
        with pytest.raises(CaptionError):
            service.create(
                str(series.id),
                CaptionCreate(
                    assembly_id=assembly.id,
                    episode_id=episode.id,
                    narration_id=other_narration.id,
                    text="Bad",
                    start_time_seconds=0.0,
                    end_time_seconds=1.0,
                ),
            )

    def test_update_and_delete(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        caption = service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                text="Old",
                start_time_seconds=0.0,
                end_time_seconds=1.0,
            ),
        )
        updated = service.update(str(series.id), caption.id, CaptionUpdate(text="New"))
        assert updated.text == "New"
        service.remove(str(series.id), caption.id)
        with pytest.raises(CaptionNotFoundError):
            service.get(str(series.id), caption.id)

    def test_too_many_lines_rejected(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        style = CaptionStyle(max_lines=1, max_chars_per_line=10)
        with pytest.raises(CaptionError):
            service.create(
                str(series.id),
                CaptionCreate(
                    assembly_id=assembly.id,
                    episode_id=episode.id,
                    text="This caption is far too long to fit on one line",
                    start_time_seconds=0.0,
                    end_time_seconds=1.0,
                    style=style,
                ),
            )


class TestCaptionRendering:
    def test_ass_generation_and_escaping(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _, assembly = _seed(db)
        service = CaptionService(db)
        service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                text="Line one\nLine two {bold} and 'quotes'",
                start_time_seconds=0.0,
                end_time_seconds=3.0,
                style=CaptionStyle(max_chars_per_line=20, max_lines=2),
            ),
        )
        renderer = FFmpegVideoRenderer(
            db, FilesystemStorage("storage"), command_runner=RecordingRunner()
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            captions = service.list_for_assembly(str(series.id), assembly.id)
            ass_path = renderer._build_ass_file(captions, Path(tmpdir), 1080, 1920)
            assert ass_path is not None
            content = ass_path.read_text(encoding="utf-8")
            assert "[Script Info]" in content
            assert "Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,," in content
            assert "\\{" in content and "\\}" in content
            assert "\\N" in content

    def test_renderer_includes_ass_filter(self, db: Session) -> None:
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
        ) = _seed(db)
        from app.models import AssemblyItem
        from app.models.enums import AssemblyItemType, AssemblyTrack

        db.add(
            AssemblyItem(
                assembly_id=assembly.id,
                series_id=series.id,
                episode_id=episode.id,
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO.value,
                track=AssemblyTrack.VIDEO.value,
                sequence_order=1,
                start_time_seconds=0.0,
                duration_seconds=2.0,
                asset_id=video_asset.id,
            )
        )
        db.commit()
        service = CaptionService(db)
        service.create(
            str(series.id),
            CaptionCreate(
                assembly_id=assembly.id,
                episode_id=episode.id,
                text="Hello",
                start_time_seconds=0.0,
                end_time_seconds=1.0,
            ),
        )

        class Storage:
            def exists(self, key: str) -> bool:
                return True

            def get(self, key: str):
                return BytesIO(b"video")

            def put(self, key, data, content_type=None):
                pass

            def delete(self, key):
                pass

            def get_metadata(self, key):
                return StorageObject(key=key, size=5, content_type="application/octet-stream")

        runner = RecordingRunner()
        renderer = FFmpegVideoRenderer(db, Storage(), command_runner=runner)
        try:
            renderer.render(str(series.id), assembly.id, "/tmp/out.mp4")
        except Exception:
            pass
        filter_complex = runner.last_args[runner.last_args.index("-filter_complex") + 1]
        assert "ass=" in filter_complex


class RecordingRunner:
    """Records FFmpeg argument lists for testing."""

    def __init__(self):
        self.last_args: list[str] = []

    def run(self, args: list[str]) -> tuple[int, str, str]:
        self.last_args = args
        return 0, "", ""
