"""Tracks the kids bot's posts and channel stats into dashboard/kids.json.

This JSON is what the Nyxtold dashboard reads to show a "Kids Channel" section.
Kept deliberately small; no external deps beyond youtube_upload.
"""
from __future__ import annotations
import datetime
import json
import os

_HERE = os.path.dirname(__file__)
DATA_FILE = os.path.join(_HERE, "dashboard", "kids.json")


def _load() -> dict:
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def record(video_id: str, title: str, fmt: str, rounds: int,
           manual: bool = False) -> None:
    """Add a freshly-posted video to the board."""
    data = _load()
    videos = data.setdefault("videos", [])
    videos.insert(0, {
        "id": video_id,
        "url": f"https://youtube.com/shorts/{video_id}",
        "title": title,
        "format": fmt,
        "rounds": rounds,
        "posted": _now_iso(),
        "manual": manual,
        "views": 0,
        "likes": 0,
        "comments": 0,
    })
    data["updated"] = _now_iso()
    data.setdefault("started", _now_iso())
    _save(data)


def refresh_stats() -> dict:
    """Pull live channel + per-video numbers from YouTube. Safe if offline."""
    import youtube_upload

    data = _load()
    ch = youtube_upload.channel_stats()
    if ch:
        data["channel"] = ch

    videos = data.get("videos", [])
    ids = [v["id"] for v in videos if v.get("id")]
    stats = youtube_upload.video_stats(ids)
    for v in videos:
        s = stats.get(v.get("id"))
        if s:
            v.update(s)

    data["updated"] = _now_iso()
    _save(data)
    return data


def posts_today(date: str | None = None) -> int:
    """How many NON-manual videos were posted on `date` (default: today UTC).

    Uses UTC to match the stored `posted` timestamps (and the cloud runner).
    """
    date = date or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    data = _load()
    return sum(
        1 for v in data.get("videos", [])
        if not v.get("manual") and str(v.get("posted", "")).startswith(date)
    )


if __name__ == "__main__":
    d = refresh_stats()
    print("channel:", d.get("channel"))
    print("videos tracked:", len(d.get("videos", [])))
