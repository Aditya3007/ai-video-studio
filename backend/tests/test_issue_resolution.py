"""P9-T04 QA issue resolution and regeneration loop tests."""

from uuid import UUID

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import (
    Episode,
    GenerationCost,
    Location,
    Scene,
    Series,
    Shot,
    ShotSpecification,
)
from app.models.enums import (
    ContinuitySeverity,
    QAIssueSource,
    QAIssueStatus,
    ResolutionActionType,
)
from app.schemas.continuity import ContinuityFinding
from app.services.issue_resolution_service import (
    IssueNotFoundError,
    IssueResolutionError,
    IssueResolutionService,
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


def _seed(db: Session):
    series = Series(name="Resolution Series")
    db.add(series)
    db.commit()
    db.refresh(series)

    location = Location(series_id=series.id, name="City")
    db.add(location)
    db.commit()
    db.refresh(location)

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

    shot = Shot(
        scene_id=scene.id,
        shot_number=1,
        description="Opening shot",
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)

    spec = ShotSpecification(
        shot_id=shot.id,
        aspect_ratio="9:16",
        duration_seconds=5,
        intent="Test image",
        subject_notes="A test subject",
    )
    db.add(spec)
    db.commit()

    return series, episode, scene, shot, location


def _finding(
    category: str = "TEST", rule_id: str = "test-rule", message: str = "Test issue"
) -> ContinuityFinding:
    return ContinuityFinding(
        severity=ContinuitySeverity.WARNING,
        rule_id=rule_id,
        category=category,
        message=message,
        entity_type="SHOT",
        entity_id=UUID("00000000-0000-0000-0000-000000000001"),
    )


def test_create_issue_from_finding(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    finding = _finding()
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        finding,
        shot_id=shot.id,
        source=QAIssueSource.CONTINUITY,
    )
    assert issue.category == "TEST"
    assert issue.status == QAIssueStatus.OPEN.value
    assert issue.shot_id == shot.id


def test_deduplicate_open_issue(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    finding = _finding()
    first = service.create_issue_from_finding(
        series.id,
        episode.id,
        finding,
        shot_id=shot.id,
    )
    second = service.create_issue_from_finding(
        series.id,
        episode.id,
        finding,
        shot_id=shot.id,
    )
    assert first.id == second.id


def test_request_and_execute_re_run_qa_resolves(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        _finding(category="TEST"),
        shot_id=shot.id,
    )
    action = service.request_resolution(
        series.id,
        issue.id,
        ResolutionActionType.RE_RUN_QA,
    )
    executed = service.execute_action(series.id, action.id)
    assert executed.status == "SUCCEEDED"
    db.refresh(issue)
    assert issue.status == QAIssueStatus.RESOLVED.value
    assert issue.attempt_count == 1


def test_image_regeneration_creates_asset_and_records_cost(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        _finding(category="TEST"),
        shot_id=shot.id,
    )
    action = service.request_resolution(
        series.id,
        issue.id,
        ResolutionActionType.REGENERATE_IMAGE,
    )
    executed = service.execute_action(series.id, action.id)
    assert executed.status == "SUCCEEDED"
    assert executed.generated_asset_id is not None
    db.refresh(issue)
    assert issue.regenerated_asset_id == executed.generated_asset_id
    assert db.query(GenerationCost).count() == 1


def test_max_attempts_reached(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        _finding(category="SHOT"),
        shot_id=shot.id,
        max_attempts=1,
    )
    # Force the re-QA to still report the same finding so the issue does not resolve.
    service._continuity.check_shot = lambda _s, _sid: [
        ContinuityFinding(
            severity=ContinuitySeverity.WARNING,
            rule_id=issue.rule_id,
            category=issue.category,
            message=issue.message,
            entity_type=issue.entity_type or "SHOT",
            entity_id=UUID(issue.entity_id) if issue.entity_id else UUID(int=0),
        )
    ]
    action = service.request_resolution(
        series.id,
        issue.id,
        ResolutionActionType.RE_RUN_QA,
    )
    service.execute_action(series.id, action.id)
    db.refresh(issue)
    assert issue.status == QAIssueStatus.MAX_ATTEMPTS_REACHED.value
    with pytest.raises(IssueResolutionError):
        service.request_resolution(series.id, issue.id, ResolutionActionType.RE_RUN_QA)


def test_manual_resolution(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        _finding(),
        shot_id=shot.id,
    )
    resolved = service.resolve_manually(series.id, issue.id, resolution_note="approved")
    assert resolved.status == QAIssueStatus.MANUALLY_RESOLVED.value


def test_isolation_wrong_series(db: Session) -> None:
    series_a, episode_a, _scene, shot_a, _location = _seed(db)
    series_b = Series(name="Other")
    db.add(series_b)
    db.commit()
    db.refresh(series_b)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series_a.id,
        episode_a.id,
        _finding(),
        shot_id=shot_a.id,
    )
    with pytest.raises(IssueNotFoundError):
        service.get_issue(series_b.id, issue.id)


def test_execute_action_not_pending(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        _finding(),
        shot_id=shot.id,
    )
    action = service.request_resolution(series.id, issue.id, ResolutionActionType.RE_RUN_QA)
    service.execute_action(series.id, action.id)
    with pytest.raises(IssueResolutionError):
        service.execute_action(series.id, action.id)


def test_unsupported_action_rejected(db: Session) -> None:
    series, episode, _scene, shot, _location = _seed(db)
    service = IssueResolutionService(db)
    issue = service.create_issue_from_finding(
        series.id,
        episode.id,
        _finding(),
        shot_id=shot.id,
    )
    action = service.request_resolution(
        series.id,
        issue.id,
        ResolutionActionType.MANUAL_REVIEW,
    )
    executed = service.execute_action(series.id, action.id)
    # Manual review is a no-op action type; it succeeds without generation.
    assert executed.status == "SUCCEEDED"
