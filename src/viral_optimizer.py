"""
viral_optimizer.py — Viral analysis and optimization engine for YouTube Shorts.

Analyses trending topics and script content to score virality potential,
generate A/B title variants, suggest engagement hooks, and predict click-through
rates.  All heuristics are offline — no paid API keys required.

Typical usage::

    from src.viral_optimizer import ViralOptimizer
    optimizer = ViralOptimizer()
    score = optimizer.score_topic("AI breakthrough changes everything")
    optimized = optimizer.optimize_script_data(script_data, topic)
"""

import logging
import re
import time
from typing import TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Virality signal keywords — words/patterns associated with high engagement
# ---------------------------------------------------------------------------
_URGENCY_WORDS: set[str] = {
    "breaking", "urgent", "alert", "just in", "now", "today", "new", "latest",
    "first", "record", "historic", "unprecedented", "shocking", "explosive",
}

_CURIOSITY_WORDS: set[str] = {
    "secret", "hidden", "truth", "real", "actually", "nobody", "nobody knows",
    "untold", "unknown", "surprising", "unexpected", "exposed", "revealed",
    "you didn't know", "you need to know", "must see", "must watch",
}

_EMOTIONAL_WORDS: set[str] = {
    "amazing", "incredible", "unbelievable", "mind-blowing", "shocking",
    "heartbreaking", "inspiring", "emotional", "powerful", "life-changing",
    "game-changer", "revolutionary", "brilliant", "genius",
}

_LIST_PATTERNS: list[str] = [
    r"\b\d+\s+(things|ways|tips|tricks|facts|reasons|steps|secrets|hacks)\b",
    r"\b(top|best|worst|most)\s+\d+\b",
]

_QUESTION_PATTERN = re.compile(r"\?")
_NUMBER_PATTERN = re.compile(r"\b\d+\b")

# High-engagement niches proven to drive viral reach on Shorts
_HIGH_ENGAGEMENT_NICHES: set[str] = {
    "psychology", "money", "finance", "investing", "crypto", "ai", "tech",
    "health", "fitness", "life hacks", "productivity", "motivation", "mindset",
    "relationships", "dating", "travel", "food", "cooking", "beauty",
    "mystery", "crime", "history", "science", "space", "animals",
}

# Optimal title patterns for click-through rate on Shorts
_VIRAL_TITLE_PATTERNS: list[str] = [
    "{Topic} Will Shock You 😱",
    "Nobody Is Talking About {Topic} 🤫",
    "{Topic} Changes Everything 🔥",
    "The Truth About {Topic} Nobody Tells You 👀",
    "{Topic} in 60 Seconds — You Need This 📌",
    "Why {Topic} Is Blowing Up Right Now 🚀",
    "Stop Scrolling — {Topic} Just Changed ⚡",
    "{Topic}: The Part They Don't Tell You 🧠",
    "This {Topic} Secret Will Surprise You 💡",
    "{Topic} — I Had No Idea 😮",
    "Warning: {Topic} Is Not What You Think ⚠️",
    "{Topic} Explained Under 60 Seconds 🎯",
]

# Engagement hook phrases inserted at strategic video points
_ENGAGEMENT_HOOKS: list[str] = [
    "Stay to the end — the last part is the most important.",
    "Watch all the way through — you will not want to miss this.",
    "The detail at the end changes everything.",
    "This gets even more interesting in just a moment.",
    "Here comes the part most people miss entirely.",
    "This is where it gets really interesting.",
    "Pay close attention to what comes next.",
    "The next thirty seconds will surprise you.",
    "Most people stop here — the smart ones keep watching.",
    "Hold on — this is about to get a lot more interesting.",
]

# Comment-baiting prompts that drive engagement (ethical)
_COMMENT_PROMPTS: list[str] = [
    "What's your take on this? Drop it below. 👇",
    "Has this happened to you? Tell me in the comments.",
    "What did I miss? Let me know below. 💬",
    "Agree or disagree? Hit the comments.",
    "Share this with someone who needs to hear it.",
    "What would you add? Comment below.",
    "Which point surprised you most? Tell me.",
    "What topic should I cover next? Drop your idea below.",
]

