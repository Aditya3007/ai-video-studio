"""FastAPI dependencies."""

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.storage import StorageBackend, create_storage_backend


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


@lru_cache
def _storage_backend() -> StorageBackend:
    """Create and cache the configured storage backend."""
    return create_storage_backend(get_settings())


def get_storage() -> Generator[StorageBackend, None, None]:
    """Yield the configured storage backend."""
    yield _storage_backend()


StorageDep = Annotated[StorageBackend, Depends(get_storage)]
