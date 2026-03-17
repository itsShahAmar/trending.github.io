"""
tests/test_music_selector.py — Unit tests for src/music_selector.py

Tests verify the selection logic (FMA → alternatives → silence) without
making real network calls or writing to the real cache directory.
Run with: python -m pytest tests/ -v
"""

import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub heavy optional imports not needed for these tests
for _mod in ("moviepy", "moviepy.editor", "PIL", "PIL.Image",
             "PIL.ImageDraw", "pydub", "mutagen", "mutagen.mp3",
             "googleapiclient", "googleapiclient.discovery"):
    sys.modules.setdefault(_mod, MagicMock())


class TestBuildMoodQuery(unittest.TestCase):
    """Tests for music_selector._build_mood_query()."""

    def _import(self):
        from src.music_selector import _build_mood_query
        return _build_mood_query

    def test_food_topic_yields_kitchen_query(self):
        fn = self._import()
        query = fn(["cooking pasta", "kitchen utensils"], "pasta recipes")
        self.assertIn("kitchen", query.lower())

    def test_tech_topic_yields_cinematic_query(self):
        fn = self._import()
        query = fn(["robot assembly", "circuit board"], "AI innovation")
        self.assertIn("tech", query.lower())

    def test_generic_topic_contains_upbeat(self):
        fn = self._import()
        query = fn(["scenic forest", "mountain view"], "nature walk")
        self.assertIn("upbeat", query.lower())

    def test_returns_string(self):
        fn = self._import()
        result = fn([], "")
        self.assertIsInstance(result, str)


class TestCreateSilence(unittest.TestCase):
    """Tests for music_selector._create_silence()."""

    def _import(self):
        from src.music_selector import _create_silence
        return _create_silence

    def test_creates_valid_wav_file(self):
        fn = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "silence.wav"
            result = fn(3, out)
            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 0)
            # Verify it's a valid WAV
            with wave.open(str(result), "r") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 44100)

    def test_returns_same_path(self):
        fn = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "silence.wav"
            result = fn(1, out)
        self.assertEqual(result, out)


class TestSelectBackgroundMusic(unittest.TestCase):
    """Tests for music_selector.select_background_music()."""

    def _import(self):
        from src.music_selector import select_background_music
        return select_background_music

    def _run_with_cache(self, fma_result, alt_result):
        """Helper: run select_background_music with a persistent temp cache dir."""
        import atexit
        import shutil
        tmp = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, tmp, True)  # clean up at process exit
        cache_dir = Path(tmp) / "music"
        with patch("src.music_selector._CACHE_DIR", cache_dir), \
             patch("src.music_selector._fetch_fma_track", return_value=fma_result), \
             patch("src.music_alternatives.download_incompetech_track", return_value=None), \
             patch("src.music_alternatives.download_ccmixter_track", return_value=None), \
             patch("src.music_selector.get_alternative_music", return_value=alt_result):
            fn = self._import()
            result = fn(scenes=["kitchen"], topic="cooking", duration=3)
        return result

    def test_falls_back_to_silence_when_all_sources_fail(self):
        """When FMA and alternatives both fail, a WAV path is returned."""
        result = self._run_with_cache(fma_result=None, alt_result=None)
        self.assertIsNotNone(result)
        self.assertEqual(result.suffix, ".wav")

    def test_silence_fallback_is_readable_wav(self):
        """The silence WAV produced by the fallback is a valid audio file."""
        result = self._run_with_cache(fma_result=None, alt_result=None)
        with wave.open(str(result), "r") as wf:
            self.assertEqual(wf.getnchannels(), 2)

    def test_uses_fma_result_when_available(self):
        """When FMA succeeds, its path is returned (after cache rename)."""
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "music"
            cache_dir.mkdir(parents=True)
            # Simulate FMA returning a path inside the cache dir
            fma_path = cache_dir / "fma_abc123.mp3"
            fma_path.write_bytes(b"fake_mp3")

            with patch("src.music_selector._CACHE_DIR", cache_dir), \
                 patch("src.music_selector._fetch_fma_track", return_value=fma_path), \
                 patch("src.music_selector.get_alternative_music", return_value=None):
                fn = self._import()
                result = fn(scenes=["office"], topic="tech", duration=3)

        self.assertIsNotNone(result)
        self.assertEqual(result.suffix, ".mp3")

    def test_cache_hit_skips_network(self):
        """A second call with the same topic/scenes uses the cache."""
        import hashlib
        import shutil
        tmp = tempfile.mkdtemp()
        try:
            cache_dir = Path(tmp) / "music"
            cache_dir.mkdir(parents=True)

            # Pre-populate cache with a silence file matching the expected key.
            # Key uses: topic + "|" + "|".join(scenes)
            key = hashlib.md5(("cooking|kitchen").encode()).hexdigest()[:12]
            cached_file = cache_dir / f"{key}_silence.wav"
            # Write a minimal valid WAV
            with wave.open(str(cached_file), "w") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b"\x00" * 44100 * 2 * 2)

            fma_mock = MagicMock(return_value=None)
            alt_mock = MagicMock(return_value=None)

            with patch("src.music_selector._CACHE_DIR", cache_dir), \
                 patch("src.music_selector._fetch_fma_track", fma_mock), \
                 patch("src.music_selector.get_alternative_music", alt_mock):
                fn = self._import()
                result = fn(scenes=["kitchen"], topic="cooking", duration=3)

            # Cache was hit so network helpers should not have been called
            fma_mock.assert_not_called()
            alt_mock.assert_not_called()
            self.assertEqual(result, cached_file)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFetchFmaTrack(unittest.TestCase):
    """Tests for music_selector._fetch_fma_track()."""

    def _import(self):
        from src.music_selector import _fetch_fma_track
        return _fetch_fma_track

    def test_returns_none_on_http_404(self):
        """FMA returning 404 yields None without crashing."""
        import requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=404)
        )
        with patch("requests.get", return_value=mock_resp):
            fn = self._import()
            with tempfile.TemporaryDirectory() as tmp:
                result = fn("background music", Path(tmp))
        self.assertIsNone(result)

    def test_returns_none_when_dataset_is_empty(self):
        """Empty FMA dataset yields None."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"dataset": []}

        with patch("requests.get", return_value=mock_resp):
            fn = self._import()
            with tempfile.TemporaryDirectory() as tmp:
                result = fn("background music", Path(tmp))
        self.assertIsNone(result)

    def test_returns_none_on_connection_error(self):
        """Connection errors yield None without crashing."""
        import requests

        with patch("requests.get", side_effect=requests.ConnectionError("timeout")):
            fn = self._import()
            with tempfile.TemporaryDirectory() as tmp:
                result = fn("background music", Path(tmp))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
