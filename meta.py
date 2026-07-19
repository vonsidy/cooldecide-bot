"""Build the YouTube title, description, tags and channel comment for a video,
from the rounds it contains. Kid-fun, clicky, and honest (no clickbait lies).

Titles are the channel's most-repeated surface, so they're the easiest place to
LOOK recycled: two Shorts with the byte-identical title read as "same content
re-uploaded" to both viewers and YouTube's dedup. Two defences here:
  1. Every title template embeds the video's OWN first matchup ({a}/{b}, or the
     trivia {q}). The matchup is already de-duplicated per video (content.several),
     so baking it into the title makes the title unique for free — no two videos
     share one. The old pool had several matchup-free templates
     ("This Would You Rather is IMPOSSIBLE") that produced the exact same string
     every time they were picked; those are gone.
  2. A rolling ledger of the last _TITLE_MEMORY titles (output/used_titles.json,
     committed by the workflow like the other used_*.json files). build() re-rolls
     until it lands a title that isn't in that window, so even a coincidental
     collision can't post the same title twice in a row.
Template x emoji x concrete-matchup gives thousands of distinct titles before the
ledger ever has to intervene.
"""
from __future__ import annotations
import json
import os
import random

import content

# Punchy title templates per format. EVERY template embeds the concrete matchup
# ({a}/{b}, or {q} for trivia) so the title is as unique as the video itself.
# {pct} is an optional "N% fail" number; unused placeholders are ignored by format.
_TITLES = {
    "wyr": [
        "Would You Rather: {a} or {b}?",
        "{a} or {b}?? Choose ONE!",
        "Only 1% pick right: {a} or {b}?",
        "{a} or {b} — what do YOU pick?",
        "Impossible choice: {a} or {b}",
        "You HAVE to choose: {a} or {b}",
        "{a} vs {b}... which one??",
        "Be honest: {a} or {b}?",
        "Hardest WYR ever: {a} or {b}",
        "{a} or {b}? Don't overthink it!",
        "This one splits everyone: {a} or {b}",
        "No right answer: {a} or {b}?",
    ],
    "this_or_that": [
        "This or That: {a} or {b}?",
        "{a} or {b}? Pick fast!",
        "Quick! {a} or {b}?",
        "{a} vs {b} — go with your gut!",
        "Can you choose? {a} or {b}",
        "{a} or {b}? First instinct only!",
        "Team {a} or team {b}?",
    ],
    "rank": [
        "Who would WIN? {a} vs {b}",
        "{a} vs {b} — who wins??",
        "The ultimate battle: {a} vs {b}",
        "{a} or {b}: who takes it?",
        "{a} vs {b} — you decide the winner!",
        "Dream matchup: {a} vs {b}",
        "{a} vs {b}... closer than you think",
        "Winner takes all: {a} vs {b}",
    ],
    "higher_lower": [
        "Which is BIGGER? {a} or {b}",
        "Bet you get this wrong: {a} or {b}?",
        "{a} vs {b} — which is bigger?",
        "Higher or lower? {a} vs {b}",
        "{a} or {b}: which one's more?",
        "Guess the bigger one: {a} or {b}",
    ],
    "trivia": [
        "Can you guess: {q}?",
        "Only smart kids get this: {q}",
        "{q}? Bet you can't!",
        "Guess it: {q}",
        "Do you know? {q}",
        "{q} — are you right?",
        "Most people fail this: {q}",
        "Only {pct}% get this: {q}",
    ],
}

# A mood-matched emoji is appended (not baked into the template) so every template
# multiplies into ~7-10 variants — more surface variety before anything repeats.
_EMOJI = {
    "wyr": ["🤔", "😳", "😭", "🫠", "😰", "🤯", "👀", "💭", "⚖️", "🥲"],
    "this_or_that": ["🔥", "⚡", "😤", "💥", "👀", "🤨", "🆚"],
    "rank": ["🏆", "💥", "⚔️", "🔥", "😳", "💪", "🥊"],
    "higher_lower": ["🤯", "📈", "🧐", "😵", "🤔", "📊"],
    "trivia": ["🧠", "🤓", "✅", "❓", "🎯", "😮"],
}

