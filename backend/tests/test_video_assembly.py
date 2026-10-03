"""P8-T01 Video assembly and timeline model tests."""

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
    AssemblyItemUpdate,
    VideoAssemblyCreate,
    VideoAssemblyUpdate,
)
from app.services.video_assembly_service import (
    AssemblyItemError,
    AssemblyItemNotFoundError,
    VideoAssemblyNotFoundError,
    VideoAssemblyService,
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


def _seed(db: Session) -> tuple[Series, Episode, Scene, Shot, Asset, Asset, Narration, AudioCue]:
    series = Series(name="Assembly Series")
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
        storage_key="fake://video/1.mp4",
        name="Generated video",
        shot_id=shot.id,
    )
    db.add(video_asset)

    audio_asset = Asset(
        series_id=series.id,
        asset_type=AssetType.AUDIO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        approval_status=ApprovalStatus.PENDING.value,
        storage_backend="fake",
        storage_key="fake://audio/1.mp3",
        name="Generated audio",
    )
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
        source_text="Hello world",
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
        prompt="Upbeat theme",
        generated_asset_id=audio_asset.id,
    )
    db.add(music_cue)
    db.commit()
    db.refresh(music_cue)

    return series, episode, scene, shot, video_asset, audio_asset, narration, music_cue


class TestVideoAssemblyService:
    def test_create_and_get(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(
            str(series.id),
            VideoAssemblyCreate(
                episode_id=episode.id,
                output_config={"aspect_ratio": "9:16", "resolution": "1080x1920"},
            ),
        )
        db.commit()

        assert assembly.status == AssemblyStatus.DRAFT.value
        assert assembly.output_config == {"aspect_ratio": "9:16", "resolution": "1080x1920"}

        retrieved = service.get(str(series.id), assembly.id)
        assert retrieved.id == assembly.id

    def test_update_status_and_output(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))
        db.commit()

        updated = service.update(
            str(series.id),
            assembly.id,
            VideoAssemblyUpdate(
                status=AssemblyStatus.READY,
                duration_seconds=30.0,
            ),
        )
        assert updated.status == AssemblyStatus.READY.value
        assert updated.duration_seconds == 30.0

    def test_assembly_belongs_to_episode_unique(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))
        db.commit()

        with pytest.raises(Exception):  # IntegrityError on duplicate episode
            service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))
            db.commit()
        db.rollback()

    def test_video_item(self, db: Session) -> None:
        series, episode, scene, shot, video_asset, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        item = service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO,
                track=AssemblyTrack.VIDEO,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=4.0,
                asset_id=video_asset.id,
            ),
        )
        db.commit()

        assert item.item_type == AssemblyItemType.VIDEO.value
        assert item.track == AssemblyTrack.VIDEO.value
        assert item.start_time_seconds == 0.0
        assert item.duration_seconds == 4.0
        assert item.shot_id == shot.id

    def test_narration_item(self, db: Session) -> None:
        series, episode, scene, shot, _, audio_asset, narration, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        item = service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.NARRATION,
                track=AssemblyTrack.DIALOGUE,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=3.0,
                asset_id=audio_asset.id,
                narration_id=narration.id,
            ),
        )
        db.commit()

        assert item.item_type == AssemblyItemType.NARRATION.value
        assert item.track == AssemblyTrack.DIALOGUE.value
        assert item.narration_id == narration.id

    def test_music_item(self, db: Session) -> None:
        series, episode, _, _, _, audio_asset, _, music_cue = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        item = service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                item_type=AssemblyItemType.MUSIC,
                track=AssemblyTrack.MUSIC,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=30.0,
                asset_id=audio_asset.id,
                audio_cue_id=music_cue.id,
            ),
        )
        db.commit()

        assert item.item_type == AssemblyItemType.MUSIC.value
        assert item.track == AssemblyTrack.MUSIC.value
        assert item.audio_cue_id == music_cue.id

    def test_sound_effect_item(self, db: Session) -> None:
        series, episode, _, _, _, audio_asset, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        sfx_cue = AudioCue(
            series_id=series.id,
            episode_id=episode.id,
            name="Explosion",
            audio_type=AudioCueType.SOUND_EFFECT.value,
            status=AudioCueStatus.GENERATED.value,
            generated_asset_id=audio_asset.id,
        )
        db.add(sfx_cue)
        db.commit()
        db.refresh(sfx_cue)

        item = service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                item_type=AssemblyItemType.SOUND_EFFECT,
                track=AssemblyTrack.SFX,
                sequence_order=0,
                start_time_seconds=2.0,
                duration_seconds=0.5,
                asset_id=audio_asset.id,
                audio_cue_id=sfx_cue.id,
            ),
        )
        db.commit()

        assert item.item_type == AssemblyItemType.SOUND_EFFECT.value
        assert item.track == AssemblyTrack.SFX.value
        assert item.start_time_seconds == 2.0

    def test_list_items_deterministic_order(self, db: Session) -> None:
        series, episode, scene, shot, video_asset, audio_asset, narration, music_cue = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO,
                track=AssemblyTrack.VIDEO,
                sequence_order=2,
                start_time_seconds=0.0,
                duration_seconds=4.0,
                asset_id=video_asset.id,
            ),
        )
        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                item_type=AssemblyItemType.MUSIC,
                track=AssemblyTrack.MUSIC,
                sequence_order=1,
                start_time_seconds=0.0,
                duration_seconds=30.0,
                asset_id=audio_asset.id,
                audio_cue_id=music_cue.id,
            ),
        )
        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.NARRATION,
                track=AssemblyTrack.DIALOGUE,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=3.0,
                asset_id=audio_asset.id,
                narration_id=narration.id,
            ),
        )
        db.commit()

        items = service.list_items(str(series.id), assembly.id)
        tracks = [item.track for item in items]
        assert tracks == [
            AssemblyTrack.DIALOGUE.value,
            AssemblyTrack.MUSIC.value,
            AssemblyTrack.VIDEO.value,
        ]

    def test_invalid_video_asset_type(self, db: Session) -> None:
        series, episode, scene, shot, _, audio_asset, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        with pytest.raises(AssemblyItemError):
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
                    duration_seconds=4.0,
                    asset_id=audio_asset.id,
                ),
            )

    def test_invalid_audio_asset_for_narration(self, db: Session) -> None:
        series, episode, _, _, video_asset, _, narration, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        with pytest.raises(AssemblyItemError):
            service.add_item(
                str(series.id),
                assembly.id,
                AssemblyItemCreate(
                    item_type=AssemblyItemType.NARRATION,
                    track=AssemblyTrack.DIALOGUE,
                    sequence_order=0,
                    start_time_seconds=0.0,
                    duration_seconds=3.0,
                    asset_id=video_asset.id,
                    narration_id=narration.id,
                ),
            )

    def test_negative_start_time_rejected(self, db: Session) -> None:
        series, episode, _, _, video_asset, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        with pytest.raises(AssemblyItemError):
            service.add_item(
                str(series.id),
                assembly.id,
                AssemblyItemCreate(
                    item_type=AssemblyItemType.NARRATION,
                    track=AssemblyTrack.DIALOGUE,
                    sequence_order=0,
                    start_time_seconds=-1.0,
                    duration_seconds=3.0,
                    asset_id=video_asset.id,
                ),
            )

    def test_zero_duration_rejected(self, db: Session) -> None:
        series, episode, _, _, video_asset, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        with pytest.raises(AssemblyItemError):
            service.add_item(
                str(series.id),
                assembly.id,
                AssemblyItemCreate(
                    item_type=AssemblyItemType.MUSIC,
                    track=AssemblyTrack.MUSIC,
                    sequence_order=0,
                    start_time_seconds=0.0,
                    duration_seconds=0.0,
                    asset_id=video_asset.id,
                ),
            )

    def test_video_requires_shot_and_scene(self, db: Session) -> None:
        series, episode, _, _, video_asset, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        with pytest.raises(AssemblyItemError):
            service.add_item(
                str(series.id),
                assembly.id,
                AssemblyItemCreate(
                    item_type=AssemblyItemType.VIDEO,
                    track=AssemblyTrack.VIDEO,
                    sequence_order=0,
                    start_time_seconds=0.0,
                    duration_seconds=4.0,
                    asset_id=video_asset.id,
                ),
            )

    def test_narration_requires_narration_reference(self, db: Session) -> None:
        series, episode, _, _, _, audio_asset, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        with pytest.raises(AssemblyItemError):
            service.add_item(
                str(series.id),
                assembly.id,
                AssemblyItemCreate(
                    item_type=AssemblyItemType.NARRATION,
                    track=AssemblyTrack.DIALOGUE,
                    sequence_order=0,
                    start_time_seconds=0.0,
                    duration_seconds=3.0,
                    asset_id=audio_asset.id,
                ),
            )

    def test_cross_series_asset_rejected(self, db: Session) -> None:
        series, episode, _, _, _, _, _, _ = _seed(db)
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
            storage_key="fake://video/2.mp4",
            name="Other video",
        )
        db.add(other_asset)
        db.commit()
        db.refresh(other_asset)

        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))
        shot = db.get(Shot, assembly.episode_id)  # placeholder, not used
        # get a valid shot from series
        shot = db.query(Shot).filter(Shot.scene.has(episode_id=episode.id)).first()

        with pytest.raises(AssemblyItemError):
            service.add_item(
                str(series.id),
                assembly.id,
                AssemblyItemCreate(
                    scene_id=shot.scene_id,
                    shot_id=shot.id,
                    item_type=AssemblyItemType.VIDEO,
                    track=AssemblyTrack.VIDEO,
                    sequence_order=0,
                    start_time_seconds=0.0,
                    duration_seconds=4.0,
                    asset_id=other_asset.id,
                ),
            )

    def test_cross_series_assembly_get_rejected(self, db: Session) -> None:
        series_a, episode_a, _, _, _, _, _, _ = _seed(db)
        series_b = Series(name="B")
        db.add(series_b)
        db.commit()
        db.refresh(series_b)

        service = VideoAssemblyService(db)
        assembly = service.create(str(series_a.id), VideoAssemblyCreate(episode_id=episode_a.id))
        db.commit()

        with pytest.raises(VideoAssemblyNotFoundError):
            service.get(str(series_b.id), assembly.id)

    def test_update_and_remove_item(self, db: Session) -> None:
        series, episode, scene, shot, video_asset, _, _, _ = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        item = service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                scene_id=scene.id,
                shot_id=shot.id,
                item_type=AssemblyItemType.VIDEO,
                track=AssemblyTrack.VIDEO,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=4.0,
                asset_id=video_asset.id,
            ),
        )
        db.commit()

        updated = service.update_item(
            str(series.id),
            assembly.id,
            item.id,
            AssemblyItemUpdate(duration_seconds=5.0),
        )
        db.commit()
        assert updated.duration_seconds == 5.0

        service.remove_item(str(series.id), assembly.id, item.id)
        db.commit()

        with pytest.raises(AssemblyItemNotFoundError):
            service.get_item(str(series.id), assembly.id, item.id)

    def test_overlapping_audio_items_allowed(self, db: Session) -> None:
        series, episode, _, _, _, audio_asset, narration, music_cue = _seed(db)
        service = VideoAssemblyService(db)
        assembly = service.create(str(series.id), VideoAssemblyCreate(episode_id=episode.id))

        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                item_type=AssemblyItemType.MUSIC,
                track=AssemblyTrack.MUSIC,
                sequence_order=0,
                start_time_seconds=0.0,
                duration_seconds=30.0,
                asset_id=audio_asset.id,
                audio_cue_id=music_cue.id,
            ),
        )
        service.add_item(
            str(series.id),
            assembly.id,
            AssemblyItemCreate(
                item_type=AssemblyItemType.NARRATION,
                track=AssemblyTrack.DIALOGUE,
                sequence_order=1,
                start_time_seconds=0.0,
                duration_seconds=3.0,
                asset_id=audio_asset.id,
                narration_id=narration.id,
            ),
        )
        db.commit()

        items = service.list_items(str(series.id), assembly.id)
        assert len(items) == 2
