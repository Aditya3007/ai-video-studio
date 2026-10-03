"""Tests for the publishing workflow and scheduling service."""

from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import get_db, get_storage
from app.db.base import Base
from app.factory import create_app
from app.models import Asset, Episode, Series, VideoAssembly
from app.models.enums import (
    AssemblyStatus,
    AssetRole,
    AssetStatus,
    AssetType,
    AuditEventType,
    EpisodeSourceType,
    EpisodeStatus,
    PublishingStatus,
)
from app.orchestration import JobTask
from app.publishing import FakePublishingProvider, PublishingResult
from app.services.audit_service import AuditService
from app.services.publishing_service import PublishingService
from app.services.publishing_workflow_service import (
    PublishingWorkflowError,
    PublishingWorkflowService,
)


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
        return BytesIO(self._data[key])

    def exists(self, key):
        return key in self._data

    def delete(self, key):
        self._data.pop(key, None)


@pytest.fixture
def storage():
    return _MemoryStorage()


class _NoOpWorker:
    def __init__(self) -> None:
        self.tasks: list[JobTask] = []

    def enqueue(self, task: JobTask) -> None:
        self.tasks.append(task)

    def wait_for(self, job_id: str, timeout: float | None = None) -> None:
        return


def _seed_publishable(
    db, storage, *, rendered=True, asset_width=720, asset_height=1280, duration=30
):
    series = Series(name="Publish Series")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        title="Episode One",
        episode_number=1,
        status=EpisodeStatus.COMPLETED.value,
        source_type=EpisodeSourceType.TOPIC.value,
    )
    db.add(episode)
    db.flush()
    storage_key = f"exports/{series.id}/{episode.id}/final.mp4"
    storage.put(storage_key, b"fake mp4")
    asset = Asset(
        series_id=series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key=storage_key,
        asset_metadata={
            "width": asset_width,
            "height": asset_height,
            "duration_seconds": duration,
            "container_format": "mp4",
        },
    )
    db.add(asset)
    db.flush()
    assembly = VideoAssembly(
        series_id=series.id,
        episode_id=episode.id,
        status=AssemblyStatus.RENDERED.value if rendered else AssemblyStatus.DRAFT.value,
        final_asset_id=asset.id,
    )
    db.add(assembly)
    thumb_key = f"thumbs/{series.id}/thumb.png"
    storage.put(thumb_key, b"png")
    thumbnail = Asset(
        series_id=series.id,
        asset_type=AssetType.STORYBOARD.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key=thumb_key,
    )
    db.add(thumbnail)
    db.commit()
    return series.id, episode.id, asset.id, thumbnail.id


def _service(db, storage, *, publishing_service=None, worker=None):
    return PublishingWorkflowService(
        db,
        storage,
        publishing_service=publishing_service,
        worker=worker,
    )


def test_immediate_publish_success(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id)
    assert job.status == PublishingStatus.READY.value
    result = service.execute(series_id, job.id)
    assert result.status == PublishingStatus.PUBLISHED.value
    assert result.external_publication_id is not None
    assert result.external_url is not None
    db.refresh(job)
    assert job.status == PublishingStatus.PUBLISHED.value


def test_publish_rejects_unrendered_assembly(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage, rendered=False)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id)
    result = service.execute(series_id, job.id)
    assert result.status == PublishingStatus.FAILED.value
    assert "rendered" in (result.error_message or "").lower()


def test_publish_rejects_wrong_series_asset(db, storage) -> None:
    series_id, episode_id, asset_id, _ = _seed_publishable(db, storage)
    other_series = Series(name="Other")
    db.add(other_series)
    db.flush()
    other_asset = Asset(
        series_id=other_series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        asset_metadata={"width": 720, "height": 1280, "duration_seconds": 30},
    )
    db.add(other_asset)
    db.flush()
    assembly = db.query(VideoAssembly).filter_by(episode_id=episode_id).first()
    assembly.final_asset_id = other_asset.id
    db.commit()
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job = service.request_publication(series_id, episode_id, other_asset.id)
    result = service.execute(series_id, job.id)
    assert result.status == PublishingStatus.FAILED.value
    assert "not belong" in (result.error_message or "").lower()


