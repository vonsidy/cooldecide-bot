"""Tracks the kids bot's posts + channel stats into dashboard/kids.json.

The Nyxtold dashboard is a MULTI-BOT HUB: it lists bots from bots.json and
renders each one from its own data file with a shared renderer. So this file
must match that renderer's schema (same shape as hushed.json / dashboard.json).

The kids bot has no story "themes/narrators/retention", so we map its `format`
(would-you-rather, trivia, …) onto the renderer's `theme` field — that's what
its "best styles" panel groups on — and leave the learning/schedule blocks as
honest empty stubs.
"""
from __future__ import annotations
import datetime
import json
import os

import content

_HERE = os.path.dirname(__file__)
DATA_FILE = os.path.join(_HERE, "dashboard", "kids.json")
ET = datetime.timezone(datetime.timedelta(hours=-4))  # US/Eastern (DST); display only


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


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def record(video_id: str, title: str, fmt: str, rounds: int,
           manual: bool = False) -> None:
    """Add a freshly-posted video to the board (hub schema)."""
    data = _load()
    now = _now()
    data.setdefault("videos", []).insert(0, {
        "date": _iso(now),
        "id": video_id,
        "url": f"https://youtube.com/shorts/{video_id}",
        "title": title,
        "format": fmt,
        "theme": content.format_label(fmt).title(),  # renderer groups on `theme`
        "rounds": rounds,
        "privacy": "unlisted" if manual else "public",
        "local_time": now.astimezone(ET).strftime("%I:%M %p"),
        "manual": manual,
        "views": 0,
        "likes": 0,
        "comments": 0,
    })
    data.setdefault("runs", []).insert(0, {
        "status": "posted", "title": title, "manual": manual, "time": _iso(now),
    })
    data["updated"] = _iso(now)
    data.setdefault("started", now.date().isoformat())
    _save(data)


def _empty_learning() -> dict:
    return {"ready": False, "trained_on": 0, "needs": 4, "min_age_days": 3.0,
            "min_per_option": 2, "themes": {}, "counts": {"theme": {}}}


def refresh_stats() -> dict:
    """Pull live channel + per-video numbers from YouTube. Safe if offline."""
    import youtube_upload

    data = _load()
    data.setdefault("videos", [])
    data.setdefault("runs", [])
    data.setdefault("learning", _empty_learning())
    data.setdefault("schedule", {"upcoming": [], "max_per_day": 2})
    data.setdefault("pending_comments", [])

    ch = youtube_upload.channel_stats()
    if ch:
        data["channel"] = ch

    ids = [v["id"] for v in data["videos"] if v.get("id")]
    stats = youtube_upload.video_stats(ids)
    for v in data["videos"]:
        s = stats.get(v.get("id"))
        if s:
            v.update(s)

    # daily snapshot so the dashboard can graph growth
    if ch:
        today = _now().date().isoformat()
        hist = data.setdefault("history", [])
        snap = {"d": today, "subs": ch["subscribers"], "views": ch["views"],
                "likes": sum(v.get("likes", 0) for v in data["videos"])}
        if hist and hist[-1]["d"] == today:
            hist[-1] = snap
        else:
            hist.append(snap)

    data["updated"] = _iso()
    data.setdefault("started", _now().date().isoformat())
    _save(data)
    return data


def posts_today(date: str | None = None) -> int:
    """How many NON-manual videos were posted on `date` (default: today UTC)."""
    date = date or _now().date().isoformat()
    data = _load()
    return sum(
        1 for v in data.get("videos", [])
        if not v.get("manual") and str(v.get("date", "")).startswith(date)
    )


if __name__ == "__main__":
    d = refresh_stats()
    print("channel:", d.get("channel"))
    print("videos tracked:", len(d.get("videos", [])))
