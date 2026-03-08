"""Central configuration for the YouTube Shorts Automation pipeline."""

import os

# API Keys (loaded from GitHub Secrets / environment variables)
# NOTE: No paid API keys required!  Script generation uses free templates
# and TTS uses Google's free gTTS library.
YOUTUBE_CLIENT_SECRET_JSON: str | None = os.getenv("YOUTUBE_CLIENT_SECRET")  # JSON string of OAuth2 client secret
YOUTUBE_TOKEN_JSON: str | None = os.getenv("YOUTUBE_TOKEN")  # JSON string of OAuth2 token
PEXELS_API_KEY: str | None = os.getenv("PEXELS_API_KEY")  # For stock footage (free tier)
REDDIT_CLIENT_ID: str | None = os.getenv("REDDIT_CLIENT_ID")  # Reddit OAuth2 app client ID (optional)
REDDIT_CLIENT_SECRET: str | None = os.getenv("REDDIT_CLIENT_SECRET")  # Reddit OAuth2 app client secret (optional)
NEWSAPI_KEY: str | None = os.getenv("NEWSAPI_KEY")  # NewsAPI.org key for trending headlines (optional)

# Video settings
VIDEO_WIDTH: int = 1080
VIDEO_HEIGHT: int = 1920
VIDEO_FPS: int = 30
VIDEO_DURATION_TARGET: int = 45  # seconds target
FONT_SIZE: int = 60
FONT_COLOR: str = "white"
BG_MUSIC_VOLUME: float = 0.08
BG_MUSIC_PATH: str = "assets/bg_music.mp3"  # Relative path to background music file (leave empty to disable)

# TTS settings (gTTS — free, no API key needed)
TTS_LANGUAGE: str = "en"  # gTTS language code

# Upload settings
YOUTUBE_CATEGORY_ID: str = "22"  # People & Blogs
PRIVACY_STATUS: str = "public"

# Scheduling
MAX_VIDEOS_PER_RUN: int = 1
