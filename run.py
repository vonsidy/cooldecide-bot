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
    ap.add_argument("--format", default=None, help="wyr | this_or_that | trivia | higher_lower | rank")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today, US/Eastern)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output", "short.mp4"))
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    item = content.daily_item(args.format, date)
    print(f"[{item.fmt}] {item.prompt}: {item.a} ({item.a_pct}%) vs {item.b} ({item.b_pct}%)")
    assemble.build(item, args.out)
    print(f"built {args.out} ({os.path.getsize(args.out)//1024} KB)")
    # Upload: reuse the Nyxtold youtube_upload flow against a NEW channel's token.
    # Left as a manual step until the channel + OAuth exist.


if __name__ == "__main__":
    main()
