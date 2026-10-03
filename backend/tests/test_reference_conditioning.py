"""P5-T04 Character/location/object reference conditioning tests."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.image import (
    FakeImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
    ReferenceAssetResolver,
    ReferenceConditioningError,
    StoryboardService,
)
from app.models import (
    Asset,
    Character,
    Episode,
    Location,
    Scene,
    Series,
    Shot,
    ShotSpecification,
    StoryObject,
)
from app.models.enums import AssetRole, AssetStatus, AssetType


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


class _RecordingFakeProvider:
    """Wraps the fake provider to capture the last request."""

    def __init__(self) -> None:
        self._fake = FakeImageGenerationProvider()
        self.last_request: ImageGenerationRequest | None = None

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.last_request = request
        return self._fake.generate(request)


class TestReferenceAssetResolver:
    def _seed_series(self, db: Session) -> Series:
        series = Series(name="Ref Series")
        db.add(series)
        db.commit()
        db.refresh(series)
        return series

    def _reference_asset(
        self,
        db: Session,
        series_id: str,
        asset_type: AssetType = AssetType.REFERENCE,
        status: AssetStatus = AssetStatus.AVAILABLE,
        character: Character | None = None,
        location: Location | None = None,
        obj: StoryObject | None = None,
    ) -> Asset:
        asset = Asset(
            series_id=series_id,
            asset_type=asset_type.value,
            role=AssetRole.REFERENCE.value,
            status=status.value,
        )
        if character:
            asset.characters.append(character)
        if location:
            asset.locations.append(location)
        if obj:
            asset.objects.append(obj)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    def test_resolve_character_reference(self, db: Session) -> None:
        series = self._seed_series(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()
        asset = self._reference_asset(db, series.id, character=character)

        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve(series.id, character_ids=[character.id])
        assert result == [asset.id]

    def test_resolve_location_reference(self, db: Session) -> None:
        series = self._seed_series(db)
        location = Location(series_id=series.id, name="Village")
        db.add(location)
        db.commit()
        asset = self._reference_asset(db, series.id, location=location)

        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve(series.id, location_ids=[location.id])
        assert result == [asset.id]

    def test_resolve_object_reference(self, db: Session) -> None:
        series = self._seed_series(db)
        obj = StoryObject(series_id=series.id, name="Sword")
        db.add(obj)
        db.commit()
        asset = self._reference_asset(db, series.id, obj=obj)

        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve(series.id, object_ids=[obj.id])
        assert result == [asset.id]

    def test_resolve_multiple_and_ordering(self, db: Session) -> None:
        series = self._seed_series(db)
        char_a = Character(series_id=series.id, name="A")
        char_b = Character(series_id=series.id, name="B")
        db.add_all([char_a, char_b])
        db.commit()
        asset_b = self._reference_asset(db, series.id, character=char_b)
        asset_a = self._reference_asset(db, series.id, character=char_a)

        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve(series.id, character_ids=[char_a.id, char_b.id])
        assert result == [asset_a.id, asset_b.id]

    def test_missing_canonical_entity(self, db: Session) -> None:
        series = self._seed_series(db)
        resolver = ReferenceAssetResolver(db)
        with pytest.raises(ReferenceConditioningError):
            resolver.resolve(series.id, character_ids=[str(uuid4())])

    def test_cross_series_canonical_entity(self, db: Session) -> None:
        series_a = self._seed_series(db)
        series_b = self._seed_series(db)
        character_b = Character(series_id=series_b.id, name="B")
        db.add(character_b)
        db.commit()

        resolver = ReferenceAssetResolver(db)
        with pytest.raises(ReferenceConditioningError):
            resolver.resolve(series_a.id, character_ids=[character_b.id])

    def test_missing_reference_asset_strict(self, db: Session) -> None:
        series = self._seed_series(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()

        resolver = ReferenceAssetResolver(db)
        with pytest.raises(ReferenceConditioningError):
            resolver.resolve(series.id, character_ids=[character.id], strict=True)

    def test_missing_reference_asset_not_strict(self, db: Session) -> None:
        series = self._seed_series(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()

        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve(series.id, character_ids=[character.id], strict=False)
        assert result == []

    def test_unavailable_asset_skipped_not_strict(self, db: Session) -> None:
        series = self._seed_series(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()
        self._reference_asset(db, series.id, character=character, status=AssetStatus.FAILED)

        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve(series.id, character_ids=[character.id], strict=False)
        assert result == []

    def test_unavailable_asset_strict_raises(self, db: Session) -> None:
        series = self._seed_series(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()
        self._reference_asset(db, series.id, character=character, status=AssetStatus.FAILED)

        resolver = ReferenceAssetResolver(db)
        with pytest.raises(ReferenceConditioningError):
            resolver.resolve(series.id, character_ids=[character.id], strict=True)

    def test_resolve_from_shot_spec(self, db: Session) -> None:
        series = self._seed_series(db)
        location = Location(series_id=series.id, name="Village")
        db.add(location)
        db.commit()
        asset = self._reference_asset(db, series.id, location=location)

        shot_spec = {
            "character_refs": [],
            "location_refs": [location.id],
            "object_refs": [],
        }
        resolver = ReferenceAssetResolver(db)
        result = resolver.resolve_from_shot_spec(series.id, shot_spec)
        assert result == [asset.id]


class TestStoryboardReferenceIntegration:
    def _seed_full_shot(self, db: Session) -> tuple[Series, Shot]:
        series = Series(name="Storyboard Ref Series")
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

        return series, shot

    def _link_asset(
        self,
        db: Session,
        series_id: str,
        character: Character,
    ) -> Asset:
        asset = Asset(
            series_id=series_id,
            asset_type=AssetType.REFERENCE.value,
            role=AssetRole.REFERENCE.value,
            status=AssetStatus.AVAILABLE.value,
        )
        asset.characters.append(character)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    def test_storyboard_uses_resolved_references(self, db: Session) -> None:
        series, shot = self._seed_full_shot(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()
        asset = self._link_asset(db, series.id, character)

        shot_spec = ShotSpecification(
            shot_id=shot.id,
            intent="Hero close-up",
            aspect_ratio="9:16",
            character_refs=[character.id],
        )
        db.add(shot_spec)
        db.commit()

        provider = _RecordingFakeProvider()
        service = StoryboardService(db, provider)
        result = service.generate_storyboard(str(series.id), str(shot.id))

        assert result.asset_type == AssetType.STORYBOARD.value
        assert provider.last_request is not None
        assert str(asset.id) in [str(aid) for aid in provider.last_request.reference_asset_ids]

    def test_storyboard_no_reference_assets_still_works(self, db: Session) -> None:
        series, shot = self._seed_full_shot(db)
        character = Character(series_id=series.id, name="Hero")
        db.add(character)
        db.commit()

        shot_spec = ShotSpecification(
            shot_id=shot.id,
            intent="Hero close-up",
            aspect_ratio="9:16",
            character_refs=[character.id],
        )
        db.add(shot_spec)
        db.commit()

        provider = FakeImageGenerationProvider()
        service = StoryboardService(db, provider)
        result = service.generate_storyboard(str(series.id), str(shot.id))
        assert result.asset_type == AssetType.STORYBOARD.value
