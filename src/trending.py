"""
trending.py — Fetch trending topics from Google Trends, YouTube Shorts niches, and NewsAPI.

Returns a deduplicated list of trending topic strings and picks the
best topic using a simple cross-source scoring heuristic.
"""

import logging
import random
import time
import xml.etree.ElementTree as ET

import requests

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_TOPICS = 10  # Minimum number of topics to maintain in the combined list
_SEED_TIME_GRANULARITY = 3600  # seconds — rotate niche pool every hour

# ---------------------------------------------------------------------------
# Fallback topics used when all external sources fail
# ---------------------------------------------------------------------------
FALLBACK_TOPICS: list[str] = [
    "Viral life hacks you need to try",
    "Mind-blowing psychology facts",
    "Money mistakes to avoid in your 20s",
    "Gadgets that will change your life",
    "Hidden travel destinations no one knows",
    "Quick healthy meals under 5 minutes",
    "Scary facts you didn't know",
    "Satisfying videos compilation ideas",
    "Fitness motivation shorts",
    "Unbelievable science experiments",
]

# ---------------------------------------------------------------------------
# YouTube Shorts viral niche pools — proven categories for Shorts engagement
# ---------------------------------------------------------------------------
_VIRAL_SHORTS_NICHES: list[str] = [
    # Life hacks & productivity
    "Life hacks that actually work",
    "Productivity tips for busy people",
    "Cleaning hacks you wish you knew sooner",
    "Kitchen hacks that save time",
    "Organization tips for small spaces",
    # Psychology & mindset
    "Dark psychology tricks people use on you",
    "Psychology facts about human behavior",
    "Signs of high intelligence most people miss",
    "Body language secrets that reveal everything",
    "Mind tricks that will blow your mind",
    # Money & finance
    "Money habits of the wealthy",
    "Side hustles you can start today",
    "Financial mistakes that keep you broke",
    "Passive income ideas for beginners",
    "Investing tips nobody tells you",
    # Health & fitness
    "Exercises you can do anywhere",
    "Foods that boost your energy instantly",
    "Sleep hacks for better rest",
    "Health myths debunked by science",
    "Quick workout routines under 1 minute",
    # Technology & gadgets
    "Cool tech gadgets you didn't know existed",
    "Phone tricks most people don't know",
    "AI tools that will change everything",
    "Best apps you're not using yet",
    "Future technology that already exists",
    # Mystery & scary
    "Unsolved mysteries that still haunt us",
    "Creepy facts that will keep you up at night",
    "Abandoned places with dark histories",
    "True crime stories you need to hear",
    "Unexplained events caught on camera",
    # Animals & nature
    "Animal facts that seem fake but are real",
    "Cutest animal moments caught on camera",
    "Most dangerous animals in the world",
    "Nature phenomena you won't believe exist",
    "Pets doing hilarious things",
    # Food & cooking
    "Recipes you can make in 60 seconds",
    "Street food from around the world",
    "Food combinations you need to try",
    "Cooking mistakes everyone makes",
    "Viral food trends you must try",
    # Motivation & self-improvement
    "Habits that changed my life",
    "Morning routines of successful people",
    "How to build confidence fast",
    "Lessons most people learn too late",
    "Mindset shifts that changed everything",
    # History & facts
    "History facts they didn't teach in school",
    "Inventions that changed the world",
    "Ancient civilizations mysteries",
    "Facts about space that will amaze you",
    "World records that seem impossible",
    # Relationships & social
    "Red flags in relationships to watch for",
    "Social skills that make you instantly likeable",
    "Communication tricks that always work",
    "Dating advice nobody talks about",
    "Friendship facts backed by psychology",
    # Entertainment & pop culture
    "Movie details you definitely missed",
    "Celebrity facts that will surprise you",
    "Behind the scenes secrets of famous shows",
    "Video game facts you never knew",
    "Music industry secrets exposed",
    # DIY & crafts
    "DIY projects anyone can do",
    "Upcycling ideas that are genius",
    "Home decor hacks on a budget",
    "Satisfying art and craft videos",
    "Easy DIY gifts people actually want",
    # Travel & adventure
    "Places that don't feel real",
    "Travel tips seasoned travelers swear by",
    "Cheapest countries to visit right now",
    "Hidden gems in popular tourist cities",
    "Extreme adventures around the world",
    # Fashion & beauty
    "Style tips that elevate any outfit",
    "Beauty hacks that actually work",
    "Fashion trends coming back in style",
    "Skincare mistakes ruining your face",
    "Outfit ideas for every occasion",
    # Sports & fitness
    "Unbelievable sports moments caught on camera",
    "Workout challenges that went viral",
    "Sports facts that will shock you",
    "Athletic feats that seem superhuman",
    "Training secrets of elite athletes",
]


