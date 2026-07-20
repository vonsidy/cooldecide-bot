"""Decides whether to post right now, and at what time of day.

Runs on US/Eastern, not UTC — the audience is US kids, so what matters is "is it
after school where they are", not what time it is in London.

The cloud checks in hourly and asks should_post(). Posting times are picked from
the day's date, so they're stable across the hour's checks but different every day:
a channel that posts at exactly 16:00:00 every single day looks like a machine.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import os
import random
from zoneinfo import ZoneInfo

import dashboard

TZ = ZoneInfo(os.getenv("BOT_TZ", "America/New_York"))
MAX_PER_DAY = int(os.getenv("MAX_UPLOADS_PER_DAY", "2"))

# How far ahead a slot may be for a check-in to act on it. The cloud only wakes
# at fixed cron minutes, so without look-ahead every upload lands at wake-minute +
# build time — the day's carefully random slot minute was thrown away, and all
# posts shared one machine-like timestamp. With look-ahead the bot builds early and
# then HOLDS the finished video until the slot, uploading it born-public at that
# minute (run.py). Deliberately not publishAt scheduling — the owner wants nothing
# sitting on the channel as a scheduled/private upload, ever.
# 30, matched to the workflow's 30-minute wake spacing so EVERY slot is caught by
# the wake before it and uploaded AT its own random minute.
#
# At 15 (sized for the Cloudflare worker's `post-now`, which fires ~7-12 min ahead)
# an unaided wake caught only ~29% of slots; the rest arrived through the
# already-passed fallback, which uploads at wake + build time. That put three posts
# on the channel at exactly :25 — the machine timestamp this whole design exists to
# avoid. Look-ahead >= wake spacing is what makes the random minute real without
# any external trigger.
#
# The cost of look-ahead is held runner minutes (~14 min average), which is exactly
# why the worker was built. This is the version that survives the worker being down.
LOOKAHEAD_MIN = float(os.getenv("PUBLISH_LOOKAHEAD_MIN", "30"))

# Windows worth posting in for a KIDS audience, in local time. Nothing before
# school and nothing near bedtime — a Short posted at 3am gets its one shot at the
# test pool while every viewer is asleep, and never recovers.
#   (label, first hour, last hour) inclusive
BUCKETS = [
    ("afterschool", 15, 18),   # 3pm - 6:59pm
    ("evening", 19, 21),       # 7pm - 9:59pm
    ("morning", 8, 11),        # weekend/holiday mornings
]
MIN_GAP_HOURS = float(os.getenv("MIN_GAP_HOURS", "4"))


def now_local() -> dt.datetime:
    return dt.datetime.now(TZ)


def _seeded(date: dt.date) -> random.Random:
    """Same picks all day, different picks tomorrow — and different per BOT.

    Seeded by the DATE so every hourly check-in agrees on today's times. If this
    were unseeded, each check would roll new times and the bot would post
    repeatedly or never.

    Salted by BOT_ID because sibling bots share this scheduler: seeding on the
    date alone made every channel pick the SAME "random" minutes each day, which
    is a coordinated-network fingerprint — three channels posting in lockstep
    looks far more automated than any one channel's timing ever could.
    (sha1, not hash(): Python randomises hash() per process, which would reroll
    the day's times on every check-in.)
    """
    salt = int(hashlib.sha1(dashboard.BOT_ID.encode()).hexdigest()[:8], 16)
    return random.Random(date.toordinal() * 7919 + salt)


def slots_for_date(d: dt.date, n: int = MAX_PER_DAY) -> list[dt.datetime]:
    """The times to post on this date — random minute, never the same twice."""
    rng = _seeded(d)
    picked = rng.sample(BUCKETS, min(n, len(BUCKETS)))
    out: list[dt.datetime] = []
    for _, lo, hi in picked:
        for _ in range(30):                     # re-roll until it clears the gap
            t = dt.datetime(d.year, d.month, d.day,
                            rng.randint(lo, hi), rng.randint(0, 59), tzinfo=TZ)
            if all(abs((t - o).total_seconds()) >= MIN_GAP_HOURS * 3600 for o in out):
                out.append(t)
                break
    return sorted(out)


def posts_today(now: dt.datetime | None = None) -> int:
    """How many videos exist for TODAY IN EASTERN TIME.

    Must be counted in ET, not UTC. Asking "how many posts share today's UTC date"
    makes the day roll over at 8pm Eastern: the quota reset mid-evening and the bot
    posted a third video the same day. Slots are chosen in ET, so the count has to
    be too, or the two disagree for four hours every night.
    """
    now = (now or now_local()).astimezone(TZ)
    today = now.date()
    count = 0
    for v in dashboard._load().get("videos", []):
        raw = v.get("date")
        if not raw:
            continue
        try:
            t = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        if t.astimezone(TZ).date() == today:
            count += 1
    return count


def next_slot(now: dt.datetime | None = None) -> dt.datetime | None:
    now = (now or now_local()).astimezone(TZ)
    done = posts_today(now)
    if done >= MAX_PER_DAY:
        return None
    slots = slots_for_date(now.date())
    return slots[done] if done < len(slots) else None


def should_post(now: dt.datetime | None = None) -> bool:
    """True if a slot is due — or close enough ahead to build for.

    Fires when the slot is within LOOKAHEAD_MIN (build now, hold, then upload AT
    the slot — see run.py), or once it has already passed (the fallback: a missed
    check-in still posts, just immediately). Without the look-ahead, an hourly
    check-in meant every upload went live at wake-minute + build time, erasing the
    day's random slot minute.
    """
    now = (now or now_local()).astimezone(TZ)
    if dashboard.paused():
        return False
    target = next_slot(now)
    return target is not None and now >= target - dt.timedelta(minutes=LOOKAHEAD_MIN)


def upcoming(days: int = 3, now: dt.datetime | None = None) -> list[dt.datetime]:
    """Future post times, for the dashboard countdown."""
    now = (now or now_local()).astimezone(TZ)
    done = posts_today(now)
    out: list[dt.datetime] = []
    for i in range(days):
        d = (now + dt.timedelta(days=i)).date()
        slots = slots_for_date(d)
        if i == 0:
            slots = slots[done:]
        out += [s for s in slots if s > now]
    return out


if __name__ == "__main__":
    n = now_local()
    print("now        :", n.strftime("%a %d %b %H:%M %Z"))
    print("posts today:", posts_today(), "/", MAX_PER_DAY)
    print("today slots:", [s.strftime("%H:%M") for s in slots_for_date(n.date())])
    print("next slot  :", (next_slot() or "— done for today"))
    print("should post:", should_post())
