"""
tts.py — Text-to-speech generation using Microsoft Edge's free neural TTS.

Converts narration script text to an MP3 audio file and returns the file
path together with the audio duration in seconds.  Completely free — no
API keys required.

Primary engine: edge-tts (Microsoft Edge neural voices — natural, high quality)
Fallback: rotates through the full edge-tts voice pool until one succeeds.

Quality features:
- Text sanitisation to strip any markup before synthesis
- Post-generation loudness normalization via pydub
- Rotating voice selection: a different neural voice (male/female) is chosen
  on each run using a time-based seed so the channel sounds varied and fresh.
"""

import asyncio
import logging
import re
import tempfile
import time
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice pool — 24 high-quality Microsoft neural voices (male + female,
# diverse accents) available free via edge-tts.  A new voice is selected
# every hour so each video sounds distinct.
# ---------------------------------------------------------------------------
_VOICE_POOL: list[dict] = [
    # --- Female voices ---
    {"name": "en-US-JennyNeural",        "gender": "female", "style": "newscast"},
    {"name": "en-US-AriaNeural",         "gender": "female", "style": "chat"},
    {"name": "en-US-SaraNeural",         "gender": "female", "style": "cheerful"},
    {"name": "en-US-MichelleNeural",     "gender": "female", "style": "natural"},
    {"name": "en-US-CoraNeural",         "gender": "female", "style": "natural"},
    {"name": "en-US-ElizabethNeural",    "gender": "female", "style": "natural"},
    {"name": "en-GB-SoniaNeural",        "gender": "female", "style": "natural"},
    {"name": "en-GB-LibbyNeural",        "gender": "female", "style": "natural"},
    {"name": "en-AU-NatashaNeural",      "gender": "female", "style": "natural"},
    {"name": "en-CA-ClaraNeural",        "gender": "female", "style": "natural"},
    {"name": "en-IN-NeerjaNeural",       "gender": "female", "style": "natural"},
    {"name": "en-IE-EmilyNeural",        "gender": "female", "style": "natural"},
    # --- Male voices ---
    {"name": "en-US-GuyNeural",          "gender": "male",   "style": "newscast"},
    {"name": "en-US-DavisNeural",        "gender": "male",   "style": "chat"},
    {"name": "en-US-TonyNeural",         "gender": "male",   "style": "natural"},
    {"name": "en-US-JasonNeural",        "gender": "male",   "style": "natural"},
    {"name": "en-US-ChristopherNeural",  "gender": "male",   "style": "newscast"},
    {"name": "en-US-EricNeural",         "gender": "male",   "style": "natural"},
    {"name": "en-US-BrandonNeural",      "gender": "male",   "style": "natural"},
    {"name": "en-GB-RyanNeural",         "gender": "male",   "style": "natural"},
    {"name": "en-GB-ThomasNeural",       "gender": "male",   "style": "natural"},
    {"name": "en-AU-WilliamNeural",      "gender": "male",   "style": "natural"},
    {"name": "en-CA-LiamNeural",         "gender": "male",   "style": "natural"},
    {"name": "en-IN-PrabhatNeural",      "gender": "male",   "style": "natural"},
]


def pick_voice() -> str:
    """Return a voice name from ``_VOICE_POOL`` selected by the current hour.

    The selection rotates through the full pool so each pipeline run (which
    is scheduled hourly) uses a different voice character.  Alternates
    naturally between male and female voices because the pool is ordered
    female-first then male.

    Returns:
        The ``en-*-*Neural`` voice name string accepted by edge-tts.
    """
    # Fall back to config value if TTS_VOICE_ROTATE is explicitly disabled
    if not getattr(config, "TTS_VOICE_ROTATE", True):
        return config.TTS_VOICE

    hour_index = int(time.time() // 3600)
    voice_entry = _VOICE_POOL[hour_index % len(_VOICE_POOL)]
    logger.info(
        "Voice selected: %s (%s, %s)",
        voice_entry["name"], voice_entry["gender"], voice_entry["style"],
    )
    return voice_entry["name"]


def _get_fallback_voice_rotation(primary_voice: str) -> list[str]:
    """Return an ordered list of fallback voices, excluding the primary voice.

    When the primary voice fails, the pipeline tries each voice in this
    rotation until one succeeds.  The list is shuffled deterministically
    so different runs try different fallback voices for variety.
    """
    hour_index = int(time.time() // 3600)
    candidates = [v["name"] for v in _VOICE_POOL if v["name"] != primary_voice]
    # Deterministic shuffle based on current hour so fallback order varies
    import random
    rng = random.Random(hour_index + 1)
    rng.shuffle(candidates)
    return candidates


def _clean_text_for_tts(text: str) -> str:
    """Sanitise *text* so it is safe and natural for TTS engines.

    Strips any residual markup, normalises whitespace, and removes characters
    that TTS engines may try to spell out (e.g. ``<``, ``>``, ``&``).
    """
    # Remove any XML/HTML-like tags that may have leaked in
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Remove HTML entities
    cleaned = re.sub(r"&[a-zA-Z]+;", " ", cleaned)
    cleaned = re.sub(r"&#x?[0-9a-fA-F]+;", " ", cleaned)
    # Remove stray angle brackets; convert literal ampersands to "and"
    # so the TTS voice says "and" instead of spelling out "ampersand"
    cleaned = cleaned.replace("<", " ").replace(">", " ").replace("&", " and ")
    # Collapse multiple spaces into one
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _get_audio_duration(audio_path: Path) -> float:
    """Return the duration (in seconds) of an audio file.

    Tries ``mutagen`` first, then ``pydub`` as a fallback.
    Returns 0.0 if neither library is available.
    """
    # --- mutagen approach ---
    try:
        from mutagen.mp3 import MP3  # type: ignore[import]

        audio = MP3(str(audio_path))
        duration: float = audio.info.length
        logger.debug("Audio duration via mutagen: %.2f s", duration)
        return duration
    except Exception:  # noqa: BLE001
        pass

    # --- pydub approach ---
    try:
        from pydub import AudioSegment  # type: ignore[import]

        segment = AudioSegment.from_file(str(audio_path))
        duration = len(segment) / 1000.0
        logger.debug("Audio duration via pydub: %.2f s", duration)
        return duration
    except Exception:  # noqa: BLE001
        pass

    logger.warning("Could not determine audio duration; defaulting to 0.0 s")
    return 0.0


def _normalize_audio(audio_path: Path) -> None:
    """Normalize the loudness of an MP3 file in-place using pydub.

    Brings the peak amplitude to 0 dBFS so the narration always plays
    at a consistent, clear volume regardless of the TTS engine output level.
    """
    try:
        from pydub import AudioSegment  # type: ignore[import]
        from pydub.effects import normalize  # type: ignore[import]

        segment = AudioSegment.from_file(str(audio_path))
        normalized = normalize(segment)
        normalized.export(str(audio_path), format="mp3", bitrate=config.AUDIO_BITRATE)
        logger.debug("Audio normalization applied to '%s'", audio_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audio normalization skipped: %s", exc)


async def _generate_edge_tts(
    text: str, output_path: str, voice: str, rate: str
) -> list[dict]:
    """Async helper that calls edge-tts to synthesise *text* and save to *output_path*.

    Passes plain text to edge-tts (SSML is **not** used because edge-tts v7+
    internally escapes all XML tags, which causes the TTS engine to read the
    markup aloud instead of interpreting it).  The neural voice already
    handles sentence boundaries and comma pauses naturally from punctuation.

    Uses ``communicate.stream()`` to capture ``WordBoundary`` events which
    provide exact word-level timestamps directly from the TTS engine.

    Returns:
        A list of ``{"word": str, "start": float, "end": float}`` dicts
        (times in seconds) derived from the ``WordBoundary`` events.
    """
    import edge_tts  # type: ignore[import]

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    word_timestamps: list[dict] = []

    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset and duration are in 100-nanosecond ticks
                offset = chunk.get("offset", 0)
                duration = chunk.get("duration", 0)
                word = chunk.get("text", "")
                if not word:
                    continue
                start_s = offset / 10_000_000
                dur_s = duration / 10_000_000
                word_timestamps.append({
                    "word": word,
                    "start": start_s,
                    "end": start_s + dur_s,
                })

    return word_timestamps


def generate_speech(script_text: str) -> tuple[Path, float, list[dict]]:
    """Generate TTS audio for *script_text* using Microsoft Edge neural TTS.

    Tries the primary voice first, then rotates through the full Edge TTS
    voice pool as fallbacks if the primary voice fails.  No gTTS dependency.

    Args:
        script_text: The narration text to convert to speech.

    Returns:
        A tuple of ``(audio_path, duration_seconds, word_timestamps)`` where
        *audio_path* is a :class:`pathlib.Path` pointing to the generated MP3
        file and *word_timestamps* is a list of
        ``{"word": str, "start": float, "end": float}`` dicts (times in seconds).

    Raises:
        RuntimeError: If all Edge TTS voices fail.
    """
    # Write to a named temp file so it persists after the call
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    audio_path = Path(tmp_file.name)
    tmp_file.close()

    logger.info("Generating TTS for %d characters of script text…", len(script_text))

    # Sanitise the text to ensure no markup or special characters are spoken
    clean_text = _clean_text_for_tts(script_text)
    logger.debug("Cleaned TTS text (%d chars): %s…", len(clean_text), clean_text[:80])

    word_timestamps: list[dict] = []
    last_exc: Exception | None = None

    try:
        import edge_tts  # type: ignore[import]  # noqa: F401 — check availability
    except ImportError as exc:
        audio_path.unlink(missing_ok=True)
        raise RuntimeError(
            "edge-tts is not installed — run: pip install edge-tts"
        ) from exc

    primary_voice = pick_voice()
    voices_to_try = [primary_voice] + _get_fallback_voice_rotation(primary_voice)

    for voice in voices_to_try:
        try:
            word_timestamps = asyncio.run(
                _generate_edge_tts(
                    clean_text,
                    str(audio_path),
                    voice,
                    config.TTS_RATE,
                )
            )
            logger.info(
                "TTS generated via edge-tts (voice: %s, %d word timestamps)",
                voice, len(word_timestamps),
            )
            break  # Success — stop trying fallbacks
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("edge-tts voice '%s' failed (%s); trying next voice…", voice, exc)
            # Clear partial output before retrying; log if this cleanup also fails
            try:
                audio_path.write_bytes(b"")
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.debug("Could not clear partial audio file '%s': %s", audio_path, cleanup_exc)
    else:
        # All voices exhausted
        audio_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"All Edge TTS voices failed — last error: {last_exc}"
        ) from last_exc

    # Normalize audio loudness for a consistent, clear output level
    if getattr(config, "TTS_VOLUME_NORMALIZE", True):
        _normalize_audio(audio_path)

    duration = _get_audio_duration(audio_path)
    logger.info("TTS audio saved to '%s' (%.2f s)", audio_path, duration)
    return audio_path, duration, word_timestamps
