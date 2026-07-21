"""Build a day's videos WITHOUT posting them — the "hand it to me" factory.

The auto-poster (run.py --upload) builds a Short and uploads it straight to
YouTube. This does the same building work but STOPS before uploading: it renders
the finished .mp4s and writes each one's ready-to-paste title / description / tags /
pinned-comment, so you can download them and upload them YOURSELF (through the
YouTube app, with a trending sound — the organic signal the API can't fake).

    python factory.py                 # build today's 2 videos into output/factory/
    python factory.py --count 3       # build 3
    python factory.py --date 2026-07-21

It never touches YouTube, never needs YouTube credentials, and never writes to the
live channel's dashboard or daily quota — so it can run alongside the auto-poster
without interfering with it. Output goes to output/factory/:
    video_1.mp4, video_1.txt   (human-readable: title, description, tags, comment)
    video_2.mp4, video_2.txt
    manifest.json              (the same data as JSON, for the dashboard)
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import sys

import assemble
import card
import config
import content
import meta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

OUT_DIR = os.path.join(os.path.dirname(__file__), "output", "factory")


def _build_one(date: str, slot: int, rounds: int) -> dict:
    """Build the slot-th video of the day and return its metadata + file path.

    Mirrors run.py's build path (same format/palette/background/topic rotation, all
    slot-aware so the day's videos differ), then stops instead of uploading.
    """
    fmt = content.format_for(date, slot)
    palette = card.set_palette(card.palette_for(date, fmt, slot))
    bg = card.set_bg_style(card.background_for(date, fmt, slot))
    topic = content.topic_for(date, fmt, slot)
    items = content.several(fmt, date, rounds, topic=topic)
    if config.ART_REQUIRED:
        items = content.ensure_art(items, fmt)

    themed = content.is_themed(items, topic)
    card.set_topic_label(content.topic_label(topic) if themed else "")

    out_mp4 = os.path.join(OUT_DIR, f"video_{slot + 1}.mp4")
    assemble.build(items, out_mp4)

    info = meta.build(items)
    print(f"  video {slot + 1}: {fmt} | {palette} | {bg} | "
          f"{topic or 'no theme'} -> {info['title']!r}")
    return {
        "file": os.path.basename(out_mp4),
        "format": fmt,
        "title": info["title"],
        "description": info["description"],
        "tags": info["tags"],
        "comment": info["comment"],
    }


def _write_readme(path: str, n: int, v: dict) -> None:
    """A copy-paste sheet for uploading this one by hand."""
    lines = [
        f"VIDEO {n}  ({v['format']})",
        "=" * 48, "",
        "TITLE (copy this):", v["title"], "",
        "DESCRIPTION (copy this):", v["description"], "",
        "TAGS:", ", ".join(v["tags"]), "",
        "PIN THIS COMMENT after you post (10-30 min later):", v["comment"], "",
        "REMINDER: upload in the YouTube app and add a TRENDING sound at low",
        "volume so it doesn't cover the countdown voice.", "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=int(os.getenv("FACTORY_COUNT", "2")),
                    help="how many videos to build for the day (default 2)")
    ap.add_argument("--rounds", type=int, default=3, help="questions per video")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today)")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"factory: building {args.count} video(s) for {date} -> {OUT_DIR}")

    built = []
    for slot in range(args.count):
        v = _build_one(date, slot, args.rounds)
        _write_readme(os.path.join(OUT_DIR, f"video_{slot + 1}.txt"), slot + 1, v)
        built.append(v)

    manifest = {"date": date, "count": len(built), "videos": built}
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # A markdown sheet for the download page (GitHub Release body / dashboard):
    # everything you need to paste, per video, in one place.
    notes = [f"# CoolDecide videos — {date}", "",
             "Download each `.mp4` below, upload it in the **YouTube app**, and add a "
             "**trending sound** (low volume, so it doesn't cover the countdown).", ""]
    for i, v in enumerate(built, 1):
        notes += [
            f"## Video {i} — `{v['file']}` ({v['format']})", "",
            f"**Title:** {v['title']}", "",
            "**Description:**", "```", v["description"], "```", "",
            f"**Tags:** {', '.join(v['tags'])}", "",
            f"**Pin this comment** (10–30 min after posting): {v['comment']}", "",
            "---", "",
        ]
    with open(os.path.join(OUT_DIR, "release_notes.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(notes))
    print(f"done: {len(built)} video(s) + metadata in {OUT_DIR}")


if __name__ == "__main__":
    main()
