"""FastAPI application factory."""

import logging
from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.errors import register_exception_handlers
from app.core.config import Settings, get_settings


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _parse_cors_origins(value: str | None) -> list[str]:
    if not value:
        return []
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _configure_cors(app: FastAPI, origins: Sequence[str]) -> None:
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(origins),
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    _configure_logging(settings.log_level)

    app = FastAPI(
        title="AI Video Studio API",
        description="AI Video Studio backend API foundation.",
        version="0.0.1",
    )

    register_exception_handlers(app)
    _configure_cors(app, _parse_cors_origins(settings.cors_origins))

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Application-level health check."""
        return {"status": "healthy"}

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {"message": "AI Video Studio API"}

    return app