# End-screen CTA recommendations for subscriber conversion
_END_SCREEN_CTAS: list[str] = [
    "Subscribe and turn on the bell — I post daily breakdowns like this.",
    "Follow now for your daily dose of insights that actually matter.",
    "Hit follow — every video is under 60 seconds and worth every second.",
    "Subscribe to stay ahead of the curve on stories like this.",
    "Turn on notifications so you never miss a briefing like this one.",
]


class ViralScoreResult(TypedDict):
    """Output from :meth:`ViralOptimizer.score_topic`."""
    score: float           # 0.0 – 1.0 virality estimate
    signals: list[str]     # Human-readable list of detected viral signals
    niche_match: bool      # True if topic matches a high-engagement niche
    urgency_score: float   # 0.0 – 1.0 urgency component
    curiosity_score: float # 0.0 – 1.0 curiosity/intrigue component
    emotion_score: float   # 0.0 – 1.0 emotional impact component


class OptimizedScriptData(TypedDict):
    """Enriched script data returned by :meth:`ViralOptimizer.optimize_script_data`."""
    title: str
    ab_title_variants: list[str]
    script: str
    caption_script: str
    hook: str
    scenes: list[str]
    tags: list[str]
    description: str
    engagement_hook: str       # Strategic mid-video retention hook
    comment_prompt: str        # Ethical comment-baiting suggestion
    end_screen_cta: str        # End-screen subscriber conversion CTA
    viral_score: float         # Virality estimate for this topic+script
    virality_signals: list[str]


