"""Slides + narration → MP3 / MP4 using Pillow and FFmpeg (flat palette, no gradients)."""

from __future__ import annotations

import logging
import shutil
import subprocess  # noqa: S404 - ffmpeg/ffprobe are invoked with fixed argument lists
import tempfile
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.models.enums import Medium

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1280, 720
BACKGROUND = "#F7F5F0"  # palette.background
TEXT = "#1F2A37"  # palette.textPrimary
TEXT_MUTED = "#556170"  # palette.textSecondary
WORDS_PER_SECOND = 2.4  # fallback duration estimate when ffprobe is unavailable
VIDEO_FPS = 12
SLIDE_FADE_SECONDS = 0.4  # each scene fades in from the background colour
REVEAL_FADE_SECONDS = 0.3  # each bullet cross-fades in
EMOJI_SIZE = 220
EMOJI_FONTS: list[tuple[str, int | None]] = [
    ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109),  # bitmap font: fixed size
    ("C:/Windows/Fonts/seguiemj.ttf", None),
]

FONT_CANDIDATES: dict[Medium, dict[str, list[str]]] = {
    Medium.en: {
        "regular": [
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ],
        "bold": [
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ],
    },
    Medium.ta: {
        "regular": [
            "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansTamilUI-Regular.ttf",
            "C:/Windows/Fonts/Nirmala.ttc",
        ],
        "bold": [
            "/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansTamilUI-Bold.ttf",
            "C:/Windows/Fonts/NirmalaB.ttc",
            "C:/Windows/Fonts/Nirmala.ttc",
        ],
    },
}


class RenderError(Exception):
    """FFmpeg or image rendering failed."""


@dataclass(frozen=True)
class SlideText:
    """What is drawn on one slide."""

    heading: str
    bullets: Sequence[str]
    emoji: str = ""
    picture: bytes | None = None  # storybook illustration (JPEG) shown behind the caption


