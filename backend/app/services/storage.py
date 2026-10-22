"""Object storage: S3-compatible (S3 / R2 / MinIO) or local filesystem for development."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when a storage operation fails."""


class Storage(Protocol):
    """Interface for media object storage."""

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        """Store ``data`` under ``key``."""
        ...

    def signed_url(self, key: str, expires_seconds: int | None = None) -> str:
        """Return a time-limited URL for downloading ``key``."""
        ...

    def delete_object(self, key: str) -> None:
        """Delete ``key`` (no error if missing)."""
        ...

    def get_object(self, key: str) -> bytes:
        """Read the bytes stored under ``key``."""
        ...


def _safe_key(key: str) -> str:
    """Validate an object key (no absolute paths or traversal)."""
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
        raise StorageError(f"Invalid storage key: {key!r}")
    return str(path)


class S3Storage:
    """S3-compatible storage via boto3."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str = "us-east-1",
        public_endpoint_url: str | None = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        def make_client(endpoint: str | None) -> Any:
            return boto3.client(
                "s3",
                endpoint_url=endpoint or None,
                aws_access_key_id=access_key_id or None,
                aws_secret_access_key=secret_access_key or None,
                region_name=region,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )

        self.bucket = bucket
        self._client: Any = make_client(endpoint_url)
        # Presigned URLs are signed for a specific host, so sign with the public one
        # (e.g. MinIO reachable as http://minio:9000 inside Docker but not from a phone).
        self._signing_client: Any = (
            make_client(public_endpoint_url)
            if public_endpoint_url and public_endpoint_url != endpoint_url
            else self._client
        )

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        """Upload bytes to the bucket."""
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._client.put_object(
                Bucket=self.bucket, Key=_safe_key(key), Body=data, ContentType=content_type
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Failed to upload {key}") from exc

    def signed_url(self, key: str, expires_seconds: int | None = None) -> str:
        """Generate a presigned GET URL."""
        expires = expires_seconds or settings.SIGNED_URL_EXPIRE_SECONDS
        url: str = self._signing_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": _safe_key(key)},
            ExpiresIn=expires,
        )
        return url

    def delete_object(self, key: str) -> None:
        """Delete an object from the bucket."""
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._client.delete_object(Bucket=self.bucket, Key=_safe_key(key))
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Failed to delete {key}") from exc

    def get_object(self, key: str) -> bytes:
        """Download an object from the bucket."""
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = self._client.get_object(Bucket=self.bucket, Key=_safe_key(key))
            return bytes(response["Body"].read())
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Failed to read {key}") from exc


class LocalStorage:
    """Filesystem storage under ``MEDIA_ROOT`` served by the API at ``/media``."""

    def __init__(self, root: Path, base_url: str) -> None:
        self.root = root
        self.base_url = base_url.rstrip("/")

    def path_for(self, key: str) -> Path:
        """Absolute filesystem path for ``key``."""
        return self.root / _safe_key(key)

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        """Write bytes to disk (``content_type`` is inferred by the static server)."""
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def signed_url(self, key: str, expires_seconds: int | None = None) -> str:
        """Return the public ``/media`` URL (local dev has no signing)."""
        return f"{self.base_url}/media/{_safe_key(key)}"

    def delete_object(self, key: str) -> None:
        """Remove the file if it exists."""
        self.path_for(key).unlink(missing_ok=True)

    def get_object(self, key: str) -> bytes:
        """Read the file."""
        try:
            return self.path_for(key).read_bytes()
        except OSError as exc:
            raise StorageError(f"Failed to read {key}") from exc


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    """Return S3 storage when ``S3_BUCKET`` is set, otherwise local filesystem storage."""
    if settings.S3_BUCKET:
        return S3Storage(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
            public_endpoint_url=settings.S3_PUBLIC_ENDPOINT_URL,
        )
    if not settings.serve_local_media:
        logger.warning("S3_BUCKET not set in production; local media will not be served")
    return LocalStorage(settings.media_root, settings.PUBLIC_BASE_URL)
