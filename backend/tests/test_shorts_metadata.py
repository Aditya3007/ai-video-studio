"""Tests for Shorts metadata and thumbnail generation."""

import uuid
from io import BytesIO

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import Asset, Episode, Series, Story
from app.models.enums import (
    AssetRole,
    AssetStatus,
    AssetType,
    EpisodeSourceType,
    EpisodeStatus,
)
from app.services.shorts_metadata_service import (
    LLMShortsMetadataGenerator,
    ShortsMetadata,
    ShortsMetadataError,
    ShortsMetadataService,
)
from app.services.thumbnail_service import ThumbnailError, ThumbnailService
from app.story_intelligence.llm.fake import FakeLLMProvider


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


def _seed_episode(db, *, with_story=True):
    series = Series(name="Metadata Series")
    db.add(series)
    db.flush()
    story = None
    if with_story:
        story = Story(
            series_id=series.id,
            title="The Hero's Journey",
            source_type="topic",
            source_content="A hero sets out on an epic quest and discovers courage within.",
            language="en",
        )
        db.add(story)
        db.flush()
    episode = Episode(
        series_id=series.id,
        title="The First Step",
        episode_number=1,
        description="Our hero takes the first step into the unknown.",
        status=EpisodeStatus.DRAFT.value,
        source_type=EpisodeSourceType.TOPIC.value,
        story_id=story.id if story else None,
    )
    db.add(episode)
    db.commit()
    return series.id, episode.id, story.id if story else None


def test_shorts_metadata_contract() -> None:
    metadata = ShortsMetadata(
        title="A valid title",
        source_episode_id=uuid.uuid4(),
        tags=["  #Shorts", "  AI ", "ai", ""],
    )
    assert metadata.title == "A valid title"
    assert metadata.tags == ["shorts", "ai"]
    assert metadata.hashtags == ["#shorts", "#ai"]


def test_shorts_metadata_title_too_long() -> None:
    with pytest.raises(Exception):
        ShortsMetadata(title="x" * 101, source_episode_id=uuid.uuid4())


def test_deterministic_generator_is_deterministic(db) -> None:
    series_id, episode_id, _story_id = _seed_episode(db)
    service = ShortsMetadataService(db)
    result1 = service.generate(series_id, episode_id, mode="deterministic")
    result2 = service.generate(series_id, episode_id, mode="deterministic")
    assert result1.title == result2.title
    assert result1.tags == result2.tags
    assert result1.generator == "deterministic"


def test_deterministic_generator_uses_story_context(db) -> None:
    series_id, episode_id, story_id = _seed_episode(db)
    service = ShortsMetadataService(db)
    result = service.generate(series_id, episode_id, mode="deterministic")
    assert "The First Step" in result.canonical_title or result.title
    assert result.source_story_id == uuid.UUID(story_id)
    assert "shorts" in result.tags
    assert any(t in result.tags for t in ["hero", "journey", "step"])


def test_ai_generator_with_fake_llm(db) -> None:
    series_id, episode_id, _story_id = _seed_episode(db)
    llm = FakeLLMProvider(
        response={
            "title": "AI Title",
            "description": "AI description.",
            "tags": ["ai", "shorts"],
            "category": "Entertainment",
            "language": "en",
            "call_to_action": "Subscribe!",
        }
    )
    service = ShortsMetadataService(db, llm_provider=llm)
    result = service.generate(series_id, episode_id, mode="ai")
    assert result.title == "AI Title"
    assert result.generator == "llm"
    assert result.tags == ["ai", "shorts"]


def test_ai_generator_malformed_response(db) -> None:
    series_id, episode_id, _story_id = _seed_episode(db)
    llm = FakeLLMProvider(response={"title": ""})
    service = ShortsMetadataService(db, llm_provider=llm)
    with pytest.raises(ShortsMetadataError):
        service.generate(series_id, episode_id, mode="ai")


def test_ai_generator_provider_failure(db) -> None:
    series_id, episode_id, _story_id = _seed_episode(db)
    llm = FakeLLMProvider(fail=True)
    service = ShortsMetadataService(db, llm_provider=llm)
    with pytest.raises(Exception):
        service.generate(series_id, episode_id, mode="ai")


def test_metadata_does_not_overwrite_canonical_content(db) -> None:
    series_id, episode_id, _story_id = _seed_episode(db)
    service = ShortsMetadataService(db)
    result = service.generate(series_id, episode_id, mode="deterministic")
    episode = db.get(Episode, episode_id)
    assert episode.title == "The First Step"
    assert result.title != ""  # generated separately
    assert result.source_episode_id == uuid.UUID(episode_id)