def test_scheduled_publication_not_executed_before_due(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    future = datetime.now(UTC) + timedelta(days=1)
    job = service.request_publication(
        series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id, scheduled_at=future
    )
    assert job.status == PublishingStatus.SCHEDULED.value
    with pytest.raises(PublishingWorkflowError, match="not yet due"):
        service.execute(series_id, job.id)


def test_execute_due_publishes_when_due(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    past = datetime.now(UTC) - timedelta(minutes=1)
    service.request_publication(
        series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id, scheduled_at=past
    )
    results = service.execute_due()
    assert len(results) == 1
    assert results[0].status == PublishingStatus.PUBLISHED.value


def test_cancel_scheduled_publication(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    future = datetime.now(UTC) + timedelta(days=1)
    job = service.request_publication(
        series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id, scheduled_at=future
    )
    result = service.cancel(series_id, job.id)
    assert result.status == PublishingStatus.CANCELLED.value


def test_cancel_published_is_rejected(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id)
    service.execute(series_id, job.id)
    with pytest.raises(PublishingWorkflowError, match="Cannot cancel"):
        service.cancel(series_id, job.id)


def test_idempotency_duplicate_key(db, storage) -> None:
    series_id, episode_id, asset_id, _ = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job1 = service.request_publication(series_id, episode_id, asset_id, idempotency_key="key-1")
    job2 = service.request_publication(series_id, episode_id, asset_id, idempotency_key="key-1")
    assert job1.id == job2.id


def test_retry_failed_publication(db, storage) -> None:
    series_id, episode_id, asset_id, _ = _seed_publishable(db, storage)
    worker = _NoOpWorker()

    class ToggleProvider:
        provider_id = "toggle"

        def __init__(self) -> None:
            self.calls = 0

        def publish(self, request):
            self.calls += 1
            if self.calls == 1:
                return PublishingResult(
                    publication_id="",
                    status=PublishingStatus.FAILED,
                    provider=self.provider_id,
                    requested_at=datetime.now(UTC),
                    error_message="Simulated failure",
                )
            return PublishingResult(
                publication_id=f"pub-{request.asset_id}",
                status=PublishingStatus.PUBLISHED,
                provider=self.provider_id,
                requested_at=datetime.now(UTC),
                published_at=datetime.now(UTC),
                url=f"https://example.com/watch/{request.asset_id}",
            )

        def get_status(self, publication_id: str):
            raise NotImplementedError

        def cancel(self, publication_id: str):
            raise NotImplementedError

    provider = ToggleProvider()
    publishing_service = PublishingService(db, storage, provider=provider)
    service = _service(db, storage, publishing_service=publishing_service, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id)
    result = service.execute(series_id, job.id)
    assert result.status == PublishingStatus.FAILED.value
    assert result.attempts == 1

    retry_result = service.retry(series_id, job.id)
    assert retry_result.status == PublishingStatus.READY.value
    result = service.execute(series_id, job.id)
    assert result.status == PublishingStatus.PUBLISHED.value
    assert result.attempts == 2


def test_retry_exhausted(db, storage) -> None:
    series_id, episode_id, asset_id, _ = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    publishing_service = PublishingService(
        db, storage, provider=FakePublishingProvider(should_fail=True)
    )
    service = _service(db, storage, publishing_service=publishing_service, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id, max_attempts=1)
    service.execute(series_id, job.id)
    with pytest.raises(PublishingWorkflowError, match="exhausted"):
        service.retry(series_id, job.id)


def test_audit_events_emitted(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id, thumbnail_asset_id=thumb_id)
    service.execute(series_id, job.id)
    audit = AuditService(db)
    events = audit.get_history(series_id)
    types = [e.event_type for e in events]
    assert AuditEventType.PUBLICATION_REQUESTED.value in types
    assert AuditEventType.PUBLICATION_VALIDATED.value in types
    assert AuditEventType.PUBLICATION_STARTED.value in types
    assert AuditEventType.PUBLICATION_COMPLETED.value in types


def test_series_isolation_for_get(db, storage) -> None:
    series_id, episode_id, asset_id, _ = _seed_publishable(db, storage)
    worker = _NoOpWorker()
    service = _service(db, storage, worker=worker)
    job = service.request_publication(series_id, episode_id, asset_id)
    other_series = Series(name="Other")
    db.add(other_series)
    db.commit()
    with pytest.raises(PublishingWorkflowError):
        service.get(other_series.id, job.id)


def test_api_create_and_get(db, storage) -> None:
    series_id, episode_id, asset_id, thumb_id = _seed_publishable(db, storage)
    app = create_app()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_storage():
        yield storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/publishing",
        json={
            "series_id": series_id,
            "episode_id": episode_id,
            "asset_id": asset_id,
            "thumbnail_asset_id": thumb_id,
        },
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["status"] == "PUBLISHED"
    get_resp = client.get(f"/api/v1/publishing/{series_id}/{data['job_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["job_id"] == data["job_id"]
