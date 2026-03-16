"""Central configuration for the YouTube Shorts Automation pipeline."""

import os

# API Keys (loaded from GitHub Secrets / environment variables)
YOUTUBE_CLIENT_SECRET_JSON: str | None = os.getenv("YOUTUBE_CLIENT_SECRET")  # JSON string of OAuth2 client secret
YOUTUBE_TOKEN_JSON: str | None = os.getenv("YOUTUBE_TOKEN")  # JSON string of OAuth2 token
PEXELS_API_KEY: str | None = os.getenv("PEXELS_API_KEY")  # For stock footage (free tier)
NEWSAPI_KEY: str | None = os.getenv("NEWSAPI_KEY")  # NewsAPI.org key for trending headlines (optional)

# ---------------------------------------------------------------------------
# OpenRouter.ai — main AI script writing engine
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")  # OpenRouter.ai API key
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
OPENROUTER_FALLBACK_MODELS: list = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2-7b-instruct:free",
]
OPENROUTER_TIMEOUT: int = 30  # seconds per API request
OPENROUTER_ENABLED: bool = (
    # Allow explicit opt-out via OPENROUTER_ENABLED=false even when key is set
    os.getenv("OPENROUTER_ENABLED", "").lower() not in ("0", "false", "no")
    and bool(os.getenv("OPENROUTER_API_KEY"))
)

# ---------------------------------------------------------------------------
# Stock footage sources — multi-provider with smart fallback chain
# ---------------------------------------------------------------------------
PIXABAY_API_KEY: str | None = os.getenv("PIXABAY_API_KEY")  # Pixabay free video API
STOCK_FOOTAGE_SOURCES: list = ["pexels", "pixabay"]  # ordered priority list

# Video settings
VIDEO_WIDTH: int = 1080
VIDEO_HEIGHT: int = 1920
VIDEO_FPS: int = 30
VIDEO_DURATION_TARGET: int = 45  # seconds target
FONT_SIZE: int = 60
FONT_COLOR: str = "white"
BG_MUSIC_VOLUME: float = 0.08
BG_MUSIC_PATH: str = "assets/bg_music.mp3"  # Relative path to background music file (leave empty to disable)

# ---------------------------------------------------------------------------
# Subtitle / caption styling — modern TikTok-style animated word bursts
# ---------------------------------------------------------------------------
SUBTITLE_FONT_SIZE: int = 88           # base font size; adaptive scaling applies per-chunk
SUBTITLE_FONT: str = "Liberation-Sans-Bold"  # fallback fonts tried in order by MoviePy
SUBTITLE_FONT_FALLBACKS: list = [      # tried in order if primary font is unavailable
    "Arial-Bold", "DejaVu-Sans-Bold", "FreeSans-Bold", "Liberation-Sans-Bold",
]
SUBTITLE_STROKE_WIDTH: int = 6         # thicker stroke = sharper legibility on any bg
SUBTITLE_BG_OPACITY: float = 0.82     # slightly more opaque pill for better contrast
SUBTITLE_HIGHLIGHT_COLOR: str = "#FFEE00"   # bold yellow — primary highlight word
SUBTITLE_SECONDARY_COLOR: str = "#00FFC8"   # neon mint — alternating accent
SUBTITLE_ACCENT_COLOR: str = "#FF4081"      # hot pink — third accent
SUBTITLE_POSITION: float = 0.72        # vertical position (0 = top, 1 = bottom of frame)
SUBTITLE_MAX_WORDS: int = 4            # max words per caption burst
SUBTITLE_BG_CORNER_RADIUS: int = 28   # rounder pill for modern look
SUBTITLE_SHADOW_OFFSET: int = 3       # drop shadow offset in px
SUBTITLE_GLOW: bool = True             # neon glow behind pill background
SUBTITLE_GLOW_COLOR: str = "#00FFC8"  # glow colour (matches secondary accent)
SUBTITLE_GLOW_RADIUS: int = 18        # glow blur radius in px
SUBTITLE_WORD_TIMING: bool = True      # scale each caption's duration by word count
SUBTITLE_ADAPTIVE_FONT: bool = True    # bigger font for short (1-2 word) power bursts
SUBTITLE_POP_SCALE: float = 1.12      # scale factor for 1-word pop-in animation
SUBTITLE_ALL_CAPS: bool = True         # render captions in uppercase for impact

# ---------------------------------------------------------------------------
# Video encoding quality — high-bitrate for crisp 1080 × 1920 Shorts
# ---------------------------------------------------------------------------
VIDEO_PRESET: str = "slow"
VIDEO_BITRATE: str = "16000k"          # raised from 12000k for sharper quality
AUDIO_BITRATE: str = "320k"            # raised from 256k for cleaner audio
VIDEO_TRANSITION_DURATION: float = 0.35
VIDEO_VIGNETTE: bool = True            # cinematic dark-edge vignette overlay
VIDEO_COLOR_GRADE: bool = True         # subtle cinematic colour grade (contrast + warmth)
VIDEO_CLIP_RANDOM_START: bool = True   # random clip start for visual variety per run

# ---------------------------------------------------------------------------
# TTS settings — rotating voice pool, one new voice character per run
# ---------------------------------------------------------------------------
TTS_VOICE: str = "en-US-JennyNeural"  # fallback voice if rotation is disabled
TTS_VOICE_ROTATE: bool = True          # True = pick a different voice each run
TTS_RATE: str = "+0%"                  # natural pace
TTS_VOLUME_NORMALIZE: bool = True      # normalize loudness with pydub

# Pexels fetch settings
PEXELS_PER_PAGE: int = 10  # more results = better footage variety (was 8)

# Upload settings
YOUTUBE_CATEGORY_ID: str = "22"  # People & Blogs
PRIVACY_STATUS: str = "public"

# Scheduling
MAX_VIDEOS_PER_RUN: int = 1

# ---------------------------------------------------------------------------
# Viral Optimization Engine settings
# ---------------------------------------------------------------------------
VIRAL_OPTIMIZATION_ENABLED: bool = True   # Enable viral scoring and optimization
VIRAL_MIN_SCORE: float = 0.6              # Minimum virality score to accept a topic (0–1)
VIRAL_ENGAGEMENT_HOOKS: bool = True       # Insert engagement hooks at strategic points
VIRAL_AB_TESTING: bool = True             # Generate A/B title variants

# ---------------------------------------------------------------------------
# Background music — free royalty-free sources
# ---------------------------------------------------------------------------
BG_MUSIC_ENABLED: bool = True             # Auto-fetch background music when no local file
BG_MUSIC_SOURCES: list = [               # ordered fallback list for free music
    "freemusicarchive",
    "incompetech",
]
