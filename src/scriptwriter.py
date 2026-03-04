"""
scriptwriter.py — AI-powered YouTube Shorts script generator.

Uses OpenAI's Chat Completions API (gpt-4o-mini) to produce structured
scripts complete with title, narration, scene descriptions, tags, and a
YouTube description.
"""

import json
import logging
import time
from typing import Any, TypedDict

import config

logger = logging.getLogger(__name__)

# Minimum / maximum acceptable word counts for the narration script
_MIN_WORDS = 60
_MAX_WORDS = 200

_SYSTEM_PROMPT = (
    "You are a professional YouTube Shorts scriptwriter. "
    "You craft highly engaging, viral short-form video scripts optimised for "
    "the YouTube Shorts feed. Your scripts are conversational, punchy, and "
    "always start with a hook that grabs attention within the first 3 seconds."
)

_USER_PROMPT_TEMPLATE = """Write a YouTube Shorts script about: {topic}

Return ONLY a valid JSON object with exactly these keys:
- "title": A catchy, click-worthy YouTube Shorts title (max 100 chars)
- "script": The full 30–50 second narration text (spoken words only, no stage directions)
- "scenes": A list of exactly 5 short visual scene descriptions for B-roll footage (each max 10 words)
- "tags": A list of 15–20 relevant hashtag-style tags (without the # symbol)
- "description": A YouTube video description (150–300 words) with relevant hashtags at the end

Rules for the script:
1. Open with a powerful hook in the first 1-2 sentences.
2. Use a conversational, energetic tone.
3. Keep sentences short and punchy.
4. End with a clear call-to-action (subscribe, like, comment).
5. The script should read naturally when spoken aloud — aim for 30-50 seconds at normal speaking pace.
"""


class ScriptData(TypedDict):
    """Structured output from the script generator."""

    title: str
    script: str
    scenes: list[str]
    tags: list[str]
    description: str


def _call_openai(topic: str, retries: int = 3, backoff: float = 2.0) -> dict[str, Any]:
    """Call the OpenAI Chat Completions API with retry/backoff logic."""
    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc

    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(topic=topic)},
                ],
                temperature=0.8,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)

    raise RuntimeError(f"OpenAI API failed after {retries} attempts for topic: {topic!r}")


def _validate_script(data: dict[str, Any]) -> ScriptData:
    """Validate and coerce the raw API response into a :class:`ScriptData`."""
    required_keys = {"title", "script", "scenes", "tags", "description"}
    missing = required_keys - data.keys()
    if missing:
        raise ValueError(f"Script response missing keys: {missing}")

    script_text: str = str(data["script"]).strip()
    word_count = len(script_text.split())
    if word_count < _MIN_WORDS:
        raise ValueError(f"Script too short ({word_count} words; min={_MIN_WORDS})")
    if word_count > _MAX_WORDS:
        logger.warning("Script slightly long (%d words); truncating is not applied", word_count)

    scenes = data["scenes"]
    if not isinstance(scenes, list) or len(scenes) < 1:
        raise ValueError("scenes must be a non-empty list")
    # Ensure exactly 5 scene descriptions
    while len(scenes) < 5:
        scenes.append(scenes[-1])
    scenes = scenes[:5]

    tags = data["tags"]
    if not isinstance(tags, list):
        tags = str(tags).split(",")

    return ScriptData(
        title=str(data["title"])[:100].strip(),
        script=script_text,
        scenes=[str(s).strip() for s in scenes],
        tags=[str(t).strip().lstrip("#") for t in tags],
        description=str(data["description"]).strip(),
    )


def generate_script(topic: str) -> ScriptData:
    """Generate a structured YouTube Shorts script for *topic*.

    Args:
        topic: The trending topic string to write about.

    Returns:
        A :class:`ScriptData` dict with title, script, scenes, tags, and
        description.

    Raises:
        RuntimeError: If the OpenAI API is unavailable or misconfigured.
        ValueError: If the generated script fails validation.
    """
    logger.info("Generating script for topic: '%s'", topic)
    raw = _call_openai(topic)
    script_data = _validate_script(raw)
    logger.info(
        "Script generated — title: '%s', words: %d",
        script_data["title"],
        len(script_data["script"].split()),
    )
    return script_data
