"""API utility helpers."""

from sqlalchemy import exc

from app.api.errors import AppError


def commit_or_409(session) -> None:
    """Commit the session or translate integrity errors into 409 responses."""
    try:
        session.commit()
    except exc.IntegrityError as integrity_error:
        session.rollback()
        raise AppError(
            "CONFLICT",
            "A resource with the same identifying fields already exists.",
            status_code=409,
        ) from integrity_error
