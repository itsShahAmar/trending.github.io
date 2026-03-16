"""
tests/test_tts.py — Unit tests for src/tts.py

Tests the Edge TTS voice selection, text sanitisation, and fallback rotation
without making real network calls to the TTS service.
Run with: python -m pytest tests/ -v
"""

import sys
import unittest
from unittest.mock import MagicMock

# Stub heavy optional imports not needed for TTS tests
for mod in ("edge_tts", "moviepy", "moviepy.editor",
            "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
            "pydub", "pydub.effects", "mutagen", "mutagen.mp3",
            "googleapiclient", "googleapiclient.discovery"):
    sys.modules.setdefault(mod, MagicMock())


class TestPickVoice(unittest.TestCase):
    """Tests for tts.pick_voice()."""

    def setUp(self):
        from src.tts import pick_voice, _VOICE_POOL
        self.pick_voice = pick_voice
        self.voice_pool = _VOICE_POOL

    def test_returns_string(self):
        voice = self.pick_voice()
        self.assertIsInstance(voice, str)

    def test_returns_valid_neural_voice(self):
        """Returned voice must be in the pool."""
        voice = self.pick_voice()
        pool_names = [v["name"] for v in self.voice_pool]
        self.assertIn(voice, pool_names)

    def test_voice_rotation_produces_variety(self):
        """Different hour seeds must produce at least 2 different voices from pool."""
        import src.tts as tts_module
        import time

        voices_seen: set = set()
        # Simulate 24 different hours to verify rotation
        original_time = time.time
        try:
            for hour in range(24):
                time.time = lambda h=hour: h * 3600.0
                voices_seen.add(tts_module.pick_voice())
        finally:
            time.time = original_time

        self.assertGreater(len(voices_seen), 1, "Voice rotation must produce multiple voices")


class TestCleanTextForTTS(unittest.TestCase):
    """Tests for tts._clean_text_for_tts()."""

    def setUp(self):
        from src.tts import _clean_text_for_tts
        self.clean = _clean_text_for_tts

    def test_removes_xml_tags(self):
        cleaned = self.clean("<speak>Hello world</speak>")
        self.assertNotIn("<speak>", cleaned)
        self.assertNotIn("</speak>", cleaned)

    def test_removes_ssml_tags(self):
        cleaned = self.clean("<voice name='test'>Hello</voice>")
        self.assertNotIn("<voice", cleaned)
        self.assertNotIn("</voice>", cleaned)

    def test_converts_ampersand(self):
        cleaned = self.clean("cats & dogs")
        self.assertIn("and", cleaned)
        self.assertNotIn("&", cleaned)

    def test_collapses_whitespace(self):
        cleaned = self.clean("hello   world   test")
        self.assertNotIn("  ", cleaned)

    def test_plain_text_unchanged(self):
        text = "This is a clean plain text sentence."
        cleaned = self.clean(text)
        self.assertEqual(cleaned.strip(), text)

    def test_empty_string(self):
        cleaned = self.clean("")
        self.assertEqual(cleaned, "")


class TestFallbackVoiceRotation(unittest.TestCase):
    """Tests for tts._get_fallback_voice_rotation()."""

    def setUp(self):
        from src.tts import _get_fallback_voice_rotation, _VOICE_POOL
        self.get_fallback = _get_fallback_voice_rotation
        self.voice_pool = _VOICE_POOL

    def test_excludes_primary_voice(self):
        primary = "en-US-JennyNeural"
        fallbacks = self.get_fallback(primary)
        self.assertNotIn(primary, fallbacks)

    def test_returns_list_of_strings(self):
        fallbacks = self.get_fallback("en-US-GuyNeural")
        self.assertIsInstance(fallbacks, list)
        self.assertTrue(all(isinstance(v, str) for v in fallbacks))

    def test_contains_all_other_voices(self):
        """Fallback list should include all pool voices except the primary."""
        primary = "en-US-JennyNeural"
        fallbacks = self.get_fallback(primary)
        pool_names = {v["name"] for v in self.voice_pool}
        expected = pool_names - {primary}
        self.assertEqual(set(fallbacks), expected)


class TestNoGTTSDependency(unittest.TestCase):
    """Verify that gTTS is not imported or used anywhere in tts.py."""

    def test_gtts_not_imported_in_tts_module(self):
        """tts.py must not import gTTS."""
        from pathlib import Path
        tts_source = (
            Path(__file__).parent.parent / "src" / "tts.py"
        ).read_text()
        # Check that gTTS is not imported (allow docstring mentions)
        import re
        import_lines = [
            line for line in tts_source.splitlines()
            if re.match(r"\s*(import|from)\s+", line)
        ]
        self.assertFalse(
            any("gtts" in line.lower() for line in import_lines),
            "tts.py must not import gTTS",
        )

    def test_requirements_no_gtts(self):
        """requirements.txt must not include gTTS."""
        from pathlib import Path
        requirements = (
            Path(__file__).parent.parent / "requirements.txt"
        ).read_text().lower()
        self.assertNotIn("gtts", requirements,
                         "requirements.txt must not include gTTS")


if __name__ == "__main__":
    unittest.main()
