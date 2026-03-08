"""
tts.py — Text-to-speech generation using Microsoft Edge's free neural TTS.

Converts narration script text to an MP3 audio file and returns the file
path together with the audio duration in seconds.  Completely free — no
API keys required.

Primary engine: edge-tts (Microsoft Edge neural voices — natural, high quality)
Fallback engine: gTTS (Google's free TTS — works offline)
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import config

logger = logging.getLogger(__name__)


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


async def _generate_edge_tts(text: str, output_path: str, voice: str, rate: str) -> None:
    """Async helper that calls edge-tts to synthesise *text* and save to *output_path*."""
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

    # --- Primary: edge-tts (free Microsoft neural voice) ---
    try:
        import edge_tts  # type: ignore[import]  # noqa: F401 — check availability before asyncio.run

        asyncio.run(
            _generate_edge_tts(
                script_text,
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
                text=script_text,
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

    duration = _get_audio_duration(audio_path)
    logger.info("TTS audio saved to '%s' (%.2f s)", audio_path, duration)
    return audio_path, duration
