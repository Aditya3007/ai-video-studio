"""SQLAlchemy database foundation."""

import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def generate_uuid() -> str:
    """Generate a string UUID primary key."""
    return str(uuid.uuid4())


def _enable_sqlite_fk(dbapi_connection, _connection_record):
    """Enable SQLite foreign-key enforcement for every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _make_engine():
    settings = get_settings()
    database_url = settings.database_url or "sqlite:///:memory:"
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    new_engine = create_engine(database_url, connect_args=connect_args)
    event.listen(new_engine, "connect", _enable_sqlite_fk)
    return new_engine


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables from registered model metadata."""
    # Import models so they register with Base.metadata.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
