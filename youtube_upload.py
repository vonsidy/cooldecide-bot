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
    """Upload the video and return its id.

    Always uploads at the configured privacy DIRECTLY — no publishAt scheduling.
    The owner wants each video born public at its moment, never sitting on the
    channel as a private/scheduled upload; the random go-live minute is achieved
    by run.py HOLDING the finished video until the slot, then uploading.
    """
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
    """Seed engagement with a channel comment. Never fails the upload.

    Returns the comment id on success, None on failure — callers retry on None,
    so this must not return None after actually posting.
    """
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
    """Channel totals for the dashboard, in the hub's schema. None on failure."""
    try:
        resp = _service().channels().list(part="statistics,snippet", mine=True).execute()
        it = resp["items"][0]
        s = it["statistics"]
        thumbs = it["snippet"].get("thumbnails", {})
        thumb = (thumbs.get("default") or thumbs.get("medium") or {}).get("url", "")
        return {
            "title": it["snippet"]["title"],
            "subscribers": int(s.get("subscriberCount", 0)),
            "views": int(s.get("viewCount", 0)),
            "videoCount": int(s.get("videoCount", 0)),
            "thumbnail": thumb,
        }
    except Exception as e:  # noqa: BLE001
        print("  (channel stats skipped:", e, ")")
        return None


def video_privacy(video_ids: list[str]) -> dict:
    """{video_id: 'public'|'unlisted'|'private'} for ids that still exist.

    A missing id means the video was deleted — the caller uses that to drop a
    queued comment rather than retry forever.
    """
    out: dict[str, str] = {}
    if not video_ids:
        return out
    try:
        for i in range(0, len(video_ids), 50):
            resp = _service().videos().list(
                part="status", id=",".join(video_ids[i:i + 50])
            ).execute()
            for it in resp.get("items", []):
                out[it["id"]] = it["status"]["privacyStatus"]
    except Exception as e:  # noqa: BLE001
        print("  (privacy check skipped:", e, ")")
    return out


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


def already_commented(video_id: str) -> bool:
    """True if THIS channel already has a top-level comment on this video.

    The engagement-comment queue lives in the dashboard file, so if a run posts the
    comment but then fails to persist the queue removal (a concurrent run, a rejected
    dashboard push), the next check-in sees it still queued and comments a SECOND
    time — the duplicate "Which one did you pick?" we saw. YouTube knows whether we
    already commented; checking it here makes the queue removal's persistence
    irrelevant.

    False on any API failure (fail-open: a transient error must never suppress a
    video's first comment).
    """
    try:
        svc = _service()
        me = svc.channels().list(part="id", mine=True).execute()
        my_id = me["items"][0]["id"]
        resp = svc.commentThreads().list(
            part="snippet", videoId=video_id, maxResults=100, textFormat="plainText",
        ).execute()
        for it in resp.get("items", []):
            top = it["snippet"]["topLevelComment"]["snippet"]
            author = (top.get("authorChannelId") or {}).get("value")
            if author and author == my_id:
                return True
        return False
    except Exception as e:  # noqa: BLE001
        print("  (already-commented check skipped:", e, ")")
        return False


def uploads_today() -> int:
    """How many videos this channel has ACTUALLY published so far today (US/Eastern),
    straight from YouTube. This is the ground truth the daily cap is enforced against.

    The dashboard file the scheduler normally counts can UNDERCOUNT — a run that
    uploaded but then failed to record, commit, or push its dashboard update (a
    concurrent run, a rejected push) leaves the channel with a video the count never
    saw, and the next check-in, seeing "0 posts today", posts a second time. Asking
    YouTube can't undercount that way, so a guard on this value makes double-posting
    impossible regardless of dashboard/push races.

    Returns 0 on any API failure: a transient error must never BLOCK a legitimate
    post, and the dashboard-based check still runs upstream.
    """
    import datetime
    from zoneinfo import ZoneInfo

    try:
        svc = _service()
        ch = svc.channels().list(part="contentDetails", mine=True).execute()
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        resp = svc.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads, maxResults=50,
        ).execute()
        tz = ZoneInfo("America/New_York")
        today = datetime.datetime.now(tz).date()
        n = 0
        for it in resp.get("items", []):
            raw = (it.get("contentDetails", {}).get("videoPublishedAt")
                   or it.get("snippet", {}).get("publishedAt"))
            if not raw:
                continue
            try:
                t = datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if t.astimezone(tz).date() == today:
                n += 1
        return n
    except Exception as e:  # noqa: BLE001
        print("  (uploads_today check skipped:", e, ")")
        return 0


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
