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
import time
from typing import TypedDict

logger = logging.getLogger(__name__)

# Minimum / maximum acceptable word counts for the narration script
_MIN_WORDS = 60
_MAX_WORDS = 200


class ScriptData(TypedDict):
    """Structured output from the script generator."""

    title: str
    script: str
    caption_script: str
    hook: str
    scenes: list[str]
    tags: list[str]
    description: str


# ---------------------------------------------------------------------------
# Hook templates — the critical first 5 seconds that make or break watch time
# ---------------------------------------------------------------------------
_HOOKS: list[str] = [
    # Authority / breaking news
    "Breaking developments in {topic} are reshaping the landscape as we speak.",
    "Industry leaders are calling {topic} the most significant shift of the decade.",
    "Here is what the latest data reveals about {topic} — and why it matters to you.",
    "A critical update on {topic} that every informed person needs to hear right now.",
    "The conversation around {topic} just reached a tipping point — let me explain.",
    "{topic} is making headlines worldwide, and the implications are far-reaching.",
    "Experts have weighed in on {topic}, and their findings are truly compelling.",
    "If {topic} is not on your radar yet, this sixty-second briefing will change that.",
    "New analysis on {topic} has surfaced, and the results are impossible to ignore.",
    "Three pivotal insights about {topic} that will change how you see it entirely.",
    # Curiosity / hidden-truth
    "What most people get wrong about {topic} might actually cost them — here is the truth.",
    "The one detail about {topic} that mainstream coverage consistently overlooks.",
    "You have probably heard about {topic}, but the part they are not telling you is remarkable.",
    "Beneath the surface of {topic} lies a story that fundamentally changes the narrative.",
    "Stop what you are doing — {topic} just changed in a way most people have not noticed.",
    "Everyone is talking about {topic}, but nobody is telling you the most important part.",
    # Challenge / sceptic
    "Even the harshest critics of {topic} are now acknowledging the mounting evidence.",
    "Sceptics of {topic} are rethinking their position after the latest data dropped.",
    "The people who dismissed {topic} are now quietly reversing course — here is why.",
    # Urgency
    "The window to understand {topic} before it reshapes everything is narrowing fast.",
    "Time-sensitive insight on {topic}: here is what you need to act on right now.",
    "In the next sixty seconds I am going to show you why {topic} demands your attention today.",
    "Do not scroll past this — {topic} is developing faster than anyone predicted.",
    # Emotional / storytelling
    "A year ago, nobody took {topic} seriously. That changes right now.",
    "The story of {topic} is not what you think — and the real version is far more compelling.",
    "Here is the moment {topic} stopped being a theory and became an undeniable reality.",
    # Question / curiosity
    "What if everything you assumed about {topic} turned out to be only half the story?",
    "Could {topic} be the single most important development shaping the next five years?",
    "Why are the people closest to {topic} suddenly talking about it in hushed tones?",
    "What does {topic} actually mean for you — and why should you care right now?",
    # Number / list hook
    "Five words that define the {topic} story right now: pivotal, verified, urgent, real, yours.",
    "Three things the media gets wrong about {topic} — and one thing they got exactly right.",
]

