"""Central configuration for the YouTube Shorts Automation pipeline."""

import os

# API Keys (loaded from GitHub Secrets / environment variables)
# NOTE: No paid API keys required!  Script generation uses free templates
# and TTS uses Google's free gTTS library.
YOUTUBE_CLIENT_SECRET_JSON: str | None = os.getenv("YOUTUBE_CLIENT_SECRET")  # JSON string of OAuth2 client secret
YOUTUBE_TOKEN_JSON: str | None = os.getenv("YOUTUBE_TOKEN")  # JSON string of OAuth2 token
PEXELS_API_KEY: str | None = os.getenv("PEXELS_API_KEY")  # For stock footage (free tier)
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

# Subtitle / caption styling
SUBTITLE_FONT_SIZE: int = 80
SUBTITLE_FONT: str = "Liberation-Sans-Bold"
SUBTITLE_STROKE_WIDTH: int = 5
SUBTITLE_BG_OPACITY: float = 0.75
SUBTITLE_HIGHLIGHT_COLOR: str = "#00E5FF"
SUBTITLE_SECONDARY_COLOR: str = "#FFD700"
SUBTITLE_POSITION: float = 0.70
SUBTITLE_MAX_WORDS: int = 4
SUBTITLE_BG_CORNER_RADIUS: int = 20
SUBTITLE_SHADOW_OFFSET: int = 4

# Video encoding quality
VIDEO_PRESET: str = "slow"
VIDEO_BITRATE: str = "12000k"
AUDIO_BITRATE: str = "256k"
VIDEO_TRANSITION_DURATION: float = 0.4

# TTS settings (edge-tts — free neural voice, no API key needed)
# AndrewNeural is a clear, natural male voice well-suited for narration.
# Browse available voices: https://speech.microsoft.com/portal/voicegallery
TTS_VOICE: str = "en-US-AndrewNeural"
TTS_RATE: str = "+5%"
TTS_LANGUAGE: str = "en"  # Fallback for gTTS

# Upload settings
YOUTUBE_CATEGORY_ID: str = "22"  # People & Blogs
PRIVACY_STATUS: str = "public"

# Scheduling
MAX_VIDEOS_PER_RUN: int = 1
