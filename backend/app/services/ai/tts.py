"""Text-to-speech abstraction: Google Cloud TTS (API key) and an offline fake."""

from __future__ import annotations

import base64
import logging
import re
import shutil
import subprocess  # noqa: S404 - used only to invoke ffmpeg with fixed arguments
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
GOOGLE_MAX_BYTES = 4500

# medium -> (languageCode, preferred voice name or None for provider default)
VOICES: dict[str, tuple[str, str | None]] = {
    "en": ("en-IN", "en-IN-Neural2-A"),
    "ta": ("ta-IN", "ta-IN-Standard-A"),
}


class TTSError(Exception):
    """Raised when speech synthesis fails."""


class TTSClient(Protocol):
    """Interface for text-to-speech providers."""

    def synthesize(self, text: str, medium: str) -> bytes:
        """Synthesise ``text`` in the language for ``medium`` (``en``/``ta``); return MP3 bytes.

        Raises:
            TTSError: on provider failure.
        """
        ...


def split_text(text: str, max_bytes: int = GOOGLE_MAX_BYTES) -> list[str]:
    """Split ``text`` into chunks of at most ``max_bytes`` UTF-8 bytes on sentence boundaries.

    Sentences longer than the limit are split on whitespace, and as a last resort
    by characters.
    """
    text = text.strip()
    if not text:
        return []
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]

    sentences = [s for s in re.split(r"(?<=[.!?।])\s+|\n+", text) if s.strip()]
    pieces: list[str] = []
    for sentence in sentences:
        if len(sentence.encode("utf-8")) <= max_bytes:
            pieces.append(sentence)
            continue
        pieces.extend(_split_long(sentence, max_bytes))

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current} {piece}" if current else piece
        if len(candidate.encode("utf-8")) <= max_bytes:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks


def _split_long(sentence: str, max_bytes: int) -> list[str]:
    out: list[str] = []
    current = ""
    for word in sentence.split():
        while len(word.encode("utf-8")) > max_bytes:
            # Hard split a pathological "word" by characters.
            cut = len(word)
            while len(word[:cut].encode("utf-8")) > max_bytes:
                cut -= 1
            if current:
                out.append(current)
                current = ""
            out.append(word[:cut])
            word = word[cut:]
        candidate = f"{current} {word}" if current else word
        if len(candidate.encode("utf-8")) <= max_bytes:
            current = candidate
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    return out


class GoogleTTSClient:
    """Google Cloud Text-to-Speech via REST with an API key."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def synthesize(self, text: str, medium: str) -> bytes:
        """Synthesise MP3 audio, chunking long text and concatenating the MP3 frames."""
        language_code, voice_name = VOICES.get(medium, VOICES["en"])
        chunks = split_text(text)
        if not chunks:
            raise TTSError("Nothing to synthesise")
        audio = bytearray()
        with httpx.Client(timeout=self._timeout) as client:
            for chunk in chunks:
                audio.extend(self._synthesize_chunk(client, chunk, language_code, voice_name))
        return bytes(audio)

    def _synthesize_chunk(
        self, client: httpx.Client, text: str, language_code: str, voice_name: str | None
    ) -> bytes:
        voice: dict[str, str] = {"languageCode": language_code}
        if voice_name:
            voice["name"] = voice_name
        body = {
            "input": {"text": text},
            "voice": voice,
            "audioConfig": {"audioEncoding": "MP3"},
        }
        try:
            response = client.post(GOOGLE_TTS_URL, params={"key": self._api_key}, json=body)
            if response.status_code == 400 and voice_name:
                # Voice may be unavailable for this project/region: retry with default voice.
                body["voice"] = {"languageCode": language_code}
                response = client.post(GOOGLE_TTS_URL, params={"key": self._api_key}, json=body)
            response.raise_for_status()
            content = response.json().get("audioContent")
        except (httpx.HTTPError, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("Google TTS request failed (status=%s)", status)
            raise TTSError("Google TTS request failed") from exc
        if not content:
            raise TTSError("Google TTS returned no audio")
        return base64.b64decode(content)


# --------------------------------------------------------------------------- fake

# Minimal valid MPEG-1 Layer III frame (128 kbps, 44.1 kHz, silent), repeated.
_SILENT_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413
FALLBACK_SILENT_MP3 = _SILENT_FRAME * 38  # ~1 second


@lru_cache(maxsize=1)
def _silent_mp3() -> bytes:
    """Generate one second of silent MP3 via ffmpeg (cached); fall back to embedded bytes."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or settings.is_test:  # keep the test suite free of subprocesses
        return FALLBACK_SILENT_MP3
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "silence.mp3"
        try:
            subprocess.run(  # noqa: S603 - fixed argument list, no shell
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=24000:cl=mono",
                    "-t",
                    "1",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "32k",
                    "-y",
                    str(out),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
            data = out.read_bytes()
        except (OSError, subprocess.SubprocessError):
            logger.warning("ffmpeg silent MP3 generation failed; using embedded fallback")
            return FALLBACK_SILENT_MP3
    return data or FALLBACK_SILENT_MP3


class FakeTTSClient:
    """Offline TTS returning a short silent MP3; records calls for tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, medium: str) -> bytes:
        """Return silent MP3 bytes regardless of input."""
        if not text.strip():
            raise TTSError("Nothing to synthesise")
        self.calls.append((text, medium))
        return _silent_mp3()


_fake_singleton = FakeTTSClient()


def get_fake_tts_client() -> FakeTTSClient:
    """Return the process-wide fake TTS client."""
    return _fake_singleton


def get_tts_client() -> TTSClient:
    """Return the configured TTS client (Google when TTS_PROVIDER=google and a key exists)."""
    if settings.TTS_PROVIDER == "google" and settings.TTS_API_KEY and not settings.is_test:
        return GoogleTTSClient(settings.TTS_API_KEY, timeout=settings.TTS_TIMEOUT_SECONDS)
    if settings.TTS_PROVIDER == "azure":
        logger.warning("Azure TTS is not implemented; using fake TTS")
    return _fake_singleton
