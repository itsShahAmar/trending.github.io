"""
tests/test_music_alternatives.py — Unit tests for src/music_alternatives.py

Tests verify error-handling behaviour (404s, SSL errors, timeouts) without
making real network calls.  Run with: python -m pytest tests/ -v
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub heavy optional imports not needed for these tests
for _mod in ("moviepy", "moviepy.editor", "PIL", "PIL.Image",
             "PIL.ImageDraw", "pydub", "mutagen", "mutagen.mp3",
             "googleapiclient", "googleapiclient.discovery"):
    sys.modules.setdefault(_mod, MagicMock())


class TestDownloadIncompetechTrack(unittest.TestCase):
    """Tests for music_alternatives.download_incompetech_track()."""

    def _import(self):
        from src.music_alternatives import download_incompetech_track
        return download_incompetech_track

    def test_returns_path_on_success(self):
        """A successful download returns a Path."""
        import requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content = MagicMock(return_value=[b"audio_data"])

        with patch("requests.get", return_value=mock_resp):
            fn = self._import()
            result = fn("TestTrack", "https://example.com/track.mp3")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Path)

    def test_returns_none_on_http_404(self):
        """HTTP 404 returns None rather than raising."""
        import requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=404)
        )
        with patch("requests.get", return_value=mock_resp):
            fn = self._import()
            result = fn("MissingTrack", "https://example.com/missing.mp3")
        self.assertIsNone(result)

    def test_returns_none_on_connection_error(self):
        """Connection errors return None rather than raising."""
        import requests

        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            fn = self._import()
            result = fn("AnyTrack", "https://example.com/track.mp3")
        self.assertIsNone(result)


class TestDownloadCcmixterTrack(unittest.TestCase):
    """Tests for music_alternatives.download_ccmixter_track()."""

    def _import(self):
        from src.music_alternatives import download_ccmixter_track
        return download_ccmixter_track

    def test_returns_path_on_success(self):
        """Successful download returns a Path."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content = MagicMock(return_value=[b"audio_data"])

        with patch("requests.get", return_value=mock_resp):
            fn = self._import()
            result = fn(12345, "https://ccmixter.org/content/artist/track.mp3")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Path)

    def test_returns_none_on_ssl_error(self):
        """SSL errors (as seen in CI) return None rather than raising."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.SSLError("cert verify failed")):
            fn = self._import()
            result = fn(99999, "https://ccmixter.org/content/artist/track.mp3")
        self.assertIsNone(result)

    def test_returns_none_on_http_404(self):
        """HTTP 404 returns None rather than raising."""
        import requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=404)
        )
        with patch("requests.get", return_value=mock_resp):
            fn = self._import()
            result = fn(11111, "https://ccmixter.org/content/artist/missing.mp3")
        self.assertIsNone(result)

    def test_uses_verify_false(self):
        """SSL verification must be disabled to fix ccMixter cert errors."""
        calls = []

        def _fake_get(*args, **kwargs):
            calls.append(kwargs)
            m = MagicMock()
            m.raise_for_status = MagicMock()
            m.iter_content = MagicMock(return_value=[b"x"])
            return m

        with patch("requests.get", side_effect=_fake_get):
            fn = self._import()
            fn(1, "https://ccmixter.org/content/a/b.mp3")

        self.assertTrue(calls, "requests.get was not called")
        self.assertFalse(
            calls[0].get("verify", True),
            "verify should be False for ccMixter to fix SSL errors",
        )


class TestGetAlternativeMusic(unittest.TestCase):
    """Tests for music_alternatives.get_alternative_music()."""

    def _import(self):
        from src.music_alternatives import get_alternative_music
        return get_alternative_music

    def test_returns_none_when_all_fail(self):
        """Returns None when every source fails."""
        with patch("src.music_alternatives.download_incompetech_track", return_value=None), \
             patch("src.music_alternatives.download_ccmixter_track", return_value=None):
            fn = self._import()
            result = fn()
        self.assertIsNone(result)

    def test_returns_path_from_incompetech(self):
        """Returns Path when Incompetech succeeds."""
        fake_path = Path("/tmp/fake_track.mp3")
        with patch("src.music_alternatives.download_incompetech_track", return_value=fake_path), \
             patch("src.music_alternatives.download_ccmixter_track", return_value=None):
            fn = self._import()
            result = fn()
        self.assertEqual(result, fake_path)

    def test_falls_back_to_ccmixter_when_incompetech_fails(self):
        """Falls back to ccMixter when all Incompetech tracks fail."""
        fake_path = Path("/tmp/fake_ccmixter.mp3")
        with patch("src.music_alternatives.download_incompetech_track", return_value=None), \
             patch("src.music_alternatives.download_ccmixter_track", return_value=fake_path):
            fn = self._import()
            result = fn()
        self.assertEqual(result, fake_path)


if __name__ == "__main__":
    unittest.main()
