"""P14-T02 Episode budget and usage control tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.media_generation.image import (
    FakeImageGenerationProvider,
    ImageGenerationJobService,
)
from app.media_generation.tts import FakeTTSProvider
from app.models import Episode, Narration, Scene, Series, Shot, ShotSpecification, Voice
from app.models.enums import BudgetStatus, NarrationStatus
from app.services.episode_budget_service import (
    BudgetError,
    EpisodeBudgetService,
    InvalidBudgetError,
)
from app.services.generation_cost_service import CostComponent, GenerationCostService
from app.services.narration_generation_service import (
    NarrationGenerationError,
    NarrationGenerationService,
)
from app.storage import StorageObject


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


def _seed_series_episode(db: Session):
    series = Series(name="Budget Series")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        title="Episode 1",
        episode_number=1,
        source_type="TOPIC",
    )
    db.add(episode)
    db.flush()
    return series, episode


def _seed_shot(db: Session, episode_id: str, scene_number: int = 1, shot_number: int = 1):
    scene = Scene(
        episode_id=episode_id,
        scene_number=scene_number,
        sequence_order=scene_number - 1,
        title=f"Scene {scene_number}",
    )
    db.add(scene)
    db.flush()
    shot = Shot(
        scene_id=scene.id,
        shot_number=shot_number,
        sequence_order=shot_number - 1,
        description=f"Shot {shot_number}",
    )
    db.add(shot)
    db.flush()
    spec = ShotSpecification(
        shot_id=shot.id,
        intent="Establish the hero",
        framing="Medium close-up",
        composition="Rule of thirds",
        subject_notes="Hero",
        visual_direction="Golden hour",
        camera_notes="Static",
        aspect_ratio="9:16",
    )
    db.add(spec)
    db.flush()
    return shot


def _seed_voice_narration(db: Session, series_id: str, episode_id: str):
    voice = Voice(
        series_id=series_id,
        name="Narrator",
        voice_metadata={"provider": "fake", "voice_id": "fake-voice-1"},
    )
    db.add(voice)
    db.flush()
    narration = Narration(
        series_id=series_id,
        episode_id=episode_id,
        source_text="Hello world",
        voice_id=voice.id,
        status=NarrationStatus.PENDING.value,
    )
    db.add(narration)
    db.flush()
    return narration, voice


class FakeStorage:
    """In-memory storage backend for narration tests."""

    _objects: dict[str, bytes] = {}

    def put(self, key, data, content_type=None, metadata=None) -> StorageObject:
        payload = data if isinstance(data, bytes) else data.read()
        self._objects[key] = payload
        return StorageObject(
            key=key,
            size=len(payload),
            content_type=content_type or "application/octet-stream",
            etag="fake",
        )

    def get(self, key):
        return self._objects[key]

    def exists(self, key):
        return key in self._objects


def test_configure_and_get_budget(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    budget = service.configure_budget(
        series.id,
        episode.id,
        "100.00",
        currency="USD",
    )
    assert Decimal(budget.budget_amount) == Decimal("100.00")
    assert budget.cost_currency == "USD"
    assert budget.active is True

    retrieved = service.get_budget(series.id, episode.id)
    assert retrieved is not None
    assert Decimal(retrieved.budget_amount) == Decimal("100.00")


def test_invalid_and_negative_budget(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    with pytest.raises(InvalidBudgetError):
        service.configure_budget(series.id, episode.id, "-10")
    with pytest.raises(InvalidBudgetError):
        service.configure_budget(series.id, episode.id, "10", currency="US")


def test_update_budget_preserves_historical_costs(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series.id, episode.id, "100")
    cost_service = GenerationCostService(db)
    cost_service.record(
        series_id=series.id,
        generation_type="IMAGE",
        provider="fake",
        model="fake",
        components=[CostComponent(name="cost", quantity=1, unit="usd", unit_price="50")],
        episode_id=episode.id,
    )
    db.commit()
    service.configure_budget(series.id, episode.id, "40")
    usage = service.get_usage(series.id, episode.id)
    assert usage.spent == "50"
    assert usage.status == BudgetStatus.OVER_BUDGET.value


def test_check_and_reserve_within_budget(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series.id, episode.id, "10")
    result = service.check_and_reserve(
        series.id,
        episode.id,
        "IMAGE",
        estimated_cost="5",
    )
    assert result.allowed is True
    assert result.reason == "WITHIN_BUDGET"
    assert result.reservation_id is not None


def test_check_and_reserve_exceeds(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series.id, episode.id, "10")
    cost_service = GenerationCostService(db)
    cost_service.record(
        series_id=series.id,
        generation_type="IMAGE",
        provider="fake",
        model="fake",
        components=[CostComponent(name="cost", quantity=1, unit="usd", unit_price="8")],
        episode_id=episode.id,
    )
    db.commit()
    result = service.check_and_reserve(
        series.id,
        episode.id,
        "IMAGE",
        estimated_cost="5",
    )
    assert result.allowed is False
    assert result.reason == "BUDGET_EXCEEDED"


def test_check_no_budget_allows(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    result = service.check_and_reserve(
        series.id,
        episode.id,
        "IMAGE",
        estimated_cost="5",
    )
    assert result.allowed is True
    assert result.reason == "NO_BUDGET_CONFIGURED"
    assert result.reservation_id is None


def test_currency_mismatch(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series.id, episode.id, "10", currency="USD")
    result = service.check_and_reserve(
        series.id,
        episode.id,
        "IMAGE",
        estimated_cost="1",
        currency="EUR",
    )
    assert result.allowed is False
    assert result.reason == "CURRENCY_MISMATCH"


def test_usage_limit(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(
        series.id,
        episode.id,
        "100",
        usage_limits={"IMAGE": {"max_generations": 1}},
    )
    cost_service = GenerationCostService(db)
    cost_service.record(
        series_id=series.id,
        generation_type="IMAGE",
        provider="fake",
        model="fake",
        components=[CostComponent(name="cost", quantity=1, unit="usd", unit_price="1")],
        episode_id=episode.id,
    )
    db.commit()
    result = service.check_and_reserve(series.id, episode.id, "IMAGE", estimated_cost="1")
    assert result.allowed is False
    assert result.reason == "USAGE_LIMIT_EXCEEDED"


def test_reservation_settle_and_release(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series.id, episode.id, "10")
    result = service.check_and_reserve(series.id, episode.id, "IMAGE", estimated_cost="3")
    reservation_id = result.reservation_id
    assert result.reserved == "3"

    service.release_reservation(reservation_id)
    usage = service.get_usage(series.id, episode.id)
    assert usage.reserved == "0"

    result2 = service.check_and_reserve(series.id, episode.id, "IMAGE", estimated_cost="4")
    service.settle_reservation(result2.reservation_id, actual_cost="3.5")
    # Verify reservation is settled by re-checking usage reserved.
    usage = service.get_usage(series.id, episode.id)
    assert usage.reserved == "0"


def test_idempotent_reservation_by_correlation(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series.id, episode.id, "10")
    result1 = service.check_and_reserve(
        series.id,
        episode.id,
        "IMAGE",
        estimated_cost="2",
        correlation_id="same",
    )
    result2 = service.check_and_reserve(
        series.id,
        episode.id,
        "IMAGE",
        estimated_cost="2",
        correlation_id="same",
    )
    assert result1.reservation_id == result2.reservation_id


def test_image_job_blocked_by_usage_limit(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    shot1 = _seed_shot(db, episode.id, scene_number=1, shot_number=1)
    shot2 = _seed_shot(db, episode.id, scene_number=2, shot_number=1)
    db.commit()
    service = EpisodeBudgetService(db)
    service.configure_budget(
        series.id,
        episode.id,
        "100",
        usage_limits={"IMAGE": {"max_generations": 1}},
    )
    provider = FakeImageGenerationProvider()
    job_service = ImageGenerationJobService(db, provider)
    job1 = job_service.create_and_run(str(series.id), str(shot1.id))
    assert job1.status == "SUCCEEDED"

    job2 = job_service.create_and_run(str(series.id), str(shot2.id))
    assert job2.status == "FAILED"
    assert "USAGE_LIMIT_EXCEEDED" in str(job2.error_message)


def test_narration_generation_respects_budget(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    narration, _ = _seed_voice_narration(db, series.id, episode.id)
    db.commit()
    service = EpisodeBudgetService(db)
    service.configure_budget(
        series.id, episode.id, "0", usage_limits={"TTS": {"max_generations": 0}}
    )
    provider = FakeTTSProvider()  # type: ignore[abstract]
    storage = FakeStorage()
    gen_service = NarrationGenerationService(db, provider=provider, storage=storage)
    with pytest.raises(NarrationGenerationError):
        gen_service.generate(str(series.id), str(narration.id))


def test_cross_series_isolation(db: Session) -> None:
    series1, episode1 = _seed_series_episode(db)
    series2, episode2 = _seed_series_episode(db)
    service = EpisodeBudgetService(db)
    service.configure_budget(series1.id, episode1.id, "10")
    with pytest.raises(BudgetError):
        service.get_budget(series2.id, episode1.id)
    with pytest.raises(BudgetError):
        service.get_usage(series1.id, episode2.id)


def _series(client: TestClient, name: str = "Budget Series") -> dict:
    response = client.post("/api/v1/series", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _episode(client: TestClient, series_id: str) -> dict:
    response = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={"title": "Episode 1", "episode_number": 1, "source_type": "TOPIC"},
    )
    assert response.status_code == 201
    return response.json()


def test_api_configure_get_usage_check(client: TestClient) -> None:
    series = _series(client)
    episode = _episode(client, series["id"])

    response = client.get(f"/api/v1/series/{series['id']}/episodes/{episode['id']}/budget")
    assert response.status_code == 404

    response = client.put(
        f"/api/v1/series/{series['id']}/episodes/{episode['id']}/budget",
        json={"budget_amount": "50.00", "cost_currency": "USD"},
    )
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["budget_amount"]) == Decimal("50.00")

    response = client.get(f"/api/v1/series/{series['id']}/episodes/{episode['id']}/budget/usage")
    assert response.status_code == 200
    usage = response.json()
    assert usage["status"] == "WITHIN_BUDGET"

    response = client.post(
        f"/api/v1/series/{series['id']}/episodes/{episode['id']}/budget/check",
        json={"generation_type": "IMAGE", "estimated_cost": "10"},
    )
    assert response.status_code == 200
    check = response.json()
    assert check["allowed"] is True
    assert check["reason"] == "WITHIN_BUDGET"


def test_api_cross_series_isolation(client: TestClient) -> None:
    series1 = _series(client, name="S1")
    episode1 = _episode(client, series1["id"])
    series2 = _series(client, name="S2")
    episode2 = _episode(client, series2["id"])

    client.put(
        f"/api/v1/series/{series1['id']}/episodes/{episode1['id']}/budget",
        json={"budget_amount": "10"},
    )

    response = client.get(f"/api/v1/series/{series2['id']}/episodes/{episode1['id']}/budget")
    assert response.status_code == 404

    response = client.get(f"/api/v1/series/{series1['id']}/episodes/{episode2['id']}/budget/usage")
    assert response.status_code == 404
