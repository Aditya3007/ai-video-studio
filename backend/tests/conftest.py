"""Shared test fixtures."""

import socket
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import get_db
from app.db.base import Base
from app.main import app


def _enable_sqlite_fk(dbapi_connection, _connection_record):
    """Enable foreign-key enforcement for SQLite test connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def client():
    """Provide an isolated TestClient with a fresh in-memory database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_fk)
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail fast if a test attempts a real outbound network connection.

    Provider adapter tests must stay fully offline and must never spend real
    money on paid APIs (Gemini, Sarvam, Groq, ...). Opt in per module with
    ``@pytest.mark.usefixtures("block_network")`` so that any provider code
    which escapes its SDK/HTTP mock fails loudly instead of silently issuing a
    real request.
    """

    def _deny(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "Real network access attempted during tests. "
            "Mock the provider SDK/HTTP boundary instead."
        )

    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket.socket, "connect_ex", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    yield
