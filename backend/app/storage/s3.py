"""S3-compatible storage backend."""

from typing import Any, BinaryIO

from app.storage.base import StorageObject
from app.storage.exceptions import (
    StorageConfigurationError,
    StorageError,
    StorageNotFoundError,
)


class S3Storage:
    """S3-compatible object storage backend."""

    def __init__(
        self,
        bucket: str,
        endpoint: str | None,
        access_key: str | None,
        secret_key: str | None,
        region: str | None = None,
    ) -> None:
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise StorageConfigurationError(
                "boto3 and botocore are required for S3 storage"
            ) from exc

        if not access_key or not secret_key:
            raise StorageConfigurationError(
                "STORAGE_ACCESS_KEY and STORAGE_SECRET_KEY are required for S3 storage"
            )

        self._bucket = bucket
        self._client: Any = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name=region,
        )
        self._ClientError = ClientError

    @staticmethod
    def _body_to_bytes(data: BinaryIO | bytes) -> bytes:
        if isinstance(data, bytes):
            return data
        return data.read()

    def put(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        """Upload an object to S3-compatible storage."""
        body = self._body_to_bytes(data)
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": body,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        if metadata:
            kwargs["Metadata"] = metadata
        try:
            response = self._client.put_object(**kwargs)
        except self._ClientError as exc:
            raise StorageError(f"Failed to put {key!r}: {exc}") from exc
        etag = response.get("ETag", "").strip('"')
        return StorageObject(
            key=key,
            size=len(body),
            content_type=content_type or "application/octet-stream",
            etag=etag,
        )

    def get(self, key: str) -> BinaryIO:
        """Download an object from S3-compatible storage."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"]
        except self._ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise StorageNotFoundError(f"Object not found: {key!r}") from exc
            raise StorageError(f"Failed to get {key!r}: {exc}") from exc

    def exists(self, key: str) -> bool:
        """Return True if the object exists."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except self._ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404", "NotFound"}:
                return False
            raise StorageError(f"Failed to check {key!r}: {exc}") from exc

    def delete(self, key: str) -> None:
        """Delete an object from S3-compatible storage."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except self._ClientError as exc:
            raise StorageError(f"Failed to delete {key!r}: {exc}") from exc

    def get_metadata(self, key: str) -> StorageObject:
        """Return S3 object metadata."""
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except self._ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise StorageNotFoundError(f"Object not found: {key!r}") from exc
            raise StorageError(f"Failed to get metadata {key!r}: {exc}") from exc
        return StorageObject(
            key=key,
            size=response.get("ContentLength", 0),
            content_type=response.get("ContentType", "application/octet-stream"),
            etag=response.get("ETag", "").strip('"'),
            last_modified=response.get("LastModified"),
        )
