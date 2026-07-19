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
    ap.add_argument("--palette", default=None, help="force a colour scheme (sunset|candy|grape|ocean|lagoon|meadow|berry|flame|coral)")
    ap.add_argument("--bg", default=None, help="force a background pattern (gradient|radial|dots|stripes|confetti|rays|bokeh|bubbles)")
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

    # WHICH post of the day this is (0 = first, 1 = second). The workflow never
    # passes --slot, so both daily posts used slot 0 — identical format, palette AND
    # background, i.e. two look-alike videos every day (the "same colour/theme"
    # sameness that gets a channel flagged). Derive it from how many already went out
    # today so the second post steps to a different format, which cascades to a
    # different palette and pattern too.
    slot = args.slot
    if not args.slot and not args.format:
        import scheduler
        slot = scheduler.posts_today()

    # Rotate the format. Without this the channel is just would-you-rather forever.
    fmt = args.format or content.format_for(date, slot)

    # A different colour scheme per video, so two Shorts in a row don't look like
    # the same one twice. Seeded by date+format: stable for a given video (a
    # re-render looks identical) but different from the next one.
    palette = card.set_palette(args.palette or card.palette_for(date, fmt, slot))

    # A second axis of variety: the background pattern (plain gradient + 7 subtle
    # shapes) rotates on its own offset, so colour AND backdrop advance
    # independently and consecutive Shorts never share the same look — that
    # sameness is what trips the "repetitive content" signal on a faceless channel.
    bg = card.set_bg_style(args.bg or card.background_for(date, fmt, slot))

    # One topic per video — all food, or all superpowers — so it has an identity
    # instead of being three unrelated questions.
    topic = args.topic or content.topic_for(date, fmt, slot)
    items = content.several(fmt, date, args.rounds, topic=topic)

    # Every option panel must carry REAL art (owner's rule — never an emoji
    # stand-in). This pre-generates each round's art now, and swaps out any round
    # whose art can't be produced for one whose art already exists on disk. Runs
    # BEFORE the theme check below, since a swap can change the video's topic mix.
    if config.ART_REQUIRED:
        items = content.ensure_art(items, fmt)

    # Only badge the video if every round really is on-topic. The fallback pool
    # can't always fill a theme, and "FOOD EDITION" over a mixed bag is worse than
    # no label.
    themed = content.is_themed(items, topic)
    card.set_topic_label(content.topic_label(topic) if themed else "")
    print(f"  format: {fmt} | palette: {palette} | bg: {bg} | topic: {topic}{'' if themed else ' (mixed — no badge)'}")
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

    # HOLD the finished video until the day's slot, then upload — born public at
    # that moment. The check-in fires up to LOOKAHEAD_MIN early (scheduler), so the
    # render is already done by now; sleeping the remainder puts the actual upload
    # at the slot's random minute instead of stamping every post with the cron's
    # wake-minute. Deliberately NOT publishAt scheduling — the owner wants no
    # private/scheduled uploads sitting on the channel, ever. Manual runs skip the
    # hold: a human pressing the button means "post now". Sleep in short chunks so
    # the Actions log shows a heartbeat instead of 40 silent minutes.
    if not args.manual:
        import time as _time

        import scheduler
        target = scheduler.next_slot()
        if target is not None:
            wait = (target - scheduler.now_local()).total_seconds()
            if wait > 0:
                print(f"video ready — holding upload until {target:%H:%M %Z} "
                      f"({wait / 60:.0f} min)")
                while wait > 0:
                    _time.sleep(min(wait, 300))
                    wait = (target - scheduler.now_local()).total_seconds()
                    if wait > 0:
                        print(f"  …{wait / 60:.0f} min to go")

    # Ground-truth quota guard, checked right before uploading (after the hold, so
    # it catches a sibling run that posted while we slept). The dashboard count can
    # undercount if a prior run uploaded but failed to record/push — YouTube itself
    # can't, so this is what actually stops double-posting. Manual runs bypass it:
    # a human pressing the button means "post now" regardless of the cap.
    if not args.manual:
        import scheduler
        already = youtube_upload.uploads_today()
        if already >= scheduler.MAX_PER_DAY:
            print(f"channel already has {already} upload(s) today "
                  f"(cap {scheduler.MAX_PER_DAY}) — skipping to avoid a double post")
            return

    info = meta.build(items)
    print(f"uploading: {info['title']!r} (privacy={config.YT_PRIVACY})")
    vid = youtube_upload.upload(args.out, info["title"], info["description"], info["tags"])
    url = f"https://youtube.com/shorts/{vid}"
    print(f"posted -> {url}")

    # The engagement question is QUEUED, not posted now: a comment from the channel
    # seconds after its own upload is a bot tell. It goes out 10-30 minutes later,
    # once the video is public (see dashboard.post_due_comments).
    due = dashboard.queue_comment(vid, info["comment"])
    print(f"comment queued for {due} (10-30 min)")

    # `fmt`, not args.format — that's None unless it was forced on the command line,
    # which would log every video's format as null on the dashboard.
    dashboard.record(vid, info["title"], fmt, len(items), manual=args.manual,
                     privacy=config.YT_PRIVACY)
    dashboard.refresh_stats()
    print("recorded to dashboard/kids.json")


if __name__ == "__main__":
    main()