# ---------------------------------------------------------------------------
# Body templates — informative middle section
# ---------------------------------------------------------------------------
_BODIES: list[str] = [
    (
        "Here is what is driving the momentum. {topic} has emerged as a defining "
        "force across multiple sectors. Leading analysts confirm that the scale of "
        "this development has few precedents in recent history. What makes it "
        "particularly noteworthy is the direct impact on consumers, businesses, "
        "and policymakers alike. The data points to a sustained trajectory that "
        "could redefine industry standards for years to come."
    ),
    (
        "Let me put this in perspective. {topic} has moved beyond early speculation "
        "into verified, measurable territory. Independent research now validates "
        "what insiders have been signaling for months. The convergence of market "
        "demand, technological advancement, and public interest has created a "
        "perfect storm of relevance. Whether you are a professional or an observer, "
        "the strategic implications here are substantial."
    ),
    (
        "Here is the full picture. {topic} has captured global attention for "
        "a reason that goes deeper than surface-level hype. Behind the headlines "
        "lies a fundamental shift in how stakeholders approach this space. "
        "Innovation, accountability, and scale are the three pillars driving "
        "this forward. The trajectory suggests that early adopters and informed "
        "audiences will benefit the most from understanding these dynamics now."
    ),
    (
        "Consider the broader context. {topic} represents more than a single "
        "event — it signals a structural transformation. The professional "
        "community has responded with unprecedented engagement, and fresh data "
        "continues to reinforce the significance of this movement. What began "
        "as a niche discussion has evolved into a mainstream priority with "
        "real-world consequences that are already taking shape."
    ),
    (
        "Let me walk you through the key factors. {topic} is gaining traction "
        "because it addresses a genuine need in the current landscape. Credible "
        "sources across industries have validated its importance, and the "
        "momentum shows no sign of slowing. For those paying close attention, "
        "the opportunities and implications here are both timely and actionable. "
        "This is a development worth following closely."
    ),
    (
        "Step back and look at the pattern. {topic} did not arrive without warning — "
        "the signals were there for those willing to look. What has changed is the "
        "pace of development and the scale of attention it now commands. The "
        "intersection of credible research, real-world outcomes, and public "
        "awareness has reached a critical threshold that makes this moment "
        "distinctly different from everything that came before it."
    ),
    (
        "Here is the angle that most coverage misses. {topic} is not just a story "
        "about what is happening right now — it is a story about what becomes "
        "possible next. The groundwork being laid today will determine outcomes "
        "that play out over months and years. Analysts who have studied comparable "
        "developments emphasise that the strategic value of staying informed "
        "right now is exceptionally high."
    ),
    (
        "The numbers tell a compelling story. {topic} has registered measurable "
        "movement across multiple indicators that analysts watch closely. The "
        "combination of increased participation, verifiable outcomes, and sustained "
        "momentum puts this in a category that demands serious attention. For "
        "context, comparable developments have historically preceded major shifts "
        "in how industries and individuals operate."
    ),
    (
        "Here is what makes {topic} different from the noise. Most trending stories "
        "fade within days. This one has compounding factors — a base of credible "
        "evidence, a growing community of informed voices, and real-world "
        "implications that build on each other. The quality of engagement "
        "surrounding {topic} signals something more durable than typical hype."
    ),
    (
        "Let us talk about the stakes. {topic} sits at the intersection of "
        "technology, society, and economics in a way that makes it genuinely "
        "consequential. The individuals and organisations who engage thoughtfully "
        "with this information now are positioning themselves well for what "
        "follows. The evidence consistently favours those who act on informed "
        "analysis rather than waiting for consensus to form."
    ),
    # New emotional / storytelling bodies
    (
        "Here is something the headlines rarely capture. {topic} is not just "
        "a news story — it is a turning point that real people are living through "
        "right now. Behind the data are individuals whose decisions, livelihoods, "
        "and futures are directly shaped by how this unfolds. That human dimension "
        "is precisely why understanding {topic} at a deeper level matters so much."
    ),
    (
        "Let me share what I have found. Digging beyond the surface on {topic} "
        "reveals a sequence of events that follows a remarkably consistent "
        "pattern. Those who recognised the early signals repositioned quickly. "
        "Those who waited are now playing catch-up. The gap between informed "
        "and uninformed is widening, and the information in this brief is "
        "designed to put you firmly on the right side of it."
    ),
    (
        "The context you are missing changes everything. {topic} did not emerge "
        "in a vacuum — it is the product of compounding forces that have been "
        "building quietly for years. Now that critical mass has been reached, "
        "the pace of change is accelerating. The smartest move right now is "
        "to understand the full picture rather than reacting to fragments."
    ),
    (
        "Picture this scenario. Six months from now, people will look back at "
        "this moment as when the trajectory of {topic} became undeniable. "
        "The evidence is not speculative — it is documented, peer-reviewed, "
        "and corroborated by independent sources across multiple disciplines. "
        "What you do with this information in the next few days genuinely matters."
    ),
    (
        "The detail that changes your understanding: {topic} has a second-order "
        "effect that almost nobody is discussing publicly. While the first-order "
        "impact is visible in headlines, the downstream consequences are shaping "
        "decisions at the highest levels of government, industry, and academia. "
        "This is the level of analysis that separates informed observers from "
        "those who are simply reacting to noise."
    ),
]

# ---------------------------------------------------------------------------
# Call-to-action templates — closing that drives engagement
# ---------------------------------------------------------------------------
_CTAS: list[str] = [
    "If this was valuable, tap like and subscribe for daily insights. Share your perspective on {topic} in the comments below.",
    "Hit subscribe so you never miss a briefing like this. What is your take on {topic}? Drop your thoughts in the comments.",
    "Like this breakdown and turn on notifications to stay ahead of the curve. Tell me how {topic} is affecting your world.",
    "Subscribe for concise, well-researched updates delivered daily. Let me know your experience with {topic} in the comments.",
    "If you found this insightful, share it with someone who needs to know. Follow for more expert-level analysis on trending topics.",
    "Stay ahead — subscribe and tap the bell so you never miss a briefing. What is your read on {topic}? Comment below.",
    "Every like tells the algorithm this content matters. Subscribe and join the conversation about {topic}.",
    "If you made it this far, you are exactly the kind of thoughtful viewer this channel is built for. Subscribe now.",
    "Knowledge is the edge — share this with someone navigating {topic} and help them stay informed.",
    "Follow for sharp, concise analysis every day. Drop a comment: what is your biggest question about {topic}?",
    # New power CTAs
    "This is the kind of insight that travels. Share it with one person who needs to hear it — then subscribe for more.",
    "Do not just watch — react. Leave your take on {topic} below. I read every comment.",
    "Tap follow and set a reminder — the follow-up to this story is going to be even bigger.",
    "If this changed how you see {topic}, the like button is how you say thank you to the algorithm. Do it.",
    "The smartest thing you can do right now: subscribe, share, and stay informed. See you in the next one.",
]

