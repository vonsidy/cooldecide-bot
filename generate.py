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

# The pull of this format is the DAYDREAM, not the preference. "Summer or Winter"
# is something a kid already has an answer to, so there's nothing to picture and
# nothing to argue about. "Dragon or unicorn" makes them imagine owning one.
_IMAGINATIVE = (
    "\nMake them IMAGINATIVE and magical — wish-fulfilment a kid would daydream "
    "about: powers, creatures, magic, space, secret worlds, impossible pets, being "
    "a hero. Both options must be things they'd genuinely WANT, so picking hurts. "
    "Avoid everyday preferences (summer vs winter, chocolate vs vanilla, dogs vs "
    "cats) — those are boring and already decided. Every option must be something "
    "you could draw a fun picture of."
)

_PROMPTS = {
    # opinion formats: two fun options, each with one fitting emoji
    "wyr": ("fun 'would you rather' dilemmas kids would genuinely argue about "
            "(video games, superpowers, animals, money, food, silly hypotheticals)",
            '{"a":"have a pet dragon","a_emoji":"\\ud83d\\udc09","a_art":"a cute friendly dragon",'
            '"b":"have a pet dinosaur","b_emoji":"\\ud83e\\udd96","b_art":"a cute friendly dinosaur"}'),
    "this_or_that": ("quick 'this or that' preferences (one word or short each)",
                     '{"a":"Pizza","a_emoji":"\\ud83c\\udf55","a_art":"a slice of pizza",'
                     '"b":"Burgers","b_emoji":"\\ud83c\\udf54","b_art":"a cheeseburger"}'),
    "rank": ("'who would win' or 'which is cooler' matchups between two fun things",
             '{"a":"Sharks","a_emoji":"\\ud83e\\udd88","a_art":"a great white shark",'
             '"b":"Dinosaurs","b_emoji":"\\ud83e\\udd96","b_art":"a t-rex dinosaur"}'),
}

# Each option also needs a drawable description. An image model can't interpret an
# abstract option: prompted with "never do homework again" it draws a kid DOING
# homework, and "be invisible" draws a plainly visible girl. Claude writes the
# option and the picture for it in the SAME call, so this costs nothing extra.
_ART_RULE = (
    "\nEach option also needs \"a_art\"/\"b_art\": a short, CONCRETE description of a "
    "single picture that represents it, for a cartoon illustrator. It must be "
    "physically drawable — never an abstract phrase. Bad: \"never do homework again\". "
    "Good: \"a happy kid throwing homework papers into the air\". If the option is "
    "already a thing you can draw (a dragon, pizza), just describe that thing."
)


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
                rows.append((str(a), str(b), str(d.get("a_emoji", "")), str(d.get("b_emoji", "")),
                             str(d.get("a_art", "")), str(d.get("b_art", ""))))
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
            f"{_IMAGINATIVE if fmt in ('wyr', 'this_or_that') else ''}"
            f"{_ART_RULE}"
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
