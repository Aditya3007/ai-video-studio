"""P9-T03 QA workflow orchestration tests."""

from uuid import UUID

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
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
from app.models.enums import AIQAMode, AssetRole, AssetStatus, ContinuitySeverity, QAWorkflowStatus
from app.schemas.ai_qa import AIQAFinding
from app.services.ai_qa_service import FakeAIQAProvider
from app.services.qa_workflow_service import QAWorkflowNotFoundError, QAWorkflowService


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


def _seed(db: Session) -> tuple:
    series = Series(name="Workflow Series")
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

    spec = ShotSpecification(
        shot_id=shot.id,
        aspect_ratio="9:16",
        duration_seconds=10,
        character_refs=[character.id],
        location_refs=[location.id],
        object_refs=[obj.id],
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)

    return series, episode, scene, shot, character, location, obj


def _ai_finding(
    entity_id: str, rule_id: str = "ai-narrative-mismatch", category: str = "NARRATIVE"
) -> AIQAFinding:
    return AIQAFinding(
        severity=ContinuitySeverity.WARNING,
        rule_id=rule_id,
        category=category,
        message="AI detected a possible issue.",
        entity_type="EPISODE",
        entity_id=UUID(entity_id),
        confidence=0.8,
    )


class TestQAWorkflowService:
    def test_pass_with_no_findings(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        service = QAWorkflowService(db)

        result = service.evaluate_episode(str(series.id), str(episode.id), ai_modes=[])

        assert result.status == QAWorkflowStatus.PASS
        assert result.counts.total == 0
        assert result.ai_failed is False

    def test_fail_with_deterministic_error(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed(db)
        shot.specification.character_refs = ["does-not-exist"]

        service = QAWorkflowService(db)
        result = service.evaluate_episode(str(series.id), str(episode.id), ai_modes=[])

        assert result.status == QAWorkflowStatus.FAIL
        assert result.counts.error >= 1
        assert result.counts.deterministic >= 1

    def test_warn_with_ai_finding(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        finding = _ai_finding(episode.id)
        provider = FakeAIQAProvider(findings=[finding])
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_episode(
            str(series.id), str(episode.id), ai_modes=[AIQAMode.NARRATIVE]
        )

        assert result.status == QAWorkflowStatus.WARN
        assert result.counts.ai >= 1
        assert any(f.source == "ai" for f in result.findings)

    def test_fail_precedes_warn(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed(db)
        shot.specification.character_refs = ["does-not-exist"]
        ai_finding = _ai_finding(episode.id)
        provider = FakeAIQAProvider(findings=[ai_finding])
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_episode(
            str(series.id),
            str(episode.id),
            ai_modes=[AIQAMode.NARRATIVE],
        )

        assert result.status == QAWorkflowStatus.FAIL
        assert result.counts.error >= 1
        assert result.counts.warning >= 1

    def test_deterministic_and_narrative_visual_combined(self, db: Session) -> None:
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

        narrative = _ai_finding(episode.id, rule_id="ai-story-mismatch", category="NARRATIVE")
        visual = _ai_finding(shot.id, rule_id="ai-visual-mismatch", category="VISUAL")
        provider = FakeAIQAProvider(findings=[narrative, visual])
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_episode(
            str(series.id),
            str(episode.id),
            ai_modes=[AIQAMode.NARRATIVE, AIQAMode.VISUAL],
        )

        assert result.status == QAWorkflowStatus.WARN
        assert result.counts.ai == 2
        sources = {f.source for f in result.findings}
        assert "ai" in sources

    def test_deduplication_of_duplicate_ai_findings(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        finding = _ai_finding(episode.id)
        provider = FakeAIQAProvider(findings=[finding])
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_episode(
            str(series.id),
            str(episode.id),
            ai_modes=[AIQAMode.NARRATIVE, AIQAMode.VISUAL],
        )

        assert result.counts.ai == 1
        assert result.counts.total == 1

    def test_ai_failure_keeps_deterministic_results(self, db: Session) -> None:
        series, episode, _scene, shot, _char, _loc, _obj = _seed(db)
        shot.specification.character_refs = ["does-not-exist"]
        provider = FakeAIQAProvider(fail=True)
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_episode(
            str(series.id),
            str(episode.id),
            ai_modes=[AIQAMode.NARRATIVE],
        )

        assert result.status == QAWorkflowStatus.FAIL
        assert result.counts.error >= 1
        assert result.ai_failed is True
        assert result.ai_error is not None

    def test_ai_failure_without_deterministic_is_degraded(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        provider = FakeAIQAProvider(fail=True)
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_episode(
            str(series.id),
            str(episode.id),
            ai_modes=[AIQAMode.NARRATIVE],
        )

        assert result.status == QAWorkflowStatus.DEGRADED
        assert result.ai_failed is True
        assert result.counts.error == 0

    def test_shot_workflow_with_visual(self, db: Session) -> None:
        _series, _episode, _scene, shot, _char, _loc, _obj = _seed(db)
        finding = _ai_finding(shot.id, rule_id="ai-visual-mismatch", category="VISUAL")
        provider = FakeAIQAProvider(findings=[finding])
        service = QAWorkflowService(db, ai_provider=provider)

        result = service.evaluate_shot(str(_series.id), str(shot.id), ai_modes=[AIQAMode.VISUAL])

        assert result.scope_type == "shot"
        assert result.status == QAWorkflowStatus.WARN
        assert result.counts.ai == 1

    def test_not_found_isolation(self, db: Session) -> None:
        series, episode, _scene, _shot, _char, _loc, _obj = _seed(db)
        other = Series(name="Other")
        db.add(other)
        db.commit()

        service = QAWorkflowService(db)
        with pytest.raises(QAWorkflowNotFoundError):
            service.evaluate_episode(str(other.id), str(episode.id), ai_modes=[])


class TestQAWorkflowAPI:
    def test_episode_workflow_not_found(self, client) -> None:
        zero = str(UUID(int=0))
        response = client.post(
            f"/api/v1/series/{zero}/episodes/{zero}/qa-workflow",
            json={"ai_modes": []},
        )
        assert response.status_code == 404
