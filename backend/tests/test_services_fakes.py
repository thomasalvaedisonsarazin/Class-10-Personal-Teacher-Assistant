"""Fake service implementations work offline and are selected under test settings."""

import pytest
from pydantic import BaseModel, Field

from app.config import settings
from app.services.ai.llm import FakeLLMClient, get_fake_llm_client, get_llm_client
from app.services.ai.tts import FakeTTSClient, get_tts_client, split_text
from app.services.push import FakePushSender, get_push_sender, send_push
from app.services.storage import LocalStorage, get_storage
from app.workers import celery_app


class Slide(BaseModel):
    heading: str
    bullets: list[str]
    narration: str


class Explanation(BaseModel):
    title: str
    slides: list[Slide] = Field(min_length=1)
    summary: str
    difficulty: int | None = None


def test_settings_are_test_safe() -> None:
    assert settings.ENVIRONMENT == "test"
    assert settings.OPENAI_API_KEY == ""
    assert settings.TTS_PROVIDER == "fake"


def test_fake_llm_synthesises_valid_instance() -> None:
    client = get_llm_client()
    assert isinstance(client, FakeLLMClient)
    result = client.generate_json("system", "user", Explanation)
    assert isinstance(result, Explanation)
    assert result.slides[0].bullets
    assert client.calls[-1][2] is Explanation


def test_fake_llm_registry() -> None:
    fake = get_fake_llm_client()
    canned = Explanation(
        title="Canned",
        slides=[Slide(heading="h", bullets=["b"], narration="n")],
        summary="s",
    )
    fake.register(Explanation, lambda system, user: canned)
    assert fake.generate_json("s", "u", Explanation) is canned
    fake.unregister(Explanation)
    assert fake.generate_json("s", "u", Explanation).title != "Canned"


def test_fake_tts_returns_mp3() -> None:
    client = get_tts_client()
    assert isinstance(client, FakeTTSClient)
    audio = client.synthesize("Hello students.", "en")
    assert len(audio) > 100
    assert audio[:3] == b"ID3" or audio[0] == 0xFF


def test_split_text_respects_byte_limit() -> None:
    sentence = "இது ஒரு சோதனை. "  # Tamil
    text = sentence * 600
    chunks = split_text(text, max_bytes=4500)
    assert len(chunks) > 1
    assert all(len(c.encode("utf-8")) <= 4500 for c in chunks)
    assert "".join(chunks).replace(" ", "") == text.strip().replace(" ", "")


def test_local_storage_roundtrip() -> None:
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
    storage.put_object("lessons/1/audio.mp3", b"abc", "audio/mpeg")
    assert storage.path_for("lessons/1/audio.mp3").read_bytes() == b"abc"
    assert storage.signed_url("lessons/1/audio.mp3").endswith("/media/lessons/1/audio.mp3")
    storage.delete_object("lessons/1/audio.mp3")
    assert not storage.path_for("lessons/1/audio.mp3").exists()


def test_fake_push() -> None:
    sender = get_push_sender()
    assert isinstance(sender, FakePushSender)
    tickets = send_push(["ExponentPushToken[x]"], "Title", "Body", {"k": "v"})
    assert tickets[0]["status"] == "ok"
    assert sender.sent[-1]["title"] == "Title"


def test_celery_eager_in_tests() -> None:
    assert celery_app.conf.task_always_eager is True


def test_google_tts_key_sent_in_header_not_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API key must never appear in a request URL (URLs end up in logs)."""
    import base64

    import httpx

    from app.services.ai import tts

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"audioContent": base64.b64encode(b"mp3").decode()})

    real_client = httpx.Client
    monkeypatch.setattr(
        tts.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    assert tts.GoogleTTSClient("secret-key-123").synthesize("hello", "en") == b"mp3"
    assert "secret-key-123" not in str(seen[0].url)
    assert seen[0].headers["X-Goog-Api-Key"] == "secret-key-123"
