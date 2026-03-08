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
SUBTITLE_WORD_TIMING: bool = True    # scale each caption's duration proportionally by its word count
SUBTITLE_ADAPTIVE_FONT: bool = True  # increase font size for short (1-2 word) bursts

# Video encoding quality
VIDEO_PRESET: str = "slow"
VIDEO_BITRATE: str = "12000k"
AUDIO_BITRATE: str = "256k"
VIDEO_TRANSITION_DURATION: float = 0.4
VIDEO_VIGNETTE: bool = True           # apply a cinematic dark-edge vignette overlay
VIDEO_CLIP_RANDOM_START: bool = True  # start stock clips at a random timestamp for visual variety

# TTS settings (edge-tts — free neural voice, no API key needed)
# JennyNeural is a clear, natural female voice well-suited for narration.
# Browse available voices: https://speech.microsoft.com/portal/voicegallery
TTS_VOICE: str = "en-US-JennyNeural"
TTS_RATE: str = "+0%"          # natural pace; was "+5%" — slower reads more clearly
TTS_LANGUAGE: str = "en"       # Fallback for gTTS
TTS_VOLUME_NORMALIZE: bool = True   # normalize TTS audio loudness with pydub after generation
TTS_NATURAL_PAUSES: bool = True     # inject SSML <break> pauses at sentence boundaries

# Pexels fetch settings
PEXELS_PER_PAGE: int = 8  # results per search query — more results = better footage variety

# Upload settings
YOUTUBE_CATEGORY_ID: str = "22"  # People & Blogs
PRIVACY_STATUS: str = "public"

# Scheduling
MAX_VIDEOS_PER_RUN: int = 1
