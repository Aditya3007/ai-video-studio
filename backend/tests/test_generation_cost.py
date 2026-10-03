"""P14-T01 Generation cost tracking tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

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
from app.media_generation.image.provider import (
    ImageGenerationResult,
    ImageReference,
    ImageUsage,
)
from app.media_generation.tts import FakeTTSProvider
from app.models import Episode, Narration, Scene, Series, Shot, ShotSpecification, Voice
from app.models.enums import CostStatus, GenerationType, NarrationStatus
from app.services.generation_cost_service import CostComponent, GenerationCostService
from app.services.narration_generation_service import NarrationGenerationService
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


class _FakeStorage:
    """In-memory storage backend for narration tests."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

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


def _seed_series_episode(db: Session):
    series = Series(name="Cost Series")
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


def _seed_shot(db: Session, series_id: str, episode_id: str):
    scene = Scene(
        episode_id=episode_id,
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
        description="Shot 1",
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


def _seed_narration(db: Session, series_id: str, episode_id: str):
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


def test_cost_calculation(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = GenerationCostService(db)
    components = [
        CostComponent(name="input_tokens", quantity=100, unit="token", unit_price="0.001"),
        CostComponent(name="output_tokens", quantity=50, unit="token", unit_price="0.002"),
    ]
    cost = service.record(
        series_id=series.id,
        generation_type=GenerationType.TEXT,
        provider="fake",
        model="fake-llm",
        components=components,
        episode_id=episode.id,
    )
    assert cost.total_cost == Decimal("0.2")
    assert cost.cost_currency == "USD"
    assert cost.cost_status == CostStatus.ACTUAL.value


def test_zero_cost_and_zero_usage(db: Session) -> None:
    series, _ = _seed_series_episode(db)
    service = GenerationCostService(db)
    cost = service.record(
        series_id=series.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[],
    )
    assert cost.total_cost == Decimal("0")


def test_idempotency_by_correlation_id(db: Session) -> None:
    series, _ = _seed_series_episode(db)
    service = GenerationCostService(db)
    correlation = str(uuid4())
    cost1 = service.record(
        series_id=series.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="1.5"),
        ],
        correlation_id=correlation,
    )
    cost2 = service.record(
        series_id=series.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="9.9"),
        ],
        correlation_id=correlation,
    )
    assert cost1.id == cost2.id
    assert cost1.total_cost == Decimal("1.5")


def test_series_total_and_aggregation(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = GenerationCostService(db)
    service.record(
        series_id=series.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="2.0"),
        ],
        episode_id=episode.id,
    )
    service.record(
        series_id=series.id,
        generation_type=GenerationType.TTS,
        provider="fake",
        model="fake-tts",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="0.5"),
        ],
        episode_id=episode.id,
    )
    db.commit()
    assert service.get_total_by_series(series.id) == Decimal("2.5")
    assert service.get_total_by_episode(series.id, episode.id) == Decimal("2.5")
    assert service.aggregate_by_generation_type(series.id) == {
        "IMAGE": Decimal("2.0"),
        "TTS": Decimal("0.5"),
    }
    assert service.aggregate_by_provider(series.id) == {"fake": Decimal("2.5")}


def test_cross_series_isolation(db: Session) -> None:
    series1, _ = _seed_series_episode(db)
    series2, _ = _seed_series_episode(db)
    service = GenerationCostService(db)
    service.record(
        series_id=series1.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="1.0"),
        ],
    )
    service.record(
        series_id=series2.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="3.0"),
        ],
    )
    db.commit()
    assert service.get_total_by_series(series1.id) == Decimal("1.0")
    assert service.get_total_by_series(series2.id) == Decimal("3.0")
    assert len(service.list_by_series(series1.id)) == 1