def test_security_secrets_redacted_from_metadata(db) -> None:
    series = Series(name="Secret Series")
    db.add(series)
    db.flush()
    story = Story(
        series_id=series.id,
        title="Story",
        source_type="topic",
        source_content="The secret is api_key=super-secret and Authorization: Bearer token123.",
    )
    db.add(story)
    db.flush()
    episode = Episode(
        series_id=series.id,
        title="Episode",
        episode_number=1,
        description="Episode with Authorization: Bearer leaked-token",
        status=EpisodeStatus.DRAFT.value,
        source_type=EpisodeSourceType.TOPIC.value,
        story_id=story.id,
    )
    db.add(episode)
    db.commit()
    service = ShortsMetadataService(db)
    result = service.generate(series.id, episode.id, mode="deterministic")
    combined = f"{result.title} {result.description or ''} {' '.join(result.tags)}"
    assert "super-secret" not in combined
    assert "leaked-token" not in combined
    assert "token123" not in combined
    assert "***REDACTED***" in combined or "bearer" not in combined.lower()


def test_thumbnail_service_selects_valid_image(db, storage) -> None:
    series_id, episode_id, _story_id = _seed_episode(db)
    storage_key = f"thumbs/{series_id}/thumb.png"
    storage.put(storage_key, b"png")
    asset = Asset(
        series_id=series_id,
        asset_type=AssetType.STORYBOARD.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key=storage_key,
    )
    db.add(asset)
    db.commit()
    service = ThumbnailService(db, storage)
    selection = service.select(series_id, episode_id, asset.id)
    assert selection.asset_id == uuid.UUID(asset.id)


def test_thumbnail_rejects_wrong_series(db, storage) -> None:
    series_a, episode_a, _ = _seed_episode(db)
    series_b = Series(name="Other")
    db.add(series_b)
    db.flush()
    storage_key = f"thumbs/{series_a}/thumb.png"
    storage.put(storage_key, b"png")
    asset = Asset(
        series_id=series_a,
        asset_type=AssetType.IMAGE.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key=storage_key,
    )
    db.add(asset)
    db.commit()
    service = ThumbnailService(db, storage)
    with pytest.raises(ThumbnailError, match="does not belong"):
        service.select(series_b.id, episode_a, asset.id)


def test_thumbnail_rejects_video_asset(db, storage) -> None:
    series_id, episode_id, _ = _seed_episode(db)
    asset = Asset(
        series_id=series_id,
        asset_type=AssetType.VIDEO.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
    )
    db.add(asset)
    db.commit()
    service = ThumbnailService(db, storage)
    with pytest.raises(ThumbnailError, match="image-type"):
        service.select(series_id, episode_id, asset.id)


def test_thumbnail_rejects_missing_storage(db, storage) -> None:
    series_id, episode_id, _ = _seed_episode(db)
    asset = Asset(
        series_id=series_id,
        asset_type=AssetType.IMAGE.value,
        role=AssetRole.GENERATED.value,
        status=AssetStatus.AVAILABLE.value,
        storage_backend="memory",
        storage_key="missing-thumb.png",
    )
    db.add(asset)
    db.commit()
    service = ThumbnailService(db, storage)
    with pytest.raises(ThumbnailError, match="not available in storage"):
        service.select(series_id, episode_id, asset.id)


def test_llm_prompt_does_not_contain_secrets(db) -> None:
    series_id, episode_id, _ = _seed_episode(db)
    series = db.get(Series, series_id)
    episode = db.get(Episode, episode_id)
    story = db.get(Story, episode.story_id)
    story.source_content = "The vault password is password=abc123."
    db.commit()

    captured: dict = {}

    class RecordingFakeLLM:
        provider_id = "recording-fake"

        def generate(self, *, system_prompt=None, user_prompt, response_model=None):
            captured["user_prompt"] = user_prompt
            return FakeLLMProvider(
                response={
                    "title": "Safe",
                    "description": "Safe description.",
                    "tags": ["safe"],
                }
            ).generate(user_prompt=user_prompt, response_model=response_model)

    generator = LLMShortsMetadataGenerator(RecordingFakeLLM())
    generator.generate(series, episode, story)
    assert "abc123" not in captured["user_prompt"]
    assert "***REDACTED***" in captured["user_prompt"]
