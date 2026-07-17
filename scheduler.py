"""Decides whether to post right now, and at what time of day.

Runs on US/Eastern, not UTC — the audience is US kids, so what matters is "is it
after school where they are", not what time it is in London.

The cloud checks in hourly and asks should_post(). Posting times are picked from
the day's date, so they're stable across the hour's checks but different every day:
a channel that posts at exactly 16:00:00 every single day looks like a machine.
"""
from __future__ import annotations
import datetime as dt
import os
import random
from zoneinfo import ZoneInfo

import dashboard

TZ = ZoneInfo(os.getenv("BOT_TZ", "America/New_York"))
MAX_PER_DAY = int(os.getenv("MAX_UPLOADS_PER_DAY", "2"))

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
    """Same picks all day, different picks tomorrow.

    Seeded by the DATE so every hourly check-in agrees on today's times. If this
    were unseeded, each check would roll new times and the bot would post
    repeatedly or never.
    """
    return random.Random(date.toordinal() * 7919)


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
    """True if a slot is due and today's quota isn't spent.

    A slot counts as due once its time has PASSED — the check-in is hourly, so a
    target of 16:20 is first seen at 17:00. Requiring an exact match would mean
    never posting at all.
    """
    now = (now or now_local()).astimezone(TZ)
    if dashboard.paused():
        return False
    target = next_slot(now)
    return target is not None and now >= target


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