def ffmpeg_path() -> str | None:
    """Path to ffmpeg, or None when it is not installed."""
    return shutil.which("ffmpeg")


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(  # noqa: S603 - fixed binary + generated temp paths
            args, capture_output=True, timeout=settings.FFMPEG_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RenderError(f"{Path(args[0]).name} failed to run") from exc
    if result.returncode != 0:
        tail = result.stderr.decode("utf-8", "replace")[-400:]
        raise RenderError(f"{Path(args[0]).name} exited {result.returncode}: {tail}")
    return result


def audio_duration(mp3: bytes, narration: str) -> float:
    """Duration of an MP3 in seconds (ffprobe), else estimated from the narration."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        with tempfile.TemporaryDirectory(prefix="pta-dur-") as tmp:
            path = Path(tmp) / "a.mp3"
            path.write_bytes(mp3)
            try:
                out = _run(
                    [
                        ffprobe,
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "csv=p=0",
                        str(path),
                    ]
                ).stdout.decode()
                return max(float(out.strip()), 0.5)
            except (RenderError, ValueError):
                logger.warning("ffprobe could not read duration; estimating")
    return max(len(narration.split()) / WORDS_PER_SECOND, 1.0)


def concat_mp3(parts: Sequence[bytes]) -> bytes:
    """Join MP3 clips (re-encoded with ffmpeg when available, else frame concatenation)."""
    ffmpeg = ffmpeg_path()
    if not ffmpeg or len(parts) == 1:
        return b"".join(parts)
    with tempfile.TemporaryDirectory(prefix="pta-audio-") as tmp:
        root = Path(tmp)
        listing = []
        for i, part in enumerate(parts):
            clip = root / f"{i:03d}.mp3"
            clip.write_bytes(part)
            listing.append(f"file '{clip.as_posix()}'")
        (root / "list.txt").write_text("\n".join(listing), encoding="utf-8")
        out = root / "out.mp3"
        try:
            _run(
                [
                    ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(root / "list.txt"),
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "64k",
                    str(out),
                ]
            )
        except RenderError:
            logger.warning("ffmpeg audio concat failed; falling back to frame concatenation")
            return b"".join(parts)
        return out.read_bytes()


@lru_cache(maxsize=16)
def _font(medium: Medium, weight: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[medium][weight]:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    logger.warning("No %s %s font found; using Pillow default", medium, weight)
    return ImageFont.load_default(size=size)


TAMIL_BLOCK = (0x0B80, 0x0BFF)


def tamil_shaping_available() -> bool:
    """True when Pillow can shape Tamil (needs libraqm); without it Tamil glyphs break."""
    from PIL import features

    return bool(features.check("raqm"))


def contains_tamil(text: str) -> bool:
    """Whether ``text`` has any Tamil-script characters."""
    return any(TAMIL_BLOCK[0] <= ord(ch) <= TAMIL_BLOCK[1] for ch in text)


def _runs(text: str) -> list[tuple[bool, str]]:
    """Split text into (is_tamil, chunk) runs so each run uses a font that has its glyphs."""
    runs: list[tuple[bool, str]] = []
    for ch in text:
        tamil = TAMIL_BLOCK[0] <= ord(ch) <= TAMIL_BLOCK[1]
        if ch == " " and runs:
            tamil = runs[-1][0]  # spaces stay with the current run
        if runs and runs[-1][0] == tamil:
            runs[-1] = (tamil, runs[-1][1] + ch)
        else:
            runs.append((tamil, ch))
    return runs


class _Fonts:
    """Latin + Tamil font pair; draws mixed-script (Tanglish) lines run by run."""

    def __init__(self, weight: str, size: int) -> None:
        self.latin = _font(Medium.en, weight, size)
        self.tamil = _font(Medium.ta, weight, size)

    def draw(
        self, draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, fill: str
    ) -> None:
        x, y = xy
        for tamil, chunk in _runs(text):
            font = self.tamil if tamil else self.latin
            draw.text((x, y), chunk, font=font, fill=fill)
            x += draw.textlength(chunk, font=font)


def reveal_offsets(duration: float, bullet_count: int) -> list[float]:
    """Seconds into a slide at which each bullet appears (mirrored by the mobile player).

    The heading shows at 0; bullet ``k`` (1-based) appears at ``duration * k / (n + 1)``.
    """
    return [duration * k / (bullet_count + 1) for k in range(1, bullet_count + 1)]


@lru_cache(maxsize=64)
def _emoji_image(emoji: str) -> Image.Image | None:
    """Render a colour emoji to a square RGBA image, or None if no emoji font works."""
    for path, native in EMOJI_FONTS:
        if not Path(path).exists():
            continue
        size = native or EMOJI_SIZE
        try:
            font = ImageFont.truetype(path, size)
            canvas = Image.new("RGBA", (int(size * 1.5), int(size * 1.5)), (0, 0, 0, 0))
            ImageDraw.Draw(canvas).text(
                (size * 0.1, size * 0.1), emoji, font=font, embedded_color=True
            )
        except (OSError, ValueError):
            continue
        box = canvas.getbbox()
        if box is None:
            continue
        glyph = canvas.crop(box)
        scale = EMOJI_SIZE / max(glyph.size)
        return glyph.resize((max(1, int(glyph.width * scale)), max(1, int(glyph.height * scale))))
    return None


CARD_ALPHA = 238  # caption card: solid off-white, slightly see-through (no gradient)
KEN_BURNS_ZOOM = 0.08  # each picture slowly zooms in by 8% over its scene


def _card_frames(slide: SlideText, accent: str, index: int, total: int) -> list[bytes]:
    """Transparent overlay frames: a caption card at the bottom that fills in bullet by bullet."""
    heading_font = _Fonts("bold", 44)
    body_font = _Fonts("regular", 32)
    small_font = _Fonts("regular", 24)
    heading_lines = textwrap.wrap(slide.heading, width=48)[:2]
    bullet_lines = [textwrap.wrap(b, width=64)[:2] for b in slide.bullets]
    bullet_lines = [lines for lines in bullet_lines if lines]
    height = 40 + 56 * len(heading_lines) + 14 + sum(42 * len(b) + 10 for b in bullet_lines) + 26
    top = max(HEIGHT - 24 - height, HEIGHT // 2 - 40)
    left, right, bottom = 40, WIDTH - 40, HEIGHT - 24

    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    r, g, b = (int(BACKGROUND[i : i + 2], 16) for i in (1, 3, 5))
    draw.rounded_rectangle([left, top, right, bottom], radius=22, fill=(r, g, b, CARD_ALPHA))
    draw.rounded_rectangle([left, top, left + 10, bottom], radius=5, fill=accent)
    draw.rounded_rectangle([WIDTH - 150, 24, WIDTH - 40, 64], radius=20, fill=(r, g, b, CARD_ALPHA))
    small_font.draw(draw, (WIDTH - 124, 30), f"{index}/{total}", TEXT_MUTED)
    y = top + 28
    for line in heading_lines:
        heading_font.draw(draw, (76, y), line, TEXT)
        y += 56
    y += 14

    frames = [_png(base)]
    current = base.copy()
    for lines in bullet_lines:
        if y > bottom - 40:
            break
        draw = ImageDraw.Draw(current)
        draw.ellipse([78, y + 14, 92, y + 28], fill=accent)
        for line in lines:
            body_font.draw(draw, (110, y), line, TEXT)
            y += 42
        y += 10
        frames.append(_png(current))
    return frames


def render_slide_frames(slide: SlideText, accent: str, index: int, total: int) -> list[bytes]:
    """PNG frames for one slide: heading only, then one more bullet per frame.

    With a picture: transparent caption-card overlays (the picture moves underneath).
    Without: a flat full slide with an optional emoji bubble on the right.
    """
    if slide.picture is not None:
        return _card_frames(slide, accent, index, total)
    emoji = _emoji_image(slide.emoji) if slide.emoji else None
    heading_font = _Fonts("bold", 52)
    body_font = _Fonts("regular", 36)
    small_font = _Fonts("regular", 26)
    heading_width = 30 if emoji else 38
    bullet_width = 44 if emoji else 56

    base = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(base)
    draw.rectangle([0, 0, WIDTH, 16], fill=accent)
    if emoji is not None:
        cx, cy = WIDTH - 210, 300
        draw.ellipse(
            [cx - 160, cy - 160, cx + 160, cy + 160], fill="#FFFFFF", outline=accent, width=4
        )
        base.paste(emoji, (cx - emoji.width // 2, cy - emoji.height // 2), emoji)
    y = 80
    for line in textwrap.wrap(slide.heading, width=heading_width)[:2]:
        heading_font.draw(draw, (80, y), line, TEXT)
        y += 70
    y += 30
    small_font.draw(draw, (80, HEIGHT - 64), f"{index}/{total}", TEXT_MUTED)

    frames = [_png(base)]
    current = base.copy()
    for bullet in slide.bullets:
        lines = textwrap.wrap(bullet, width=bullet_width)[:3]
        if not lines or y > HEIGHT - 140:
            break
        draw = ImageDraw.Draw(current)
        draw.ellipse([84, y + 16, 100, y + 32], fill=accent)
        for line in lines:
            body_font.draw(draw, (124, y), line, TEXT)
            y += 50
        y += 18
        frames.append(_png(current))
    return frames


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _ken_burns(index: int, frame_count: int) -> str:
    """Slow zoom-in; odd scenes also pan left→right (filter for a 2560x1440 still)."""
    zoom = f"1+{KEN_BURNS_ZOOM}*on/{frame_count}"
    x = f"(iw-iw/zoom)*on/{frame_count}" if index % 2 else "(iw-iw/zoom)/2"
    return (
        "scale=2560:-2,crop=2560:1440:(iw-2560)/2:(ih-1440)/3,"
        f"zoompan=z='{zoom}':x='{x}':y='(ih-ih/zoom)/2':d=1:s={WIDTH}x{HEIGHT}:fps={VIDEO_FPS}"
    )


def _slide_segment(
    root: Path,
    i: int,
    frames: Sequence[bytes],
    mp3: bytes,
    duration: float,
    picture: bytes | None = None,
) -> Path:
    """Encode one animated slide with its narration.

    Bullets cross-fade in on time; with a picture, the overlay sits on a slow pan/zoom.
    """
    ffmpeg = ffmpeg_path()
    assert ffmpeg is not None  # noqa: S101 - checked by render_video
    reveal = reveal_offsets(duration, len(frames) - 1)
    starts = [0.0, *reveal]
    lengths = [b - a for a, b in zip(starts, [*starts[1:], duration], strict=True)]
    fade = min(REVEAL_FADE_SECONDS, min(lengths) / 2) if len(frames) > 1 else 0.0

    args = [ffmpeg, "-y", "-v", "error"]
    offset = 0
    if picture is not None:
        picture_path = root / f"s{i:03d}.jpg"
        picture_path.write_bytes(picture)
        args += ["-loop", "1", "-framerate", str(VIDEO_FPS), "-t", f"{duration:.3f}"]
        args += ["-i", str(picture_path)]
        offset = 1
    for k, png in enumerate(frames):
        frame_path = root / f"s{i:03d}f{k:02d}.png"
        frame_path.write_bytes(png)
        hold = lengths[k] + (fade if k < len(frames) - 1 else 0.0)
        args += ["-loop", "1", "-framerate", str(VIDEO_FPS), "-t", f"{hold:.3f}"]
        args += ["-i", str(frame_path)]
    audio_path = root / f"s{i:03d}.mp3"
    audio_path.write_bytes(mp3)
    args += ["-i", str(audio_path)]

    pix = "format=rgba," if picture is not None else ""
    chain: list[str] = [f"[{offset}:v]{pix}null[x0]"]
    last = "[x0]"
    for k in range(1, len(frames)):
        chain.append(f"[{offset + k}:v]{pix}null[f{k}]")
        chain.append(
            f"{last}[f{k}]xfade=transition=fade:duration={fade:.3f}:offset={starts[k]:.3f}[x{k}]"
        )
        last = f"[x{k}]"
    bg_colour = BACKGROUND.replace("#", "0x")
    if picture is not None:
        frame_count = max(int(duration * VIDEO_FPS), 1)
        chain.append(f"[0:v]{_ken_burns(i, frame_count)}[bg]")
        chain.append(f"[bg]{last}overlay=0:0:format=auto[ov]")
        last = "[ov]"
    chain.append(f"{last}fade=t=in:st=0:d={SLIDE_FADE_SECONDS}:color={bg_colour},format=yuv420p[v]")

    segment = root / f"seg{i:03d}.mp4"
    args += [
        "-filter_complex", ";".join(chain),
        "-map", "[v]", "-map", f"{offset + len(frames)}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-r", str(VIDEO_FPS),
        "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1",
        "-shortest", str(segment),
    ]  # fmt: skip
    _run(args)
    return segment


def render_video(
    slides: Sequence[Sequence[bytes]],
    audios: Sequence[bytes],
    durations: Sequence[float],
    pictures: Sequence[bytes | None] | None = None,
) -> bytes:
    """Build an MP4 where every slide animates in time with its narration clip.

    Args:
        slides: Per slide, the frames from :func:`render_slide_frames`
        audios: Per slide, the narration MP3
        durations: Per slide, the narration length in seconds
        pictures: Per slide, an optional storybook illustration (JPEG)

    Raises:
        RenderError: ffmpeg is missing or failed.
    """
    if not ffmpeg_path():
        raise RenderError("ffmpeg is not installed")
    if not slides or not (len(slides) == len(audios) == len(durations)):
        raise RenderError("Slides and audio clips do not match")
    with tempfile.TemporaryDirectory(prefix="pta-video-") as tmp:
        root = Path(tmp)
        pics = list(pictures) if pictures is not None else [None] * len(slides)
        segments = [
            _slide_segment(root, i, frames, mp3, max(duration, 1.0), pics[i])
            for i, (frames, mp3, duration) in enumerate(zip(slides, audios, durations, strict=True))
        ]
        listing = "\n".join(f"file '{seg.as_posix()}'" for seg in segments)
        (root / "list.txt").write_text(listing, encoding="utf-8")
        out = root / "lesson.mp4"
        ffmpeg = ffmpeg_path() or "ffmpeg"
        _run(
            [
                ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                "-i", str(root / "list.txt"),
                "-c", "copy", "-movflags", "+faststart", str(out),
            ]
        )  # fmt: skip
        return out.read_bytes()
