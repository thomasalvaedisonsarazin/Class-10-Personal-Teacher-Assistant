"""Tests for object storage URL signing."""

from app.services.storage import S3Storage


def test_signed_url_uses_public_endpoint() -> None:
    storage = S3Storage(
        bucket="pta-media",
        endpoint_url="http://minio:9000",
        access_key_id="test",
        secret_access_key="test",
        public_endpoint_url="http://10.0.2.2:9000",
    )
    url = storage.signed_url("lessons/1/audio.mp3", expires_seconds=60)
    assert url.startswith("http://10.0.2.2:9000/pta-media/lessons/1/audio.mp3?")


def test_signed_url_defaults_to_internal_endpoint() -> None:
    storage = S3Storage(
        bucket="pta-media",
        endpoint_url="http://localhost:9000",
        access_key_id="test",
        secret_access_key="test",
    )
    assert storage.signed_url("a.mp3", expires_seconds=60).startswith(
        "http://localhost:9000/pta-media/a.mp3?"
    )
