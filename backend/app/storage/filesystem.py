"""Filesystem-backed storage implementation."""

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageObject
from app.storage.exceptions import StorageNotFoundError, StorageSecurityError


class FilesystemStorage:
    """Local filesystem storage backend."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        """Resolve a logical key to a safe filesystem path."""
        if not key or key.startswith("/") or "\\" in key:
            raise StorageSecurityError(f"Invalid storage key: {key!r}")
        parts = [part for part in key.split("/") if part and part != "."]
        if not parts or ".." in parts:
            raise StorageSecurityError(f"Invalid storage key: {key!r}")
        target = (self._root / Path(*parts)).resolve()
        if not target.is_relative_to(self._root):
            raise StorageSecurityError(f"Storage key escapes root: {key!r}")
        return target

    @staticmethod
    def _meta_path(path: Path) -> Path:
        return path.parent / f"{path.name}.meta.json"

    @staticmethod
    def _md5(path: Path) -> str:
        hasher = hashlib.md5()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _read_meta(self, path: Path) -> tuple[str, dict[str, str]]:
        meta_path = self._meta_path(path)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            return meta.get("content_type", "application/octet-stream"), meta.get("metadata", {})
        return "application/octet-stream", {}

    def put(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        """Write an object to the filesystem."""
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.parent / f".{path.name}.tmp"

        if isinstance(data, bytes):
            temp_path.write_bytes(data)
        else:
            with temp_path.open("wb") as output:
                shutil.copyfileobj(data, output)

        temp_path.replace(path)
        meta_path = self._meta_path(path)
        meta_payload = {
            "content_type": content_type or "application/octet-stream",
            "metadata": metadata or {},
        }
        meta_path.write_text(json.dumps(meta_payload))

        size = path.stat().st_size
        etag = self._md5(path)
        return StorageObject(
            key=key,
            size=size,
            content_type=meta_payload["content_type"],
            etag=etag,
        )

    def get(self, key: str) -> BinaryIO:
        """Return a readable stream for the object."""
        path = self._safe_path(key)
        if not path.is_file():
            raise StorageNotFoundError(f"Object not found: {key!r}")
        return path.open("rb")

    def exists(self, key: str) -> bool:
        """Return True if the object exists."""
        try:
            path = self._safe_path(key)
        except StorageSecurityError:
            return False
        return path.is_file()

    def delete(self, key: str) -> None:
        """Delete the object and its sidecar metadata."""
        path = self._safe_path(key)
        if not path.is_file():
            raise StorageNotFoundError(f"Object not found: {key!r}")
        path.unlink()
        meta_path = self._meta_path(path)
        if meta_path.exists():
            meta_path.unlink()

    def get_metadata(self, key: str) -> StorageObject:
        """Return object metadata."""
        path = self._safe_path(key)
        if not path.is_file():
            raise StorageNotFoundError(f"Object not found: {key!r}")
        content_type, _metadata = self._read_meta(path)
        stat = path.stat()
        return StorageObject(
            key=key,
            size=stat.st_size,
            content_type=content_type,
            etag=self._md5(path),
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )
