"""P5-T02 Image generation provider boundary tests."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.image import (
    FakeImageGenerationProvider,
    ImageGenerationProviderFactory,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageGenerationService,
    ImageProviderAuthError,
    ImageProviderRateLimitError,
    ImageProviderUnavailableError,
    ImageRequestError,
)
from app.models import Asset, Character, Location, Series, StoryObject


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


class TestImageGenerationRequest:
    def test_valid_request(self) -> None:
        request = ImageGenerationRequest(
            prompt="A hero stands in a village square.",
            aspect_ratio="9:16",
            num_images=2,
        )
        assert request.prompt == "A hero stands in a village square."
        assert request.aspect_ratio == "9:16"
        assert request.num_images == 2

    def test_invalid_aspect_ratio(self) -> None:
        with pytest.raises(ValueError):
            ImageGenerationRequest(prompt="Test", aspect_ratio="not-a-ratio")

    def test_from_shot_specification(self) -> None:
        shot_spec = {
            "intent": "Establish the village",
            "framing": "Wide shot",
            "visual_direction": "Golden hour lighting",
            "aspect_ratio": "9:16",
            "character_refs": [],
            "location_refs": [],
            "object_refs": [],
            "output_constraints": {"width": 1080, "height": 1920},
            "extra": {"style": "cinematic"},
        }
        request = ImageGenerationRequest.from_shot_specification(shot_spec)
        assert "Establish the village" in request.prompt
        assert request.aspect_ratio == "9:16"
        assert request.width == 1080
        assert request.height == 1920
        assert request.options == {"style": "cinematic"}

    def test_prompt_override(self) -> None:
        shot_spec = {"intent": "", "aspect_ratio": "1:1"}
        request = ImageGenerationRequest.from_shot_specification(
            shot_spec, prompt_override="Custom prompt"
        )
        assert request.prompt == "Custom prompt"


class TestFakeImageGenerationProvider:
    def test_successful_generation(self) -> None:
        provider = FakeImageGenerationProvider()
        request = ImageGenerationRequest(prompt="A sword in the village.", aspect_ratio="9:16")
        result = provider.generate(request)
        assert isinstance(result, ImageGenerationResult)
        assert len(result.images) == 1
        assert result.images[0].content_type == "image/png"
        # 9:16 scaled so the short side is 1024 px.
        assert result.images[0].width == 1024
        assert result.images[0].height == 1820
        assert result.provider == "fake"
        assert result.usage.cost_usd == 0.0

    def test_multiple_images(self) -> None:
        provider = FakeImageGenerationProvider()
        request = ImageGenerationRequest(prompt="Hero", num_images=3)
        result = provider.generate(request)
        assert len(result.images) == 3
        assert result.images[0].uri != result.images[1].uri

    def test_empty_prompt_rejected(self) -> None:
        provider = FakeImageGenerationProvider()
        request = ImageGenerationRequest(prompt="")
        with pytest.raises(ImageRequestError):
            provider.generate(request)

    @pytest.mark.parametrize(
        "fail_mode,exc_type",
        [
            ("auth", ImageProviderAuthError),
            ("unavailable", ImageProviderUnavailableError),
            ("rate_limit", ImageProviderRateLimitError),
        ],
    )
    def test_failure_modes(self, fail_mode: str, exc_type: type[Exception]) -> None:
        provider = FakeImageGenerationProvider(fail_mode=fail_mode)
        request = ImageGenerationRequest(prompt="Test failure")
        with pytest.raises(exc_type):
            provider.generate(request)

    def test_provider_neutral_result(self) -> None:
        provider = FakeImageGenerationProvider()
        result = provider.generate(ImageGenerationRequest(prompt="Landscape"))
        assert all("fake" in image.uri for image in result.images)
        assert result.request_id.startswith("fake-req-")


class TestImageGenerationService:
    def _seed_series(self, db: Session) -> Series:
        series = Series(name="Image Series")
        db.add(series)
        db.commit()
        db.refresh(series)
        return series

    def test_valid_canonical_refs(self, db: Session) -> None:
        series = self._seed_series(db)
        character = Character(series_id=series.id, name="Hero")
        location = Location(series_id=series.id, name="Village")
        obj = StoryObject(series_id=series.id, name="Sword")
        db.add_all([character, location, obj])
        db.commit()

        provider = FakeImageGenerationProvider()
        service = ImageGenerationService(db, provider)
        request = ImageGenerationRequest(
            prompt="Hero in village",
            canonical_character_ids=[character.id],
            canonical_location_ids=[location.id],
            canonical_object_ids=[obj.id],
        )
        result = service.generate(str(series.id), request)
        assert len(result.images) == 1

    def test_cross_series_character_rejected(self, db: Session) -> None:
        series_a = self._seed_series(db)
        series_b = self._seed_series(db)
        character_b = Character(series_id=series_b.id, name="B")
        db.add(character_b)
        db.commit()

        provider = FakeImageGenerationProvider()
        service = ImageGenerationService(db, provider)
        request = ImageGenerationRequest(prompt="Cross", canonical_character_ids=[character_b.id])
        with pytest.raises(ImageRequestError):
            service.generate(str(series_a.id), request)

    def test_nonexistent_reference_asset_rejected(self, db: Session) -> None:
        series = self._seed_series(db)
        provider = FakeImageGenerationProvider()
        service = ImageGenerationService(db, provider)
        request = ImageGenerationRequest(prompt="Ref", reference_asset_ids=[uuid4()])
        with pytest.raises(ImageRequestError):
            service.generate(str(series.id), request)

    def test_reference_asset_other_series_rejected(self, db: Session) -> None:
        series_a = self._seed_series(db)
        series_b = self._seed_series(db)
        asset_b = Asset(
            series_id=series_b.id,
            asset_type="IMAGE",
            role="CANONICAL",
            status="AVAILABLE",
        )
        db.add(asset_b)
        db.commit()

        provider = FakeImageGenerationProvider()
        service = ImageGenerationService(db, provider)
        request = ImageGenerationRequest(prompt="Ref", reference_asset_ids=[asset_b.id])
        with pytest.raises(ImageRequestError):
            service.generate(str(series_a.id), request)

    def test_generate_from_shot_specification(self, db: Session) -> None:
        series = self._seed_series(db)
        shot_spec = {
            "intent": "Hero close-up",
            "aspect_ratio": "9:16",
            "character_refs": [],
            "location_refs": [],
            "object_refs": [],
        }
        provider = FakeImageGenerationProvider()
        service = ImageGenerationService(db, provider)
        result = service.generate_from_shot_specification(str(series.id), shot_spec)
        assert len(result.images) == 1


class TestImageGenerationProviderFactory:
    def test_factory_returns_fake_by_default(self) -> None:
        provider = ImageGenerationProviderFactory.create()
        assert isinstance(provider, FakeImageGenerationProvider)

    def test_factory_rejects_unknown_provider(self) -> None:
        settings = type("Settings", (), {"image_generation_provider": "unknown"})
        with pytest.raises(ValueError):
            ImageGenerationProviderFactory.create(settings())
