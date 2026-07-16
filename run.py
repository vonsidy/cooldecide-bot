"""Daily entry point: pick today's item, build the Short, (optionally) upload.

    python run.py                      # build only -> output/short.mp4
    python run.py --format wyr         # force a format
    python run.py --upload             # build AND post to YouTube + track it
    python run.py --date 2026-07-20
"""
from __future__ import annotations
import argparse
import datetime
import os
import sys

import assemble
import card
import config
import content

# Titles contain emoji; the Windows console defaults to cp1252 and would crash
# on print(). Force UTF-8 so local --upload runs don't blow up before uploading.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 - non-reconfigurable streams are fine
    pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", default="wyr", help="wyr | this_or_that | trivia | higher_lower | rank")
    ap.add_argument("--rounds", type=int, default=3, help="questions per video")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output", "short.mp4"))
    ap.add_argument("--upload", action="store_true", help="post the video to YouTube")
    ap.add_argument("--manual", action="store_true", help="mark as a test post (doesn't count toward the daily quota)")
    ap.add_argument("--palette", default=None, help="force a colour scheme (sky|sunset|mint|candy|ocean|sunny|grape)")
    ap.add_argument("--topic", default=None, help="force a topic (food|powers|animals|gaming|magic|space|money|school)")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()

    # A different colour scheme per video, so two Shorts in a row don't look like
    # the same one twice. Seeded by date+format: stable for a given video (a
    # re-render looks identical) but different from the next one.
    palette = card.set_palette(args.palette or card.palette_for(date, args.format))

    # One topic per video — all food, or all superpowers — so it has an identity
    # instead of being three unrelated questions.
    topic = args.topic or content.topic_for(date, args.format)
    items = content.several(args.format, date, args.rounds, topic=topic)

    # Only badge the video if every round really is on-topic. The fallback pool
    # can't always fill a theme, and "FOOD EDITION" over a mixed bag is worse than
    # no label.
    themed = content.is_themed(items, topic)
    card.set_topic_label(content.topic_label(topic) if themed else "")
    print(f"  palette: {palette} | topic: {topic}{'' if themed else ' (mixed — no badge)'}")
    for i, it in enumerate(items, 1):
        print(f"  round {i} [{it.fmt}] {it.a} ({it.a_pct}%) vs {it.b} ({it.b_pct}%)")
    assemble.build(items, args.out)
    print(f"built {args.out} ({os.path.getsize(args.out)//1024} KB) — {len(items)} rounds")

    if not (args.upload or config.UPLOAD):
        return

    # --- Post to YouTube + record it for the dashboard -----------------------
    import dashboard
    import meta
    import youtube_upload

    # Honor a dashboard "Pause 1 day" click (auto-scheduled runs only; an explicit
    # --manual test still posts so you can verify things work while paused).
    if dashboard.paused() and not args.manual:
        print("paused via dashboard — skipping today's post (auto-resumes later)")
        return

    info = meta.build(items)
    print(f"uploading: {info['title']!r} (privacy={config.YT_PRIVACY})")
    vid = youtube_upload.upload(args.out, info["title"], info["description"], info["tags"])
    url = f"https://youtube.com/shorts/{vid}"
    print(f"posted -> {url}")

    youtube_upload.post_comment(vid, info["comment"])
    dashboard.record(vid, info["title"], args.format, len(items), manual=args.manual)
    dashboard.refresh_stats()
    print("recorded to dashboard/kids.json")


if __name__ == "__main__":
    main()
