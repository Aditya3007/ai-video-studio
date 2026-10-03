"""P14-T03 unit economics dashboard tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import Episode, GenerationCost, Series
from app.models.enums import CostStatus
from app.services.episode_budget_service import EpisodeBudgetService
from app.services.generation_cost_service import CostComponent, GenerationCostService
from app.services.unit_economics_service import UnitEconomicsService


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


def _seed_series(db: Session, name: str = "Unit Economics Series") -> Series:
    series = Series(name=name)
    db.add(series)
    db.flush()
    return series


def _seed_episodes(db: Session, series: Series, titles: list[str]) -> list[Episode]:
    episodes = []
    for i, title in enumerate(titles, start=1):
        episode = Episode(
            series_id=series.id,
            title=title,
            episode_number=i,
            source_type="TOPIC",
        )
        db.add(episode)
        episodes.append(episode)
    db.flush()
    return episodes


def _record_cost(
    db: Session,
    series_id: str,
    episode_id: str,
    generation_type: str,
    provider: str,
    model: str,
    cost: str,
    recorded_at: datetime | None = None,
) -> None:
    service = GenerationCostService(db)
    service.record(
        series_id=series_id,
        generation_type=generation_type,
        provider=provider,
        model=model,
        components=[CostComponent(name="cost", quantity=1, unit="usd", unit_price=cost)],
        episode_id=episode_id,
        cost_status=CostStatus.ACTUAL,
        currency="USD",
    )
    if recorded_at:
        # Patch the recorded_at timestamp manually for time-range tests.
        cost_record = (
            db.query(GenerationCost)
            .filter(
                GenerationCost.series_id == series_id,
                GenerationCost.episode_id == episode_id,
                GenerationCost.provider == provider,
                GenerationCost.model == model,
            )
            .first()
        )
        if cost_record:
            cost_record.recorded_at = recorded_at
            db.flush()


def test_empty_series(db: Session) -> None:
    series = _seed_series(db)
    _seed_episodes(db, series, ["Ep 1"])
    db.commit()
    service = UnitEconomicsService(db)
    result = service.get_series_economics(series.id)
    assert result.total_actual_cost == "0"
    assert result.generation_count == 0
    assert result.episode_count == 0
    assert result.total_configured_budget == "0"
    assert result.average_cost_per_generation == "0"
    assert result.episode_summaries[0].actual_spend == "0"


def test_series_with_multiple_episodes_and_types(db: Session) -> None:
    series = _seed_series(db)
    episodes = _seed_episodes(db, series, ["Ep 1", "Ep 2"])
    _record_cost(db, series.id, episodes[0].id, "IMAGE", "fake", "fake-image", "1.5")
    _record_cost(db, series.id, episodes[0].id, "VIDEO", "fake", "fake-video", "2.5")
    _record_cost(db, series.id, episodes[1].id, "IMAGE", "fake", "fake-image", "0.5")
    _record_cost(db, series.id, episodes[1].id, "TTS", "fake", "fake-tts", "0.25")
    db.commit()
    service = UnitEconomicsService(db)
    result = service.get_series_economics(series.id)
    assert Decimal(result.total_actual_cost) == Decimal("4.75")
    assert result.generation_count == 4
    assert result.episode_count == 2
    assert Decimal(result.average_cost_per_generation) == Decimal("1.1875")
    assert len(result.cost_by_generation_type) == 3
    assert {b.value for b in result.cost_by_generation_type} == {"IMAGE", "VIDEO", "TTS"}
    assert {b.value for b in result.cost_by_provider} == {"fake"}
    assert {b.value for b in result.cost_by_model} == {"fake-image", "fake-video", "fake-tts"}


def test_budget_vs_actual_spend(db: Session) -> None:
    series = _seed_series(db)
    episodes = _seed_episodes(db, series, ["Ep 1"])
    EpisodeBudgetService(db).configure_budget(series.id, episodes[0].id, "100")
    _record_cost(db, series.id, episodes[0].id, "IMAGE", "fake", "fake-image", "25")
    _record_cost(db, series.id, episodes[0].id, "VIDEO", "fake", "fake-video", "25")
    db.commit()
    service = UnitEconomicsService(db)
    result = service.get_series_economics(series.id)
    assert Decimal(result.total_configured_budget) == Decimal("100")
    assert Decimal(result.total_actual_spend) == Decimal("50")
    assert Decimal(result.total_remaining_budget) == Decimal("50")
    assert Decimal(result.budget_utilization) == Decimal("0.5")

    ep = service.get_episode_economics(series.id, episodes[0].id)
    assert Decimal(ep.actual_spend) == Decimal("50")
    assert Decimal(ep.remaining_budget) == Decimal("50")
    assert ep.budget_status == "WITHIN_BUDGET"


def test_zero_budget_and_exhausted(db: Session) -> None:
    series = _seed_series(db)
    episodes = _seed_episodes(db, series, ["Ep 1"])
    EpisodeBudgetService(db).configure_budget(series.id, episodes[0].id, "0")
    db.commit()
    service = UnitEconomicsService(db)
    result = service.get_episode_economics(series.id, episodes[0].id)
    assert result.budget_amount == "0"
    assert result.budget_status == "EXHAUSTED"
    assert Decimal(result.utilization) == Decimal("0")


def test_active_reservation_not_double_counted(db: Session) -> None:
    series = _seed_series(db)
    episodes = _seed_episodes(db, series, ["Ep 1"])
    EpisodeBudgetService(db).configure_budget(series.id, episodes[0].id, "100")
    EpisodeBudgetService(db).check_and_reserve(
        series.id, episodes[0].id, "IMAGE", estimated_cost="10"
    )
    _record_cost(db, series.id, episodes[0].id, "IMAGE", "fake", "fake-image", "5")
    db.commit()
    service = UnitEconomicsService(db)
    result = service.get_series_economics(series.id)
    # Reservation is excluded from actual spend; only actual cost is spend.
    assert Decimal(result.total_actual_spend) == Decimal("5")
    assert Decimal(result.total_reserved) == Decimal("10")
    assert Decimal(result.total_remaining_budget) == Decimal("85")

    ep = service.get_episode_economics(series.id, episodes[0].id)
    assert Decimal(ep.active_reservation) == Decimal("10")
    assert Decimal(ep.available_budget) == Decimal("85")


def test_filter_generation_type(db: Session) -> None:
    series = _seed_series(db)
    episodes = _seed_episodes(db, series, ["Ep 1"])
    _record_cost(db, series.id, episodes[0].id, "IMAGE", "fake", "fake-image", "1")
    _record_cost(db, series.id, episodes[0].id, "VIDEO", "fake", "fake-video", "10")
    db.commit()
    service = UnitEconomicsService(db)
    from app.services.unit_economics_service import EconomicsFilter

    result = service.get_series_economics(
        series.id,
        EconomicsFilter(generation_type="IMAGE"),
    )
    assert Decimal(result.total_actual_cost) == Decimal("1")
    assert result.generation_count == 1
    assert result.cost_by_generation_type[0].value == "IMAGE"


def test_filter_time_range(db: Session) -> None:
    series = _seed_series(db)
    episodes = _seed_episodes(db, series, ["Ep 1"])
    now = datetime.now(UTC)
    _record_cost(db, series.id, episodes[0].id, "IMAGE", "fake", "fake-image", "1")
    _record_cost(
        db,
        series.id,
        episodes[0].id,
        "VIDEO",
        "fake",
        "fake-video",
        "10",
        recorded_at=now - timedelta(days=10),
    )
    db.commit()
    service = UnitEconomicsService(db)
    from app.services.unit_economics_service import EconomicsFilter

    result = service.get_series_economics(
        series.id,
        EconomicsFilter(start=now - timedelta(days=1), end=now + timedelta(days=1)),
    )
    assert Decimal(result.total_actual_cost) == Decimal("1")
    assert result.generation_count == 1


def test_series_isolation(db: Session) -> None:
    series_a = _seed_series(db, name="A")
    series_b = _seed_series(db, name="B")
    episodes_a = _seed_episodes(db, series_a, ["A1"])
    episodes_b = _seed_episodes(db, series_b, ["B1"])
    _record_cost(db, series_a.id, episodes_a[0].id, "IMAGE", "fake", "fake", "5")
    _record_cost(db, series_b.id, episodes_b[0].id, "IMAGE", "fake", "fake", "7")
    db.commit()
    service = UnitEconomicsService(db)
    result_a = service.get_series_economics(series_a.id)
    result_b = service.get_series_economics(series_b.id)
    assert Decimal(result_a.total_actual_cost) == Decimal("5")
    assert Decimal(result_b.total_actual_cost) == Decimal("7")


def test_api_series_economics(client: TestClient) -> None:
    response = client.post("/api/v1/series", json={"name": "API Series"})
    assert response.status_code == 201
    series = response.json()
    response = client.post(
        f"/api/v1/series/{series['id']}/episodes",
        json={"title": "E1", "episode_number": 1, "source_type": "TOPIC"},
    )
    assert response.status_code == 201
    episode = response.json()
    response = client.get(f"/api/v1/series/{series['id']}/economics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_actual_cost"] == "0"
    assert data["generation_count"] == 0
    assert any(e["episode_id"] == episode["id"] for e in data["episode_summaries"])


def test_api_episode_isolation(client: TestClient) -> None:
    s1 = client.post("/api/v1/series", json={"name": "S1"}).json()
    s2 = client.post("/api/v1/series", json={"name": "S2"}).json()
    e1 = client.post(
        f"/api/v1/series/{s1['id']}/episodes",
        json={"title": "E1", "episode_number": 1, "source_type": "TOPIC"},
    ).json()
    response = client.get(f"/api/v1/series/{s2['id']}/episodes/{e1['id']}/economics")
    assert response.status_code == 404
