# 🎬 YouTube Shorts Automation

A fully automated, end-to-end YouTube Shorts creation and upload system that
runs 24/7 via **GitHub Actions** — no server required.

---

## What it Does

Every 6 hours the pipeline:

1. 🔍 **Finds trending topics** from Google Trends and Reddit
2. ✍️ **Writes a professional script** using OpenAI GPT (gpt-4o-mini)
3. 🎙️ **Converts the script to speech** using OpenAI TTS (tts-1-hd)
4. 🎬 **Creates a vertical 1080 × 1920 video** with Pexels stock footage and animated captions
5. 🖼️ **Generates an eye-catching thumbnail** with Pillow
6. 🚀 **Uploads to YouTube** with optimised title, tags, description, and thumbnail

---

## Architecture

```
GitHub Actions (cron: every 6 h)
        │
        ▼
src/pipeline.py  ──────────────────────────────────────────────┐
        │                                                       │
        ├─► src/trending.py      (Google Trends + Reddit)      │
        │         │ trending topic                              │
        ├─► src/scriptwriter.py  (OpenAI GPT-4o-mini)          │
        │         │ title, script, scenes, tags, description    │
        ├─► src/tts.py           (OpenAI TTS tts-1-hd)         │
        │         │ audio MP3 + duration                        │
        ├─► src/video_creator.py (Pexels API + MoviePy)        │
        │         │ 1080×1920 MP4                               │
        ├─► src/thumbnail.py     (Pillow)                       │
        │         │ 1280×720 JPEG                               │
        └─► src/uploader.py      (YouTube Data API v3)          │
                  │ video ID + URL                              │
                  └───────────────────────────────────────────►─┘
```

---

## Setup

### 1. Fork this Repository

Click **Fork** at the top right of this page.

### 2. Set Up YouTube OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project and enable the **YouTube Data API v3**
3. Create **OAuth 2.0 Client ID** credentials (Desktop app)
4. Download the client secret JSON
5. Run the one-time OAuth flow locally to generate a token JSON:

```bash
pip install google-auth-oauthlib
python - <<'EOF'
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json",
    scopes=["https://www.googleapis.com/auth/youtube.upload"]
)
creds = flow.run_local_server(port=0)
import json
print(json.dumps({
    "access_token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
}))
EOF
```

### 3. Get an OpenAI API Key

Visit [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

### 4. Get a Pexels API Key

Sign up at [pexels.com/api](https://www.pexels.com/api/) (free tier available).

### 5. Add Secrets to GitHub

In your forked repository go to **Settings → Secrets and variables → Actions**
and add the following secrets:

| Secret name              | Value                                          |
|--------------------------|------------------------------------------------|
| `OPENAI_API_KEY`         | Your OpenAI API key                            |
| `YOUTUBE_CLIENT_SECRET`  | Full JSON string of the OAuth2 client secret   |
| `YOUTUBE_TOKEN`          | JSON string with `access_token`, `refresh_token`|
| `PEXELS_API_KEY`         | Your Pexels API key                            |

### 6. Enable GitHub Actions

Go to the **Actions** tab in your repository and click **"I understand my
workflows, go ahead and enable them"** if prompted.

The workflow will run automatically every 6 hours, or you can trigger it
manually via **Actions → YouTube Shorts Automation → Run workflow**.

---

## How it Works — Step by Step

| Step | Module | Description |
|------|--------|-------------|
| 1 | `src/trending.py` | Fetches daily trending searches from Google Trends (US) and top posts from Reddit r/popular. Scores topics by cross-source appearance. |
| 2 | `src/scriptwriter.py` | Sends the topic to GPT-4o-mini with a detailed prompt. Returns title, narration, scene descriptions, tags, and YouTube description. |
| 3 | `src/tts.py` | Converts the narration to an MP3 file using OpenAI `tts-1-hd` and measures audio duration. |
| 4 | `src/video_creator.py` | Queries Pexels for portrait video clips per scene, assembles them with MoviePy, adds captions, overlays audio, and exports to MP4. |
| 5 | `src/thumbnail.py` | Creates a gradient 1280 × 720 JPEG thumbnail with the video title and a topic emoji using Pillow. |
| 6 | `src/uploader.py` | Uploads the video via the YouTube Data API v3 resumable upload endpoint, then attaches the thumbnail. |

---

## Customisation

Edit `config.py` to change:

| Setting | Default | Description |
|---------|---------|-------------|
| `VIDEO_FPS` | `30` | Output frame rate |
| `FONT_SIZE` | `60` | Caption font size (px) |
| `TTS_VOICE` | `"alloy"` | OpenAI TTS voice (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) |
| `YOUTUBE_CATEGORY_ID` | `"22"` | YouTube category (22 = People & Blogs) |
| `PRIVACY_STATUS` | `"public"` | Upload privacy (`public`, `unlisted`, `private`) |
| `MAX_VIDEOS_PER_RUN` | `1` | Videos per pipeline run |

---

## Cost Estimates (per video)

| Service | Usage | Approx. cost |
|---------|-------|--------------|
| OpenAI GPT-4o-mini | ~800 tokens | ~$0.001 |
| OpenAI TTS tts-1-hd | ~300 characters | ~$0.015 |
| Pexels API | Free tier | $0.00 |
| GitHub Actions | ~10 min / run | Free (2,000 min/month included) |
| **Total** | | **~$0.02 / video** |

---

## Disclaimer

This tool is intended for educational and creative purposes. Ensure your use
of the YouTube API complies with [YouTube's Terms of Service](https://www.youtube.com/t/terms)
and the [YouTube API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service).
You are solely responsible for the content uploaded by this automation.
Always review the content before publishing publicly if possible.

---

## License

This project is licensed under the **MIT License**.
See [LICENSE](LICENSE) for details.
