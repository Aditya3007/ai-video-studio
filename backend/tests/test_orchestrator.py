"""Tests for the asynchronous production orchestration boundary."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.image import StoryboardError
from app.models import Episode, Scene, Series, Shot, ShotSpecification
from app.models.enums import (
    EpisodeSourceType,
    EpisodeStatus,
    ImageGenerationJobStatus,
)
from app.orchestration import (
    ImmediateWorker,
    JobTask,
    JobType,
    OrchestrationError,
    Orchestrator,
    ThreadedWorker,
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


@pytest.fixture
def db_factory(db):
    """Return a factory that creates a new session on the same test engine."""
    engine = db.bind
    testing_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session_factory


def _seed_shot(db) -> str:
    series = Series(name="Orchestrator Series")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        title="Episode 1",
        episode_number=1,
        status=EpisodeStatus.DRAFT.value,
        source_type=EpisodeSourceType.TOPIC.value,
    )
    db.add(episode)
    db.flush()
    scene = Scene(
        episode_id=episode.id,
        scene_number=1,
        sequence_order=0,
        title="Scene 1",
    )
    db.add(scene)
    db.flush()
    shot = Shot(
        scene_id=scene.id,
        shot_number=1,
        sequence_order=0,
        description="Test shot",
    )
    db.add(shot)
    db.flush()
    spec = ShotSpecification(
        shot_id=shot.id,
        intent="Establish the hero",
        framing="Medium close-up",
        composition="Rule of thirds",
        subject_notes="Hero looking determined",
        visual_direction="Golden hour lighting",
        aspect_ratio="16:9",
    )
    db.add(spec)
    db.commit()
    return series.id, shot.id


class _NoOpWorker:
    """Worker that records tasks but never executes them."""

    def __init__(self) -> None:
        self.tasks: list[JobTask] = []

    def enqueue(self, task: JobTask) -> None:
        self.tasks.append(task)

    def wait_for(self, job_id: str, timeout: float | None = None) -> None:
        return


def test_orchestrator_submit_image_immediate_worker(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    orchestrator = Orchestrator(db_factory=db_factory, worker=ImmediateWorker)
    job = orchestrator.submit_image_generation(db, series_id, shot_id)

    db.refresh(job)
    assert job.status == "SUCCEEDED"
    assert job.result_asset_ids is not None
    assert len(job.result_asset_ids) == 1


def test_orchestrator_submit_image_threaded_worker(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    worker = ThreadedWorker
    orchestrator = Orchestrator(db_factory=db_factory, worker=worker)
    job = orchestrator.submit_image_generation(db, series_id, shot_id)

    db.refresh(job)
    assert job.status == "QUEUED"

    orchestrator.wait_for(job.id, timeout=10)
    db.refresh(job)
    assert job.status == "SUCCEEDED"
    assert job.result_asset_ids is not None


def test_orchestrator_job_queued_state(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    orchestrator = Orchestrator(db_factory=db_factory, worker=_NoOpWorker())
    job = orchestrator.submit_image_generation(db, series_id, shot_id)

    db.refresh(job)
    assert job.status == "QUEUED"


def test_orchestrator_cancel_image_job(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    orchestrator = Orchestrator(db_factory=db_factory, worker=_NoOpWorker())
    job = orchestrator.submit_image_generation(db, series_id, shot_id)

    cancelled = orchestrator.cancel_image_generation(db, series_id, job.id)
    assert cancelled.status == "CANCELLED"


def test_orchestrator_series_isolation(db, db_factory) -> None:
    series_a_id, shot_a_id = _seed_shot(db)
    series_b = Series(name="Other Series")
    db.add(series_b)
    db.commit()

    orchestrator = Orchestrator(db_factory=db_factory, worker=_NoOpWorker())
    job = orchestrator.submit_image_generation(db, series_a_id, shot_a_id)

    with pytest.raises(StoryboardError):
        orchestrator.get_image_generation(db, series_b.id, job.id)


def test_orchestrator_get_image_job(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    orchestrator = Orchestrator(db_factory=db_factory, worker=_NoOpWorker())
    job = orchestrator.submit_image_generation(db, series_id, shot_id)

    retrieved = orchestrator.get_image_generation(db, series_id, job.id)
    assert retrieved.id == job.id


def _create_queued_image_job(db, db_factory, series_id, shot_id):
    orchestrator = Orchestrator(db_factory=db_factory, worker=_NoOpWorker())
    return orchestrator.submit_image_generation(db, series_id, shot_id)


def _executor(db_factory):
    return Orchestrator(db_factory=db_factory, worker=ImmediateWorker)


def test_duplicate_queued_job_execution_is_idempotent(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    executor = _executor(db_factory)

    task = JobTask(
        job_type=JobType.IMAGE_GENERATION,
        job_id=job.id,
        series_id=series_id,
    )
    executor._worker.enqueue(task)
    executor._worker.enqueue(task)

    db.refresh(job)
    assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
    assert len(job.result_asset_ids) == 1


def test_duplicate_running_job_is_skipped(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.RUNNING.value
    db.commit()

    executor = _executor(db_factory)
    executor._worker.enqueue(
        JobTask(
            job_type=JobType.IMAGE_GENERATION,
            job_id=job.id,
            series_id=series_id,
        )
    )

    db.refresh(job)
    assert job.status == ImageGenerationJobStatus.RUNNING.value


def test_succeeded_job_is_not_executed_again(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    executor = _executor(db_factory)
    executor._worker.enqueue(
        JobTask(
            job_type=JobType.IMAGE_GENERATION,
            job_id=job.id,
            series_id=series_id,
        )
    )
    db.refresh(job)
    asset_id = job.result_asset_ids[0]

    executor._worker.enqueue(
        JobTask(
            job_type=JobType.IMAGE_GENERATION,
            job_id=job.id,
            series_id=series_id,
        )
    )
    db.refresh(job)
    assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
    assert job.result_asset_ids == [asset_id]


def test_retry_failed_job_succeeds(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.FAILED.value
    job.attempts = 1
    db.commit()

    executor = _executor(db_factory)
    executor.retry_image_generation(db, series_id, job.id)
    db.refresh(job)

    assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
    assert job.attempts == 2


def test_retry_exhaustion_is_terminal(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.FAILED.value
    job.attempts = job.max_attempts
    db.commit()

    executor = _executor(db_factory)
    with pytest.raises(OrchestrationError):
        executor.retry_image_generation(db, series_id, job.id)


def test_cancelled_job_cannot_be_retried(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.CANCELLED.value
    db.commit()

    executor = _executor(db_factory)
    with pytest.raises(OrchestrationError):
        executor.retry_image_generation(db, series_id, job.id)


def test_resume_queued_job_executes(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)

    executor = _executor(db_factory)
    executor.resume_image_generation(db, series_id, job.id)
    db.refresh(job)

    assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
    assert len(job.result_asset_ids) == 1


def test_resume_stale_running_job(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.RUNNING.value
    db.commit()

    executor = _executor(db_factory)
    executor.resume_image_generation(db, series_id, job.id)
    db.refresh(job)

    assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
    assert job.attempts == 1


def test_resume_failed_job_with_remaining_attempts(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.FAILED.value
    job.attempts = 1
    db.commit()

    executor = _executor(db_factory)
    executor.resume_image_generation(db, series_id, job.id)
    db.refresh(job)

    assert job.status == ImageGenerationJobStatus.SUCCEEDED.value
    assert job.attempts == 2


def test_resume_completed_job_is_rejected(db, db_factory) -> None:
    series_id, shot_id = _seed_shot(db)
    job = _create_queued_image_job(db, db_factory, series_id, shot_id)
    job.status = ImageGenerationJobStatus.SUCCEEDED.value
    db.commit()

    executor = _executor(db_factory)
    with pytest.raises(OrchestrationError):
        executor.resume_image_generation(db, series_id, job.id)


def test_retry_and_resume_series_isolation(db, db_factory) -> None:
    series_a_id, shot_a_id = _seed_shot(db)
    series_b = Series(name="Other Series")
    db.add(series_b)
    db.commit()

    job = _create_queued_image_job(db, db_factory, series_a_id, shot_a_id)
    job.status = ImageGenerationJobStatus.FAILED.value
    job.attempts = 1
    db.commit()

    executor = _executor(db_factory)
    with pytest.raises(StoryboardError):
        executor.retry_image_generation(db, series_b.id, job.id)
    with pytest.raises(StoryboardError):
        executor.resume_image_generation(db, series_b.id, job.id)
