"""
pipeline.py — Main orchestrator for the YouTube Shorts automation pipeline.

Runs all steps in sequence:
  1. Fetch the best trending topic
  2. Generate an AI script
  3. Convert the script to speech (TTS)
  4. Create the video
  5. Upload to YouTube

Usage::

    python -m src.pipeline
"""

import logging
import time
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _cleanup(*paths: Path | None) -> None:
    """Delete temporary files, ignoring errors."""
    for p in paths:
        if p is not None:
            try:
                p.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass


def run_pipeline() -> None:
    """Execute the full YouTube Shorts creation and upload pipeline."""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("YouTube Shorts Automation — pipeline starting")
    logger.info("=" * 60)

    audio_path: Path | None = None
    video_path: Path | None = None

    try:
        # ------------------------------------------------------------------
        # Step 0: Validate YouTube credentials (fail fast before heavy work)
        # ------------------------------------------------------------------
        logger.info("[0/6] Validating YouTube credentials…")
        from src.uploader import validate_credentials  # noqa: PLC0415

        validate_credentials()
        logger.info("      Credentials OK")

        # ------------------------------------------------------------------
        # Step 1: Find best trending topic
        # ------------------------------------------------------------------
        logger.info("[1/6] Fetching trending topics…")
        from src.trending import get_best_topic  # noqa: PLC0415

        topic = get_best_topic()
        logger.info("      Topic selected: '%s'", topic)

        # ------------------------------------------------------------------
        # Step 2: Generate AI script
        # ------------------------------------------------------------------
        logger.info("[2/6] Generating script for topic: '%s'…", topic)
        from src.scriptwriter import generate_script  # noqa: PLC0415

        script_data = generate_script(topic)

        # ------------------------------------------------------------------
        # Step 2b: Viral optimization (enrich script data with engagement hooks)
        # ------------------------------------------------------------------
        if getattr(config, "VIRAL_OPTIMIZATION_ENABLED", False):
            try:
                from src.viral_optimizer import ViralOptimizer  # noqa: PLC0415
                optimizer = ViralOptimizer()
                optimized = optimizer.optimize_script_data(script_data, topic)
                # Overlay viral fields onto script_data while keeping base fields intact
                script_data = {**script_data, **optimized}
                logger.info(
                    "      Viral score: %.2f — signals: %s",
                    optimized.get("viral_score", 0.0),
                    ", ".join(optimized.get("virality_signals", [])) or "none",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Viral optimization skipped: %s", exc)

        title = script_data["title"]
        script_text = script_data["script"]
        caption_text = script_data["caption_script"]
        hook_text = script_data["hook"]
        scenes = script_data["scenes"]
        tags = script_data["tags"]
        description = script_data["description"]
        logger.info("      Title: '%s'", title)

        # ------------------------------------------------------------------
        # Step 3: Text-to-speech
        # ------------------------------------------------------------------
        logger.info("[3/6] Generating TTS audio…")
        from src.tts import generate_speech  # noqa: PLC0415

        audio_path, audio_duration, word_timestamps = generate_speech(script_text)
        logger.info("      Audio duration: %.2f s", audio_duration)

        # ------------------------------------------------------------------
        # Step 3.5: Background music selection
        # ------------------------------------------------------------------
        logger.info("[3.5/6] 🎵 Music — selecting scene-aware background music…")
        music_path = None
        if getattr(config, "BG_MUSIC_ENABLED", False):
            try:
                from src.music_selector import select_background_music  # noqa: PLC0415

                music_path = select_background_music(
                    scenes=scenes,
                    topic=topic,
                    duration=int(audio_duration) + 5,
                )
                logger.info("      Background music: '%s'", music_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Music selection failed, continuing without music: %s", exc)

        # ------------------------------------------------------------------
        # Step 4: Create video
        # ------------------------------------------------------------------
        logger.info("[4/6] 🎬 Assembling — creating video with stock footage…")
        from src.video_creator import create_video  # noqa: PLC0415

        # Pass full script text so every spoken word gets a caption.
        # A single subtitle band in the lower third covers hook + body + CTA —
        # no duplicate top subtitle.
        video_path = create_video(
            audio_path, script_text, scenes, audio_duration,
            hook_text=hook_text, word_timestamps=word_timestamps,
            music_path=music_path,
        )
        logger.info("      Video path: '%s'", video_path)

        # ------------------------------------------------------------------
        # Step 5: Upload to YouTube
        # ------------------------------------------------------------------
        logger.info("[5/6] Uploading to YouTube…")
        from src.uploader import upload_video  # noqa: PLC0415

        video_id, video_url = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
        )
        logger.info("      Upload complete: %s", video_url)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("Pipeline completed in %.1f seconds", elapsed)
        logger.info("  Topic      : %s", topic)
        logger.info("  Title      : %s", title)
        logger.info("  Video ID   : %s", video_id)
        logger.info("  URL        : %s", video_url)
        logger.info("=" * 60)

    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - start_time
        logger.error("Pipeline failed after %.1f seconds: %s", elapsed, exc, exc_info=True)
    finally:
        _cleanup(audio_path, video_path)
        logger.info("Temporary files cleaned up")


if __name__ == "__main__":
    run_pipeline()
