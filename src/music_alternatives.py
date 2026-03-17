"""
music_alternatives.py — Alternative royalty-free music downloaders.

Provides download helpers for:
- Kevin MacLeod / Incompetech (CC-BY 3.0 licensed MP3s)
- ccMixter (Creative Commons tracks)

Each helper returns a local :class:`~pathlib.Path` on success, or *None*
on any failure (HTTP 404, connection error, SSL error, etc.) so that the
caller can transparently fall back to the next source.

ccMixter note: SSL certificate verification is intentionally disabled for
ccmixter.org because their certificate chain is frequently incomplete in
CI and headless server environments, causing ``SSLCertVerificationError``.
We only download audio files from these trusted open-licence sources, so
the security trade-off is acceptable.
"""

import logging
import tempfile
import time
import warnings
from pathlib import Path

import requests
import urllib3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Incompetech (Kevin MacLeod) — CC-BY 3.0 licensed tracks
# These are well-known, long-standing URLs from the Kevin MacLeod collection.
# The list is ordered so that the most reliable, genre-neutral tracks come
# first.  A 404 for any entry is caught and the next track is tried.
# ---------------------------------------------------------------------------
_INCOMPETECH_TRACKS: list[tuple[str, str]] = [
    ("Cipher",         "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher.mp3"),
    ("Chill",          "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Chill.mp3"),
    ("Motivate",       "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Motivate.mp3"),
    ("Wallpaper",      "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3"),
    ("Sneaky Snitch",  "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sneaky%20Snitch.mp3"),
    ("Thinking Music", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Thinking%20Music.mp3"),
    ("Local Forecast", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Local%20Forecast.mp3"),
]

# ---------------------------------------------------------------------------
# ccMixter — Creative Commons tracks
# ---------------------------------------------------------------------------
_CCMIXTER_TRACKS: list[dict] = [
    {"id": 54335, "url": "https://ccmixter.org/content/mindmapthat/mindmapthat_-_Hanging_Eleven.mp3"},
    {"id": 15611, "url": "https://ccmixter.org/content/DoKashiteru/DoKashiteru_-_Home_Tonight.mp3"},
    {"id": 42577, "url": "https://ccmixter.org/content/copperhead/copperhead_-_The_Wind_of_Love.mp3"},
    {"id": 33440, "url": "https://ccmixter.org/content/SackJo22/SackJo22_-_Lamadio_Tiado.mp3"},
    {"id": 33338, "url": "https://ccmixter.org/content/mindmapthat/mindmapthat_-_Vox_Vs._Uke.mp3"},
    {"id": 33941, "url": "https://ccmixter.org/content/casimps1/casimps1_-_Broken.mp3"},
    {"id": 42137, "url": "https://ccmixter.org/content/SackJo22/SackJo22_-_SuperSTARS_(w_Vidian_and_HEJ31).mp3"},
    {"id": 21426, "url": "https://ccmixter.org/content/DoKashiteru/DoKashiteru_-_Independence_Day.mp3"},
    {"id": 26831, "url": "https://ccmixter.org/content/CiggiBurns/CiggiBurns_-_Letting_It_Go.mp3"},
    {"id": 37086, "url": "https://ccmixter.org/content/SackJo22/SackJo22_-_BREATHe.mp3"},
]


def download_incompetech_track(
    name: str,
    url: str,
    dest_dir: Path | None = None,
) -> Path | None:
    """Download a single Kevin MacLeod track from Incompetech.

    Args:
        name:     Human-readable track name (used in log messages).
        url:      Direct MP3 URL.
        dest_dir: Directory to save the file in; a temp file is used if
                  *None*.

    Returns:
        :class:`~pathlib.Path` of the downloaded file, or *None* on
        failure (HTTP error, timeout, …).
    """
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        if dest_dir is not None:
            dest_dir.mkdir(parents=True, exist_ok=True)
            safe_name = name.replace(" ", "_").replace("/", "_")
            out_path = dest_dir / f"incompetech_{safe_name}.mp3"
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            out_path = Path(tmp.name)
            tmp.close()

        with open(out_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)

        logger.info("Downloaded Incompetech track '%s' → %s", name, out_path)
        return out_path

    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to download Incompetech track '%s': %s", name, exc)
        return None


def download_ccmixter_track(
    track_id: int,
    url: str,
    dest_dir: Path | None = None,
) -> Path | None:
    """Download a ccMixter track by ID.

    SSL certificate verification is disabled for ccmixter.org to work
    around the ``SSLCertVerificationError`` caused by their incomplete
    certificate chain in many server environments.

    Args:
        track_id: ccMixter track ID (used for logging and file naming).
        url:      Direct MP3 download URL on ``ccmixter.org``.
        dest_dir: Directory to save the file in; a temp file is used if
                  *None*.

    Returns:
        :class:`~pathlib.Path` of the downloaded file, or *None* on
        failure.
    """
    try:
        # Suppress the InsecureRequestWarning that urllib3 emits when
        # verify=False is used, since the warning would clutter CI logs.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, timeout=30, stream=True, verify=False)  # noqa: S501
        resp.raise_for_status()

        if dest_dir is not None:
            dest_dir.mkdir(parents=True, exist_ok=True)
            out_path = dest_dir / f"ccmixter_{track_id}.mp3"
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            out_path = Path(tmp.name)
            tmp.close()

        with open(out_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)

        logger.info("Downloaded ccMixter track id=%s → %s", track_id, out_path)
        return out_path

    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to download ccMixter track id=%s: %s", track_id, exc)
        return None


def get_alternative_music(dest_dir: Path | None = None) -> Path | None:
    """Try to obtain a royalty-free MP3 from Incompetech then ccMixter.

    Iterates through the known track lists, starting at an hourly offset
    so that repeated runs use different tracks.  Returns the first
    successfully downloaded file, or *None* if every source fails.

    Args:
        dest_dir: Optional directory to save the downloaded file in.

    Returns:
        :class:`~pathlib.Path` to a downloaded MP3, or *None*.
    """
    hour_offset = int(time.time() // 3600)

    # --- Incompetech ---
    n = len(_INCOMPETECH_TRACKS)
    for i in range(n):
        idx = (hour_offset + i) % n
        name, url = _INCOMPETECH_TRACKS[idx]
        path = download_incompetech_track(name, url, dest_dir)
        if path is not None:
            return path

    # --- ccMixter ---
    m = len(_CCMIXTER_TRACKS)
    for i in range(m):
        idx = (hour_offset + i) % m
        track = _CCMIXTER_TRACKS[idx]
        path = download_ccmixter_track(track["id"], track["url"], dest_dir)
        if path is not None:
            return path

    return None
