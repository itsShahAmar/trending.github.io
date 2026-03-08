"""
video_creator.py — Build a vertical YouTube Shorts video from stock footage,
TTS audio, and animated captions using MoviePy.

Workflow:
1. Fetch stock video clips from the Pexels API for each scene description.
2. Resize / crop each clip to 1080 × 1920 (portrait).
3. Concatenate clips to match the TTS audio duration.
4. Overlay TTS audio.
5. Burn sentence-level captions at the bottom third of the frame.
6. Apply fade-in / fade-out.
7. Export as H.264/AAC MP4.
"""

import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Pillow 10+ removed Image.ANTIALIAS; MoviePy 1.x still references it.
# Restore the alias so MoviePy's resize() calls work with modern Pillow.
# ---------------------------------------------------------------------------
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

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
    """Return a list of downloadable video URLs from Pexels for *query*."""
    try:
        resp = requests.get(
            _PEXELS_VIDEO_SEARCH,
            headers=_pexels_headers(),
            params={"query": query, "per_page": per_page, "orientation": "portrait", "size": "medium"},
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        urls: list[str] = []
        for video in data.get("videos", []):
            files = video.get("video_files", [])
            # Prefer HD files; fall back to any
            hd = [f for f in files if f.get("quality") in ("hd", "sd")]
            chosen = hd[0] if hd else (files[0] if files else None)
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
            params={"query": query, "per_page": 3, "orientation": "portrait"},
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        photos = data.get("photos", [])
        if photos:
            return photos[0]["src"]["large"]
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


def _build_caption_clips(script_text: str, total_duration: float, video_w: int, video_h: int) -> list[Any]:
    """Create TikTok-style word-burst caption clips timed across *total_duration*."""
    try:
        from moviepy.editor import TextClip, ColorClip, CompositeVideoClip  # type: ignore[import]
    except Exception:  # noqa: BLE001
        return []

    chunks = _split_into_chunks(script_text, max_words=config.SUBTITLE_MAX_WORDS)
    if not chunks:
        return []

    duration_per_chunk = total_duration / len(chunks)
    clips: list[Any] = []
    y_pos = int(video_h * config.SUBTITLE_POSITION)

    for i, chunk in enumerate(chunks):
        start = i * duration_per_chunk
        dur = duration_per_chunk
        # Alternate between white and the accent highlight color
        color = config.SUBTITLE_HIGHLIGHT_COLOR if i % 2 == 1 else "white"
        text_upper = chunk.upper()
        try:
            txt_clip = TextClip(
                text_upper,
                fontsize=config.SUBTITLE_FONT_SIZE,
                font=config.SUBTITLE_FONT,
                color=color,
                stroke_color="black",
                stroke_width=config.SUBTITLE_STROKE_WIDTH,
                method="caption",
                size=(video_w - 80, None),
                align="center",
            )
            txt_w, txt_h = txt_clip.size
            pad_x, pad_y = 20, 10
            # Semi-transparent dark background box
            bg_clip = (
                ColorClip(
                    size=(txt_w + pad_x * 2, txt_h + pad_y * 2),
                    color=(0, 0, 0),
                )
                .set_opacity(config.SUBTITLE_BG_OPACITY)
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", y_pos - pad_y))
                .crossfadein(0.1)
                .crossfadeout(0.1)
            )
            txt_clip = (
                txt_clip
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", y_pos))
                .crossfadein(0.1)
                .crossfadeout(0.1)
            )
            clips.extend([bg_clip, txt_clip])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not create caption clip for chunk %d: %s", i, exc)
    return clips

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_video(
    audio_path: Path,
    script_text: str,
    scenes: list[str],
    audio_duration: float,
) -> Path:
    """Create a vertical 1080 × 1920 YouTube Shorts MP4 video.

    Args:
        audio_path: Path to the TTS MP3 audio file.
        script_text: Full narration text (used for captions).
        scenes: List of scene description strings (used for Pexels queries).
        audio_duration: Duration in seconds of the TTS audio.

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
            video_urls = _search_pexels_video(scene, per_page=3)
            for url in video_urls:
                try:
                    clip_path = _download_file(url, ".mp4")
                    downloaded.append(clip_path)
                    vc = VideoFileClip(str(clip_path), audio=False)
                    # Loop / trim to match scene duration
                    if vc.duration < time_per_scene:
                        loops = math.ceil(time_per_scene / vc.duration)
                        vc = vc.loop(n=loops)
                    vc = vc.subclip(0, time_per_scene)
                    vc = _resize_clip(vc, w, h)
                    video_clips.append(vc)
                    clip_added = True
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to load video from Pexels: %s", exc)

            if not clip_added:
                # Fallback: try a static image
                img_url = _search_pexels_image(scene)
                if img_url:
                    try:
                        img_path = _download_file(img_url, ".jpg")
                        downloaded.append(img_path)
                        ic = ImageClip(str(img_path)).set_duration(time_per_scene)
                        ic = _resize_clip(ic, w, h)
                        video_clips.append(ic)
                        clip_added = True
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to load image from Pexels: %s", exc)

            if not clip_added:
                # Last resort: solid colour placeholder
                logger.warning("No footage for scene '%s'; using colour placeholder", scene)
                placeholder = ColorClip(size=(w, h), color=(30, 30, 30)).set_duration(time_per_scene)
                video_clips.append(placeholder)

        # ------------------------------------------------------------------
        # 2. Concatenate clips
        # ------------------------------------------------------------------
        if not video_clips:
            raise RuntimeError("No video clips could be assembled")

        base = concatenate_videoclips(video_clips, method="compose")
        # Trim or pad to match audio duration
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
                mixed_audio = CompositeAudioClip([bg_audio, tts_audio])
                base = base.set_audio(mixed_audio)
                logger.info("Background music mixed in at volume %.2f", config.BG_MUSIC_VOLUME)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not mix background music: %s — using TTS only", exc)
                base = base.set_audio(tts_audio)
        else:
            base = base.set_audio(tts_audio)

        # ------------------------------------------------------------------
        # 4. Captions
        # ------------------------------------------------------------------
        caption_clips = _build_caption_clips(script_text, target_duration, w, h)
        if caption_clips:
            final = CompositeVideoClip([base] + caption_clips, size=(w, h))
        else:
            final = base

        # ------------------------------------------------------------------
        # 5. Fade-in / fade-out
        # ------------------------------------------------------------------
        final = final.fadein(0.5).fadeout(0.5)

        # ------------------------------------------------------------------
        # 6. Export
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
