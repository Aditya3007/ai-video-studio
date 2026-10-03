"""Provider-neutral production audit and observability service."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.models.enums import AuditEventType, AuditStatus

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "auth_header",
    "authorization",
    "private_key",
    "credentials",
    "connection_string",
}

SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "private_key",
    "credentials",
    "connection_string",
)


class AuditServiceError(Exception):
    """Raised when audit persistence fails and the service is configured to raise."""


class AuditService:
    """Append-only production audit log backed by the existing database."""

    def __init__(self, db: Session, *, on_error: str = "raise") -> None:
        self._db = db
        self._on_error = on_error

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.lower().replace("-", "_")
        if normalized in SENSITIVE_KEYS:
            return True
        return any(sub in normalized for sub in SENSITIVE_SUBSTRINGS)

    @classmethod
    def _scrub(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: cls._redact_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._scrub(v) for v in value]
        if isinstance(value, str):
            return cls._redact_string(value)
        return value

    @classmethod
    def _redact_value(cls, key: str, value: Any) -> Any:
        if cls._is_sensitive_key(key):
            return "***REDACTED***"
        return cls._scrub(value)

    @classmethod
    def _redact_string(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        patterns = [
            (r"(Bearer\s+)[A-Za-z0-9_\-]+", r"\1***REDACTED***"),
            (
                r"(?i)(api[_-]?key\s*[:=]\s*)[^&\s,;]+",
                r"\1***REDACTED***",
            ),
            (r"(?i)(token\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
            (r"(?i)(password\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
        ]
        for pattern, repl in patterns:
            value = re.sub(pattern, repl, value)
        return value

    def record(
        self,
        *,
        series_id: str,
        event_type: AuditEventType | str,
        episode_id: str | None = None,
        scene_id: str | None = None,
        shot_id: str | None = None,
        asset_id: str | None = None,
        job_id: str | None = None,
        production_run_id: str | None = None,
        stage: str | None = None,
        status: AuditStatus | str | None = None,
        attempt: int | None = None,
        metadata: dict | None = None,
        error_message: str | None = None,
    ) -> AuditEvent | None:
        """Persist a sanitized audit event."""
        event = AuditEvent(
            series_id=series_id,
            episode_id=episode_id,
            scene_id=scene_id,
            shot_id=shot_id,
            asset_id=asset_id,
            job_id=job_id,
            production_run_id=production_run_id,
            event_type=str(event_type),
            stage=stage,
            status=str(status) if status is not None else None,
            attempt=attempt,
            timestamp=datetime.now(UTC),
            event_metadata=self._scrub(metadata),
            error_message=self._redact_string(error_message) if error_message else None,
        )
        try:
            self._db.add(event)
            self._db.flush()
            return event
        except Exception as exc:
            if self._on_error == "raise":
                raise AuditServiceError(f"Audit record failed: {exc}") from exc
            logger.warning("Audit record failed: %s", exc)
            return None

    def get_history(
        self,
        series_id: str,
        *,
        episode_id: str | None = None,
        production_run_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Return audit history for a series/episode/run in chronological order."""
        query = self._db.query(AuditEvent).filter_by(series_id=series_id)
        if episode_id:
            query = query.filter_by(episode_id=episode_id)
        if production_run_id:
            query = query.filter_by(production_run_id=production_run_id)
        return query.order_by(AuditEvent.timestamp.asc()).limit(limit).all()
