"""Daily entry point: pick today's item, build the Short, (optionally) upload.

    python run.py                 # build today's video into output/short.mp4
    python run.py --format wyr    # force a format
    python run.py --date 2026-07-20
"""
from __future__ import annotations
import argparse
import datetime
import os

import assemble
import content


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", default="wyr", help="wyr | this_or_that | trivia | higher_lower | rank")
    ap.add_argument("--rounds", type=int, default=3, help="questions per video")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today, US/Eastern)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output", "short.mp4"))
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    items = content.several(args.format, date, args.rounds)
    for i, it in enumerate(items, 1):
        print(f"  round {i} [{it.fmt}] {it.a} ({it.a_pct}%) vs {it.b} ({it.b_pct}%)")
    assemble.build(items, args.out)
    print(f"built {args.out} ({os.path.getsize(args.out)//1024} KB) — {len(items)} rounds")
    # Upload: reuse the Nyxtold youtube_upload flow against a NEW channel's token.
    # Left as a manual step until the channel + OAuth exist.


if __name__ == "__main__":
    main()
