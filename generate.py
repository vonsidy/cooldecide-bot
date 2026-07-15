"""Generates brand-new questions with Claude, so the bot never runs out and every
post is original. Falls back to the curated pools in content.py when no API key
is set or a call fails, so the bot always works.

Set ANTHROPIC_API_KEY (env or a local .env) to enable generation.
"""
from __future__ import annotations
import json
import os
import re

MODEL = "claude-haiku-4-5-20251001"   # fast + cheap, plenty for short questions

_SAFE = ("Wholesome and safe for ages 8-14: no violence, weapons aimed at people, "
         "scary/horror, romance, politics, or gross-out. Keep it playful.")

_PROMPTS = {
    # opinion formats: two fun options, each with one fitting emoji
    "wyr": ("fun 'would you rather' dilemmas kids would genuinely argue about "
            "(video games, superpowers, animals, money, food, silly hypotheticals)",
            '{"a":"have a pet dragon","a_emoji":"\\ud83d\\udc09","b":"have a pet dinosaur","b_emoji":"\\ud83e\\udd96"}'),
    "this_or_that": ("quick 'this or that' preferences (one word or short each)",
                     '{"a":"Pizza","a_emoji":"\\ud83c\\udf55","b":"Burgers","b_emoji":"\\ud83c\\udf54"}'),
    "rank": ("'who would win' or 'which is cooler' matchups between two fun things",
             '{"a":"Sharks","a_emoji":"\\ud83e\\udd88","b":"Dinosaurs","b_emoji":"\\ud83e\\udd96"}'),
}


def available() -> bool:
    return bool(_api_key())


def _api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env):
        for line in open(env):
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _rows_from_json(text: str, factual: bool) -> list[tuple]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    data = json.loads(match.group(0) if match else text)
    rows = []
    for d in data:
        if factual:
            q, c, w = d.get("question"), d.get("correct"), d.get("wrong")
            if q and c and w:
                rows.append((str(q), str(c), str(w)))
        else:
            a, b = d.get("a"), d.get("b")
            if a and b:
                rows.append((str(a), str(b), str(d.get("a_emoji", "")), str(d.get("b_emoji", ""))))
    return rows


def generate(fmt: str, n: int, avoid: list[str] | None = None) -> list[tuple]:
    """Returns rows in the same shape as content.py's pools, or [] on any failure."""
    key = _api_key()
    if not key or fmt not in _PROMPTS:
        return []
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        kind, example = _PROMPTS[fmt]
        avoid_txt = ("\nDo NOT repeat or closely echo any of these already-used ones:\n- "
                     + "\n- ".join((avoid or [])[-40:])) if avoid else ""
        prompt = (
            f"Write {n + 3} original {kind} for a kids' YouTube Shorts channel. {_SAFE}\n"
            f"Each needs two short options (2-6 words) and one fitting emoji per option. "
            f"Use clear object emojis, never plain colored squares/circles. Be creative and varied."
            f"{avoid_txt}\n\n"
            f'Return ONLY a JSON array of objects like: {example}'
        )
        msg = client.messages.create(
            model=MODEL, max_tokens=1000, temperature=1.0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return _rows_from_json(text, factual=False)
    except Exception:
        return []


if __name__ == "__main__":
    print("generation available:", available())
    if available():
        for r in generate("wyr", 3):
            print("  ", r)
