"""
tests/test_trending.py — Unit tests for src/trending.py

Tests the trending hashtag generation without making external API calls.
Run with: python -m pytest tests/test_trending.py -v
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Stub heavy optional imports not needed for trending tests
for mod in ("edge_tts", "gtts", "moviepy", "moviepy.editor",
            "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
            "pydub", "mutagen", "mutagen.mp3",
            "googleapiclient", "googleapiclient.discovery"):
    sys.modules.setdefault(mod, MagicMock())


class TestGetTrendingHashtags(unittest.TestCase):
    """Tests for trending.get_trending_hashtags()."""

    def setUp(self):
        from src.trending import get_trending_hashtags
        self.get_trending_hashtags = get_trending_hashtags

    def test_returns_list_of_strings(self):
        """Result must be a list of strings."""
        topics = ["AI advancements", "Bitcoin price"]
        result = self.get_trending_hashtags(topics=topics)
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(t, str) for t in result))

    def test_hashtags_start_with_hash(self):
        """Every returned hashtag must start with '#'."""
        topics = ["climate change", "space exploration"]
        result = self.get_trending_hashtags(topics=topics)
        for tag in result:
            self.assertTrue(tag.startswith("#"), f"Hashtag {tag!r} must start with '#'")

    def test_includes_evergreen_hashtags(self):
        """Result should include evergreen hashtags like #Shorts, #Trending."""
        result = self.get_trending_hashtags(topics=["test topic"])
        lower_tags = [t.lower() for t in result]
        self.assertIn("#shorts", lower_tags)
        self.assertIn("#trending", lower_tags)

    def test_max_tags_limit(self):
        """Result should not exceed the max_tags limit."""
        topics = [f"topic {i}" for i in range(50)]
        result = self.get_trending_hashtags(topics=topics, max_tags=5)
        self.assertLessEqual(len(result), 5)

    def test_no_duplicate_hashtags(self):
        """Hashtags must be deduplicated (case-insensitive)."""
        topics = ["AI tools", "ai innovations", "AI breakthrough"]
        result = self.get_trending_hashtags(topics=topics)
        lower_tags = [t.lower() for t in result]
        self.assertEqual(len(lower_tags), len(set(lower_tags)),
                         "Hashtags must not contain duplicates")

    def test_empty_topics_returns_evergreen(self):
        """With no topics, should still return evergreen hashtags."""
        result = self.get_trending_hashtags(topics=[])
        self.assertGreater(len(result), 0)

    def test_short_words_filtered(self):
        """Words with 2 or fewer characters should not become hashtags."""
        topics = ["AI is here"]
        result = self.get_trending_hashtags(topics=topics)
        # "is" (2 chars) should not be a standalone hashtag
        individual_tags = [t.lower() for t in result]
        self.assertNotIn("#is", individual_tags)

    def test_default_max_tags(self):
        """Default max_tags should be 15."""
        topics = [f"topic word{i} extra{i}" for i in range(50)]
        result = self.get_trending_hashtags(topics=topics)
        self.assertLessEqual(len(result), 15)


if __name__ == "__main__":
    unittest.main()