def _fetch_google_trends(retries: int = 3, backoff: float = 2.0) -> list[str]:
    """Fetch daily trending searches for the US from Google Trends RSS feed.

    Uses the public Google Trends RSS endpoint which is more reliable than
    the unofficial pytrends scraping library.
    """
    url = "https://trends.google.com/trending/rss?geo=US"

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            # Python 3.7.1+ stdlib XML parser does not resolve external entities
            # and has built-in protection against entity expansion attacks.
            root = ET.fromstring(resp.text)
            topics: list[str] = []
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    topics.append(title_el.text.strip())
            logger.info("Google Trends RSS returned %d topics", len(topics))
            return topics[:20]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Trends RSS attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)
    return []


def _fetch_youtube_trending_rss(retries: int = 3, backoff: float = 2.0) -> list[str]:
    """Fetch trending searches on YouTube via Google Trends RSS feed.

    Uses the ``gprop=youtube`` parameter to filter Google Trends for
    YouTube-specific searches.  Completely free — no API key required.
    """
    url = "https://trends.google.com/trending/rss"
    params = {"geo": "US", "gprop": "youtube"}

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            topics: list[str] = []
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    topics.append(title_el.text.strip())
            logger.info("YouTube Trends RSS returned %d topics", len(topics))
            return topics[:20]
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube Trends RSS attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)
    return []


def _get_viral_shorts_niches(count: int = 15) -> list[str]:
    """Return a rotating subset of proven viral YouTube Shorts niche topics.

    Uses time-seeded randomization so that each hourly pipeline run picks
    a different batch of niches, keeping content fresh and varied.
    """
    seed = int(time.time()) // _SEED_TIME_GRANULARITY
    rng = random.Random(seed)
    selected = rng.sample(_VIRAL_SHORTS_NICHES, min(count, len(_VIRAL_SHORTS_NICHES)))
    logger.info("Viral Shorts niches selected %d topics (seed=%d)", len(selected), seed)
    return selected


