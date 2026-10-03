"""P9-T02 AI visual/narrative QA tests."""

from uuid import UUID

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import Asset, Character, Episode, Location, Scene, Series, Shot, StoryObject
from app.models.enums import AIQAMode, AssetRole, AssetStatus, ContinuitySeverity
from app.schemas.ai_qa import AIQAFinding, AIQARequest, AIQAResult
from app.services.ai_qa_service import (
    AIQAProvider,
    AIQAProviderError,
    AIQAService,
    AIQAValidationError,
    FakeAIQAProvider,
)


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
    return session


@pytest.fixture
def db():
    session = _memory_db()
    try:
        yield session
    finally:
        session.close()


class RecordingProvider:
    """Records the last AIQARequest and returns a configurable result."""

    def __init__(self, result: AIQAResult) -> None:
        self.result = result
        self.last_request: AIQARequest | None = None

    def evaluate(self, request: AIQARequest) -> AIQAResult:
        self.last_request = request
        return self.result


def _seed(db: Session) -> tuple:
    series = Series(name="QA Series")
    db.add(series)
    db.commit()
    db.refresh(series)

    character = Character(series_id=series.id, name="Hero")
    location = Location(series_id=series.id, name="City")
    obj = StoryObject(series_id=series.id, name="Sword")
    db.add_all([character, location, obj])
    db.commit()
    for entity in [character, location, obj]:
        db.refresh(entity)

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
        location_id=location.id,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)

    shot = Shot(scene_id=scene.id, shot_number=1, description="Opening")
    db.add(shot)
    db.commit()
    db.refresh(shot)

    return series, episode, scene, shot, character, location, obj


def _make_finding(
    entity_id: str, rule_id: str = "ai-narrative-mismatch", category: str = "NARRATIVE"
) -> AIQAFinding:
    return AIQAFinding(
        severity=ContinuitySeverity.WARNING,
        rule_id=rule_id,
        category=category,
        message="AI detected a possible issue.",
        entity_type="EPISODE",
        entity_id=UUID(entity_id),
        confidence=0.85,
    )


class TestAIQAService:
    def test_narrative_episode_qa_returns_findings(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        finding = _make_finding(episode.id)
        provider = FakeAIQAProvider(findings=[finding])
        service = AIQAService(db, provider=provider)

        response = service.evaluate_episode(str(series.id), str(episode.id), AIQAMode.NARRATIVE)

        assert response.mode == AIQAMode.NARRATIVE
        assert len(response.findings) == 1
        assert response.findings[0].rule_id == "ai-narrative-mismatch"
        assert response.findings[0].source == "ai"
        assert response.provider == "fake"

    def test_visual_shot_qa_includes_asset_refs(self, db: Session) -> None:
        series, episode, scene, shot, _char, _loc, _obj = _seed(db)
        asset = Asset(
            series_id=series.id,
            asset_type="VIDEO",
            role=AssetRole.GENERATED.value,
            status=AssetStatus.AVAILABLE.value,
            storage_backend="filesystem",
            storage_key="shots/1.mp4",
            shot_id=shot.id,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        finding = _make_finding(shot.id, rule_id="ai-visual-mismatch", category="VISUAL")
        recording = RecordingProvider(AIQAResult(findings=[finding], provider="fake"))
        service = AIQAService(db, provider=recording)

        response = service.evaluate_shot(str(series.id), str(shot.id), AIQAMode.VISUAL)

        assert response.mode == AIQAMode.VISUAL
        assert recording.last_request is not None
        assert len(recording.last_request.context.asset_refs) == 1
        assert str(recording.last_request.context.asset_refs[0].asset_id) == asset.id

    def test_cross_series_finding_rejected(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        other = Series(name="Other")
        db.add(other)
        db.commit()
        db.refresh(other)

        finding = _make_finding(
            other.id,
            rule_id="ai-narrative-mismatch",
            category="NARRATIVE",
        )
        provider = FakeAIQAProvider(findings=[finding])
        service = AIQAService(db, provider=provider)

        with pytest.raises(AIQAValidationError):
            service.evaluate_episode(str(series.id), str(episode.id), AIQAMode.NARRATIVE)

    def test_invalid_category_rejected(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        finding = _make_finding(episode.id, category="UNKNOWN")
        provider = FakeAIQAProvider(findings=[finding])
        service = AIQAService(db, provider=provider)

        with pytest.raises(AIQAValidationError):
            service.evaluate_episode(str(series.id), str(episode.id), AIQAMode.NARRATIVE)

    def test_provider_failure_propagates(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        provider = FakeAIQAProvider(fail=True)
        service = AIQAService(db, provider=provider)

        with pytest.raises(AIQAProviderError):
            service.evaluate_episode(str(series.id), str(episode.id), AIQAMode.NARRATIVE)

    def test_not_found_isolation(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        from app.services.ai_qa_service import AIQANotFoundError

        service = AIQAService(db, provider=FakeAIQAProvider())
        with pytest.raises(AIQANotFoundError):
            service.evaluate_episode(
                str(series.id), "00000000-0000-0000-0000-000000000000", AIQAMode.NARRATIVE
            )


class TestAIQAProviderContract:
    def test_fake_provider_is_runtime_checkable(self) -> None:
        assert isinstance(FakeAIQAProvider(), AIQAProvider)


class TestAIQAAPI:
    def test_episode_qa_not_found(self, client) -> None:
        zero = str(UUID(int=0))
        response = client.get(f"/api/v1/series/{zero}/episodes/{zero}/qa?mode=NARRATIVE")
        assert response.status_code == 404
