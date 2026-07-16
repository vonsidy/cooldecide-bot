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
CONTROLS_FILE = os.path.join(_HERE, "dashboard", "controls.json")
BOT_ID = "kids"
ET = datetime.timezone(datetime.timedelta(hours=-4))  # US/Eastern (DST); display only


def paused() -> bool:
    """True if this bot is manually paused via the dashboard 'Pause 1 day' button.

    Reads dashboard/controls.json (shared with the story bots' hub). The pause
    auto-expires once `paused_until` passes. Missing file/field = not paused.
    """
    try:
        with open(CONTROLS_FILE, encoding="utf-8") as f:
            ctl = json.load(f)
    except (OSError, ValueError):
        return False
    until = (ctl.get(BOT_ID) or {}).get("paused_until")
    if not until:
        return False
    try:
        t = datetime.datetime.fromisoformat(str(until).replace("Z", "+00:00"))
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return _now() < t


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


def queue_comment(video_id: str, text: str) -> str:
    """Hold the channel's engagement question for 10-30 minutes after posting.

    A comment from the channel seconds after its own upload is a bot tell — a real
    person hasn't even watched it back yet. The story bots already delay theirs;
    this is the same idea. Returns the ISO time it becomes due.
    """
    import random
    data = _load()
    due = _now() + datetime.timedelta(minutes=random.randint(10, 30))
    data.setdefault("pending_comments", []).append({
        "video_id": video_id, "text": text, "due": _iso(due),
    })
    _save(data)
    return _iso(due)


def post_due_comments() -> int:
    """Post any queued comments that are now due. Returns how many went out.

    Only posts once the video is actually PUBLIC (an unlisted test shouldn't get a
    comment), drops the entry if the video has been deleted, and leaves it queued
    on a transient failure so the next run retries.
    """
    import youtube_upload

    data = _load()
    queue = data.get("pending_comments") or []
    if not queue:
        return 0

    now, keep, sent = _now(), [], 0
    live = youtube_upload.video_privacy([q["video_id"] for q in queue])
    for q in queue:
        try:
            due = datetime.datetime.fromisoformat(str(q["due"]).replace("Z", "+00:00"))
        except ValueError:
            continue                      # unparseable: drop it rather than loop forever
        status = live.get(q["video_id"])
        if status is None:                # video is gone — nothing to comment on
            continue
        if now < due or status != "public":
            keep.append(q)
            continue
        if youtube_upload.post_comment(q["video_id"], q["text"]):
            sent += 1
        else:
            keep.append(q)                # transient failure: try again next run
    data["pending_comments"] = keep
    _save(data)
    return sent


def record(video_id: str, title: str, fmt: str, rounds: int,
           manual: bool = False, privacy: str = "") -> None:
    """Add a freshly-posted video to the board (hub schema).

    `privacy` must be the value the video was ACTUALLY uploaded with. It used to be
    guessed from `manual` ("unlisted if manual else public"), which labelled a
    genuinely unlisted cloud post as public on the dashboard — the one place you'd
    look to check.
    """
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
        "privacy": privacy or "unknown",
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
    # Re-read privacy from YouTube rather than trusting what we wrote at upload
    # time: you may have flipped a video public by hand, and a stale label on the
    # dashboard is worse than none.
    live = youtube_upload.video_privacy(ids)
    for v in data["videos"]:
        s = stats.get(v.get("id"))
        if s:
            v.update(s)
        if v.get("id") in live:
            v["privacy"] = live[v["id"]]

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
