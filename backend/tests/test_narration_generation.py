"""P7-T03 Narration generation workflow tests."""

import io

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.tts import (
    FakeTTSProvider,
    TTSProvider,
    TTSReference,
    TTSResult,
)
from app.models import Asset, Episode, Narration, Series, Voice
from app.models.enums import AssetRole, AssetStatus, AssetType, NarrationStatus
from app.services.narration_generation_service import (
    NarrationGenerationError,
    NarrationGenerationService,
)
from app.storage import StorageError, StorageObject


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


class FakeStorageBackend:
    """In-memory storage backend for testing."""

    def __init__(self, fail: bool = False) -> None:
        self._objects: dict[str, bytes] = {}
        self._meta: dict[str, dict] = {}
        self.fail = fail

    def put(
        self,
        key: str,
        data: object,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        if self.fail:
            raise StorageError("Simulated storage failure.")
        payload = data if isinstance(data, bytes) else data.read()
        self._objects[key] = payload
        self._meta[key] = metadata or {}
        return StorageObject(
            key=key,
            size=len(payload),
            content_type=content_type or "application/octet-stream",
            etag="fake",
        )

    def get(self, key: str) -> io.BytesIO:
        if key not in self._objects:
            raise StorageError("Not found.")
        return io.BytesIO(self._objects[key])

    def exists(self, key: str) -> bool:
        return key in self._objects

    def delete(self, key: str) -> None:
        if key not in self._objects:
            raise StorageError("Not found.")
        del self._objects[key]
        self._meta.pop(key, None)

    def get_metadata(self, key: str) -> StorageObject:
        if key not in self._objects:
            raise StorageError("Not found.")
        return StorageObject(
            key=key,
            size=len(self._objects[key]),
            content_type=self._meta[key].get("content_type", "application/octet-stream"),
            etag="fake",
        )


class BrokenTTSProvider:
    """Provider that returns an invalid audio result."""

    def synthesize(self, request: object) -> TTSResult:
        return TTSResult(
            audio=TTSReference(
                uri="fake://empty.mp3",
                content_type="audio/mpeg",
                audio_format="mp3",
                duration=0.0,
                data=None,
            ),
            provider="broken",
            model="broken",
        )


def _seed(db: Session) -> tuple[Series, Episode, Voice, Narration]:
    series = Series(name="Narration Series")
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

    voice = Voice(
        series_id=series.id,
        name="Narrator",
        voice_metadata={"gender": "neutral"},
    )
    db.add(voice)
    db.commit()
    db.refresh(voice)

    narration = Narration(
        series_id=series.id,
        episode_id=episode.id,
        source_text="Hello world",
        voice_id=voice.id,
    )
    db.add(narration)
    db.commit()
    db.refresh(narration)

    return series, episode, voice, narration


class TestNarrationGenerationService:
    def test_happy_path(self, db: Session) -> None:
        series, _episode, voice, narration = _seed(db)
        storage = FakeStorageBackend()
        provider = FakeTTSProvider(voice_mapping={str(voice.id): "fake-voice-mapped"})
        service = NarrationGenerationService(db, provider=provider, storage=storage)

        result = service.generate(str(series.id), str(narration.id))

        assert result.status == NarrationStatus.GENERATED.value
        assert result.generated_asset_id is not None
        assert result.duration_seconds is not None

        asset = db.get(Asset, str(result.generated_asset_id))
        assert asset is not None
        assert asset.asset_type == AssetType.AUDIO.value
        assert asset.role == AssetRole.GENERATED.value
        assert asset.status == AssetStatus.AVAILABLE.value
        assert asset.storage_key.startswith(f"audio/{series.id}/{narration.id}/")
        assert asset.asset_metadata["provider"] == "fake"
        assert asset.asset_metadata["audio_format"] == "mp3"

    def test_text_sent_to_provider(self, db: Session) -> None:
        series, _episode, voice, narration = _seed(db)

        class CapturingTTSProvider:
            def __init__(self) -> None:
                self.request: object | None = None

            def synthesize(self, request: object) -> TTSResult:
                self.request = request
                return FakeTTSProvider().synthesize(request)

        provider = CapturingTTSProvider()
        service = NarrationGenerationService(db, provider=provider, storage=FakeStorageBackend())
        service.generate(str(series.id), str(narration.id))

        assert provider.request is not None
        assert provider.request.text == "Hello world"
        assert provider.request.voice_id == str(voice.id)

    def test_provider_failure(self, db: Session) -> None:
        series, _episode, _voice, narration = _seed(db)
        provider = FakeTTSProvider(fail_mode="synthesis")
        service = NarrationGenerationService(db, provider=provider, storage=FakeStorageBackend())

        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

        assert narration.status == NarrationStatus.FAILED.value
        assert narration.generated_asset_id is None
        assert narration.audio_metadata is not None
        assert "error" in narration.audio_metadata

    def test_invalid_provider_result(self, db: Session) -> None:
        series, _episode, _voice, narration = _seed(db)
        provider = BrokenTTSProvider()
        service = NarrationGenerationService(db, provider=provider, storage=FakeStorageBackend())

        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

        assert narration.status == NarrationStatus.FAILED.value
        assert narration.generated_asset_id is None

    def test_storage_failure(self, db: Session) -> None:
        series, _episode, _voice, narration = _seed(db)
        provider = FakeTTSProvider()
        service = NarrationGenerationService(
            db, provider=provider, storage=FakeStorageBackend(fail=True)
        )

        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

        assert narration.status == NarrationStatus.FAILED.value
        assert narration.generated_asset_id is None

    def test_duplicate_generation_rejected(self, db: Session) -> None:
        series, _episode, voice, narration = _seed(db)
        existing_asset = Asset(
            series_id=series.id,
            asset_type=AssetType.AUDIO.value,
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            storage_backend="fake",
            storage_key="audio/existing.mp3",
            name="Existing audio",
        )
        db.add(existing_asset)
        db.commit()
        db.refresh(existing_asset)

        narration.status = NarrationStatus.GENERATED.value
        narration.generated_asset_id = existing_asset.id
        db.commit()

        service = NarrationGenerationService(
            db, provider=FakeTTSProvider(), storage=FakeStorageBackend()
        )
        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

        assert narration.generated_asset_id == existing_asset.id

    def test_cross_series_narration_rejected(self, db: Session) -> None:
        series_a, _episode_a, _voice_a, narration_a = _seed(db)
        series_b = Series(name="Other Series")
        db.add(series_b)
        db.commit()
        db.refresh(series_b)

        service = NarrationGenerationService(
            db, provider=FakeTTSProvider(), storage=FakeStorageBackend()
        )
        with pytest.raises(NarrationGenerationError):
            service.generate(str(series_b.id), str(narration_a.id))

    def test_voice_outside_series_rejected(self, db: Session) -> None:
        series, _episode, voice, narration = _seed(db)
        other_series = Series(name="Other Series")
        db.add(other_series)
        db.commit()
        db.refresh(other_series)

        other_voice = Voice(series_id=other_series.id, name="Other Voice")
        db.add(other_voice)
        db.commit()
        db.refresh(other_voice)

        narration.voice_id = other_voice.id
        db.commit()

        service = NarrationGenerationService(
            db, provider=FakeTTSProvider(), storage=FakeStorageBackend()
        )
        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

    def test_missing_voice_rejected(self, db: Session) -> None:
        series, _episode, _voice, narration = _seed(db)
        narration.voice_id = None
        db.commit()

        service = NarrationGenerationService(
            db, provider=FakeTTSProvider(), storage=FakeStorageBackend()
        )
        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

    def test_empty_text_rejected(self, db: Session) -> None:
        series, _episode, _voice, narration = _seed(db)
        narration.source_text = "   "
        db.commit()

        service = NarrationGenerationService(
            db, provider=FakeTTSProvider(), storage=FakeStorageBackend()
        )
        with pytest.raises(NarrationGenerationError):
            service.generate(str(series.id), str(narration.id))

    def test_provider_abstraction(self, db: Session) -> None:
        series, _episode, voice, narration = _seed(db)

        class CustomTTSProvider:
            def synthesize(self, request: object) -> TTSResult:
                return FakeTTSProvider().synthesize(request)

        provider: TTSProvider = CustomTTSProvider()  # type: ignore[assignment]
        service = NarrationGenerationService(db, provider=provider, storage=FakeStorageBackend())
        result = service.generate(str(series.id), str(narration.id))

        assert result.status == NarrationStatus.GENERATED.value
        assert result.generated_asset_id is not None
