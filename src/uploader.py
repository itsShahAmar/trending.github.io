"""
uploader.py — Upload videos to YouTube via the Data API v3.

Credentials are loaded from environment variables (JSON strings) so that
no OAuth2 files need to exist on disk in CI.
"""

import json
import logging
import time
from pathlib import Path

import config

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB resumable upload chunks


def _build_credentials() -> "google.oauth2.credentials.Credentials":  # type: ignore[name-defined]
    """Build OAuth2 credentials from the environment variable JSON strings.

    Raises:
        RuntimeError: If the required environment variables are missing or
            contain invalid JSON.
    """
    try:
        from google.oauth2.credentials import Credentials  # type: ignore[import]
        from google.auth.transport.requests import Request  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("google-auth package is not installed") from exc

    client_secret_raw = config.YOUTUBE_CLIENT_SECRET_JSON
    token_raw = config.YOUTUBE_TOKEN_JSON

    if not client_secret_raw:
        raise RuntimeError("YOUTUBE_CLIENT_SECRET environment variable is not set")
    if not token_raw:
        raise RuntimeError("YOUTUBE_TOKEN environment variable is not set")

    try:
        client_info = json.loads(client_secret_raw)
        # Support both "installed" and "web" application types
        app_info = client_info.get("installed") or client_info.get("web") or client_info
        client_id = app_info["client_id"]
        client_secret = app_info["client_secret"]
        token_uri = app_info.get("token_uri", "https://oauth2.googleapis.com/token")
    except (KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid YOUTUBE_CLIENT_SECRET JSON: {exc}") from exc

    try:
        token_info = json.loads(token_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid YOUTUBE_TOKEN JSON: {exc}") from exc

    # NOTE: Do NOT pass ``scopes`` here.  When scopes are provided, the
    # google-auth library includes them in the token-refresh request body.
    # Google's OAuth2 server rejects refresh requests that carry a ``scope``
    # parameter, returning ``invalid_scope: Bad Request``.  Omitting scopes
    # lets the server refresh using the scopes that were originally granted
    # during the authorization flow.
    creds = Credentials(
        token=token_info.get("access_token") or token_info.get("token"),
        refresh_token=token_info.get("refresh_token"),
        client_id=client_id,
        client_secret=client_secret,
        token_uri=token_uri,
    )

    # Always proactively refresh when we have a refresh token.  The
    # ``creds.expired`` flag is unreliable here because the Credentials
    # object is constructed from stored JSON that typically lacks an
    # ``expiry`` field — so ``expired`` is always ``False`` even if the
    # access token has long since expired.  A forced refresh guarantees we
    # start the upload with a valid access token and avoids relying on
    # google-auth-httplib2's automatic 401-retry (which would also trigger
    # the scope issue described above if scopes were present).
    if creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("OAuth2 token refreshed successfully")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Token refresh failed (will attempt upload with existing "
                "access token): %s", exc,
            )

    return creds


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = config.YOUTUBE_CATEGORY_ID,
    privacy_status: str = config.PRIVACY_STATUS,
    thumbnail_path: Path | None = None,
) -> tuple[str, str]:
    """Upload a video to YouTube and optionally set its thumbnail.

    Args:
        video_path: Path to the MP4 video file.
        title: Video title (max 100 characters).
        description: Video description.
        tags: List of tag strings.
        category_id: YouTube category ID string (default: ``"22"`` = People & Blogs).
        privacy_status: ``"public"``, ``"unlisted"``, or ``"private"``.
        thumbnail_path: Optional path to a JPEG thumbnail file.

    Returns:
        A tuple of ``(video_id, video_url)``.

    Raises:
        RuntimeError: If the upload fails after all retries.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore[import]
        from googleapiclient.http import MediaFileUpload  # type: ignore[import]
        from googleapiclient.errors import HttpError  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is not installed") from exc

    creds = _build_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=_CHUNK_SIZE)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info("Uploading video (attempt %d/%d): '%s'", attempt, _MAX_RETRIES, title)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.debug("Upload progress: %.0f%%", status.progress() * 100)

            video_id: str = response["id"]
            video_url = f"https://www.youtube.com/shorts/{video_id}"
            logger.info("Video uploaded successfully: %s", video_url)

            # Set thumbnail if provided
            if thumbnail_path and thumbnail_path.exists():
                _set_thumbnail(youtube, video_id, thumbnail_path)

            return video_id, video_url

        except Exception as exc:  # noqa: BLE001
            logger.warning("Upload attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                time.sleep(2**attempt)

    raise RuntimeError(f"Video upload failed after {_MAX_RETRIES} attempts: '{title}'")


def _set_thumbnail(youtube: object, video_id: str, thumbnail_path: Path) -> None:
    """Attach *thumbnail_path* to the already-uploaded *video_id*.

    Retries up to 3 times with increasing delays because YouTube may still
    be processing the video immediately after upload.
    """
    try:
        from googleapiclient.http import MediaFileUpload  # type: ignore[import]
        from googleapiclient.errors import HttpError  # type: ignore[import]
    except ImportError:
        logger.warning("google-api-python-client not available; skipping thumbnail")
        return

    _THUMBNAIL_RETRY_DELAYS = [5, 10, 15]  # seconds to wait before each attempt

    for attempt, delay in enumerate(_THUMBNAIL_RETRY_DELAYS, start=1):
        try:
            # Wait before setting thumbnail — the video may still be processing
            logger.info("Waiting %d s before setting thumbnail (attempt %d/%d)…",
                        delay, attempt, len(_THUMBNAIL_RETRY_DELAYS))
            time.sleep(delay)

            fresh_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            youtube.thumbnails().set(  # type: ignore[union-attr]
                videoId=video_id, media_body=fresh_media
            ).execute()
            logger.info("Thumbnail set for video %s", video_id)
            return
        except HttpError as exc:
            status = exc.resp.status if hasattr(exc, "resp") else "unknown"
            logger.warning(
                "Thumbnail attempt %d/%d failed (HTTP %s): %s. "
                "If 403, ensure the channel has custom thumbnails enabled "
                "(requires phone verification) and the OAuth token includes "
                "the youtube.force-ssl scope.",
                attempt, len(_THUMBNAIL_RETRY_DELAYS), status, exc,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Thumbnail attempt %d/%d failed: %s",
                           attempt, len(_THUMBNAIL_RETRY_DELAYS), exc)

    logger.warning(
        "Failed to set thumbnail for video %s after %d attempts. "
        "The video was uploaded successfully — thumbnail can be set manually.",
        video_id, len(_THUMBNAIL_RETRY_DELAYS),
    )
