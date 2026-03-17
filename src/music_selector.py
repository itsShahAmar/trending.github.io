"""
music_selector.py — Scene-aware background music selector.

Selects royalty-free background music based on the video topic and scene
descriptions.  Sources are tried in order:

1. Free Music Archive (FMA) public API — search with a mood-aware query.
2. Incompetech / ccMixter via :mod:`src.music_alternatives`.
3. A 60-second silent WAV file as a guaranteed fallback.

Downloaded files are cached under ``cache/music/`` using a short MD5
digest of the topic + scenes so that repeated runs for the same content
re-use the cached file instead of downloading again.
"""

import hashlib
import logging
import wave
from pathlib import Path

import requests

from src.music_alternatives import get_alternative_music

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("cache/music")
_SILENCE_DURATION_S = 60  # seconds for the silence fallback WAV


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_mood_query(scenes: list[str], topic: str) -> str:
    """Build a mood-aware FMA search query from scene descriptions and topic.

    Args:
        scenes: List of scene description strings.
        topic:  Video topic string.

    Returns:
        A short search query string suitable for the FMA API.
    """
    text = (topic + " " + " ".join(scenes)).lower()
    words = set(text.split())

    if words & {"food", "cooking", "kitchen", "recipe", "baking"}:
        mood = "upbeat kitchen"
    elif words & {"sad", "grief", "loss", "death", "memorial"}:
        mood = "melancholic ambient"
    elif words & {"tech", "science", "innovation", "ai", "robot", "data"}:
        mood = "cinematic tech"
    elif words & {"sport", "fitness", "workout", "exercise", "gym"}:
        mood = "energetic workout"
    elif words & {"nature", "travel", "adventure", "outdoor"}:
        mood = "upbeat travel"
    else:
        mood = "upbeat background"

    # Append the first two topic words to give FMA more context
    topic_words = topic.split()[:2]
    return " ".join([mood, "music"] + topic_words)


def _fetch_fma_track(query: str, cache_dir: Path) -> Path | None:
    """Attempt to download a track from the Free Music Archive API.

    Issues a search against the FMA JSON API and downloads a random
    result.  Returns *None* on any error (including HTTP 4xx/5xx).

    Args:
        query:     Mood/genre search query string.
        cache_dir: Directory to write the downloaded file.

    Returns:
        :class:`~pathlib.Path` of the downloaded MP3, or *None*.
    """
    try:
        resp = requests.get(
            "https://freemusicarchive.org/api/get/tracks.json",
            params={
                "q": query,
                "limit": 5,
                "sort": "track_date_published",
                "order": "desc",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        tracks = data.get("dataset", [])
        if not tracks:
            logger.debug("FMA: no tracks returned for query '%s'", query)
            return None

        import random
        track = random.choice(tracks)
        url = track.get("track_url") or track.get("track_listen_url")
        if not url:
            logger.debug("FMA: track record has no usable URL")
            return None

        dl_resp = requests.get(url, timeout=60, stream=True)
        dl_resp.raise_for_status()

        cache_dir.mkdir(parents=True, exist_ok=True)
        fname = f"fma_{hashlib.md5(url.encode()).hexdigest()[:12]}.mp3"
        out_path = cache_dir / fname
        with open(out_path, "wb") as fh:
            for chunk in dl_resp.iter_content(chunk_size=8192):
                fh.write(chunk)

        logger.info("FMA track downloaded: %s", out_path)
        return out_path

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        logger.warning(
            "Free Music Archive search failed for query '%s': HTTP %s — %s",
            query, status, exc,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Free Music Archive search failed for query '%s': %s", query, exc
        )
    return None


def _create_silence(duration: int, path: Path) -> Path:
    """Write a silent stereo 16-bit PCM WAV file.

    Args:
        duration: Duration in seconds.
        path:     Destination file path.

    Returns:
        The same *path* after the file has been written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    n_channels = 2
    sample_width = 2  # bytes per sample (16-bit)
    n_frames = duration * sample_rate

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * n_frames * n_channels * sample_width)

    logger.info("Created silence fallback audio (%ds WAV): %s", duration, path)
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_background_music(
    scenes: list[str],
    topic: str,
    duration: int = 60,
) -> Path:
    """Select scene-aware royalty-free background music.

    The function probes the following sources in order:

    1. **Free Music Archive (FMA)** — a mood-aware text query is built
       from *scenes* and *topic* and submitted to the FMA JSON API.
    2. **Incompetech / ccMixter** — a curated list of CC-licensed tracks
       is tried via :func:`src.music_alternatives.get_alternative_music`.
    3. **Silence WAV** — a ``{duration}``-second silent WAV is generated
       as a guaranteed fallback so that the pipeline never stalls.

    Results are cached in ``cache/music/`` using a 12-character MD5
    digest of ``topic + scenes`` as a filename prefix.  A cache hit
    skips all network activity.

    Args:
        scenes:   List of scene description strings (used to infer mood).
        topic:    Video topic string.
        duration: Target duration in seconds for the silence fallback.

    Returns:
        :class:`~pathlib.Path` to a local audio file (MP3 or WAV).
    """
    cache_key = hashlib.md5((topic + "|" + "|".join(scenes)).encode()).hexdigest()[:12]
    cache_dir = _CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Return a cached file if one already exists for this key
    for cached in cache_dir.glob(f"{cache_key}_*"):
        if cached.suffix in (".mp3", ".wav") and cached.stat().st_size > 0:
            logger.info("Using cached background music: %s", cached)
            return cached

    query = _build_mood_query(scenes, topic)

    # 1. Free Music Archive
    tmp_path = _fetch_fma_track(query, cache_dir)
    if tmp_path is not None:
        final_path = cache_dir / f"{cache_key}_{tmp_path.name}"
        if tmp_path != final_path:
            tmp_path.rename(final_path)
        return final_path

    # 2. Incompetech / ccMixter alternatives (download to a temp location
    #    so we can rename with the cache key prefix)
    import tempfile
    alt_tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = get_alternative_music(dest_dir=alt_tmp_dir)
    if tmp_path is not None:
        final_path = cache_dir / f"{cache_key}_{tmp_path.name}"
        tmp_path.rename(final_path)
        try:
            alt_tmp_dir.rmdir()
        except OSError:
            pass
        return final_path

    # 3. Silence fallback
    silence_path = cache_dir / f"{cache_key}_silence.wav"
    _create_silence(duration, silence_path)
    logger.info("Using silence fallback — no API music available")
    return silence_path