# ---------------------------------------------------------------------------
# Scene description templates — cinematic and high-energy for Pexels search
# ---------------------------------------------------------------------------
_SCENE_SETS: list[list[str]] = [
    [
        "Dramatic aerial city skyline at golden hour",
        "Close-up person scrolling phone with concentration",
        "Fast-paced montage glowing data screens",
        "Group professionals in animated discussion boardroom",
        "Abstract neon light trails motion blur",
    ],
    [
        "Extreme close-up hands typing laptop keyboard",
        "Wide angle crowd urban street rush hour",
        "Digital data visualization holographic display",
        "Confident presenter speaking direct to camera",
        "Epic sunrise over modern glass skyscrapers",
    ],
    [
        "Futuristic particle technology background dark",
        "Slow motion person walking busy city street",
        "Dramatic charts and graphs glowing monitor",
        "Creative studio workspace professional lighting",
        "Cinematic time-lapse storm clouds landscape",
    ],
    [
        "Glass office building exterior reflections sky",
        "Animated social media notifications explosion",
        "Surprised person double-take reaction close-up",
        "Vivid gradient neon abstract flowing background",
        "Bokeh night city lights shallow depth field",
    ],
    [
        "Aerial drone swooping intersection rush hour",
        "Focus pull tablet reading news articles",
        "Tense professional meeting conference glass room",
        "Highway traffic aerial fast hyperlapse",
        "Sunrise timelapse skyline silhouette",
    ],
    [
        "Professional broadcast microphone studio dark",
        "Young confident creator looking straight camera",
        "Animated statistics infographic bold colors",
        "Warm coffee shop shallow focus background",
        "Hands unlocking phone notification glow",
    ],
    [
        "Futuristic holographic interface sci-fi glow",
        "Team brainstorming whiteboard collaboration energy",
        "Financial district skyscrapers low angle dramatic",
        "Athlete sunrise training golden light",
        "Earth from orbit satellite view cinematic",
    ],
    [
        "Stacked books knowledge library warm light",
        "Entrepreneur standing desk focused working",
        "Analytics dashboard engagement metrics glowing",
        "Live event crowd energy hands raised",
        "Dramatic clouds fast motion timelapse",
    ],
    [
        "Underwater slow motion bubbles light rays",
        "Desert road perspective vanishing point dramatic",
        "Emergency lights flashing night dark city",
        "Currency notes falling slow motion",
        "Laboratory scientist close-up focus experiment",
    ],
    [
        "Mountain peak above clouds cinematic wide shot",
        "Chess pieces strategy close-up concept",
        "Breaking news broadcast studio live",
        "Handshake deal close-up confident",
        "Abstract flowing lines network connection",
    ],
]

# ---------------------------------------------------------------------------
# Title templates — SEO-strong, curiosity-driven, emoji-boosted
# ---------------------------------------------------------------------------
_TITLE_TEMPLATES: list[str] = [
    "{Topic} — What the Experts Are Saying 🔍",
    "The Real Story Behind {Topic} 📊",
    "{Topic} Is Redefining the Industry Right Now 🚀",
    "Why {Topic} Matters More Than Ever 💡",
    "{Topic} — A Must-Watch Briefing 📌",
    "The Latest on {Topic} — Key Takeaways 📈",
    "{Topic} Explained in 60 Seconds ⚡",
    "Inside {Topic} — What You Need to Know 🎯",
    "You Need to Know About {Topic} — Here's Why 🔥",
    "{Topic}: The Story Behind the Story 🧠",
    "How {Topic} Is Changing Everything Right Now 📅",
    "The Hidden Side of {Topic} Nobody Talks About 👀",
    "{Topic} — Breaking It Down in 60 Seconds ⏱️",
    "What {Topic} Really Means for You 🎯",
    "{Topic} Just Hit a New Level — Watch This 📈",
    "The Complete Picture on {Topic} 🌐",
]

