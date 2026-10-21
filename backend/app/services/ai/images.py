"""Storybook illustrations for lesson scenes (OpenAI image models) and an offline fake."""

from __future__ import annotations

import base64
import logging
from functools import lru_cache
from io import BytesIO
from typing import Literal, Protocol

from PIL import Image, ImageDraw

from app.config import settings

logger = logging.getLogger(__name__)

IMAGE_SIZE = "1536x1024"  # landscape 3:2; the players crop/pan it

# Fixed art direction + character sheet so every picture in every lesson looks alike.
STYLE_GUIDE = (
    "Flat 2D storybook illustration for a school lesson in Tamil Nadu, India. "
    "Calm, flat, solid colours (muted blue, sage green, soft teal, warm off-white, dark slate "
    "outlines), no gradients, clean simple shapes, friendly expressive faces, uncluttered "
    "background, gentle daylight. Characters when present: Kavya — Indian girl, 15, two black "
    "braids with navy ribbons, navy pinafore over a white short-sleeved shirt, black shoes; "
    "Arun — Indian boy, 15, short black hair, white short-sleeved shirt, navy trousers. "
    "Absolutely no text, words, captions, speech bubbles or watermarks. Scene: "
)


class ImageError(Exception):
    """Image generation failed."""


class ImageClient(Protocol):
    """Generates one illustration and returns JPEG bytes."""

    def generate(self, scene_prompt: str) -> bytes:
        """Return a JPEG illustration for ``scene_prompt``."""
        ...


class OpenAIImageClient:
    """OpenAI ``images.generate`` with a gpt-image model."""

    def __init__(
        self,
        api_key: str,
        model: str,
        quality: Literal["low", "medium", "high"],
        timeout: float = 180.0,
    ) -> None:
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self.model = model
        self.quality = quality

    def generate(self, scene_prompt: str) -> bytes:
        """Generate a landscape JPEG for the scene (style guide prepended)."""
        try:
            result = self._client.images.generate(
                model=self.model,
                prompt=STYLE_GUIDE + scene_prompt,
                size=IMAGE_SIZE,
                quality=self.quality,
                output_format="jpeg",
                output_compression=82,
                n=1,
            )
        except self._openai.OpenAIError as exc:
            logger.warning("Image generation failed: %s", type(exc).__name__)
            raise ImageError(f"Image request failed: {type(exc).__name__}") from exc
        data = result.data[0].b64_json if result.data else None
        if not data:
            raise ImageError("Image response was empty")
        return base64.b64decode(data)


class FakeImageClient:
    """Offline placeholder: a flat-colour card (used in tests and without an API key)."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, scene_prompt: str) -> bytes:
        """Return a small flat JPEG; records the prompt."""
        self.prompts.append(scene_prompt)
        image = Image.new("RGB", (384, 256), "#E8EEF5")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            [24, 24, 360, 232], radius=24, fill="#FFFFFF", outline="#3B6EA5", width=6
        )
        draw.ellipse([152, 88, 232, 168], fill="#4F8A6B")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()


_fake_singleton = FakeImageClient()


def get_fake_image_client() -> FakeImageClient:
    """Process-wide fake (inspect ``prompts`` in tests)."""
    return _fake_singleton


@lru_cache(maxsize=1)
def _openai_image_client() -> OpenAIImageClient:
    return OpenAIImageClient(settings.OPENAI_API_KEY, settings.IMAGE_MODEL, settings.IMAGE_QUALITY)


def get_image_client() -> ImageClient:
    """OpenAI images when enabled with a key (and not testing), else the fake."""
    if settings.IMAGES_ENABLED and settings.OPENAI_API_KEY and not settings.is_test:
        return _openai_image_client()
    return _fake_singleton
