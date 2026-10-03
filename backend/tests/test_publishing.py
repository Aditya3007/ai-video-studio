"""Tests for the provider-neutral YouTube publishing abstraction."""

import uuid
from datetime import UTC, datetime
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
from app.models import Asset, Series
from app.models.enums import AssetRole, AssetStatus, AssetType, PublishingStatus
from app.provider_registry import ProviderType, get_default_registry
from app.publishing import (
    FakePublishingProvider,
    PublishingRequest,
    PublishingResult,
)
from app.services.publishing_service import PublishingService, PublishingServiceError


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

    def get_metadata(self, key):
        return type("StorageObject", (), {"key": key, "size": len(self._data[key])})()


@pytest.fixture
def storage():
    return _MemoryStorage()


def _seed_series_and_asset(db, storage, *, width=720, height=1280, duration=30):
    series = Series(name="Publish Series")
    db.add(series)
    db.flush()
    storage_key = f"exports/{series.id}/final.mp4"
    storage.put(storage_key, b"fake mp4")
    asset = Asset(
        series_id=series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key=storage_key,
        name="Final export",
        asset_metadata={
            "width": width,
            "height": height,
            "duration_seconds": duration,
            "container_format": "mp4",
        },
    )
    db.add(asset)
    db.commit()
    return series.id, asset.id


def test_fake_provider_publish_and_get_status() -> None:
    provider = FakePublishingProvider()
    request = PublishingRequest(
        asset_id=uuid.uuid4(),
        series_id=uuid.uuid4(),
        title="Test Short",
    )
    result = provider.publish(request)
    assert result.status == PublishingStatus.PUBLISHED
    assert result.provider == "fake"
    assert result.url is not None
    assert provider.get_status(result.publication_id).status == PublishingStatus.PUBLISHED


def test_fake_provider_failure() -> None:
    provider = FakePublishingProvider(should_fail=True)
    request = PublishingRequest(
        asset_id=uuid.uuid4(),
        series_id=uuid.uuid4(),
        title="Failing Short",
    )
    result = provider.publish(request)
    assert result.status == PublishingStatus.FAILED


def test_fake_provider_deterministic_id() -> None:
    provider = FakePublishingProvider()
    request = PublishingRequest(
        asset_id=uuid.uuid4(),
        series_id=uuid.uuid4(),
        title="Deterministic",
        idempotency_key="key-1",
    )
    result1 = provider.publish(request)
    result2 = provider.publish(request)
    assert result1.publication_id == result2.publication_id
    assert result1.publication_id == "fake-publication-key-1"


def test_publishing_service_accepts_valid_final_asset(db, storage) -> None:
    series_id, asset_id = _seed_series_and_asset(db, storage)
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset_id,
        series_id=series_id,
        title="Valid Short",
    )
    result = service.publish(request)
    assert result.status == PublishingStatus.PUBLISHED
    assert result.url is not None


def test_publishing_service_rejects_missing_asset(db, storage) -> None:
    series = Series(name="No Asset")
    db.add(series)
    db.commit()
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=uuid.uuid4(),
        series_id=series.id,
        title="Missing",
    )
    with pytest.raises(PublishingServiceError, match="Asset not found"):
        service.publish(request)


def test_publishing_service_rejects_wrong_series(db, storage) -> None:
    series_a, asset_id = _seed_series_and_asset(db, storage)
    series_b = Series(name="Other")
    db.add(series_b)
    db.commit()
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset_id,
        series_id=series_b.id,
        title="Wrong Series",
    )
    with pytest.raises(PublishingServiceError, match="does not belong"):
        service.publish(request)


def test_publishing_service_rejects_non_video_asset(db, storage) -> None:
    series = Series(name="Image Series")
    db.add(series)
    db.flush()
    storage_key = f"exports/{series.id}/image.png"
    storage.put(storage_key, b"fake png")
    asset = Asset(
        series_id=series.id,
        asset_type=AssetType.IMAGE.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key=storage_key,
        asset_metadata={"width": 720, "height": 1280, "duration_seconds": 30},
    )
    db.add(asset)
    db.commit()
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset.id,
        series_id=series.id,
        title="Image",
    )
    with pytest.raises(PublishingServiceError, match="Only video assets"):
        service.publish(request)


