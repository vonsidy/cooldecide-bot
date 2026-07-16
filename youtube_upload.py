"""Upload a finished Short to YouTube via the Data API v3.

Reuses the SAME Google Cloud OAuth client as the Nyxtold bot (copy that repo's
youtube_bot/client_secret.json here), but writes its own token so this bot posts
to its OWN new channel.

One-time setup (done by YOU — needs a Google login):
  1. Create the new YouTube channel you want these videos on.
  2. Put client_secret.json in this folder (copy from the Nyxtold bot).
  3. Run:  python youtube_upload.py --auth
     A browser opens once. When Google asks which channel, PICK THE NEW ONE.
     A token is cached to yt_token.json and refreshes itself after that.
"""
from __future__ import annotations
import argparse

import config

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",   # dashboard stats
    "https://www.googleapis.com/auth/youtube.force-ssl",  # post a comment
]


def _credentials():
    import os
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(config.YT_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.YT_TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YT_CLIENT_SECRETS, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.YT_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def _service():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_credentials())


def upload(video_path: str, title: str, description: str, tags: list[str]) -> str:
    """Upload the video and return its id."""
    from googleapiclient.http import MediaFileUpload

    if "#shorts" not in description.lower():
        description = f"{description}\n\n#shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:15],
            "categoryId": config.YT_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": config.YT_PRIVACY,
            "selfDeclaredMadeForKids": config.MADE_FOR_KIDS,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = _service().videos().insert(
        part="snippet,status", body=body, media_body=media
    )
    response = request.execute()
    return response["id"]


def post_comment(video_id: str, text: str) -> str | None:
    """Seed engagement with a channel comment. Never fails the upload."""
    if config.MADE_FOR_KIDS:
        return None  # comments are disabled on made-for-kids videos
    try:
        resp = _service().commentThreads().insert(
            part="snippet",
            body={"snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text[:9000]}},
            }},
        ).execute()
        return resp["id"]
    except Exception as e:  # noqa: BLE001
        print("  (comment skipped:", e, ")")
        return None


def channel_stats() -> dict | None:
    """Subscriber / view / video totals for the dashboard. None on any failure."""
    try:
        resp = _service().channels().list(part="statistics,snippet", mine=True).execute()
        it = resp["items"][0]
        s = it["statistics"]
        return {
            "title": it["snippet"]["title"],
            "subs": int(s.get("subscriberCount", 0)),
            "views": int(s.get("viewCount", 0)),
            "videos": int(s.get("videoCount", 0)),
        }
    except Exception as e:  # noqa: BLE001
        print("  (channel stats skipped:", e, ")")
        return None


def video_stats(video_ids: list[str]) -> dict:
    """{video_id: {views, likes, comments}} for the given ids."""
    out: dict[str, dict] = {}
    if not video_ids:
        return out
    try:
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i + 50]
            resp = _service().videos().list(
                part="statistics", id=",".join(chunk)
            ).execute()
            for it in resp.get("items", []):
                s = it["statistics"]
                out[it["id"]] = {
                    "views": int(s.get("viewCount", 0)),
                    "likes": int(s.get("likeCount", 0)),
                    "comments": int(s.get("commentCount", 0)),
                }
    except Exception as e:  # noqa: BLE001
        print("  (video stats skipped:", e, ")")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true", help="Run one-time OAuth")
    args = parser.parse_args()
    if args.auth:
        _service()
        print("Authorized. Token cached at", config.YT_TOKEN_FILE)
        stats = channel_stats()
        if stats:
            print(f"Connected channel: {stats['title']} "
                  f"({stats['subs']} subs, {stats['videos']} videos)")
