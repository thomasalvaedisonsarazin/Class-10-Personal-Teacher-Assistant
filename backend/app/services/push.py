"""Push notifications via the Expo push API, with a fake for dev/tests."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EXPO_BATCH_SIZE = 100


class PushSender(Protocol):
    """Interface for sending push notifications."""

    def send_push(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Send a notification to ``tokens``; return per-message ticket dicts."""
        ...


class ExpoPushSender:
    """Sends notifications through ``https://exp.host/--/api/v2/push/send``."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout

    def send_push(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """POST messages in batches of 100. Failures are logged, never raised."""
        tickets: list[dict[str, Any]] = []
        messages = [
            {"to": token, "title": title, "body": body, "data": data or {}, "sound": "default"}
            for token in tokens
        ]
        with httpx.Client(timeout=self.timeout) as client:
            for start in range(0, len(messages), EXPO_BATCH_SIZE):
                batch = messages[start : start + EXPO_BATCH_SIZE]
                try:
                    response = client.post(
                        self.url, json=batch, headers={"Accept": "application/json"}
                    )
                    response.raise_for_status()
                    tickets.extend(response.json().get("data", []))
                except (httpx.HTTPError, ValueError):
                    logger.warning("Expo push batch failed (%d messages)", len(batch))
                    tickets.extend({"status": "error"} for _ in batch)
        return tickets


class FakePushSender:
    """Records pushes in memory instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_push(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Record the push and return ``ok`` tickets."""
        self.sent.append({"tokens": list(tokens), "title": title, "body": body, "data": data})
        logger.info("Fake push to %d device(s): %s", len(tokens), title)
        return [{"status": "ok", "id": f"fake-{i}"} for i, _ in enumerate(tokens)]


_fake_singleton = FakePushSender()


def get_push_sender() -> PushSender:
    """Return the Expo sender when ``PUSH_ENABLED`` (and not testing), else the fake."""
    if settings.PUSH_ENABLED and not settings.is_test:
        return ExpoPushSender(settings.EXPO_PUSH_URL)
    return _fake_singleton


def send_push(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper: send via the configured push sender."""
    if not tokens:
        return []
    return get_push_sender().send_push(tokens, title, body, data)
