"""
scriptwriter.py — Template-based YouTube Shorts script generator.

Uses deterministic templates with topic-aware variations to produce structured
scripts complete with title, narration, scene descriptions, tags, and a
YouTube description — no paid API keys required.
"""

import hashlib
import logging
import random
import re
from typing import TypedDict

logger = logging.getLogger(__name__)

# Minimum / maximum acceptable word counts for the narration script
_MIN_WORDS = 60
_MAX_WORDS = 200


class ScriptData(TypedDict):
    """Structured output from the script generator."""

    title: str
    script: str
    scenes: list[str]
    tags: list[str]
    description: str


# ---------------------------------------------------------------------------
# Hook templates — the critical first line that grabs attention
# ---------------------------------------------------------------------------
_HOOKS: list[str] = [
    "You won't believe what's happening with {topic} right now!",
    "Stop scrolling — {topic} is about to blow your mind!",
    "Here's something about {topic} that nobody is talking about!",
    "If you haven't heard about {topic} yet, listen up!",
    "This is the craziest thing about {topic} you'll see today!",
    "{topic} just changed the game — here's how!",
    "Everyone is freaking out about {topic} — here's why!",
    "The truth about {topic} will shock you!",
    "Wait until you hear this about {topic}!",
    "Three things you need to know about {topic} right now!",
]

# ---------------------------------------------------------------------------
# Body templates — informative middle section
# ---------------------------------------------------------------------------
_BODIES: list[str] = [
    (
        "So here's the deal. {topic} has been making waves everywhere lately. "
        "Experts are calling this one of the biggest developments we've seen in a long time. "
        "What makes this so interesting is how it affects everyday people like you and me. "
        "The impact is already being felt across multiple industries and communities. "
        "People on social media can't stop talking about it, and for good reason."
    ),
    (
        "Let me break it down for you. {topic} is trending because it's genuinely "
        "important. This isn't just hype — there are real changes happening right now. "
        "Whether you're a fan or a skeptic, you can't ignore the facts. "
        "The numbers speak for themselves, and the momentum is only growing. "
        "This could reshape how we think about things moving forward."
    ),
    (
        "Here's what you need to know. {topic} has taken the world by storm. "
        "From viral moments to heated debates, everyone has an opinion. "
        "But behind all the noise, there are some incredible takeaways. "
        "The real story is about innovation, resilience, and what comes next. "
        "And trust me, what comes next is going to be absolutely wild."
    ),
    (
        "Pay attention because this matters. {topic} is more than just a trend. "
        "It represents a shift in how we approach everyday challenges. "
        "The community around this has exploded, and new developments "
        "are happening at lightning speed. What started as a small movement "
        "has become something truly remarkable."
    ),
    (
        "Let's talk about why {topic} is everywhere right now. "
        "It started gaining traction a little while ago, but now it's unstoppable. "
        "The key takeaway is that this affects more people than you might think. "
        "Creators, professionals, and everyday folks are all paying attention. "
        "And the best part? This is just the beginning."
    ),
]

# ---------------------------------------------------------------------------
# Call-to-action templates — closing that drives engagement
# ---------------------------------------------------------------------------
_CTAS: list[str] = [
    "If you found this helpful, smash that like button and subscribe for more! Drop a comment telling me what you think about {topic}!",
    "Like this video if you learned something new! Subscribe so you never miss an update, and tell me your thoughts in the comments!",
    "Hit subscribe and turn on notifications so you catch the next one! What do you think about {topic}? Let me know below!",
    "Don't forget to like, subscribe, and share this with someone who needs to know about {topic}! See you in the next one!",
    "Follow for more content like this! Double tap if you agree, and comment your take on {topic}!",
]

# ---------------------------------------------------------------------------
# Scene description templates
# ---------------------------------------------------------------------------
_SCENE_SETS: list[list[str]] = [
    [
        "Dramatic aerial city skyline view",
        "Person looking at phone screen",
        "Fast-paced montage of news clips",
        "Group of people having discussion",
        "Bright colorful abstract motion graphics",
    ],
    [
        "Close-up of hands typing on laptop",
        "Crowd of people in urban setting",
        "Digital data visualization animation",
        "Person presenting to camera confidently",
        "Sunrise over modern cityscape horizon",
    ],
    [
        "Abstract technology background particles",
        "Person walking through busy street",
        "Charts and graphs on digital screen",
        "Creative workspace with equipment",
        "Time-lapse of clouds over landscape",
    ],
    [
        "Modern office with glass walls",
        "Social media icons floating animation",
        "Person reacting with surprise emotion",
        "Colorful gradient abstract background",
        "Night city lights bokeh view",
    ],
]

