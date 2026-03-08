"""
thumbnail.py — Generate eye-catching 1280 × 720 JPEG thumbnails using Pillow.

Creates a professional gradient background with large bold title text,
rounded accent elements, and a topic-relevant emoji as a visual accent.
"""

import logging
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Thumbnail dimensions (YouTube standard)
THUMB_W = 1280
THUMB_H = 720

# Colour palette
_BG_COLOR_TOP = (10, 10, 45)        # deep dark navy
_BG_COLOR_BOTTOM = (140, 20, 60)    # rich crimson
_ACCENT_COLOR = (255, 215, 0)       # gold / yellow
_TEXT_COLOR = (255, 255, 255)        # white
_STROKE_COLOR = (0, 0, 0)           # black for outline


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
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
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


def _draw_text_with_stroke(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                            font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
                            fill: tuple[int, ...], stroke_fill: tuple[int, ...],
                            stroke_width: int) -> None:
    """Draw text with a thick outline/stroke for readability."""
    try:
        draw.text(xy, text, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
    except TypeError:
        # Fallback for older Pillow without stroke support
        x, y = xy
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx * dx + dy * dy <= stroke_width * stroke_width:
                    draw.text((x + dx, y + dy), text, font=font, fill=stroke_fill)
        draw.text(xy, text, font=font, fill=fill)


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

    # Decorative accent bar at the bottom with rounded corners
    bar_y = THUMB_H - 90
    draw.rounded_rectangle(
        [(30, bar_y), (THUMB_W - 30, THUMB_H - 20)],
        radius=20,
        fill=_ACCENT_COLOR,
    )

    # Subtle glow behind text area for depth
    glow = Image.new("RGB", (THUMB_W, THUMB_H), (0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        [(THUMB_W // 2 - 400, 60), (THUMB_W // 2 + 400, THUMB_H - 120)],
        fill=(25, 25, 25),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=60))
    img = Image.blend(img, glow, alpha=0.3)
    draw = ImageDraw.Draw(img)

    # Emoji (large, top-left region)
    emoji = _topic_emoji(topic)
    emoji_font = _load_font(140)
    try:
        draw.text((60, 30), emoji, font=emoji_font, fill=_ACCENT_COLOR)
    except Exception:  # noqa: BLE001
        pass

    # Title text with stroke for readability
    title_font = _load_font(95)
    max_text_w = THUMB_W - 140
    lines = _wrap_text(title.upper(), title_font, max_text_w)
    line_height = 115
    total_text_h = len(lines) * line_height
    start_y = max(180, (THUMB_H - total_text_h) // 2 - 20)

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        _draw_text_with_stroke(
            draw, (70, y), line,
            font=title_font,
            fill=_TEXT_COLOR,
            stroke_fill=_STROKE_COLOR,
            stroke_width=4,
        )

    # Channel watermark on accent bar
    watermark_font = _load_font(38)
    _draw_text_with_stroke(
        draw, (70, bar_y + 18), "▶ SUBSCRIBE FOR MORE",
        font=watermark_font,
        fill=(10, 10, 45),
        stroke_fill=(10, 10, 45),
        stroke_width=0,
    )

    # Save
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    thumb_path = Path(tmp.name)
    tmp.close()
    img.save(thumb_path, "JPEG", quality=95, subsampling=0)
    logger.info("Thumbnail saved to '%s'", thumb_path)
    return thumb_path
