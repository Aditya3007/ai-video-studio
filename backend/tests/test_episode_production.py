"""Tests for the episode end-to-end production pipeline."""

import io

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import (
    Asset,
    Episode,
    Narration,
    Scene,
    Series,
    Shot,
    ShotSpecification,
    Voice,
)
from app.models.enums import (
    ApprovalStatus,
    AssetRole,
    AssetStatus,
    AssetType,
    EpisodeSourceType,
    EpisodeStatus,
    NarrationStatus,
    NarrationType,
)
from app.orchestration import ImmediateWorker, Orchestrator
from app.services.episode_production import (
    EpisodeProductionError,
    EpisodeProductionService,
    EpisodeProductionStage,
)
from app.services.video_renderer import RenderResult
from app.storage import StorageObject


def _enable_fk(dbapi_connection, _connection_record):
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
    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_factory(db):
    engine = db.bind
    testing_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session_factory


class _MemoryStorage:
    """In-memory storage backend for deterministic tests."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._meta: dict[str, StorageObject] = {}

    def put(self, key, data, content_type=None, metadata=None):
        if hasattr(data, "read"):
            payload = data.read()
        else:
            payload = data
        self._data[key] = payload
        self._meta[key] = StorageObject(
            key=key,
            size=len(payload),
            content_type=content_type or "application/octet-stream",
        )
        return self._meta[key]

    def get(self, key):
        return io.BytesIO(self._data[key])

    def exists(self, key):
        return key in self._data

    def delete(self, key):
        self._data.pop(key, None)

    def get_metadata(self, key):
        return self._meta[key]


class _FakeRenderer:
    """Renderer that writes a tiny fake MP4 and returns metadata."""

    def render(self, series_id, assembly_id, output_path):
        output_path.write_bytes(b"fake mp4")
        return RenderResult(
            output_path=str(output_path),
            duration_seconds=10.0,
            width=1280,
            height=720,
            has_video_stream=True,
            has_audio_stream=True,
            container_format="mp4",
            size_bytes=8,
        )


def _seed_episode_with_shot(db):
    series = Series(name="Pipeline Series")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        title="Episode 1",
        episode_number=1,
        status=EpisodeStatus.DRAFT.value,
        source_type=EpisodeSourceType.TOPIC.value,
    )
    db.add(episode)
    db.flush()
    scene = Scene(
        episode_id=episode.id,
        scene_number=1,
        sequence_order=0,
        title="Scene 1",
    )
    db.add(scene)
    db.flush()
    shot = Shot(
        scene_id=scene.id,
        shot_number=1,
        sequence_order=0,
        description="Test shot",
    )
    db.add(shot)
    db.flush()
    spec = ShotSpecification(
        shot_id=shot.id,
        intent="Establish the hero",
        framing="Medium close-up",
        composition="Rule of thirds",
        subject_notes="Hero looking determined",
        visual_direction="Golden hour lighting",
        aspect_ratio="16:9",
    )
    db.add(spec)
    db.commit()
    return series.id, episode.id, shot.id


def _service(db, db_factory, storage=None, renderer=None, ai_provider=None):
    orchestrator = Orchestrator(db_factory=db_factory, worker=ImmediateWorker)
    return EpisodeProductionService(
        db,
        orchestrator=orchestrator,
        storage=storage or _MemoryStorage(),
        storage_backend_name="memory",
        renderer=renderer or _FakeRenderer(),
        ai_provider=ai_provider,
    )


def test_full_episode_pipeline_produces_final_asset(db, db_factory) -> None:
    series_id, episode_id, _shot_id = _seed_episode_with_shot(db)
    service = _service(db, db_factory)

    result = service.produce(series_id, episode_id)

    assert result.status == "completed", result.message
    assert result.stage == EpisodeProductionStage.COMPLETED
    assert result.final_asset_id is not None
    assert result.assembly_id is not None


def test_existing_storyboard_is_reused(db, db_factory) -> None:
    series_id, episode_id, shot_id = _seed_episode_with_shot(db)
    service = _service(db, db_factory)

    # Pre-create an approved storyboard asset.
    asset = Asset(
        series_id=series_id,
        shot_id=shot_id,
        asset_type=AssetType.STORYBOARD.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        approval_status=ApprovalStatus.APPROVED.value,
        storage_backend="memory",
        storage_key="storyboard.png",
        name="Existing storyboard",
    )
    db.add(asset)
    db.commit()

    result = service.produce(series_id, episode_id)

    assert result.status == "completed"
    assert result.final_asset_id is not None


def test_existing_video_job_is_reused(db, db_factory) -> None:
    series_id, episode_id, shot_id = _seed_episode_with_shot(db)
    storage = _MemoryStorage()
    service = _service(db, db_factory, storage=storage)

    # Run once to generate assets/jobs.
    first = service.produce(series_id, episode_id)
    assert first.status == "completed"

    # Re-run should reuse existing assets and not crash.
    second = service.produce(series_id, episode_id)
    assert second.status == "completed"
    assert second.final_asset_id == first.final_asset_id


def test_pipeline_with_narration(db, db_factory) -> None:
    series_id, episode_id, shot_id = _seed_episode_with_shot(db)
    service = _service(db, db_factory)

    voice = Voice(series_id=series_id, name="Hero")
    db.add(voice)
    db.flush()
    narration = Narration(
        series_id=series_id,
        episode_id=episode_id,
        shot_id=shot_id,
        voice_id=voice.id,
        source_text="Hello world",
        narration_type=NarrationType.NARRATION.value,
        status=NarrationStatus.PENDING.value,
    )
    db.add(narration)
    db.commit()

    result = service.produce(series_id, episode_id)

    assert result.status == "completed", result.message
    assert result.final_asset_id is not None


def test_episode_without_scenes_fails_at_planning(db, db_factory) -> None:
    series = Series(name="Empty Series")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        title="Empty Episode",
        episode_number=1,
        status=EpisodeStatus.DRAFT.value,
        source_type=EpisodeSourceType.TOPIC.value,
    )
    db.add(episode)
    db.commit()

    service = _service(db, db_factory)
    result = service.produce(series.id, episode.id)

    assert result.status == "failed"
    assert result.stage == EpisodeProductionStage.PLANNING


def test_qa_failure_blocks_export(db, db_factory) -> None:
    from app.services.ai_qa_service import FakeAIQAProvider

    series_id, episode_id, _shot_id = _seed_episode_with_shot(db)

    service = _service(
        db,
        db_factory,
        ai_provider=FakeAIQAProvider(fail=True),
    )

    result = service.produce(series_id, episode_id)

    assert result.status == "failed"
    assert result.stage == EpisodeProductionStage.QA


def test_series_isolation(db, db_factory) -> None:
    series_a, episode_a, _shot_a = _seed_episode_with_shot(db)
    series_b = Series(name="Other Series")
    db.add(series_b)
    db.commit()

    service = _service(db, db_factory)
    with pytest.raises(EpisodeProductionError):
        service.produce(series_b.id, episode_a)
