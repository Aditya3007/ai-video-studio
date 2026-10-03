"""Provider-neutral storage interface."""

from datetime import datetime
from typing import BinaryIO, Protocol

from pydantic import BaseModel, ConfigDict


class StorageObject(BaseModel):
    """Metadata describing a stored object."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    size: int
    content_type: str
    etag: str | None = None
    last_modified: datetime | None = None


class StorageBackend(Protocol):
    """Provider-neutral storage backend interface."""

    def put(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        """Store an object and return its metadata."""

    def get(self, key: str) -> BinaryIO:
        """Return a readable stream for the object."""

    def exists(self, key: str) -> bool:
        """Return True if the object exists."""

    def delete(self, key: str) -> None:
        """Delete the object."""

    def get_metadata(self, key: str) -> StorageObject:
        """Return object metadata without reading the body."""
