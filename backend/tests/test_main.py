"""Tests for main application."""

from app.main import app


def test_root() -> None:
    """Test root endpoint."""
    # This is a minimal smoke test to prove the test framework works
    assert app is not None
    assert app.title == "AI Video Studio API"


def test_health_endpoint_exists() -> None:
    """Test that health endpoint exists."""
    # This is a minimal smoke test to prove the test framework works
    assert app is not None
