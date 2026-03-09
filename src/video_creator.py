"""
video_creator.py — Build a vertical YouTube Shorts video from stock footage,
TTS audio, and animated captions using MoviePy.

Workflow:
1. Fetch stock video clips from the Pexels API for each scene description.
2. Resize / crop each clip to 1080 × 1920 (portrait).
3. Concatenate clips with crossfade transitions.
4. Overlay TTS audio with optional background music.
5. Burn professional TikTok-style captions with rounded pill backgrounds.
6. Apply fade-in / fade-out.
7. Export as high-quality H.264/AAC MP4.
"""

import logging
import math
import os
import random
import tempfile
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Pillow 10+ compatibility shims for MoviePy 1.x
# ---------------------------------------------------------------------------
# Pillow 10 removed Image.ANTIALIAS; MoviePy 1.x still references it.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# Pillow 10 moved transpose constants; ensure top-level aliases exist.
for _constant_name in ("FLIP_LEFT_RIGHT", "FLIP_TOP_BOTTOM", "ROTATE_90",
                        "ROTATE_180", "ROTATE_270", "TRANSPOSE", "TRANSVERSE"):
    if not hasattr(Image, _constant_name) and hasattr(Image.Transpose, _constant_name):
        setattr(Image, _constant_name, getattr(Image.Transpose, _constant_name))

import config

logger = logging.getLogger(__name__)

_PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"
_PEXELS_IMAGE_SEARCH = "https://api.pexels.com/v1/search"


# ---------------------------------------------------------------------------
# Pexels helpers
# ---------------------------------------------------------------------------
def _pexels_headers() -> dict[str, str]:
    if not config.PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY environment variable is not set")
    return {"Authorization": config.PEXELS_API_KEY}

