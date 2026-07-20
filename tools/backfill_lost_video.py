"""One-off repair for the 2026-07-19 state-loss incident. Safe to run twice.

Run 29702757244 uploaded https://youtube.com/shorts/JUFdeYK8DJ4 at 21:21:32 UTC and
then lost its entire state commit: the `git pull --rebase` conflicted, left a
detached HEAD, and the old `|| echo "nothing to push"` fallback exited 0. So the
video is live on the channel while the repo has no record of it anywhere — not in
dashboard/kids.json, not in the no-repeat bank.

Two consequences this fixes:
  * the dashboard shows 6 videos when the channel has 7, and that video's views
    are invisible
  * its three questions were never marked used, so they can be posted a second time

Everything below was recovered from the run log (the only surviving record).
tools/save_state.py is what stops this recurring; this just repairs the damage
already done. Delete this file once it has been run.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIDS = os.path.join(_HERE, "dashboard", "kids.json")
USED_WYR = os.path.join(_HERE, "output", "used_wyr.json")

VIDEO_ID = "JUFdeYK8DJ4"
POSTED_AT = "2026-07-19T21:21:32+00:00"
TITLE = ("Only 1% Pick Right... Pet dragon that breathes rainbow fire or "
         "Pet dinosaur that roars like thunder?")

# content._key() format: "option a|option b", exactly as the bank stores them.
QUESTIONS = [
    "Pet dragon that breathes rainbow fire|Pet dinosaur that roars like thunder",
    "Be a wolf with a full pack family|Be an eagle soaring alone across mountains",
    "Own a talking parrot best friend|Own a talking octopus in your swimming pool",
]


def main() -> int:
    changed = False

    with open(KIDS, encoding="utf-8") as f:
        data = json.load(f)

    videos = data.setdefault("videos", [])
    if any(v.get("id") == VIDEO_ID for v in videos):
        print(f"kids.json: {VIDEO_ID} already present")
    else:
        videos.append({
            "date": POSTED_AT,
            "id": VIDEO_ID,
            "url": f"https://youtube.com/shorts/{VIDEO_ID}",
            "title": TITLE,
            "format": "wyr",
            "theme": "Would You Rather",
            "rounds": 3,
            "privacy": "public",
            "local_time": "05:21 PM",
            "manual": False,
            # Zeroes, not guesses. The next refresh_stats pulls the real numbers
            # from YouTube; inventing them would put fiction on the dashboard.
            "views": 0, "likes": 0, "comments": 0,
        })
        videos.sort(key=lambda v: str(v.get("date") or ""), reverse=True)
        changed = True
        print(f"kids.json: recorded {VIDEO_ID}")

    runs = data.setdefault("runs", [])
    if not any(r.get("time") == POSTED_AT for r in runs):
        runs.append({"status": "posted", "title": TITLE, "manual": False,
                     "time": POSTED_AT})
        runs.sort(key=lambda r: str(r.get("time") or ""), reverse=True)
        changed = True
        print("kids.json: recorded the run")

    if changed:
        with open(KIDS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    with open(USED_WYR, encoding="utf-8") as f:
        used = set(json.load(f))
    missing = [q for q in QUESTIONS if q not in used]
    if missing:
        with open(USED_WYR, "w", encoding="utf-8") as f:
            json.dump(sorted(used | set(QUESTIONS)), f)
        changed = True
        for q in missing:
            print(f"used_wyr.json: marked used — {q}")
    else:
        print("used_wyr.json: all three questions already marked used")

    print("nothing to do" if not changed else "backfill complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