def _fetch_newsapi_trending(retries: int = 3, backoff: float = 2.0) -> list[str]:
    """Fetch top headline titles from NewsAPI.org.

    Requires ``NEWSAPI_KEY`` to be set; returns an empty list gracefully
    if the key is absent or the request fails.
    """
    if not config.NEWSAPI_KEY:
        return []

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "us",
        "pageSize": 20,
        "apiKey": config.NEWSAPI_KEY,
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            topics = [
                # NewsAPI titles often include a source suffix like "Title - Source Name";
                # strip the suffix to keep only the meaningful headline text.
                a["title"].split(" - ")[0].strip()
                for a in articles
                if a.get("title") and a["title"] != "[Removed]"
            ]
            logger.info("NewsAPI returned %d topics", len(topics))
            return topics[:20]
        except Exception as exc:  # noqa: BLE001
            logger.warning("NewsAPI attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)
    return []


def get_trending_topics() -> list[str]:
    """Combine Google Trends, YouTube Trends, viral Shorts niches, and NewsAPI results into a deduplicated list.

    Returns at least 10 topic strings, falling back to :data:`FALLBACK_TOPICS`
    if the external sources cannot provide enough results.
    """
    google_topics = _fetch_google_trends()
    yt_topics = _fetch_youtube_trending_rss()
    niche_topics = _get_viral_shorts_niches()
    newsapi_topics = _fetch_newsapi_trending()

    seen: set[str] = set()
    combined: list[str] = []
    for topic in google_topics + yt_topics + niche_topics + newsapi_topics:
        normalised = topic.strip()
        if normalised and normalised.lower() not in seen:
            seen.add(normalised.lower())
            combined.append(normalised)

    if len(combined) < _MIN_TOPICS:
        logger.info("Fewer than %d topics found (%d); padding with fallbacks", _MIN_TOPICS, len(combined))
        for fallback in FALLBACK_TOPICS:
            if fallback.lower() not in seen:
                seen.add(fallback.lower())
                combined.append(fallback)
            if len(combined) >= _MIN_TOPICS:
                break

    logger.info("Total unique topics available: %d", len(combined))
    return combined


def get_best_topic() -> str:
    """Pick the most viral/interesting topic using a cross-source scoring heuristic.

    Fetches from each source once, then scores topics so that those appearing
    in multiple sources rank higher.  Within each source, earlier results
    (higher rank) get more points.
    """
    google_topics = _fetch_google_trends()
    yt_topics = _fetch_youtube_trending_rss()
    niche_topics = _get_viral_shorts_niches()
    newsapi_topics = _fetch_newsapi_trending()

    scores: dict[str, float] = {}

    for rank, topic in enumerate(google_topics):
        key = topic.strip().lower()
        scores[key] = scores.get(key, 0) + (len(google_topics) - rank)

    for rank, topic in enumerate(yt_topics):
        key = topic.strip().lower()
        # Double the score if it already appeared in Google Trends (cross-source bonus)
        bonus = 2.0 if key in scores else 1.0
        scores[key] = scores.get(key, 0) + bonus * (len(yt_topics) - rank)

    for rank, topic in enumerate(niche_topics):
        key = topic.strip().lower()
        # Bonus for niches that also appear in trending sources
        bonus = 2.0 if key in scores else 1.0
        scores[key] = scores.get(key, 0) + bonus * (len(niche_topics) - rank)

    for rank, topic in enumerate(newsapi_topics):
        key = topic.strip().lower()
        # Double the score if it already appeared in another source (cross-source bonus)
        bonus = 2.0 if key in scores else 1.0
        scores[key] = scores.get(key, 0) + bonus * (len(newsapi_topics) - rank)

    # Rebuild mapping from lower-case key → original casing
    original: dict[str, str] = {}
    for topic in google_topics + yt_topics + niche_topics + newsapi_topics:
        key = topic.strip().lower()
        if key not in original:
            original[key] = topic.strip()

    if not scores:
        logger.warning("No trending topics found; using random fallback topic")
        return random.choice(FALLBACK_TOPICS)

    # Pick randomly from the top scoring topics (up to 5) to ensure variety across runs
    sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)
    top_keys = sorted_keys[:min(5, len(sorted_keys))]
    best_key = random.choice(top_keys)
    best_topic = original.get(best_key, FALLBACK_TOPICS[0])
    logger.info("Topic selected: '%s' (score=%.1f, from top %d)", best_topic, scores[best_key], len(top_keys))

    # Pad the combined topic list with fallbacks so get_trending_topics() stays
    # consistent without making a second round of network calls.
    seen: set[str] = {t.strip().lower() for t in google_topics + yt_topics + niche_topics + newsapi_topics}
    combined = list(original.values())
    for fallback in FALLBACK_TOPICS:
        if fallback.lower() not in seen:
            seen.add(fallback.lower())
            combined.append(fallback)
        if len(combined) >= _MIN_TOPICS:
            break
    logger.info("Total unique topics available: %d", len(combined))

    return best_topic
