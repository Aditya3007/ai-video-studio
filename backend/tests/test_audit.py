"""Tests for the production observability and audit trail."""

import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.video.provider import VideoGenerationRequest
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
    AuditEventType,
    EpisodeSourceType,
    EpisodeStatus,
    QAWorkflowStatus,
    VideoGenerationJobStatus,
)
from app.orchestration import ImmediateWorker, Orchestrator
from app.services.ai_qa_service import FakeAIQAProvider
from app.services.audit_service import AuditService, AuditServiceError
from app.services.episode_production import EpisodeProductionService


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
    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(self, key, data, content_type=None, metadata=None):
        if hasattr(data, "read"):
            payload = data.read()
        else:
            payload = data
        self._data[key] = payload
        return type("StorageObject", (), {"key": key, "size": len(payload)})()

    def get(self, key):
        from io import BytesIO

        return BytesIO(self._data[key])

    def exists(self, key):
        return key in self._data

    def delete(self, key):
        self._data.pop(key, None)

    def get_metadata(self, key):
        return type("StorageObject", (), {"key": key, "size": len(self._data[key])})()


class _FakeRenderer:
    def render(self, series_id, assembly_id, output_path):
        from app.services.video_renderer import RenderResult

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


class _FailingAuditService(AuditService):
    def record(self, **kwargs):
        raise AuditServiceError("simulated audit failure")


def _seed_episode_with_shot(db):
    series = Series(name="Audit Series")
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
        description="Test shot.",
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


def _production_service(db, db_factory, ai_provider=None, audit_service=None):
    orchestrator = Orchestrator(db_factory=db_factory, worker=ImmediateWorker)
    return EpisodeProductionService(
        db,
        orchestrator=orchestrator,
        storage=_MemoryStorage(),
        storage_backend_name="memory",
        renderer=_FakeRenderer(),
        ai_provider=ai_provider,
        audit_service=audit_service,
    )


def _event_types(events):
    return [e.event_type for e in events]


def test_audit_service_records_and_redacts_secrets(db) -> None:
    series = Series(name="Secret Series")
    db.add(series)
    db.flush()
    audit = AuditService(db)
    event = audit.record(
        series_id=series.id,
        event_type=AuditEventType.JOB_FAILED,
        metadata={
            "config": {"api_key": "super-secret", "nested": {"token": "abc"}},
            "public": "ok",
        },
        error_message="Authorization: Bearer abc123 and api_key=xyz",
    )
    db.commit()

    assert event is not None
    assert event.event_metadata["config"]["api_key"] == "***REDACTED***"
    assert event.event_metadata["config"]["nested"]["token"] == "***REDACTED***"
    assert event.event_metadata["public"] == "ok"
    assert "***REDACTED***" in event.error_message


def test_production_lifecycle_events(db, db_factory) -> None:
    series_id, episode_id, _shot_id = _seed_episode_with_shot(db)
    service = _production_service(db, db_factory)

    result = service.produce(series_id, episode_id)

    assert result.status == "completed"
    audit = AuditService(db)
    history = audit.get_history(series_id, episode_id=episode_id)

    types = _event_types(history)
    assert AuditEventType.PRODUCTION_STARTED in types
    assert AuditEventType.STAGE_STARTED in types
    assert AuditEventType.STAGE_COMPLETED in types
    assert AuditEventType.QA_COMPLETED in types
    assert AuditEventType.EXPORT_COMPLETED in types
    assert AuditEventType.PRODUCTION_COMPLETED in types

    run_events = [e for e in history if str(e.production_run_id) == str(result.production_run_id)]
    assert len(run_events) > 0


def test_stage_failure_emits_production_failed(db, db_factory) -> None:
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

    service = _production_service(db, db_factory)
    result = service.produce(series.id, episode.id)

    assert result.status == "failed"
    audit = AuditService(db)
    history = audit.get_history(series.id, episode_id=episode.id)

    types = _event_types(history)
    assert AuditEventType.STAGE_FAILED in types
    assert AuditEventType.PRODUCTION_FAILED in types