# ---------------------------------------------------------------------------
# Description template
# ---------------------------------------------------------------------------
_DESCRIPTION_TEMPLATE = """🔍 {title}

Stay informed: {topic} is making waves and we break it down in under 60 seconds.

In this briefing, you will learn:
✅ Why {topic} is trending right now
✅ The key facts and data points you need to know
✅ What this means for you and what to watch next

📱 Subscribe for daily expert-level briefings on trending topics.

👍 Like this video if you found it valuable
💬 Share your perspective in the comments
🔔 Turn on notifications so you never miss an update

{hashtags}

#Shorts #Trending #Analysis #Insights #Briefing #News #Today"""


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


# ---------------------------------------------------------------------------
# Category-aware hook selection
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "tech": [
        "ai", "tech", "software", "hardware", "data", "cyber", "app", "code",
        "digital", "algorithm", "robot", "automation", "machine learning",
        "blockchain", "gpu", "chip", "semiconductor", "artificial", "intelligence",
    ],
    "finance": [
        "stock", "crypto", "bitcoin", "market", "invest", "economy", "bank",
        "fund", "trade", "money", "finance", "nasdaq", "dow", "inflation",
        "interest rate", "federal reserve",
    ],
    "health": [
        "health", "medical", "fitness", "diet", "mental", "wellness", "disease",
        "treatment", "vaccine", "drug", "nutrition", "exercise", "cancer",
        "study", "research",
    ],
}

_CATEGORY_HOOKS: dict[str, list[str]] = {
    "tech": [
        "The engineering behind {topic} is more groundbreaking than the headlines suggest.",
        "Developers and researchers are calling {topic} a once-in-a-generation technical shift.",
        "Here is the technical reality behind {topic} — stripped of hype and jargon.",
    ],
    "finance": [
        "Smart money has already positioned around {topic} — here is what they are seeing.",
        "The financial implications of {topic} are larger than most commentators admit.",
        "Before your next financial decision, understand what {topic} means for your portfolio.",
    ],
    "health": [
        "The science on {topic} just got clearer — and the findings matter for everyone.",
        "Health professionals are watching {topic} with unusual attention right now.",
        "What the latest research on {topic} reveals could genuinely change your daily habits.",
    ],
}


def _detect_category(topic: str) -> str | None:
    """Return the topic's best-matching category string, or *None* if no match."""
    t = topic.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return cat
    return None


_SEED_TIME_GRANULARITY = 21600  # seconds — changes seed every 6 hours


def _deterministic_seed(topic: str) -> int:
    """Create a seed from the topic and current time for varied selections.

    Incorporates the current hour so that each pipeline run (scheduled every
    few hours) produces a different script even for the same topic.
    """
    time_component = str(int(time.time() // _SEED_TIME_GRANULARITY))
    raw = topic + time_component
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)


def _titlecase_topic(topic: str) -> str:
    """Convert a topic string to title case for display."""
    return topic.strip().title()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_script(topic: str) -> ScriptData:
    """Generate a structured YouTube Shorts script for *topic*.

    Uses templates with time-seeded randomisation so each pipeline run
    produces a different script, even for the same topic.

    Args:
        topic: The trending topic string to write about.

    Returns:
        A :class:`ScriptData` dict with title, script, caption_script,
        scenes, tags, and description.

    Raises:
        ValueError: If the generated script fails validation.
    """
    logger.info("Generating script for topic: '%s'", topic)

    seed = _deterministic_seed(topic)
    rng = random.Random(seed)

    display_topic = _titlecase_topic(topic)

    # Select templates — include category-specific hooks when the topic matches
    category = _detect_category(topic)
    hook_pool = _HOOKS + (_CATEGORY_HOOKS.get(category, []) if category else [])
    hook = rng.choice(hook_pool).format(topic=display_topic)
    body = rng.choice(_BODIES).format(topic=display_topic)
    cta = rng.choice(_CTAS).format(topic=display_topic)
    scenes = list(rng.choice(_SCENE_SETS))

    # Build the full script (hook + body + cta for TTS audio)
    script_text = f"{hook} {body} {cta}"

    # Caption script excludes the hook to avoid duplicating the title on-screen
    caption_text = f"{body} {cta}"

    # Build title
    title = rng.choice(_TITLE_TEMPLATES).format(Topic=display_topic)
    title = title[:100]

    # Build tags
    tags = _topic_to_tags(topic)

    # Build description with trending hashtags
    try:
        from src.trending import get_trending_hashtags  # noqa: PLC0415
        trending_hashtags = get_trending_hashtags(max_tags=10)
    except Exception:  # noqa: BLE001
        trending_hashtags = []

    if trending_hashtags:
        hashtags = " ".join(trending_hashtags[:10])
    else:
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
        caption_script=caption_text,
        hook=hook,
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