class ViralOptimizer:
    """Viral analysis and optimization engine.

    All methods are stateless after construction — safe to call concurrently.
    """

    def score_topic(self, topic: str) -> ViralScoreResult:
        """Score a topic string for viral potential on YouTube Shorts.

        Uses keyword heuristics, niche matching, structural patterns, and
        title composition signals to estimate virality on a 0–1 scale.

        Args:
            topic: The trending topic string to evaluate.

        Returns:
            A :class:`ViralScoreResult` dict with score breakdown.
        """
        t_lower = topic.lower()
        signals: list[str] = []

        # --- Urgency signal ---
        urgency_hits = sum(1 for w in _URGENCY_WORDS if w in t_lower)
        urgency_score = min(urgency_hits / 3.0, 1.0)
        if urgency_hits:
            signals.append(f"urgency keywords detected ({urgency_hits})")

        # --- Curiosity signal ---
        curiosity_hits = sum(1 for w in _CURIOSITY_WORDS if w in t_lower)
        curiosity_score = min(curiosity_hits / 2.0, 1.0)
        if curiosity_hits:
            signals.append(f"curiosity keywords detected ({curiosity_hits})")

        # --- Emotional signal ---
        emotion_hits = sum(1 for w in _EMOTIONAL_WORDS if w in t_lower)
        emotion_score = min(emotion_hits / 2.0, 1.0)
        if emotion_hits:
            signals.append(f"emotional keywords detected ({emotion_hits})")

        # --- Niche match ---
        niche_match = any(niche in t_lower for niche in _HIGH_ENGAGEMENT_NICHES)
        if niche_match:
            signals.append("high-engagement niche match")

        # --- Question format (drives curiosity) ---
        has_question = bool(_QUESTION_PATTERN.search(topic))
        if has_question:
            signals.append("question format (high curiosity)")

        # --- Number/list format (drives clicks) ---
        has_number = bool(_NUMBER_PATTERN.search(topic))
        for pattern in _LIST_PATTERNS:
            if re.search(pattern, t_lower):
                has_number = True
                break
        if has_number:
            signals.append("number/list format (high CTR)")

        # --- Topic length heuristic: 4-8 words optimal ---
        word_count = len(topic.split())
        length_ok = 4 <= word_count <= 10
        if length_ok:
            signals.append("optimal topic length")

        # Composite score — weighted average
        base = (
            urgency_score * 0.25
            + curiosity_score * 0.25
            + emotion_score * 0.20
            + (0.15 if niche_match else 0.0)
            + (0.08 if has_question else 0.0)
            + (0.07 if has_number else 0.0)
        )
        # Slight boost for ideal length
        score = min(base + (0.05 if length_ok else 0.0), 1.0)
        # Minimum floor: ensures generic topics still receive a usable baseline
        # score so downstream systems always have a non-zero starting point.
        score = max(score, 0.30)

        logger.debug(
            "Viral score for '%s': %.2f (signals: %s)",
            topic, score, ", ".join(signals) or "none",
        )
        return ViralScoreResult(
            score=round(score, 3),
            signals=signals,
            niche_match=niche_match,
            urgency_score=round(urgency_score, 3),
            curiosity_score=round(curiosity_score, 3),
            emotion_score=round(emotion_score, 3),
        )

    def generate_ab_titles(self, topic: str, primary_title: str, count: int = 3) -> list[str]:
        """Generate A/B title variants for split-testing click-through rates.

        Returns a list of *count* alternative titles including the primary
        title as the first element.

        Args:
            topic:         Raw topic string.
            primary_title: The title already generated by the scriptwriter.
            count:         Total number of title variants to return (inc. primary).

        Returns:
            List of title strings.
        """
        import random
        display_topic = topic.strip().title()
        seed = int(time.time() // 3600)
        rng = random.Random(seed + 42)

        variants: list[str] = [primary_title]
        shuffled_patterns = _VIRAL_TITLE_PATTERNS.copy()
        rng.shuffle(shuffled_patterns)

        for pattern in shuffled_patterns:
            if len(variants) >= count:
                break
            candidate = pattern.format(Topic=display_topic)[:100]
            if candidate not in variants:
                variants.append(candidate)

        return variants[:count]

    def pick_engagement_hook(self, topic: str) -> str:
        """Select a mid-video retention hook suitable for *topic*.

        Args:
            topic: The video topic string.

        Returns:
            A retention hook sentence to insert at a strategic video point.
        """
        import random
        seed = int(time.time() // 3600) + hash(topic) % 1000
        rng = random.Random(seed)
        return rng.choice(_ENGAGEMENT_HOOKS)

    def pick_comment_prompt(self, topic: str) -> str:
        """Return a comment-baiting prompt for *topic*.

        Args:
            topic: The video topic string.

        Returns:
            An ethical comment engagement prompt string.
        """
        import random
        seed = int(time.time() // 3600) + hash(topic) % 500
        rng = random.Random(seed)
        return rng.choice(_COMMENT_PROMPTS)

    def pick_end_screen_cta(self) -> str:
        """Return an end-screen subscriber conversion CTA.

        Returns:
            An end-screen CTA string for overlay or description use.
        """
        import random
        seed = int(time.time() // 3600)
        rng = random.Random(seed + 99)
        return rng.choice(_END_SCREEN_CTAS)

    def optimize_script_data(self, script_data: dict, topic: str) -> "OptimizedScriptData":
        """Enrich *script_data* with viral optimization fields.

        Adds A/B title variants, engagement hooks, comment prompts, end-screen
        CTAs, and a virality score to the script data dict.

        Args:
            script_data: Base script data from the scriptwriter.
            topic:       The trending topic string used to generate the script.

        Returns:
            An :class:`OptimizedScriptData` dict with all original fields plus
            viral optimization additions.
        """
        viral_result = self.score_topic(topic)

        ab_titles = self.generate_ab_titles(
            topic, script_data.get("title", ""), count=3
        )
        engagement_hook = self.pick_engagement_hook(topic)
        comment_prompt = self.pick_comment_prompt(topic)
        end_screen_cta = self.pick_end_screen_cta()

        optimized: OptimizedScriptData = OptimizedScriptData(
            title=script_data.get("title", ""),
            ab_title_variants=ab_titles,
            script=script_data.get("script", ""),
            caption_script=script_data.get("caption_script", ""),
            hook=script_data.get("hook", ""),
            scenes=script_data.get("scenes", []),
            tags=script_data.get("tags", []),
            description=script_data.get("description", ""),
            engagement_hook=engagement_hook,
            comment_prompt=comment_prompt,
            end_screen_cta=end_screen_cta,
            viral_score=viral_result["score"],
            virality_signals=viral_result["signals"],
        )

        logger.info(
            "Viral optimization complete — score: %.2f, signals: %s",
            viral_result["score"],
            ", ".join(viral_result["signals"]) or "none",
        )
        return optimized
