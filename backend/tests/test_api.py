"""Tests for the API framework."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import AppError
from app.core.config import load_settings
from app.factory import create_app


def test_create_app_returns_fastapi_instance() -> None:
    """create_app returns a configured FastAPI instance."""
    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "AI Video Studio API"


def test_health_endpoint() -> None:
    """Application-level health endpoint returns a simple JSON response."""
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_v1_health_endpoint() -> None:
    """The /api/v1 router is mounted and exposes a framework health endpoint."""
    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "api": "v1"}


def test_root_endpoint() -> None:
    """Root endpoint remains usable."""
    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "AI Video Studio API"}


def test_cors_allowed_origin() -> None:
    """CORS middleware reflects configured allowed origins."""
    settings = load_settings({"CORS_ORIGINS": "http://localhost:3000,http://localhost:5173"})
    app = create_app(settings)
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_disallowed_origin() -> None:
    """Origins not in the configured list do not receive CORS headers."""
    settings = load_settings({"CORS_ORIGINS": "http://localhost:3000"})
    app = create_app(settings)
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "http://evil.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_app_error_handler() -> None:
    """AppError renders a predictable JSON error response."""
    app = create_app()

    @app.get("/trigger-error")
    async def trigger_error() -> None:
        raise AppError("TEST_ERROR", "Something went wrong.", status_code=418)

    client = TestClient(app)
    response = client.get("/trigger-error")

    assert response.status_code == 418
    body = response.json()
    assert body["error"]["code"] == "TEST_ERROR"
    assert body["error"]["message"] == "Something went wrong."
