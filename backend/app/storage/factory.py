"""Storage backend factory."""

from app.core.config import Settings
from app.storage.exceptions import StorageConfigurationError
from app.storage.filesystem import FilesystemStorage
from app.storage.s3 import S3Storage


def create_storage_backend(settings: Settings) -> FilesystemStorage | S3Storage:
    """Create the configured storage backend."""
    backend = settings.storage_backend
    if backend == "filesystem":
        return FilesystemStorage(settings.storage_local_root)

    if backend == "s3":
        if not settings.storage_bucket:
            raise StorageConfigurationError("STORAGE_BUCKET is required when STORAGE_BACKEND=s3")
        access_key = (
            settings.storage_access_key.get_secret_value() if settings.storage_access_key else None
        )
        secret_key = (
            settings.storage_secret_key.get_secret_value() if settings.storage_secret_key else None
        )
        return S3Storage(
            bucket=settings.storage_bucket,
            endpoint=settings.storage_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=settings.storage_region,
        )

    raise StorageConfigurationError(f"Unknown storage backend: {backend}")