def test_publishing_service_rejects_unavailable_asset(db, storage) -> None:
    series = Series(name="Pending Series")
    db.add(series)
    db.flush()
    asset = Asset(
        series_id=series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.PENDING.value,
        asset_metadata={"width": 720, "height": 1280, "duration_seconds": 30},
    )
    db.add(asset)
    db.commit()
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset.id,
        series_id=series.id,
        title="Pending",
    )
    with pytest.raises(PublishingServiceError, match="not available"):
        service.publish(request)


def test_publishing_service_rejects_missing_storage(db, storage) -> None:
    series = Series(name="Missing Storage")
    db.add(series)
    db.flush()
    asset = Asset(
        series_id=series.id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key="missing-key",
        asset_metadata={"width": 720, "height": 1280, "duration_seconds": 30},
    )
    db.add(asset)
    db.commit()
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset.id,
        series_id=series.id,
        title="Missing Storage",
    )
    with pytest.raises(PublishingServiceError, match="not available in storage"):
        service.publish(request)


def test_shorts_constraints_invalid_aspect_ratio(db, storage) -> None:
    # 1280x720 is 16:9, not 9:16
    series_id, asset_id = _seed_series_and_asset(db, storage, width=1280, height=720, duration=30)
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset_id,
        series_id=series_id,
        title="Wrong Ratio",
    )
    with pytest.raises(PublishingServiceError, match="9:16"):
        service.publish(request)


def test_shorts_constraints_too_long(db, storage) -> None:
    series_id, asset_id = _seed_series_and_asset(db, storage, width=720, height=1280, duration=61)
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset_id,
        series_id=series_id,
        title="Too Long",
    )
    with pytest.raises(PublishingServiceError, match="exceeds Shorts"):
        service.publish(request)


def test_publishing_service_allows_non_shorts_without_ratio_check(db, storage) -> None:
    # 16:9 asset should be allowed when not targeting Shorts.
    series_id, asset_id = _seed_series_and_asset(db, storage, width=1280, height=720, duration=90)
    service = PublishingService(db, storage, provider=FakePublishingProvider())
    request = PublishingRequest(
        asset_id=asset_id,
        series_id=series_id,
        title="Wide Video",
        is_shorts=False,
    )
    result = service.publish(request)
    assert result.status == PublishingStatus.PUBLISHED


def test_security_error_sanitization(db, storage) -> None:
    series_id, asset_id = _seed_series_and_asset(db, storage)

    class LeakyProvider:
        provider_id = "leaky"

        def publish(self, request: PublishingRequest) -> PublishingResult:
            return PublishingResult(
                publication_id="leaky-1",
                status=PublishingStatus.FAILED,
                provider=self.provider_id,
                requested_at=datetime.now(UTC),
                error_message="Authorization: Bearer super-secret-token",
            )

        def get_status(self, publication_id: str) -> PublishingResult:
            raise NotImplementedError

        def cancel(self, publication_id: str) -> PublishingResult:
            raise NotImplementedError

    service = PublishingService(db, storage, provider=LeakyProvider())
    request = PublishingRequest(
        asset_id=asset_id,
        series_id=series_id,
        title="Leaky",
    )
    result = service.publish(request)
    assert "super-secret-token" not in (result.error_message or "")
    assert "***REDACTED***" in (result.error_message or "")


def test_registry_resolve_fake_publishing() -> None:
    registry = get_default_registry()
    provider = registry.resolve(ProviderType.PUBLISHING, "fake")
    assert isinstance(provider, FakePublishingProvider)


def test_api_publish_endpoint(db, storage) -> None:
    series_id, asset_id = _seed_series_and_asset(db, storage)
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
    response = client.post(
        "/api/v1/publish",
        json={
            "asset_id": str(asset_id),
            "series_id": str(series_id),
            "title": "API Short",
            "is_shorts": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PUBLISHED"
    assert data["provider"] == "fake"
