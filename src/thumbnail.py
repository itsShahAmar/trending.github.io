"""
thumbnail.py — Generate eye-catching 1280 × 720 JPEG thumbnails using Pillow.

Creates a gradient background with large bold title text, and a
topic-relevant emoji / icon as a visual accent.
"""

import logging
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Thumbnail dimensions (YouTube standard)
THUMB_W = 1280
THUMB_H = 720

# Colour palette
_BG_COLOR_TOP = (20, 20, 60)       # deep navy
_BG_COLOR_BOTTOM = (180, 10, 10)   # deep red
_ACCENT_COLOR = (255, 215, 0)      # gold / yellow
_TEXT_COLOR = (255, 255, 255)      # white


def _make_gradient(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    """Create a vertical linear gradient image."""
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top[0] + t * (bottom[0] - top[0]))
        g = int(top[1] + t * (bottom[1] - top[1]))
        b = int(top[2] + t * (bottom[2] - top[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Attempt to load a TrueType font; fall back to the default bitmap font."""
    font_candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    logger.warning("No TrueType font found; using default bitmap font")
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    """Break *text* into lines that fit within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _topic_emoji(topic: str) -> str:
    """Return a simple emoji that loosely matches the topic keyword."""
    topic_lower = topic.lower()
    mapping = [
        (["ai", "artificial intelligence", "robot", "tech"], "🤖"),
        (["space", "nasa", "rocket", "planet", "star"], "🚀"),
        (["money", "finance", "crypto", "stock", "invest"], "💰"),
        (["health", "fitness", "gym", "workout", "diet"], "💪"),
        (["food", "cook", "recipe", "eat", "restaurant"], "🍔"),
        (["travel", "vacation", "trip", "adventure"], "✈️"),
        (["science", "research", "discover", "experiment"], "🔬"),
        (["music", "song", "artist", "album", "concert"], "🎵"),
        (["sport", "game", "football", "basketball", "soccer"], "⚽"),
        (["news", "world", "politics", "election"], "📰"),
    ]
    for keywords, emoji in mapping:
        if any(kw in topic_lower for kw in keywords):
            return emoji
    return "🔥"  # default


def create_thumbnail(title: str, topic: str) -> Path:
    """Generate a 1280 × 720 JPEG thumbnail for the given video *title*.

    Args:
        title: The video title to display prominently.
        topic: The trending topic (used for emoji selection).

    Returns:
        Path to the saved JPEG thumbnail file.
    """
    img = _make_gradient(THUMB_W, THUMB_H, _BG_COLOR_TOP, _BG_COLOR_BOTTOM)
    draw = ImageDraw.Draw(img)

    # Accent bar at the bottom
    draw.rectangle([(0, THUMB_H - 80), (THUMB_W, THUMB_H)], fill=_ACCENT_COLOR)

    # Emoji (large, top-left region)
    emoji = _topic_emoji(topic)
    emoji_font = _load_font(140)
    try:
        draw.text((60, 40), emoji, font=emoji_font, fill=_ACCENT_COLOR)
    except Exception:  # noqa: BLE001
        # Some default fonts can't render emoji; silently skip
        pass

    # Title text
    title_font = _load_font(90)
    max_text_w = THUMB_W - 120
    lines = _wrap_text(title.upper(), title_font, max_text_w)
    line_height = 105
    total_text_h = len(lines) * line_height
    start_y = (THUMB_H - total_text_h) // 2

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        # Drop shadow
        draw.text((62, y + 4), line, font=title_font, fill=(0, 0, 0))
        draw.text((60, y), line, font=title_font, fill=_TEXT_COLOR)

    # Channel watermark on accent bar
    watermark_font = _load_font(40)
    draw.text((60, THUMB_H - 62), "▶ Subscribe for more", font=watermark_font, fill=(20, 20, 60))

    # Save
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    thumb_path = Path(tmp.name)
    tmp.close()
    img.save(thumb_path, "JPEG", quality=92)
    logger.info("Thumbnail saved to '%s'", thumb_path)
    return thumb_path
