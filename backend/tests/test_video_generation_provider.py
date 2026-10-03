"""P6-T01 Video generation provider boundary tests."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.video import (
    FakeVideoGenerationProvider,
    VideoCapabilityError,
    VideoGenerationFailedError,
    VideoGenerationProvider,
    VideoGenerationProviderFactory,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoGenerationService,
    VideoProviderAuthError,
    VideoProviderRateLimitError,
    VideoProviderUnavailableError,
    VideoRequestError,
)
from app.models import Asset, Series
from app.models.enums import AssetStatus


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


class TestVideoGenerationRequestContract:
    def test_valid_request(self) -> None:
        request = VideoGenerationRequest(prompt="A hero runs through the city")
        assert request.prompt == "A hero runs through the city"

    def test_invalid_aspect_ratio_rejected(self) -> None:
        with pytest.raises(ValueError):
            VideoGenerationRequest(prompt="A hero runs through the city", aspect_ratio="16x9")

    def test_zero_dimension_rejected(self) -> None:
        with pytest.raises(ValueError):
            VideoGenerationRequest(prompt="A hero runs", width=0)

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValueError):
            VideoGenerationRequest(prompt="A hero runs", duration=-1.0)


class TestFakeVideoGenerationProvider:
    def test_deterministic_success(self) -> None:
        provider = FakeVideoGenerationProvider()
        request = VideoGenerationRequest(
            prompt="A hero runs through the city",
            aspect_ratio="9:16",
            duration=5.0,
            seed=42,
        )
        result = provider.generate(request)

        assert isinstance(result, VideoGenerationResult)
        assert len(result.videos) == 1
        video = result.videos[0]
        assert video.uri.startswith("fake://video/")
        assert video.duration == 5.0
        assert video.content_type == "video/mp4"
        assert video.width > 0 and video.height > 0
        assert result.provider == "fake"
        assert result.request_id is not None

    def test_empty_prompt_rejected(self) -> None:
        provider = FakeVideoGenerationProvider()
        with pytest.raises(VideoRequestError):
            provider.generate(VideoGenerationRequest(prompt=""))

    def test_fail_auth(self) -> None:
        provider = FakeVideoGenerationProvider(fail_mode="auth")
        with pytest.raises(VideoProviderAuthError):
            provider.generate(VideoGenerationRequest(prompt="A hero runs"))

    def test_fail_unavailable(self) -> None:
        provider = FakeVideoGenerationProvider(fail_mode="unavailable")
        with pytest.raises(VideoProviderUnavailableError):
            provider.generate(VideoGenerationRequest(prompt="A hero runs"))

    def test_fail_rate_limit(self) -> None:
        provider = FakeVideoGenerationProvider(fail_mode="rate_limit")
        with pytest.raises(VideoProviderRateLimitError):
            provider.generate(VideoGenerationRequest(prompt="A hero runs"))

    def test_fail_generation(self) -> None:
        provider = FakeVideoGenerationProvider(fail_mode="generation")
        with pytest.raises(VideoGenerationFailedError):
            provider.generate(VideoGenerationRequest(prompt="A hero runs"))

    def test_fail_capability(self) -> None:
        provider = FakeVideoGenerationProvider(fail_mode="capability")
        with pytest.raises(VideoCapabilityError):
            provider.generate(VideoGenerationRequest(prompt="A hero runs"))


class TestVideoGenerationProviderFactory:
    def test_factory_returns_fake_provider(self) -> None:
        provider = VideoGenerationProviderFactory.create()
        assert isinstance(provider, FakeVideoGenerationProvider)
        assert isinstance(provider, VideoGenerationProvider)

    def test_factory_unknown_provider(self) -> None:
        settings = type("Settings", (), {"video_generation_provider": "unknown"})()
        with pytest.raises(ValueError):
            VideoGenerationProviderFactory.create(settings)


class TestVideoGenerationService:
    def test_service_invokes_provider(self, db: Session) -> None:
        series = Series(name="Video Series")
        db.add(series)
        db.commit()

        provider = FakeVideoGenerationProvider()
        service = VideoGenerationService(db, provider)
        result = service.generate(
            str(series.id),
            VideoGenerationRequest(prompt="A hero runs", aspect_ratio="9:16"),
        )
        assert result.videos

    def test_service_rejects_missing_series(self, db: Session) -> None:
        provider = FakeVideoGenerationProvider()
        service = VideoGenerationService(db, provider)
        with pytest.raises(VideoRequestError):
            service.generate(
                "00000000-0000-0000-0000-000000000000",
                VideoGenerationRequest(prompt="A hero runs"),
            )

    def test_service_rejects_cross_series_reference(self, db: Session) -> None:
        series_a = Series(name="A")
        series_b = Series(name="B")
        db.add_all([series_a, series_b])
        db.commit()

        asset_b = Asset(
            series_id=series_b.id,
            asset_type="STORYBOARD",
            status=AssetStatus.AVAILABLE.value,
        )
        db.add(asset_b)
        db.commit()

        provider = FakeVideoGenerationProvider()
        service = VideoGenerationService(db, provider)
        with pytest.raises(VideoRequestError):
            service.generate(
                str(series_a.id),
                VideoGenerationRequest(
                    prompt="A hero runs",
                    reference_asset_ids=[asset_b.id],
                ),
            )

    def test_no_provider_sdk_imported(self) -> None:
        import sys

        for name in ["runway", "kling", "sora", "veo", "luma"]:
            assert name not in sys.modules