def test_record_from_image_result(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    service = GenerationCostService(db)
    result = ImageGenerationResult(
        images=[
            ImageReference(uri="fake://x.png", width=720, height=1280, content_type="image/png")
        ],
        provider="fake",
        model="fake-image",
        usage=ImageUsage(credits=1, cost_usd=0.05),
        request_id="req-1",
    )
    cost = service.record_from_image_result(
        series.id,
        result,
        episode_id=episode.id,
        job_id="job-1",
    )
    assert cost is not None
    assert cost.generation_type == GenerationType.IMAGE.value
    assert cost.total_cost == Decimal("0.05")
    assert cost.request_id == "req-1"


def test_image_job_records_generation_cost(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    shot = _seed_shot(db, series.id, episode.id)
    db.commit()
    provider = FakeImageGenerationProvider()
    service = ImageGenerationJobService(db, provider)
    job = service.create_and_run(str(series.id), str(shot.id))
    assert job.status == "SUCCEEDED"
    cost_service = GenerationCostService(db)
    costs = cost_service.get_by_job(series.id, str(job.id))
    assert len(costs) == 1
    assert costs[0].generation_type == GenerationType.IMAGE.value
    assert costs[0].provider == "fake"
    assert costs[0].asset_id is not None


def test_narration_records_generation_cost(db: Session) -> None:
    series, episode = _seed_series_episode(db)
    narration, _ = _seed_narration(db, series.id, episode.id)
    db.commit()
    provider = FakeTTSProvider()
    storage = _FakeStorage()
    service = NarrationGenerationService(db, provider=provider, storage=storage)
    service.generate(str(series.id), str(narration.id))
    cost_service = GenerationCostService(db)
    costs = cost_service.get_by_job(series.id, str(narration.id))
    assert len(costs) == 1
    assert costs[0].generation_type == GenerationType.TTS.value
    assert costs[0].episode_id == episode.id


def test_estimated_cost_status(db: Session) -> None:
    series, _ = _seed_series_episode(db)
    service = GenerationCostService(db)
    cost = service.record(
        series_id=series.id,
        generation_type=GenerationType.TEXT,
        provider="fake",
        model="fake-llm",
        components=[
            CostComponent(name="input_tokens", quantity=10, unit="token", unit_price="0.001"),
        ],
        cost_status=CostStatus.ESTIMATED,
    )
    assert cost.cost_status == CostStatus.ESTIMATED.value


def test_cost_filters_by_time_range(db: Session) -> None:
    series, _ = _seed_series_episode(db)
    service = GenerationCostService(db)
    service.record(
        series_id=series.id,
        generation_type=GenerationType.IMAGE,
        provider="fake",
        model="fake-image",
        components=[
            CostComponent(name="cost", quantity=1, unit="usd", unit_price="1.0"),
        ],
    )
    db.commit()
    start = datetime.now(UTC) - timedelta(hours=1)
    end = datetime.now(UTC) + timedelta(hours=1)
    results = service.get_time_range(series.id, start, end)
    assert len(results) == 1
    far_future = datetime.now(UTC) + timedelta(days=1)
    results = service.get_time_range(series.id, far_future, far_future + timedelta(hours=1))
    assert len(results) == 0


def _series(client: TestClient, name: str = "Cost Series") -> dict:
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


def _scene(client: TestClient, episode_id: str) -> dict:
    response = client.post(
        f"/api/v1/episodes/{episode_id}/scenes",
        json={"scene_number": 1, "sequence_order": 0, "title": "Scene 1"},
    )
    assert response.status_code == 201
    return response.json()


def _shot(client: TestClient, scene_id: str) -> dict:
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"shot_number": 1, "sequence_order": 0, "description": "Shot 1"},
    )
    assert response.status_code == 201
    return response.json()


def _spec(client: TestClient, scene_id: str, shot_id: str) -> dict:
    payload = {
        "intent": "Establish the hero",
        "framing": "Medium close-up",
        "composition": "Rule of thirds",
        "subject_notes": "Hero",
        "visual_direction": "Golden hour",
        "camera_notes": "Static",
        "aspect_ratio": "9:16",
    }
    response = client.post(
        f"/api/v1/scenes/{scene_id}/shots/{shot_id}/specification",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def test_api_list_series_costs(client: TestClient) -> None:
    series = _series(client)
    episode = _episode(client, series["id"])
    scene = _scene(client, episode["id"])
    shot = _shot(client, scene["id"])
    _spec(client, scene["id"], shot["id"])

    response = client.post(
        f"/api/v1/series/{series['id']}/shots/{shot['id']}/image-generation-jobs",
        json={},
    )
    assert response.status_code == 201

    response = client.get(f"/api/v1/costs/{series['id']}")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert len(data["costs"]) == 1
    assert data["costs"][0]["generation_type"] == "IMAGE"


def test_api_episode_costs_enforce_series_isolation(client: TestClient) -> None:
    series = _series(client)
    episode = _episode(client, series["id"])
    other_series = _series(client, name="Other")
    other_episode = _episode(client, other_series["id"])

    response = client.get(f"/api/v1/costs/{series['id']}/episodes/{other_episode['id']}")
    assert response.status_code == 404

    response = client.get(f"/api/v1/costs/{series['id']}/episodes/{episode['id']}")
    assert response.status_code == 200
