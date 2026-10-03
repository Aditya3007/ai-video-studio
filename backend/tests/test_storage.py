"""Tests for the storage abstraction and filesystem backend."""

import io
import tempfile
from pathlib import Path

import pytest

from app.core.config import load_settings
from app.storage import FilesystemStorage, create_storage_backend
from app.storage.exceptions import (
    StorageConfigurationError,
    StorageNotFoundError,
    StorageSecurityError,
)


@pytest.fixture
def storage():
    """Provide a filesystem backend in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield FilesystemStorage(tmp)


def test_put_get_and_delete(storage: FilesystemStorage) -> None:
    """Round-trip write, read, and delete."""
    obj = storage.put(
        "series/a/test.txt",
        b"hello",
        content_type="text/plain",
    )
    assert obj.key == "series/a/test.txt"
    assert obj.size == 5
    assert obj.content_type == "text/plain"
    assert obj.etag is not None
    assert storage.exists("series/a/test.txt")

    handle = storage.get("series/a/test.txt")
    assert handle.read() == b"hello"
    handle.close()

    storage.delete("series/a/test.txt")
    assert not storage.exists("series/a/test.txt")


def test_nested_key(storage: FilesystemStorage) -> None:
    """Deep nested keys create directories and store files."""
    storage.put(
        "series/uuid/characters/uuid/references/image.png",
        b"\x89PNG",
        content_type="image/png",
    )
    assert storage.exists("series/uuid/characters/uuid/references/image.png")


def test_binary_data(storage: FilesystemStorage) -> None:
    """Arbitrary binary content is preserved exactly."""
    data = bytes(range(256))
    storage.put("bin", data)
    handle = storage.get("bin")
    assert handle.read() == data
    handle.close()


def test_empty_content(storage: FilesystemStorage) -> None:
    """Empty files can be stored and read."""
    storage.put("empty", b"")
    assert storage.exists("empty")
    assert storage.get("empty").read() == b""


def test_missing_object(storage: FilesystemStorage) -> None:
    """Accessing missing objects raises StorageNotFoundError."""
    with pytest.raises(StorageNotFoundError):
        storage.get("missing")
    with pytest.raises(StorageNotFoundError):
        storage.delete("missing")
    with pytest.raises(StorageNotFoundError):
        storage.get_metadata("missing")


def test_path_traversal_rejected(storage: FilesystemStorage) -> None:
    """Dangerous keys are rejected."""
    with pytest.raises(StorageSecurityError):
        storage.put("../../outside", b"bad")
    with pytest.raises(StorageSecurityError):
        storage.put("../../../etc/passwd", b"bad")
    with pytest.raises(StorageSecurityError):
        storage.put("/absolute/path", b"bad")


def test_metadata(storage: FilesystemStorage) -> None:
    """Metadata is stored and returned with objects."""
    storage.put("meta", b"x", content_type="text/plain", metadata={"foo": "bar"})
    meta = storage.get_metadata("meta")
    assert meta.content_type == "text/plain"
    assert meta.size == 1
    assert meta.etag is not None


def test_binary_io_stream(storage: FilesystemStorage) -> None:
    """BinaryIO streams can be stored and read back."""
    stream = io.BytesIO(b"stream")
    storage.put("stream", stream)
    handle = storage.get("stream")
    assert handle.read() == b"stream"
    handle.close()


def test_factory_default_filesystem() -> None:
    """Factory creates a filesystem backend by default."""
    with tempfile.TemporaryDirectory() as tmp:
        settings = load_settings({"STORAGE_LOCAL_ROOT": tmp})
        backend = create_storage_backend(settings)
        assert isinstance(backend, FilesystemStorage)


def test_factory_s3_requires_bucket() -> None:
    """S3 backend without a bucket raises a configuration error."""
    with pytest.raises(StorageConfigurationError):
        create_storage_backend(load_settings({"STORAGE_BACKEND": "s3"}))


def test_files_stay_under_root(storage: FilesystemStorage) -> None:
    """Written files are contained within the configured root."""
    storage.put("nested/file", b"data")
    root = Path(storage._root)
    assert (root / "nested" / "file").exists()
    assert not (root.parent / "file").exists()
