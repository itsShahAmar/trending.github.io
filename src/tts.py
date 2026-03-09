"""
tts.py — Text-to-speech generation using Microsoft Edge's free neural TTS.

Converts narration script text to an MP3 audio file and returns the file
path together with the audio duration in seconds.  Completely free — no
API keys required.

Primary engine: edge-tts (Microsoft Edge neural voices — natural, high quality)
Fallback engine: gTTS (Google's free TTS — works offline)

Quality features:
- Text sanitisation to strip any markup before synthesis
- Post-generation loudness normalization via pydub
"""

import asyncio
import logging
import re
import tempfile
from pathlib import Path

import config

logger = logging.getLogger(__name__)


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


async def _generate_edge_tts(text: str, output_path: str, voice: str, rate: str) -> None:
    """Async helper that calls edge-tts to synthesise *text* and save to *output_path*.

    Passes plain text to edge-tts (SSML is **not** used because edge-tts v7+
    internally escapes all XML tags, which causes the TTS engine to read the
    markup aloud instead of interpreting it).  The neural voice already
    handles sentence boundaries and comma pauses naturally from punctuation.
    """
    import edge_tts  # type: ignore[import]

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def generate_speech(script_text: str) -> tuple[Path, float]:
    """Generate TTS audio for *script_text*.

    Tries Microsoft Edge's free neural TTS (edge-tts) first for natural,
    high-quality audio.  Falls back to Google's gTTS if edge-tts is
    unavailable or fails.

    Args:
        script_text: The narration text to convert to speech.

    Returns:
        A tuple of ``(audio_path, duration_seconds)`` where *audio_path* is a
        :class:`pathlib.Path` pointing to the generated MP3 file.

    Raises:
        RuntimeError: If all TTS engines fail.
    """
    # Write to a named temp file so it persists after the call
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    audio_path = Path(tmp_file.name)
    tmp_file.close()

    logger.info("Generating TTS for %d characters of script text…", len(script_text))

    # Sanitise the text to ensure no markup or special characters are spoken
    clean_text = _clean_text_for_tts(script_text)
    logger.debug("Cleaned TTS text (%d chars): %s…", len(clean_text), clean_text[:80])

    # --- Primary: edge-tts (free Microsoft neural voice) ---
    try:
        import edge_tts  # type: ignore[import]  # noqa: F401 — check availability before asyncio.run

        asyncio.run(
            _generate_edge_tts(
                clean_text,
                str(audio_path),
                config.TTS_VOICE,
                config.TTS_RATE,
            )
        )
        logger.info("TTS generated via edge-tts (voice: %s)", config.TTS_VOICE)
    except Exception as edge_exc:  # noqa: BLE001
        logger.warning("edge-tts failed (%s); falling back to gTTS", edge_exc)

        # --- Fallback: gTTS ---
        try:
            from gtts import gTTS  # type: ignore[import]
        except ImportError as exc:
            audio_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Neither edge-tts nor gTTS is installed — "
                "run: pip install edge-tts gTTS"
            ) from exc

        try:
            tts = gTTS(
                text=clean_text,
                lang=config.TTS_LANGUAGE,
                slow=False,
            )
            tts.save(str(audio_path))
            logger.info("TTS generated via gTTS (lang: %s)", config.TTS_LANGUAGE)
        except Exception as gtts_exc:
            audio_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Both TTS engines failed — edge-tts: {edge_exc}; gTTS: {gtts_exc}"
            ) from gtts_exc

    # Normalize audio loudness for a consistent, clear output level
    if getattr(config, "TTS_VOLUME_NORMALIZE", True):
        _normalize_audio(audio_path)

    duration = _get_audio_duration(audio_path)
    logger.info("TTS audio saved to '%s' (%.2f s)", audio_path, duration)
    return audio_path, duration
