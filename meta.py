"""Build the YouTube title, description, tags and channel comment for a video,
from the rounds it contains. Kid-fun, clicky, and honest (no clickbait lies).
"""
from __future__ import annotations
import random

import content

# A rotating set of punchy title patterns per format. {a}/{b} are the first
# round's two options so the title previews the actual video.
_TITLES = {
    "wyr": [
        "Would You Rather: {a} or {b}? 🤔",
        "{a} or {b}?? Choose ONE! 😳",
        "Only 1% Pick Right... {a} or {b}?",
        "This Would You Rather is IMPOSSIBLE 😭",
    ],
    "this_or_that": [
        "This or That: {a} vs {b}! 🔥",
        "{a} or {b}? Pick fast! ⚡",
        "Can You Choose? {a} vs {b} 😤",
    ],
    "rank": [
        "Who Would WIN? {a} vs {b} 🏆",
        "{a} vs {b} — who wins?? 💥",
        "The Ultimate Battle: {a} vs {b}!",
    ],
    "higher_lower": [
        "Which is BIGGER? {a} or {b} 🤯",
        "Bet You Get This WRONG... {a} or {b}?",
        "{a} vs {b} — which is bigger?",
    ],
    "trivia": [
        "Can You Guess It? 🧠 ({pct}% fail!)",
        "Only Smart Kids Get This Right 🤓",
        "Guess The Answer! Are You Right? ✅",
    ],
}

_HASHTAGS = ["#shorts", "#wouldyourather", "#quiz", "#kids", "#fun", "#challenge"]

_COMMENTS = [
    "Comment your answers below! 👇 A or B?",
    "Which one did you pick?? 🤔 Let me know!",
    "How many did you get right? Comment below! 👇",
    "Drop your answers in the comments! 🔥",
    # Identity bait: people comment to claim a tribe, not to report a vote.
    "Your 3 picks = your personality. Drop them 👇😳",
    "Everyone who picked the first one is brave, everyone who picked the second is smart 🧠🔥 Which are you?",
    "I can guess your age from your picks… prove me wrong 👇",
]


def _clean(s: str) -> str:
    # Titles read better without a leading article / trailing punctuation noise.
    return s.strip().rstrip("?.!").strip()


def build(items: list[content.Item]) -> dict:
    """Return {title, description, tags, comment} for a finished video."""
    fmt = items[0].fmt if items else "wyr"
    a, b = (_clean(items[0].a), _clean(items[0].b)) if items else ("this", "that")
    rng = random.Random()

    pattern = rng.choice(_TITLES.get(fmt, _TITLES["wyr"]))
    title = pattern.format(a=a, b=b, pct=rng.choice([90, 95, 99]))
    if len(title) > 100:
        title = title[:99].rstrip() + "…"

    label = content.format_label(fmt).title()
    lines = [f"{label}! Play along and comment your answers. 👇", ""]
    for i, it in enumerate(items, 1):
        if it.fmt == "trivia":
            lines.append(f"{i}. {it.prompt}? {it.a} or {it.b}")
        else:
            lines.append(f"{i}. {it.a}  vs  {it.b}")
    lines += ["", "New fun videos every day — subscribe! 🔔", "", " ".join(_HASHTAGS)]
    description = "\n".join(lines)

    # tag pool: format + option words
    tags = ["would you rather", "quiz", "kids games", "this or that", "trivia",
            "challenge", "fun", "shorts"]

    return {
        "title": title,
        "description": description,
        "tags": tags[:15],
        "comment": rng.choice(_COMMENTS),
    }
