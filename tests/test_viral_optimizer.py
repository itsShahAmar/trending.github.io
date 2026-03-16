"""
tests/test_viral_optimizer.py — Unit tests for src/viral_optimizer.py

Tests the viral scoring engine, A/B title generation, and script optimization
without any external API calls.
Run with: python -m pytest tests/ -v
"""

import sys
import unittest
from unittest.mock import MagicMock

# Stub heavy optional imports not needed for viral optimizer tests
for mod in ("edge_tts", "moviepy", "moviepy.editor",
            "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
            "pydub", "mutagen", "mutagen.mp3",
            "googleapiclient", "googleapiclient.discovery"):
    sys.modules.setdefault(mod, MagicMock())


class TestViralScore(unittest.TestCase):
    """Tests for ViralOptimizer.score_topic()."""

    def setUp(self):
        from src.viral_optimizer import ViralOptimizer
        self.optimizer = ViralOptimizer()

    def test_returns_score_in_range(self):
        """Viral score must be between 0 and 1 inclusive."""
        result = self.optimizer.score_topic("breaking AI news")
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)

    def test_returns_required_keys(self):
        """ViralScoreResult must contain all required keys."""
        result = self.optimizer.score_topic("crypto market crash")
        required = {"score", "signals", "niche_match", "urgency_score",
                    "curiosity_score", "emotion_score"}
        self.assertEqual(required, required & result.keys())

    def test_signals_is_list_of_strings(self):
        """Signals must be a list of strings."""
        result = self.optimizer.score_topic("secret weight loss tips")
        self.assertIsInstance(result["signals"], list)
        self.assertTrue(all(isinstance(s, str) for s in result["signals"]))

    def test_niche_topic_scores_higher(self):
        """A known high-engagement niche topic should score at or above the minimum floor."""
        result = self.optimizer.score_topic("AI breakthrough")
        self.assertGreaterEqual(result["score"], 0.3)

    def test_empty_topic_does_not_raise(self):
        """Empty topic string must not raise an exception."""
        try:
            result = self.optimizer.score_topic("")
            self.assertIsInstance(result["score"], float)
        except Exception as exc:
            self.fail(f"score_topic('') raised unexpectedly: {exc}")

    def test_niche_match_flag(self):
        """High-engagement niche topics should set niche_match=True."""
        result = self.optimizer.score_topic("crypto investing tips")
        self.assertTrue(result["niche_match"])

    def test_generic_topic_niche_match_false(self):
        """A topic with no niche keywords should set niche_match=False."""
        result = self.optimizer.score_topic("random abstract concept xyz")
        self.assertFalse(result["niche_match"])


class TestABTitles(unittest.TestCase):
    """Tests for ViralOptimizer.generate_ab_titles()."""

    def setUp(self):
        from src.viral_optimizer import ViralOptimizer
        self.optimizer = ViralOptimizer()

    def test_returns_list_of_strings(self):
        variants = self.optimizer.generate_ab_titles("AI", "AI — What You Need to Know 🔍", count=3)
        self.assertIsInstance(variants, list)
        self.assertTrue(all(isinstance(v, str) for v in variants))

    def test_returns_correct_count(self):
        variants = self.optimizer.generate_ab_titles("bitcoin", "Bitcoin Title", count=3)
        self.assertEqual(len(variants), 3)

    def test_primary_title_is_first(self):
        primary = "My Original Title 📌"
        variants = self.optimizer.generate_ab_titles("topic", primary, count=3)
        self.assertEqual(variants[0], primary)

    def test_titles_within_100_chars(self):
        variants = self.optimizer.generate_ab_titles(
            "a very long topic name " * 3, "Original Title", count=3
        )
        for v in variants:
            self.assertLessEqual(len(v), 100, f"Title too long: {v!r}")

    def test_no_duplicate_titles(self):
        variants = self.optimizer.generate_ab_titles("space", "Space Title", count=3)
        self.assertEqual(len(variants), len(set(variants)))


class TestEngagementHooks(unittest.TestCase):
    """Tests for ViralOptimizer engagement hook and CTA helpers."""

    def setUp(self):
        from src.viral_optimizer import ViralOptimizer
        self.optimizer = ViralOptimizer()

    def test_engagement_hook_is_non_empty_string(self):
        hook = self.optimizer.pick_engagement_hook("machine learning")
        self.assertIsInstance(hook, str)
        self.assertTrue(hook.strip())

    def test_comment_prompt_is_non_empty_string(self):
        prompt = self.optimizer.pick_comment_prompt("health tips")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip())

    def test_end_screen_cta_is_non_empty_string(self):
        cta = self.optimizer.pick_end_screen_cta()
        self.assertIsInstance(cta, str)
        self.assertTrue(cta.strip())


class TestOptimizeScriptData(unittest.TestCase):
    """Tests for ViralOptimizer.optimize_script_data()."""

    def setUp(self):
        from src.viral_optimizer import ViralOptimizer
        self.optimizer = ViralOptimizer()
        self.base_script = {
            "title": "Test Title",
            "script": "Test script body.",
            "caption_script": "Caption script.",
            "hook": "Opening hook.",
            "scenes": ["scene 1", "scene 2"],
            "tags": ["tag1", "tag2"],
            "description": "Test description.",
        }

    def test_returns_all_required_keys(self):
        result = self.optimizer.optimize_script_data(self.base_script, "AI news")
        required = {
            "title", "ab_title_variants", "script", "caption_script", "hook",
            "scenes", "tags", "description", "engagement_hook", "comment_prompt",
            "end_screen_cta", "viral_score", "virality_signals",
        }
        self.assertEqual(required, required & result.keys())

    def test_preserves_original_title(self):
        result = self.optimizer.optimize_script_data(self.base_script, "AI news")
        self.assertEqual(result["title"], self.base_script["title"])

    def test_viral_score_in_range(self):
        result = self.optimizer.optimize_script_data(self.base_script, "breaking news")
        self.assertGreaterEqual(result["viral_score"], 0.0)
        self.assertLessEqual(result["viral_score"], 1.0)

    def test_ab_title_variants_is_list(self):
        result = self.optimizer.optimize_script_data(self.base_script, "climate change")
        self.assertIsInstance(result["ab_title_variants"], list)
        self.assertGreater(len(result["ab_title_variants"]), 0)

    def test_virality_signals_is_list(self):
        result = self.optimizer.optimize_script_data(self.base_script, "shocking truth revealed")
        self.assertIsInstance(result["virality_signals"], list)

    def test_does_not_crash_on_empty_script(self):
        empty_script = {
            "title": "", "script": "", "caption_script": "",
            "hook": "", "scenes": [], "tags": [], "description": "",
        }
        try:
            result = self.optimizer.optimize_script_data(empty_script, "")
            self.assertIn("viral_score", result)
        except Exception as exc:
            self.fail(f"optimize_script_data raised unexpectedly: {exc}")


if __name__ == "__main__":
    unittest.main()