def test_qa_failure_blocks_export_and_audits(db, db_factory) -> None:
    series_id, episode_id, _shot_id = _seed_episode_with_shot(db)
    service = _production_service(db, db_factory, ai_provider=FakeAIQAProvider(fail=True))

    result = service.produce(series_id, episode_id)

    assert result.status == "failed"
    audit = AuditService(db)
    history = audit.get_history(series_id, episode_id=episode_id)

    types = _event_types(history)
    assert AuditEventType.STAGE_FAILED in types
    assert AuditEventType.PRODUCTION_FAILED in types
    qa_event = [e for e in history if e.event_type == AuditEventType.QA_COMPLETED][0]
    assert qa_event.status == QAWorkflowStatus.DEGRADED.value


def test_asset_reuse_emits_reused_event(db, db_factory) -> None:
    series_id, episode_id, shot_id = _seed_episode_with_shot(db)
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

    service = _production_service(db, db_factory)
    result = service.produce(series_id, episode_id)

    assert result.status == "completed"
    audit = AuditService(db)
    history = audit.get_history(series_id, episode_id=episode_id)
    reused = [e for e in history if e.event_type == AuditEventType.ASSET_REUSED]
    assert len(reused) >= 1
    assert reused[0].asset_id == asset.id


def test_job_lifecycle_events(db, db_factory) -> None:
    series_id, episode_id, shot_id = _seed_episode_with_shot(db)
    run_id = "run-123"
    orchestrator = Orchestrator(db_factory=db_factory, worker=ImmediateWorker)

    job = orchestrator.submit_image_generation(db, series_id, shot_id, production_run_id=run_id)
    audit = AuditService(db)
    history = audit.get_history(series_id, production_run_id=run_id)

    types = _event_types(history)
    assert AuditEventType.JOB_SUBMITTED in types
    assert AuditEventType.JOB_STARTED in types
    assert AuditEventType.JOB_COMPLETED in types
    assert AuditEventType.ASSET_CREATED in types
    assert job.id in [e.job_id for e in history]


def test_retry_history(db, db_factory) -> None:
    series_id, episode_id, shot_id = _seed_episode_with_shot(db)
    run_id = "retry-run"

    # Create an already-failed video job with a bogus keyframe asset so validation fails.
    payload = VideoGenerationRequest(
        prompt="test",
        keyframe_asset_ids=[str(uuid.uuid4())],
        duration_seconds=5,
        aspect_ratio="16:9",
    ).model_dump(mode="json")
    job = VideoGenerationJob(
        series_id=series_id,
        shot_id=shot_id,
        request_payload=payload,
        status=VideoGenerationJobStatus.FAILED.value,
        attempts=0,
        max_attempts=2,
        error_message="previous failure",
    )
    db.add(job)
    db.commit()

    orchestrator = Orchestrator(db_factory=db_factory, worker=ImmediateWorker)
    orchestrator.retry_video_generation(db, series_id, job.id, production_run_id=run_id)

    audit = AuditService(db)
    history = audit.get_history(series_id, production_run_id=run_id)
    types = _event_types(history)

    assert types == [
        AuditEventType.JOB_RETRIED,
        AuditEventType.JOB_STARTED,
        AuditEventType.JOB_FAILED,
    ]
    failed_event = [e for e in history if e.event_type == AuditEventType.JOB_FAILED][0]
    assert failed_event.attempt == 1
    assert failed_event.error_message is not None


def test_audit_series_isolation(db, db_factory) -> None:
    series_a, episode_a, _shot_a = _seed_episode_with_shot(db)
    service = _production_service(db, db_factory)
    service.produce(series_a, episode_a)

    series_b = Series(name="Other Series")
    db.add(series_b)
    db.commit()

    audit = AuditService(db)
    assert audit.get_history(series_b.id, episode_id=episode_a) == []


def test_audit_failure_does_not_stop_production(db, db_factory) -> None:
    series_id, episode_id, _shot_id = _seed_episode_with_shot(db)
    failing_audit = _FailingAuditService(db)
    service = _production_service(db, db_factory, audit_service=failing_audit)

    result = service.produce(series_id, episode_id)

    assert result.status == "completed"
    assert any("Audit event failed" in w for w in result.warnings)
