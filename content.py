"""Content for the kids fun-Shorts channel — all original, so it can monetize.

Five formats, all built around the same hook: show two things, count down, reveal
a percentage split (the % is made up on purpose — it's for fun and engagement).
`daily_item(format, date)` gives a stable-per-day pick so each day is fresh but a
day's video doesn't change between renders.
"""
from __future__ import annotations
import hashlib
import json
import os
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
    ("have a lightsaber", "have a magic wand", "⚔️", "🪄"),
    ("be a superhero", "be a wizard", "🦸", "🧙"),
    ("have night vision", "have x-ray vision", "🌙", "🦴"),
    ("live on the moon", "live underwater", "🌕", "🐠"),
    ("have a robot butler", "have a flying car", "🤖", "🚗"),
    ("turn invisible", "turn into any animal", "🫥", "🐯"),
    ("have unlimited pizza", "have unlimited tacos", "🍕", "🌮"),
    ("be best at soccer", "be best at basketball", "⚽", "🏀"),
    ("have a pet penguin", "have a pet monkey", "🐧", "🐵"),
    ("get a puppy", "get a kitten", "🐕", "🐈"),
    ("have a treehouse", "have a secret underground base", "🌳", "🕳️"),
    ("have wings", "have a tail", "🪽", "🦎"),
    ("time travel to the past", "time travel to the future", "⏪", "⏩"),
    ("have a chocolate river", "have a candy mountain", "🍫", "🍭"),
    ("be super lucky", "be super smart", "🍀", "🧠"),
    ("have a pet unicorn", "have a pet phoenix", "🦄", "🔥"),
    ("never have to sleep", "never have to eat", "😴", "🍽️"),
    ("have a magic carpet", "have a hoverboard", "🧞", "🛹"),
    ("swim like a fish", "run like a cheetah", "🐟", "🐆"),
    ("have a giant water slide", "have a giant trampoline", "🛝", "🤸"),
    ("own a candy store", "own a toy store", "🍬", "🧸"),
    ("be able to teleport", "be able to freeze time", "🌀", "⏱️"),
    ("have a dinosaur as a pet", "ride a dragon to school", "🦕", "🐉"),
    ("have a pool full of jelly", "a pool full of slime", "🟢", "🫧"),
    ("be a famous singer", "be a famous actor", "🎤", "🎬"),
    ("have super strength", "have super hearing", "💪", "👂"),
    ("live in a candy house", "live in a giant treehouse", "🏠", "🌲"),
    ("have a magic backpack", "have magic shoes", "🎒", "👟"),
    ("be able to talk to animals", "speak every language", "🐾", "🗣️"),
    ("have a pet shark", "have a pet whale", "🦈", "🐋"),
    ("get every LEGO set", "get every Nerf gun", "🧱", "🔫"),
    ("have a jetpack to school", "a slide from your room", "🚀", "🛝"),
    ("be in your favorite movie", "be in your favorite game", "🎬", "🕹️"),
    ("have endless ice cream", "endless donuts", "🍦", "🍩"),
    ("control the weather", "control gravity", "🌦️", "🪐"),
    ("have a clone of yourself", "have a robot twin", "👥", "🤖"),
    ("be able to fly a plane", "drive a race car", "✈️", "🏎️"),
    ("have glow-in-the-dark skin", "color-changing hair", "✨", "🌈"),
    ("find $500 on the ground", "win a giant teddy bear", "💵", "🧸"),
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


def _build(fmt: str, row: tuple, rng: random.Random) -> Item:
    label, prompt, pool, mode = FORMATS[fmt]
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
    a_pct, b_pct = _split(rng)
    return Item(prompt=prompt, a=a, b=b, a_emoji=ae, b_emoji=be, a_pct=a_pct, b_pct=b_pct, fmt=fmt, correct=None)


def daily_item(fmt: str | None = None, date: str = "today") -> Item:
    if fmt is None:
        fmt = FORMAT_ROTATION[_rng("fmt", date).randrange(len(FORMAT_ROTATION))]
    pool = FORMATS[fmt][2]
    row = pool[_rng(fmt, date).randrange(len(pool))]
    return _build(fmt, row, _rng(fmt, date))


# --- No-repeat picking: remember what's been used so every post is different ----

def _key(row: tuple) -> str:
    return f"{row[0]}|{row[1]}"


def _used_path(fmt: str) -> str:
    return os.path.join(os.path.dirname(__file__), "output", f"used_{fmt}.json")


def _load_used(fmt: str) -> set[str]:
    try:
        with open(_used_path(fmt)) as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def _save_used(fmt: str, keys: set[str]) -> None:
    os.makedirs(os.path.dirname(_used_path(fmt)), exist_ok=True)
    with open(_used_path(fmt), "w") as f:
        json.dump(sorted(keys), f)


def several(fmt: str, date: str | None = None, n: int = 3, avoid_repeats: bool = True) -> list[Item]:
    """n distinct items of one format. Prefers freshly AI-generated questions (so
    every post is brand-new); falls back to the curated pool so the bot always
    works. Never repeats a question until everything's been used."""
    import generate
    pool = FORMATS[fmt][2]
    n = min(n, len(pool))
    used = _load_used(fmt) if avoid_repeats else set()
    rng = random.Random()
    chosen: list[tuple] = []
    picked_keys: set[str] = set()

    # 1) brand-new questions from Claude, skipping anything already used
    for row in generate.generate(fmt, n, avoid=sorted(used)):
        k = _key(row)
        if k not in used and k not in picked_keys:
            chosen.append(row)
            picked_keys.add(k)
            if len(chosen) >= n:
                break

    # 2) top up from the curated pool if generation was unavailable or short
    if len(chosen) < n:
        avail = [r for r in pool if _key(r) not in used and _key(r) not in picked_keys]
        if len(avail) < n - len(chosen):         # pool exhausted -> fresh cycle
            used = set(picked_keys)
            avail = [r for r in pool if _key(r) not in picked_keys]
        for row in rng.sample(avail, n - len(chosen)):
            chosen.append(row)
            picked_keys.add(_key(row))

    if avoid_repeats:
        _save_used(fmt, used | picked_keys)
    return [_build(fmt, row, random.Random()) for row in chosen]


def format_label(fmt: str) -> str:
    return FORMATS[fmt][0]


if __name__ == "__main__":
    for d in ["2026-07-15", "2026-07-16", "2026-07-17", "2026-07-18", "2026-07-19"]:
        it = daily_item(date=d)
        print(f"{d}  [{it.fmt}]  {it.prompt}: {it.a} ({it.a_pct}%) vs {it.b} ({it.b_pct}%)")
