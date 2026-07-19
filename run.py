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
    ap.add_argument("--format", default=None,
                    help="wyr | this_or_that | trivia | higher_lower | rank "
                         "(default: today's slot in the rotation)")
    ap.add_argument("--slot", type=int, default=0, help="Nth video of the day (shifts the rotation)")
    ap.add_argument("--rounds", type=int, default=3, help="questions per video")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output", "short.mp4"))
    ap.add_argument("--upload", action="store_true", help="post the video to YouTube")
    ap.add_argument("--manual", action="store_true", help="mark as a test post (doesn't count toward the daily quota)")
    ap.add_argument("--palette", default=None, help="force a colour scheme (sky|sunset|mint|candy|ocean|sunny|grape)")
    ap.add_argument("--topic", default=None, help="force a topic (food|powers|animals|gaming|magic|space|money|school)")
    ap.add_argument("--comments-only", action="store_true",
                    help="just post any queued comments that are due, then exit")
    args = ap.parse_args()

    # Drain any comments that came due since the last run, before anything else —
    # a queued comment is useless if nothing ever posts it.
    if args.upload or config.UPLOAD or args.comments_only:
        import dashboard as _dash
        try:
            n = _dash.post_due_comments()
            if n:
                print(f"posted {n} due comment(s)")
        except Exception as e:  # noqa: BLE001 - never block a post over this
            print("  (comment queue skipped:", e, ")")
    if args.comments_only:
        return

    date = args.date or datetime.date.today().isoformat()

    # Rotate the format. Without this the channel is just would-you-rather forever.
    fmt = args.format or content.format_for(date, args.slot)

    # A different colour scheme per video, so two Shorts in a row don't look like
    # the same one twice. Seeded by date+format: stable for a given video (a
    # re-render looks identical) but different from the next one.
    palette = card.set_palette(args.palette or card.palette_for(date, fmt))

    # One topic per video — all food, or all superpowers — so it has an identity
    # instead of being three unrelated questions.
    topic = args.topic or content.topic_for(date, fmt)
    items = content.several(fmt, date, args.rounds, topic=topic)

    # Only badge the video if every round really is on-topic. The fallback pool
    # can't always fill a theme, and "FOOD EDITION" over a mixed bag is worse than
    # no label.
    themed = content.is_themed(items, topic)
    card.set_topic_label(content.topic_label(topic) if themed else "")
    print(f"  format: {fmt} | palette: {palette} | topic: {topic}{'' if themed else ' (mixed — no badge)'}")
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

    # Publish AT the day's random slot, not at upload time. The workflow wakes at a
    # fixed minute each hour, so uploading straight to public stamped every video
    # with the same wake-minute — a clockwork pattern that defeated the scheduler's
    # whole point. Instead the check-in fires up to an hour EARLY (scheduler
    # look-ahead), the upload goes up private, and YouTube itself flips it public at
    # the slot. Manual runs skip this: a human pressing the button means "post now".
    # The 3-minute floor keeps publishAt safely in the future — YouTube rejects
    # scheduling into the past, and the upload itself takes a moment.
    publish_at = None
    if not args.manual:
        import scheduler
        target = scheduler.next_slot()
        if target is not None and (target - scheduler.now_local()).total_seconds() > 180:
            publish_at = target

    info = meta.build(items)
    print(f"uploading: {info['title']!r} (privacy={config.YT_PRIVACY}"
          + (f", goes public {publish_at:%H:%M %Z}" if publish_at else "") + ")")
    vid = youtube_upload.upload(args.out, info["title"], info["description"], info["tags"],
                                publish_at=publish_at)
    url = f"https://youtube.com/shorts/{vid}"
    print(("scheduled -> " if publish_at else "posted -> ") + url)

    # The engagement question is QUEUED, not posted now: a comment from the channel
    # seconds after its own upload is a bot tell. It goes out 10-30 minutes after
    # the video is PUBLIC (see dashboard.post_due_comments) — anchored to the
    # scheduled publish time when there is one.
    due = dashboard.queue_comment(vid, info["comment"], after=publish_at)
    print(f"comment queued for {due} (10-30 min after publish)")

    # `fmt`, not args.format — that's None unless it was forced on the command line,
    # which would log every video's format as null on the dashboard.
    dashboard.record(vid, info["title"], fmt, len(items), manual=args.manual,
                     privacy=config.YT_PRIVACY)
    dashboard.refresh_stats()
    print("recorded to dashboard/kids.json")


if __name__ == "__main__":
    main()
