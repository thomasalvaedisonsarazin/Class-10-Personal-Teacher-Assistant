"""Settings parsing that production relies on."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_list_settings_accept_comma_lists_and_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://admin.example.com, https://b.example.com")
    monkeypatch.setenv("ADMIN_EMAILS", '["Boss@Example.com"]')
    settings = Settings()
    assert settings.CORS_ORIGINS == ["https://admin.example.com", "https://b.example.com"]
    assert settings.ADMIN_EMAILS == ["boss@example.com"]


def _production(local_media: bool) -> Settings:
    return Settings(
        ENVIRONMENT="production",
        SECRET_KEY="k" * 40,
        DEV_LOGIN_ENABLED=False,
        EMAIL_PROVIDER="smtp",
        SMTP_HOST="smtp.example.com",
        LOCAL_MEDIA_IN_PRODUCTION=local_media,
    )


def test_local_media_is_served_in_production_only_when_enabled() -> None:
    assert _production(local_media=False).serve_local_media is False
    assert _production(local_media=True).serve_local_media is True
    assert Settings(ENVIRONMENT="development").serve_local_media is True