def _search_pexels_video(query: str, per_page: int = 5) -> list[str]:
    """Return a list of downloadable video URLs from Pexels for *query*.

    Prefers the highest-resolution HD file for each video result so that
    the assembled footage looks sharp even on high-DPI displays.
    """
    # Config value overrides the caller default (more results = better variety)
    per_page = getattr(config, "PEXELS_PER_PAGE", per_page)
    try:
        resp = requests.get(
            _PEXELS_VIDEO_SEARCH,
            headers=_pexels_headers(),
            params={"query": query, "per_page": per_page, "orientation": "portrait", "size": "large"},
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        urls: list[str] = []
        for video in data.get("videos", []):
            files = video.get("video_files", [])
            if not files:
                continue
            # Sort HD files by resolution (largest first) for maximum quality
            hd_files = sorted(
                [f for f in files if f.get("quality") == "hd"],
                key=lambda f: f.get("width", 0) * f.get("height", 0),
                reverse=True,
            )
            sd_files = sorted(
                [f for f in files if f.get("quality") == "sd"],
                key=lambda f: f.get("width", 0) * f.get("height", 0),
                reverse=True,
            )
            chosen = (
                hd_files[0] if hd_files
                else sd_files[0] if sd_files
                else files[0]
            )
            if chosen and chosen.get("link"):
                urls.append(chosen["link"])
        return urls
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pexels video search failed for '%s': %s", query, exc)
        return []

def _search_pexels_image(query: str) -> str | None:
    """Return the URL of a landscape/portrait photo from Pexels for *query*."""
    try:
        resp = requests.get(
            _PEXELS_IMAGE_SEARCH,
            headers=_pexels_headers(),
            params={"query": query, "per_page": 3, "orientation": "portrait", "size": "large"},
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        photos = data.get("photos", [])
        if photos:
            # Prefer large2x for best quality, fall back to large
            return photos[0]["src"].get("large2x", photos[0]["src"]["large"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pexels image search failed for '%s': %s", query, exc)
    return None

def _download_file(url: str, suffix: str) -> Path:
    """Stream-download *url* to a named temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp_path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=8192):
                fh.write(chunk)
    return tmp_path

# ---------------------------------------------------------------------------
# MoviePy helpers
# ---------------------------------------------------------------------------
def _resize_clip(clip: Any, w: int, h: int) -> Any:
    """Resize and centre-crop *clip* to exactly *w* × *h* pixels."""
    clip_w, clip_h = clip.size
    scale = max(w / clip_w, h / clip_h)
    resized = clip.resize(scale)
    # Centre crop
    x1 = (resized.w - w) / 2
    y1 = (resized.h - h) / 2
    return resized.crop(x1=x1, y1=y1, x2=x1 + w, y2=y1 + h)


def _ken_burns_effect(clip: Any, w: int, h: int, zoom_ratio: float = 0.08) -> Any:
    """Apply a slow Ken Burns zoom effect to a static image clip.

    Gradually zooms in over the clip's duration for a cinematic feel, then
    centre-crops to the target *w* × *h* dimensions every frame.
    """
    duration = clip.duration

    def _zoom_frame(clip_get_frame: Any, t: float) -> Any:
        import numpy as np
        frame = clip_get_frame(t)
        progress = t / duration if duration > 0 else 0
        current_zoom = 1.0 + zoom_ratio * progress
        fh, fw = frame.shape[:2]
        new_w = int(fw / current_zoom)
        new_h = int(fh / current_zoom)
        x1 = (fw - new_w) // 2
        y1 = (fh - new_h) // 2
        cropped = frame[y1:y1 + new_h, x1:x1 + new_w]
        # Resize back to original dimensions
        pil_img = Image.fromarray(cropped)
        pil_img = pil_img.resize((fw, fh), Image.Resampling.LANCZOS)
        return np.array(pil_img)

    return clip.fl(_zoom_frame)

def _clean_text_for_display(text: str) -> str:
    """Sanitise *text* for on-screen subtitle display.

    Strips any residual HTML/XML markup or entities so viewers never see
    raw code in the captions.
    """
    import re as _re
    cleaned = _re.sub(r"<[^>]+>", " ", text)
    cleaned = _re.sub(r"&[a-zA-Z]+;", " ", cleaned)
    cleaned = _re.sub(r"&#x?[0-9a-fA-F]+;", " ", cleaned)
    cleaned = cleaned.replace("<", " ").replace(">", " ")
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _split_into_chunks(text: str, max_words: int = 6) -> list[str]:
    """Break *text* into short word-burst chunks suitable for TikTok-style captions.

    Splits on sentence boundaries first, then breaks long sentences into
    smaller chunks of at most *max_words* words each.
    """
    import re
    # Split into sentences
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.replace("\n", " ").strip())
    chunks: list[str] = []
    for sentence in raw_sentences:
        sentence = sentence.strip().rstrip(".!?")
        if not sentence:
            continue
        words = sentence.split()
        if len(words) <= max_words:
            chunks.append(sentence)
        else:
            # Break into smaller word-burst chunks
            for start in range(0, len(words), max_words):
                chunk = " ".join(words[start : start + max_words])
                if chunk:
                    chunks.append(chunk)
    return [c for c in chunks if c]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a ``#RRGGBB`` hex string to an ``(R, G, B)`` tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _make_glow_pill_image(width: int, height: int, radius: int,
                          bg_color: tuple[int, int, int],
                          bg_opacity: float,
                          glow_color: tuple[int, int, int],
                          glow_radius: int) -> Any:
    """Create a rounded-rectangle pill with a soft neon glow halo.

    Renders the glow as a series of progressively-transparent concentric
    rounded rectangles so it works without scipy / PIL ImageFilter.
    """
    import numpy as np

    # Canvas is larger than the pill to accommodate the glow halo
    pad = glow_radius
    total_w = width + pad * 2
    total_h = height + pad * 2
    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Draw glow layers — outermost (faintest) to innermost (brightest)
    glow_layers = max(4, glow_radius // 3)
    for layer in range(glow_layers, 0, -1):
        shrink = int((layer / glow_layers) * pad)
        alpha = int(60 * (1 - layer / glow_layers))
        gr, gg, gb = glow_color
        rect = [(shrink, shrink), (total_w - 1 - shrink, total_h - 1 - shrink)]
        draw.rounded_rectangle(rect, radius=radius + pad - shrink,
                               fill=(*glow_color, alpha))

    # Draw the solid pill on top
    pill_alpha = int(255 * bg_opacity)
    pill_rect = [(pad, pad), (pad + width - 1, pad + height - 1)]
    draw.rounded_rectangle(pill_rect, radius=radius, fill=(*bg_color, pill_alpha))

    return np.array(canvas), pad


def _make_rounded_rect_image(width: int, height: int, radius: int,
                              color: tuple[int, int, int],
                              opacity: float) -> Any:
    """Create a rounded-rectangle RGBA image for subtitle backgrounds."""
    import numpy as np
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    alpha = int(255 * opacity)
    fill = (*color, alpha)
    draw.rounded_rectangle([(0, 0), (width - 1, height - 1)], radius=radius, fill=fill)
    return np.array(img)


def _adaptive_font_size(chunk: str, base_size: int) -> int:
    """Return a font size scaled to the number of words in *chunk*.

    Short bursts (≤ 2 words) are rendered larger for maximum impact;
    longer bursts scale down so all text fits comfortably on screen.
    """
    words = len(chunk.split())
    if words <= 1:
        return min(int(base_size * 1.20), 110)
    if words == 2:
        return min(int(base_size * 1.10), 100)
    if words <= 3:
        return base_size
    if words <= 4:
        return max(int(base_size * 0.90), 62)
    return max(int(base_size * 0.80), 55)


def _make_vignette_clip(w: int, h: int, duration: float) -> Any:
    """Create a cinematic dark-edge vignette as a transparent :class:`ImageClip`.

    The vignette gradually darkens the corners and edges of the frame,
    drawing the viewer's eye to the centre of the video.
    """
    import numpy as np
    from moviepy.editor import ImageClip  # type: ignore[import]

    # Vignette shape constants:
    #   _VIG_INNER_RADIUS  — normalised distance at which darkening begins (0 = centre, 1 = edge)
    #   _VIG_FALLOFF       — range over which opacity ramps from 0 to maximum
    #   _VIG_MAX_ALPHA     — peak alpha value (~70 % opacity = 175/255) at the corners
    _VIG_INNER_RADIUS = 0.35
    _VIG_FALLOFF = 1.1
    _VIG_MAX_ALPHA = 175

    img = np.zeros((h, w, 4), dtype=np.uint8)
    cx, cy = w / 2.0, h / 2.0
    # Normalised elliptical distance from the centre (1.0 at the corners)
    y_idx, x_idx = np.mgrid[0:h, 0:w]
    nx = (x_idx - cx) / cx
    ny = (y_idx - cy) / cy
    dist = np.sqrt(nx ** 2 + ny ** 2)
    # Ramp: transparent inside inner radius, fully dark at corners
    alpha_norm = np.clip((dist - _VIG_INNER_RADIUS) / _VIG_FALLOFF, 0.0, 1.0)
    img[:, :, 3] = (alpha_norm * _VIG_MAX_ALPHA).astype(np.uint8)
    return ImageClip(img, ismask=False, transparent=True).set_duration(duration)


def _build_caption_clips(script_text: str, total_duration: float, video_w: int, video_h: int,
                         start_offset: float = 0.0) -> list[Any]:
    """Create modern neon-style TikTok word-burst captions.

    Features:
    - Single caption zone at the lower third — no top subtitle duplication.
    - Neon glow pill backgrounds (cyan/yellow/pink palette).
    - Word-proportional timing so each burst stays readable.
    - Adaptive font: 1-word bursts render larger for maximum impact.
    - Bold uppercase text with thick stroke for contrast on any background.
    - Soft crossfade between bursts for a polished feel.

    Args:
        script_text:    Caption text to display (full script or body+CTA).
        total_duration: Total video duration in seconds.
        video_w:        Video width in pixels.
        video_h:        Video height in pixels.
        start_offset:   Seconds to delay captions from video start.
    """
    try:
        from moviepy.editor import TextClip, ImageClip  # type: ignore[import]
    except Exception:  # noqa: BLE001
        return []

    chunks = _split_into_chunks(
        _clean_text_for_display(script_text), max_words=config.SUBTITLE_MAX_WORDS
    )
    if not chunks:
        return []

    # Shift all captions slightly later so they trail the spoken audio
    # instead of appearing ahead of it.  The end buffer shrinks the
    # caption window so the last burst finishes before the speech does.
    subtitle_delay = getattr(config, "SUBTITLE_DELAY", 0.25)
    end_buffer = getattr(config, "SUBTITLE_END_BUFFER", 0.4)
    start_offset += subtitle_delay

    available_duration = total_duration - start_offset - end_buffer
    # Graceful fallback for very short videos: first drop the end buffer,
    # then drop the caller's start_offset (keep the subtitle delay so
    # captions still trail the speech slightly).
    if available_duration <= 0:
        available_duration = total_duration - start_offset
        if available_duration <= 0:
            available_duration = total_duration
            start_offset = subtitle_delay

    # Word-proportional durations — longer chunks stay on screen longer
    if getattr(config, "SUBTITLE_WORD_TIMING", True) and len(chunks) > 1:
        word_counts = [max(1, len(c.split())) for c in chunks]
        total_words = sum(word_counts)
        chunk_durations = [available_duration * wc / total_words for wc in word_counts]
    else:
        chunk_durations = [available_duration / len(chunks)] * len(chunks)

    # Cumulative start times
    chunk_starts: list[float] = []
    t = start_offset
    for dur in chunk_durations:
        chunk_starts.append(t)
        t += dur

    clips: list[Any] = []

    # Caption vertical anchor — lower third, safely above bottom UI chrome
    y_pos = int(video_h * getattr(config, "SUBTITLE_POSITION", 0.72))

    # Neon colour palette: 3-colour cycling (yellow → mint → pink → repeat)
    highlight  = getattr(config, "SUBTITLE_HIGHLIGHT_COLOR",  "#FFEE00")
    secondary  = getattr(config, "SUBTITLE_SECONDARY_COLOR",  "#00FFC8")
    accent     = getattr(config, "SUBTITLE_ACCENT_COLOR",     "#FF4081")
    color_palette = [highlight, "white", secondary, highlight, accent, "white"]

    corner_radius  = getattr(config, "SUBTITLE_BG_CORNER_RADIUS", 28)
    shadow_offset  = getattr(config, "SUBTITLE_SHADOW_OFFSET", 3)
    use_glow       = getattr(config, "SUBTITLE_GLOW", True)
    glow_color_hex = getattr(config, "SUBTITLE_GLOW_COLOR", "#00FFC8")
    glow_radius    = getattr(config, "SUBTITLE_GLOW_RADIUS", 18)
    all_caps       = getattr(config, "SUBTITLE_ALL_CAPS", True)
    font_name      = getattr(config, "SUBTITLE_FONT", "Liberation-Sans-Bold")
    stroke_w       = getattr(config, "SUBTITLE_STROKE_WIDTH", 6)
    base_font_size = getattr(config, "SUBTITLE_FONT_SIZE", 88)

    glow_rgb = _hex_to_rgb(glow_color_hex)

    for i, chunk in enumerate(chunks):
        start = chunk_starts[i]
        dur   = chunk_durations[i]
        crossfade = min(0.12, dur * 0.18)
        color = color_palette[i % len(color_palette)]
        display_text = chunk.upper() if all_caps else chunk

        font_size = (
            _adaptive_font_size(chunk, base_font_size)
            if getattr(config, "SUBTITLE_ADAPTIVE_FONT", True)
            else base_font_size
        )

        try:
            # ------------------------------------------------------------------
            # Build the main text clip
            # ------------------------------------------------------------------
            txt_clip = TextClip(
                display_text,
                fontsize=font_size,
                font=font_name,
                color=color,
                stroke_color="black",
                stroke_width=stroke_w,
                method="caption",
                size=(video_w - 120, None),
                align="center",
            )
            txt_w, txt_h = txt_clip.size
            pad_x, pad_y = 36, 20

            # ------------------------------------------------------------------
            # Pill background (with optional neon glow)
            # ------------------------------------------------------------------
            bg_w = txt_w + pad_x * 2
            bg_h = txt_h + pad_y * 2

            if use_glow:
                bg_array, glow_pad = _make_glow_pill_image(
                    bg_w, bg_h, corner_radius,
                    bg_color=(8, 8, 8), bg_opacity=config.SUBTITLE_BG_OPACITY,
                    glow_color=glow_rgb, glow_radius=glow_radius,
                )
            else:
                bg_array = _make_rounded_rect_image(
                    bg_w, bg_h, corner_radius,
                    color=(8, 8, 8), opacity=config.SUBTITLE_BG_OPACITY,
                )
                glow_pad = 0

            # Position the pill so its vertical centre aligns with y_pos
            pill_y = y_pos - bg_h // 2 - glow_pad
            bg_clip = (
                ImageClip(bg_array, ismask=False, transparent=True)
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", pill_y))
                .crossfadein(crossfade)
                .crossfadeout(crossfade)
            )

            # ------------------------------------------------------------------
            # Drop shadow — offset copy at reduced opacity
            # ------------------------------------------------------------------
            shadow_clip = (
                TextClip(
                    display_text,
                    fontsize=font_size,
                    font=font_name,
                    color="#000000",
                    stroke_color="#000000",
                    stroke_width=stroke_w + 2,
                    method="caption",
                    size=(video_w - 120, None),
                    align="center",
                )
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", y_pos - txt_h // 2 + shadow_offset))
                .set_opacity(0.45)
                .crossfadein(crossfade)
                .crossfadeout(crossfade)
            )

            # ------------------------------------------------------------------
            # Main text — vertically centred on y_pos
            # ------------------------------------------------------------------
            txt_clip = (
                txt_clip
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", y_pos - txt_h // 2))
                .crossfadein(crossfade)
                .crossfadeout(crossfade)
            )

            clips.extend([bg_clip, shadow_clip, txt_clip])

        except Exception as exc:  # noqa: BLE001
            logger.warning("Caption clip %d skipped: %s", i, exc)

    return clips

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_video(
    audio_path: Path,
    script_text: str,
    scenes: list[str],
    audio_duration: float,
    hook_text: str = "",
) -> Path:
    """Create a vertical 1080 × 1920 YouTube Shorts MP4 video.

    Args:
        audio_path:     Path to the TTS MP3 audio file.
        script_text:    Full narration script (hook + body + CTA).  Every
                        spoken word is captioned in a single lower-third
                        band — no duplicate top subtitle.
        scenes:         List of scene description strings (used as Pexels
                        search queries).
        audio_duration: Duration in seconds of the TTS audio.
        hook_text:      Kept for API compatibility; no longer used
                        internally now that the full script is captioned.

    Returns:
        Path to the exported MP4 file.

    Raises:
        RuntimeError: If video creation fails.
    """
    try:
        from moviepy.editor import (  # type: ignore[import]
            AudioFileClip,
            CompositeAudioClip,
            CompositeVideoClip,
            ColorClip,
            ImageClip,
            VideoFileClip,
            concatenate_videoclips,
        )
    except ImportError as exc:
        raise RuntimeError("moviepy is not installed") from exc

    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    target_duration = audio_duration if audio_duration > 0 else config.VIDEO_DURATION_TARGET
    transition_dur = getattr(config, "VIDEO_TRANSITION_DURATION", 0.4)
    downloaded: list[Path] = []
    video_clips: list[Any] = []

    try:
        # ------------------------------------------------------------------
        # 1. Fetch stock footage for each scene
        # ------------------------------------------------------------------
        time_per_scene = target_duration / max(len(scenes), 1)
        for scene in scenes:
            clip_added = False

            # Try video first
            video_urls = _search_pexels_video(scene, per_page=5)
            for url in video_urls:
                try:
                    clip_path = _download_file(url, ".mp4")
                    downloaded.append(clip_path)
                    vc = VideoFileClip(str(clip_path), audio=False)
                    # Loop / trim to match scene duration (add extra for crossfade)
                    scene_dur = time_per_scene + transition_dur
                    if vc.duration < scene_dur:
                        loops = math.ceil(scene_dur / vc.duration)
                        vc = vc.loop(n=loops)
                    # Start at a random offset for visual variety across runs.
                    # Only applied when there is enough extra clip length (> 1 s)
                    # to ensure we never risk exceeding the available duration.
                    if getattr(config, "VIDEO_CLIP_RANDOM_START", True):
                        max_start = max(0.0, vc.duration - scene_dur)
                        if max_start > 1.0:
                            start_t = random.uniform(0.0, max_start)
                            vc = vc.subclip(start_t, start_t + scene_dur)
                        else:
                            vc = vc.subclip(0, scene_dur)
                    else:
                        vc = vc.subclip(0, scene_dur)
                    vc = _resize_clip(vc, w, h)
                    video_clips.append(vc)
                    clip_added = True
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to load video from Pexels: %s", exc)

            if not clip_added:
                # Fallback: try a static image with Ken Burns effect
                img_url = _search_pexels_image(scene)
                if img_url:
                    try:
                        img_path = _download_file(img_url, ".jpg")
                        downloaded.append(img_path)
                        scene_dur = time_per_scene + transition_dur
                        ic = ImageClip(str(img_path)).set_duration(scene_dur)
                        ic = _resize_clip(ic, w, h)
                        ic = _ken_burns_effect(ic, w, h, zoom_ratio=0.08)
                        video_clips.append(ic)
                        clip_added = True
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to load image from Pexels: %s", exc)

            if not clip_added:
                # Last resort: gradient placeholder instead of flat colour
                logger.warning("No footage for scene '%s'; using gradient placeholder", scene)
                scene_dur = time_per_scene + transition_dur
                placeholder = ColorClip(size=(w, h), color=(20, 20, 40)).set_duration(scene_dur)
                video_clips.append(placeholder)

        # ------------------------------------------------------------------
        # 2. Concatenate clips with crossfade transitions
        # ------------------------------------------------------------------
        if not video_clips:
            raise RuntimeError("No video clips could be assembled")

        if len(video_clips) > 1 and transition_dur > 0:
            base = concatenate_videoclips(
                video_clips,
                method="compose",
                padding=-transition_dur,
            )
        else:
            base = concatenate_videoclips(video_clips, method="compose")

        # Trim to match target duration
        if base.duration > target_duration:
            base = base.subclip(0, target_duration)

        # ------------------------------------------------------------------
        # 3. Overlay TTS audio (mixed with optional background music)
        # ------------------------------------------------------------------
        tts_audio = AudioFileClip(str(audio_path))

        # Look for a background music file at the configured path
        bg_music_path = Path(config.BG_MUSIC_PATH)
        if bg_music_path.exists() and config.BG_MUSIC_VOLUME > 0:
            try:
                bg_audio = (
                    AudioFileClip(str(bg_music_path))
                    .volumex(config.BG_MUSIC_VOLUME)
                    .set_duration(target_duration)
                )
                # Fade in/out the background music for a polished feel
                bg_audio = bg_audio.audio_fadein(1.0).audio_fadeout(2.0)
                mixed_audio = CompositeAudioClip([bg_audio, tts_audio])
                base = base.set_audio(mixed_audio)
                logger.info("Background music mixed in at volume %.2f", config.BG_MUSIC_VOLUME)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not mix background music: %s — using TTS only", exc)
                base = base.set_audio(tts_audio)
        else:
            base = base.set_audio(tts_audio)

        # ------------------------------------------------------------------
        # 4. Captions — single band at lower third, covering the full script.
        #    Removes the double-subtitle issue: all spoken words (including the
        #    hook) are captioned in one consistent zone.  No top subtitle.
        # ------------------------------------------------------------------
        caption_clips = _build_caption_clips(
            script_text, audio_duration, w, h, start_offset=0.0
        )

        # ------------------------------------------------------------------
        # 5. Compose layers: base video + captions + optional vignette
        # ------------------------------------------------------------------
        layers: list[Any] = [base] + caption_clips
        if getattr(config, "VIDEO_VIGNETTE", True):
            try:
                vignette = _make_vignette_clip(w, h, target_duration)
                layers.append(vignette)
                logger.debug("Cinematic vignette overlay applied")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vignette overlay failed: %s", exc)

        final = CompositeVideoClip(layers, size=(w, h)) if len(layers) > 1 else base

        # ------------------------------------------------------------------
        # 5b. Subtle cinematic colour grade — boost contrast and warmth
        # ------------------------------------------------------------------
        if getattr(config, "VIDEO_COLOR_GRADE", True):
            try:
                import numpy as np
                from moviepy.editor import VideoClip  # type: ignore[import]

                def _grade_frame(frame: Any) -> Any:
                    """Apply a mild S-curve contrast + slight warm tint."""
                    f = frame.astype("float32") / 255.0
                    # S-curve: darken shadows, brighten highlights
                    f = np.clip(f * 1.06 - 0.03, 0.0, 1.0)
                    # Warm tint: nudge red up, blue down slightly
                    f[:, :, 0] = np.clip(f[:, :, 0] * 1.04, 0.0, 1.0)
                    f[:, :, 2] = np.clip(f[:, :, 2] * 0.97, 0.0, 1.0)
                    return (f * 255).astype("uint8")

                final = final.fl_image(_grade_frame)
                logger.debug("Colour grade applied")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Colour grade skipped: %s", exc)

        # ------------------------------------------------------------------
        # 6. Fade-in / fade-out
        # ------------------------------------------------------------------
        final = final.fadein(0.7).fadeout(0.7)

        # ------------------------------------------------------------------
        # 7. Export
        # ------------------------------------------------------------------
        out_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out_path = Path(out_tmp.name)
        out_tmp.close()

        logger.info("Rendering video to '%s' …", out_path)
        final.write_videofile(
            str(out_path),
            fps=config.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset=config.VIDEO_PRESET,
            bitrate=config.VIDEO_BITRATE,
            audio_bitrate=config.AUDIO_BITRATE,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            logger=None,
        )
        logger.info("Video rendered successfully: '%s'", out_path)
        return out_path

    finally:
        # Clean up downloaded temp files
        for p in downloaded:
            try:
                p.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
