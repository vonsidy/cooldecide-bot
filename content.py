"""Content for the kids fun-Shorts channel — all original, so it can monetize.

Five formats, all built around the same hook: show two things, count down, reveal
a percentage split (the % is made up on purpose — it's for fun and engagement).
`daily_item(format, date)` gives a stable-per-day pick so each day is fresh but a
day's video doesn't change between renders.
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass


@dataclass
class Item:
    prompt: str        # the line read aloud, e.g. "Would you rather..."
    a: str             # option A short text
    b: str             # option B short text
    a_emoji: str = ""
    b_emoji: str = ""
    a_pct: int = 0     # filled at pick time (made up)
    b_pct: int = 0
    fmt: str = "wyr"
    correct: int | None = None  # 0=a, 1=b for factual formats; None = opinion (no wrong answer)


# --- Format pools (kid-fun, broad appeal) --------------------------------------

WYR = [
    ("have $1,000,000", "have a real pet dragon", "💰", "🐉"),
    ("be invisible", "be able to fly", "👻", "🦅"),
    ("eat pizza forever", "eat ice cream forever", "🍕", "🍦"),
    ("have unlimited Robux", "have unlimited V-Bucks", "💎", "🎮"),
    ("live in Minecraft", "live in Roblox", "⛏️", "🎮"),
    ("fight 100 duck-sized horses", "fight 1 horse-sized duck", "🐴", "🦆"),
    ("never do homework again", "never be sick again", "📚", "🤒"),
    ("have a jetpack", "have a teleporter", "🚀", "🌀"),
    ("be the fastest kid alive", "be the strongest kid alive", "⚡", "💪"),
    ("have a talking dog", "have a talking cat", "🐶", "🐱"),
    ("control fire", "control water", "🔥", "💧"),
    ("have every video game free", "have every movie free", "🎮", "🎬"),
    ("be a famous YouTuber", "be a pro gamer", "📹", "🏆"),
    ("have a pet T-Rex", "have a pet giant spider", "🦖", "🕷️"),
    ("get $100 every day", "get a new phone every month", "💵", "📱"),
    ("shrink to ant size", "grow to giant size", "🐜", "🦍"),
    ("only eat candy", "only eat chips", "🍬", "🍟"),
    ("breathe underwater", "walk through walls", "🌊", "🧱"),
    ("have super speed", "read minds", "💨", "🧠"),
    ("own a private island", "own a private jet", "🏝️", "✈️"),
]

THIS_OR_THAT = [
    ("Summer", "Winter", "☀️", "❄️"),
    ("Dogs", "Cats", "🐶", "🐱"),
    ("Pizza", "Burgers", "🍕", "🍔"),
    ("PlayStation", "Xbox", "🎮", "🟢"),
    ("TikTok", "YouTube", "🎵", "📹"),
    ("Beach", "Mountains", "🏖️", "⛰️"),
    ("Marvel", "DC", "🦸", "🦇"),
    ("Chocolate", "Vanilla", "🍫", "🍦"),
]

TRIVIA = [  # (question, correct, wrong)
    ("Which planet is the biggest?", "Jupiter", "Mars"),
    ("How many legs does a spider have?", "8", "6"),
    ("What is the fastest land animal?", "Cheetah", "Lion"),
    ("What color do blue and yellow make?", "Green", "Purple"),
    ("How many continents are there?", "7", "5"),
    ("What is the biggest ocean?", "Pacific", "Atlantic"),
    ("How many hearts does an octopus have?", "3", "1"),
    ("What is the tallest animal?", "Giraffe", "Elephant"),
]

HIGHER_LOWER = [  # first option is always the bigger (correct) one; position is shuffled later
    ("A blue whale", "A school bus", "🐋", "🚌"),
    ("Mount Everest", "The Eiffel Tower", "🏔️", "🗼"),
    ("A T-Rex", "An elephant", "🦖", "🐘"),
    ("The Sun", "The Earth", "☀️", "🌍"),
    ("A blue whale", "A T-Rex", "🐋", "🦖"),
]

RANK = [  # a fun "which is better" pair, same reveal mechanic
    ("Fortnite", "Minecraft", "🎮", "🟫"),
    ("Superman", "Batman", "🦸", "🦇"),
    ("Spider-Man", "Iron Man", "🕷️", "🤖"),
    ("Sharks", "Dinosaurs", "🦈", "🦖"),
]

# label, spoken prompt, pool, mode ("opinion" = made-up % split, no wrong answer;
# "factual" = one answer is correct and gets marked on the reveal).
FORMATS = {
    "wyr": ("WOULD YOU RATHER", "Would you rather", WYR, "opinion"),
    "this_or_that": ("THIS OR THAT", "Which do you pick", THIS_OR_THAT, "opinion"),
    "trivia": ("GUESS THE ANSWER", "Can you guess", TRIVIA, "factual"),
    "higher_lower": ("WHICH IS BIGGER", "Which one is bigger", HIGHER_LOWER, "factual"),
    "rank": ("WHO WOULD WIN", "Who would win", RANK, "opinion"),
}

# One format per weekday cycle, so the channel rotates through all five.
FORMAT_ROTATION = ["wyr", "this_or_that", "wyr", "higher_lower", "wyr", "rank", "trivia"]


def _rng(*parts) -> random.Random:
    seed = int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def _split(rng: random.Random) -> tuple[int, int]:
    """A believable made-up split — never 50/50, one side clearly ahead."""
    a = rng.choice([52, 55, 58, 61, 64, 67, 71, 74, 78, 83])
    return (a, 100 - a) if rng.random() < 0.5 else (100 - a, a)


def _build(fmt: str, seed: str, row: tuple) -> Item:
    label, prompt, pool, mode = FORMATS[fmt]
    rng = _rng(fmt, seed)
    if mode == "factual":
        if fmt == "trivia":                       # (question, correct, wrong)
            prompt, correct_text, wrong_text = row[0], row[1], row[2]
            ae = be = ""
        else:                                     # (bigger, smaller, emojis) — first is correct
            correct_text, wrong_text, ae, be = (row + ("", ""))[:4]
        # Shuffle which side the correct answer sits on.
        if rng.random() < 0.5:
            a, b, a_e, b_e, correct = correct_text, wrong_text, ae, be, 0
        else:
            a, b, a_e, b_e, correct = wrong_text, correct_text, be, ae, 1
        # The correct side gets the majority "% who got it right".
        win = rng.choice([54, 58, 63, 67, 72, 77, 81])
        a_pct, b_pct = (win, 100 - win) if correct == 0 else (100 - win, win)
        return Item(prompt=prompt, a=a, b=b, a_emoji=a_e, b_emoji=b_e, a_pct=a_pct, b_pct=b_pct, fmt=fmt, correct=correct)

    a, b, ae, be = (row + ("", ""))[:4]
    a_pct, b_pct = _split(_rng(fmt, seed, a, b))
    return Item(prompt=prompt, a=a, b=b, a_emoji=ae, b_emoji=be, a_pct=a_pct, b_pct=b_pct, fmt=fmt, correct=None)


def daily_item(fmt: str | None = None, date: str = "today") -> Item:
    if fmt is None:
        fmt = FORMAT_ROTATION[_rng("fmt", date).randrange(len(FORMAT_ROTATION))]
    pool = FORMATS[fmt][2]
    row = pool[_rng(fmt, date).randrange(len(pool))]
    return _build(fmt, date, row)


def several(fmt: str, date: str, n: int = 3) -> list[Item]:
    """n distinct items of one format for a multi-round video."""
    pool = FORMATS[fmt][2]
    rng = _rng("several", fmt, date)
    idxs = rng.sample(range(len(pool)), min(n, len(pool)))
    return [_build(fmt, f"{date}#{k}", pool[i]) for k, i in enumerate(idxs)]


def format_label(fmt: str) -> str:
    return FORMATS[fmt][0]


if __name__ == "__main__":
    for d in ["2026-07-15", "2026-07-16", "2026-07-17", "2026-07-18", "2026-07-19"]:
        it = daily_item(date=d)
        print(f"{d}  [{it.fmt}]  {it.prompt}: {it.a} ({it.a_pct}%) vs {it.b} ({it.b_pct}%)")
