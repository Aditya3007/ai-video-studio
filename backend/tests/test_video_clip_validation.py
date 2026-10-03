"""P6-T04 Video clip validation and storage tests."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.video import (
    FakeVideoGenerationProvider,
    VideoClipStorageService,
    VideoClipValidator,
    VideoGenerationJobService,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoReference,
    VideoValidationError,
)
from app.models import (
    Asset,
    Episode,
    Scene,
    Series,
    Shot,
    ShotSpecification,
    VideoGenerationJob,
)
from app.models.enums import (
    ApprovalStatus,
    AssetRole,
    AssetStatus,
    AssetType,
    VideoGenerationJobStatus,
)
from app.storage.filesystem import FilesystemStorage


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


class TestVideoClipValidator:
    def _request(self, **kwargs) -> VideoGenerationRequest:
        defaults = {
            "prompt": "Hero runs",
            "aspect_ratio": "9:16",
            "duration": 5.0,
        }
        defaults.update(kwargs)
        return VideoGenerationRequest(**defaults)

    def _result(self, **kwargs) -> VideoGenerationResult:
        defaults = {
            "uri": "fake://video/1.mp4",
            "width": 1080,
            "height": 1920,
            "duration": 5.0,
            "content_type": "video/mp4",
            "data": b"fake video",
        }
        defaults.update(kwargs)
        return VideoGenerationResult(
            videos=[VideoReference(**defaults)],
            provider="fake",
            model="fake-video-model",
        )

    def test_valid_result(self) -> None:
        request = self._request()
        result = self._result(width=1080, height=1920)
        summary = VideoClipValidator.validate(request, result)
        assert summary["valid"] is True

    def test_missing_video_list(self) -> None:
        request = self._request()
        result = VideoGenerationResult(videos=[], provider="fake", model="model")
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)

    def test_invalid_content_type(self) -> None:
        request = self._request()
        result = self._result(content_type="image/png")
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)

    def test_zero_dimensions(self) -> None:
        request = self._request()
        result = self._result(width=0, height=0)
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)

    def test_invalid_duration(self) -> None:
        request = self._request()
        result = self._result(duration=-1.0)
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)

    def test_wrong_aspect_ratio(self) -> None:
        request = self._request(aspect_ratio="16:9")
        result = self._result(width=1080, height=1920)
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)

    def test_wrong_dimensions(self) -> None:
        request = self._request(width=720, height=1280)
        result = self._result(width=1080, height=1920)
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)

    def test_duration_within_tolerance(self) -> None:
        request = self._request(duration=5.0)
        result = self._result(duration=5.5)
        summary = VideoClipValidator.validate(request, result)
        assert summary["valid"] is True

    def test_duration_outside_tolerance(self) -> None:
        request = self._request(duration=5.0)
        result = self._result(duration=8.0)
        with pytest.raises(VideoValidationError):
            VideoClipValidator.validate(request, result)


class TestVideoClipStorageService:
    def _seed_shot(self, db: Session) -> tuple[Series, Shot, Asset, VideoGenerationJob]:
        series = Series(name="Clip Storage Series")
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
        )
        db.add(shot)
        db.commit()
        db.refresh(shot)

        shot_spec = ShotSpecification(
            shot_id=shot.id,
            intent="Hero runs",
            camera_movement="Camera follows",
            visual_direction="Golden hour",
            aspect_ratio="9:16",
            duration_seconds=5,
        )
        db.add(shot_spec)
        db.commit()

        asset = Asset(
            series_id=series.id,
            asset_type=AssetType.STORYBOARD.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            approval_status=ApprovalStatus.APPROVED.value,
            storage_backend="image-provider",
            storage_key="fake://image/1.png",
            name="Storyboard",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        job = VideoGenerationJob(
            series_id=str(series.id),
            shot_id=str(shot.id),
            source_asset_id=str(asset.id),
            request_payload=VideoGenerationRequest(
                prompt="Hero runs",
                aspect_ratio="9:16",
                duration=5.0,
                keyframe_asset_ids=[],
            ).model_dump(mode="json"),
            status=VideoGenerationJobStatus.SUCCEEDED.value,
            attempts=1,
            max_attempts=3,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        return series, shot, asset, job

    def test_process_result_creates_asset(self, db: Session, tmp_path) -> None:
        series, shot, source, job = self._seed_shot(db)
        storage = FilesystemStorage(str(tmp_path))
        service = VideoClipStorageService(db, storage)

        result = VideoGenerationResult(
            videos=[
                VideoReference(
                    uri="fake://video/1.mp4",
                    width=1080,
                    height=1920,
                    duration=5.0,
                    content_type="video/mp4",
                    data=b"generated video bytes",
                )
            ],
            provider="fake",
            model="fake-video-model",
        )

        asset = service.process_result(job, result)

        assert asset.asset_type == AssetType.VIDEO.value
        assert asset.series_id == series.id
        assert asset.shot_id == shot.id
        assert asset.asset_metadata["video_generation_job_id"] == job.id
        assert storage.exists(asset.storage_key)

    def test_idempotent_processing(self, db: Session, tmp_path) -> None:
        series, shot, source, job = self._seed_shot(db)
        storage = FilesystemStorage(str(tmp_path))
        service = VideoClipStorageService(db, storage)

        result = VideoGenerationResult(
            videos=[
                VideoReference(
                    uri="fake://video/1.mp4",
                    width=1080,
                    height=1920,
                    duration=5.0,
                    content_type="video/mp4",
                    data=b"generated video bytes",
                )
            ],
            provider="fake",
            model="fake-video-model",
        )

        asset1 = service.process_result(job, result)
        asset2 = service.process_result(job, result)

        assert asset1.id == asset2.id
        assert db.query(Asset).filter_by(asset_type=AssetType.VIDEO.value).count() == 1

    def test_invalid_result_does_not_create_asset(self, db: Session, tmp_path) -> None:
        series, shot, source, job = self._seed_shot(db)
        storage = FilesystemStorage(str(tmp_path))
        service = VideoClipStorageService(db, storage)

        result = VideoGenerationResult(
            videos=[
                VideoReference(
                    uri="fake://video/1.mp4",
                    width=0,
                    height=0,
                    duration=5.0,
                    content_type="video/mp4",
                    data=b"generated video bytes",
                )
            ],
            provider="fake",
            model="fake-video-model",
        )

        with pytest.raises(VideoValidationError):
            service.process_result(job, result)

        assert db.query(Asset).filter_by(asset_type=AssetType.VIDEO.value).count() == 0

    def test_storage_key_path_safety(self, db: Session, tmp_path) -> None:
        series, shot, source, job = self._seed_shot(db)
        storage = FilesystemStorage(str(tmp_path))
        service = VideoClipStorageService(db, storage)

        # Ensure the generated key does not escape the storage root.
        key = service._generate_key(job, 0)
        assert ".." not in key
        assert not key.startswith("/")

    def test_job_integration_creates_asset(self, db: Session, tmp_path) -> None:
        series, shot, source = self._seed_shot(db)[:3]
        storage = FilesystemStorage(str(tmp_path))
        provider = FakeVideoGenerationProvider()
        service = VideoGenerationJobService(db, provider=provider, storage=storage)

        job = service.create_and_run(str(series.id), str(shot.id), str(source.id))

        assert job.status == VideoGenerationJobStatus.SUCCEEDED.value
        assert job.result_metadata["asset_id"]
        asset = db.get(Asset, job.result_metadata["asset_id"])
        assert asset is not None
        assert asset.asset_type == AssetType.VIDEO.value
        assert storage.exists(asset.storage_key)

    def test_job_integration_validation_failure(self, db: Session, tmp_path) -> None:
        series, shot, source = self._seed_shot(db)[:3]
        storage = FilesystemStorage(str(tmp_path))

        class BadProvider:
            def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
                return VideoGenerationResult(
                    videos=[
                        VideoReference(
                            uri="fake://video/1.mp4",
                            width=1080,
                            height=1920,
                            duration=0.0,
                            content_type="video/mp4",
                            data=b"bad",
                        )
                    ],
                    provider="fake",
                    model="bad",
                )

        service = VideoGenerationJobService(db, provider=BadProvider(), storage=storage)
        job = service.create_and_run(str(series.id), str(shot.id), str(source.id))

        assert job.status == VideoGenerationJobStatus.FAILED.value
        assert (
            "invalid duration" in job.error_message.lower()
            or "duration" in job.error_message.lower()
        )