_HASHTAGS = ["#shorts", "#wouldyourather", "#quiz", "#kids", "#fun", "#challenge"]

# Description openers/closers also rotate — a fixed first line on every upload is
# its own recycled-content tell.
_OPENERS = [
    "{label}! Play along and comment your answers. 👇",
    "{label} time! Can you decide? Drop your picks 👇",
    "New {label}! Pause if you need to — then comment 👇",
    "{label}! Harder than it looks. What did you pick? 👇",
    "Play this {label} with me — comment your answers! 👇",
]
_CLOSERS = [
    "New fun videos every day — subscribe! 🔔",
    "Follow for a new one every day! 🔔",
    "Subscribe so you don't miss tomorrow's! 🔔",
    "Hit follow for daily challenges! 🔔",
]

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

# Rolling window of recently-used titles, so we never repeat one too soon. Lives
# beside the other output/used_*.json ledgers, which the workflow commits back.
_TITLE_LEDGER = os.path.join(os.path.dirname(__file__), "output", "used_titles.json")
_TITLE_MEMORY = 60


def _clean(s: str) -> str:
    # Titles read better without a leading article / trailing punctuation noise.
    return s.strip().rstrip("?.!").strip()


def _load_recent_titles() -> list[str]:
    try:
        with open(_TITLE_LEDGER, encoding="utf-8") as f:
            data = json.load(f)
        return [str(t) for t in data] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _remember_title(title: str, recent: list[str]) -> None:
    keep = [t for t in recent if t != title] + [title]
    keep = keep[-_TITLE_MEMORY:]
    try:
        os.makedirs(os.path.dirname(_TITLE_LEDGER), exist_ok=True)
        with open(_TITLE_LEDGER, "w", encoding="utf-8") as f:
            json.dump(keep, f, ensure_ascii=False)
    except OSError:
        pass  # a titles ledger we can't write must never block a post


def _format_title(fmt: str, a: str, b: str, q: str, rng: random.Random) -> str:
    body = rng.choice(_TITLES.get(fmt, _TITLES["wyr"])).format(
        a=a, b=b, q=q or "this one", pct=rng.choice([90, 92, 95, 97, 99]))
    title = f"{body} {rng.choice(_EMOJI.get(fmt, ['🤔']))}"
    if len(title) > 100:                      # YouTube's hard limit
        title = title[:99].rstrip() + "…"
    return title


def _pick_title(fmt, a, b, q, rng, recent) -> str:
    """A title not used in the recent window. Re-rolls template+emoji until it
    finds a fresh one; if the space is somehow exhausted, accepts the last try."""
    recent_set = set(recent)
    last = ""
    for _ in range(40):
        last = _format_title(fmt, a, b, q, rng)
        if last not in recent_set:
            return last
    return last


def build(items: list[content.Item]) -> dict:
    """Return {title, description, tags, comment} for a finished video."""
    fmt = items[0].fmt if items else "wyr"
    a, b = (_clean(items[0].a), _clean(items[0].b)) if items else ("this", "that")
    q = _clean(getattr(items[0], "prompt", "") or "") if items else ""
    rng = random.Random()

    recent = _load_recent_titles()
    title = _pick_title(fmt, a, b, q, rng, recent)
    _remember_title(title, recent)

    label = content.format_label(fmt).title()
    lines = [rng.choice(_OPENERS).format(label=label), ""]
    for i, it in enumerate(items, 1):
        if it.fmt == "trivia":
            lines.append(f"{i}. {it.prompt}? {it.a} or {it.b}")
        else:
            lines.append(f"{i}. {it.a}  vs  {it.b}")
    lines += ["", rng.choice(_CLOSERS), "", " ".join(_HASHTAGS)]
    description = "\n".join(lines)

    # tag pool: format + option words. Sampled (not fixed) so tags vary too.
    tag_pool = ["would you rather", "wyr", "quiz", "kids games", "this or that",
                "trivia", "challenge", "fun", "shorts", "who would win",
                "pick one", "brain teaser", "family fun", "guessing game"]
    tags = rng.sample(tag_pool, min(12, len(tag_pool)))

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "comment": rng.choice(_COMMENTS),
    }