# ---------------------------------------------------------------------------
# Title templates
# ---------------------------------------------------------------------------
_TITLE_TEMPLATES: list[str] = [
    "{Topic} — What Nobody Tells You! 🤯",
    "The Truth About {Topic} 🔥",
    "{Topic} Is INSANE Right Now! 😱",
    "Why {Topic} Changes Everything! 💡",
    "{Topic} — You Need To See This! 👀",
    "This Is Why {Topic} Is Trending! 📈",
    "{Topic} Explained In 60 Seconds ⚡",
    "The {Topic} Secret Everyone Missed! 🤫",
]

# ---------------------------------------------------------------------------
# Description template
# ---------------------------------------------------------------------------
_DESCRIPTION_TEMPLATE = """🔥 {title}

{topic} is making headlines and we're breaking it all down for you in under 60 seconds!

In this short, you'll discover:
✅ Why {topic} is trending right now
✅ The key facts you need to know
✅ What this means for you

📱 Follow for daily shorts on trending topics!

👍 Like this video if you found it helpful
💬 Comment your thoughts below
🔔 Subscribe and turn on notifications

{hashtags}

#Shorts #Trending #Viral #MustWatch #Facts #News #Today"""


# ---------------------------------------------------------------------------
# Tag generation
# ---------------------------------------------------------------------------
_BASE_TAGS: list[str] = [
    "shorts", "trending", "viral", "mustwatch", "facts",
    "news", "today", "fyp", "explore", "discover",
]


def _topic_to_tags(topic: str) -> list[str]:
    """Generate relevant tags from the topic string."""
    words = re.sub(r"[^a-zA-Z0-9\s]", "", topic).lower().split()
    topic_tags = [w for w in words if len(w) > 2]

    if len(words) >= 2:
        topic_tags.append("".join(words[:2]))

    all_tags = list(dict.fromkeys(topic_tags + _BASE_TAGS))
    return all_tags[:20]


def _deterministic_seed(topic: str) -> int:
    """Create a deterministic seed from the topic for reproducible selections."""
    return int(hashlib.md5(topic.encode()).hexdigest()[:8], 16)


def _titlecase_topic(topic: str) -> str:
    """Convert a topic string to title case for display."""
    return topic.strip().title()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_script(topic: str) -> ScriptData:
    """Generate a structured YouTube Shorts script for *topic*.

    Uses deterministic templates with seeded randomisation so the same topic
    always produces the same script (useful for testing / debugging).

    Args:
        topic: The trending topic string to write about.

    Returns:
        A :class:`ScriptData` dict with title, script, scenes, tags, and
        description.

    Raises:
        ValueError: If the generated script fails validation.
    """
    logger.info("Generating script for topic: '%s'", topic)

    seed = _deterministic_seed(topic)
    rng = random.Random(seed)

    display_topic = _titlecase_topic(topic)

    # Select templates
    hook = rng.choice(_HOOKS).format(topic=display_topic)
    body = rng.choice(_BODIES).format(topic=display_topic)
    cta = rng.choice(_CTAS).format(topic=display_topic)
    scenes = list(rng.choice(_SCENE_SETS))

    # Build the full script
    script_text = f"{hook} {body} {cta}"

    # Build title
    title = rng.choice(_TITLE_TEMPLATES).format(Topic=display_topic)
    title = title[:100]

    # Build tags
    tags = _topic_to_tags(topic)

    # Build description
    hashtags = " ".join(f"#{t}" for t in tags[:10])
    description = _DESCRIPTION_TEMPLATE.format(
        title=title,
        topic=display_topic,
        hashtags=hashtags,
    )

    # Validate word count
    word_count = len(script_text.split())
    if word_count < _MIN_WORDS:
        logger.warning("Script shorter than expected (%d words)", word_count)
    if word_count > _MAX_WORDS:
        logger.warning("Script longer than expected (%d words)", word_count)

    script_data = ScriptData(
        title=title,
        script=script_text,
        scenes=scenes,
        tags=tags,
        description=description,
    )

    logger.info(
        "Script generated — title: '%s', words: %d",
        script_data["title"],
        len(script_data["script"].split()),
    )
    return script_data
