"""Generates a cartoon sticker for ANY option, so every card has art.

Why generate instead of searching a photo library
-------------------------------------------------
Most options aren't photographable. "Never do homework again" has no photo, and
a stock search for it returns junk (a real search for "be in your favorite movie"
returned a beer advert). Generation covers everything AND gives one consistent
look, instead of a mishmash of stock photos in different styles.

The catch, and the fix
----------------------
An image model can't interpret an abstract option either — prompted with the raw
text "never do homework again" it drew a kid DOING homework, and "being invisible"
drew a plainly visible girl. So the option is translated into something concrete
and drawable FIRST ("a happy kid throwing homework papers into the air"), which
renders perfectly. That translation comes from:
  1. `hint` — Claude writes one per option when it writes the question (generate.py)
  2. ART_HINTS — hand-written for the built-in pool
  3. the raw option text — fine for concrete things ("a pet dragon" is great)

Images are cached on disk and committed, so the cloud never regenerates (it's
~10-45s per image) and never ships art nobody reviewed.
"""
from __future__ import annotations
import hashlib
import os
import re
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://image.pollinations.ai/prompt/"
CACHE = os.path.join(os.path.dirname(__file__), "assets", "art")
UA = {"User-Agent": "cooldecide-bot/0.1"}
TIMEOUT = 100
RETRIES = 4
BACKOFF = 6      # seconds; multiplied on 429 and by attempt number

# One house style for every card. Flat sticker art on white reads instantly at
# thumbnail size and cuts out cleanly against the coloured panels.
STYLE = ("cute simple flat cartoon sticker illustration of {}, bold clean outlines, "
         "vibrant colors, plain white background, centered, no text, for kids")

# Abstract options translated into something an image model can actually draw.
# Concrete options ("have a pet dragon") are left out — the raw text works.
ART_HINTS = {
    "be invisible": "a child turning see-through and transparent, fading outline",
    "turn invisible": "a child turning see-through and transparent, fading outline",
    "be able to fly": "a happy kid flying through the sky, arms stretched out",
    "never do homework again": "a happy kid throwing homework papers into the air",
    "never be sick again": "a strong healthy kid flexing, glowing with health",
    "be the fastest kid alive": "a kid running super fast with speed lines",
    "be the strongest kid alive": "a kid lifting a huge heavy dumbbell",
    "control fire": "a hand shooting a burst of flames",
    "control water": "a hand swirling a ribbon of water in the air",
    "have super speed": "a kid running so fast they blur, speed lines",
    "read minds": "a head with floating thought bubbles and question marks",
    "shrink to ant size": "a tiny kid standing next to a giant ant",
    "grow to giant size": "a giant kid towering over tiny houses",
    "breathe underwater": "a smiling kid breathing happily underwater with fish",
    "walk through walls": "a kid stepping straight through a brick wall",
    "have night vision": "glowing green eyes seeing in the dark",
    "have x-ray vision": "eyes with beams revealing a skeleton hand",
    "time travel to the past": "a kid stepping into a swirling portal toward a dinosaur",
    "time travel to the future": "a kid stepping into a glowing futuristic portal",
    "be super lucky": "a kid holding a four leaf clover surrounded by sparkles",
    "be super smart": "a kid with a glowing brain and a stack of books",
    "never have to sleep": "a wide awake happy kid at night under a moon",
    "never have to eat": "a kid cheerfully pushing away a plate of food",
    "swim like a fish": "a kid swimming fast underwater like a fish",
    "run like a cheetah": "a kid racing alongside a cheetah",
    "be able to teleport": "a kid vanishing into a swirling portal",
    "be able to freeze time": "a kid standing still while frozen clocks float around",
    "be able to talk to animals": "a kid happily chatting with a dog and a bird",
    "speak every language": "a kid surrounded by colorful speech bubbles",
    "turn into any animal": "a kid transforming into a tiger",
    "control the weather": "a kid holding a storm cloud in one hand and sunshine in the other",
    "control gravity": "a kid floating objects in the air around them",
    "have a clone of yourself": "two identical smiling kids standing side by side",
    "have a robot twin": "a kid standing beside a friendly robot copy of themselves",
    "have glow-in-the-dark skin": "a kid glowing brightly in the dark",
    "color-changing hair": "a kid with rainbow color-changing hair",
    "have unlimited robux": "a big pile of shiny blue gems",
    "have unlimited v-bucks": "a big pile of glowing gold coins",
    "get $100 every day": "a happy kid holding a fan of banknotes",
    "have $1,000,000": "a huge pile of money and gold coins",
    "find $500 on the ground": "a kid picking up money off the pavement",
    "be a famous youtuber": "a kid filming themselves with a camera and ring light",
    "be a pro gamer": "a kid with a headset winning at a gaming setup",
    "never sick": "a healthy glowing kid",
    "have a magic backpack": "a glowing magical backpack with sparkles",
    "have magic shoes": "a pair of glowing magical sneakers with sparkles",
    "own a candy store": "a kid behind the counter of a colorful candy shop",
    "own a toy store": "a kid inside a bright toy shop full of toys",
    "be in your favorite movie": "a kid stepping into a glowing cinema screen",
    "be in your favorite game": "a kid stepping into a glowing video game world",
    "have every video game free": "a kid holding a huge stack of game boxes",
    "have every movie free": "a kid surrounded by floating film reels and popcorn",
}


def _slug(s: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:44]
    return f"{base}_{hashlib.sha1(s.lower().encode()).hexdigest()[:6]}"


def visual_for(option_text: str, hint: str | None = None) -> str:
    """The concrete thing to draw for this option."""
    return hint or ART_HINTS.get(option_text.strip().lower()) or option_text


def fetch(option_text: str, hint: str | None = None) -> str | None:
    """A local cartoon sticker for this option, or None. Never raises."""
    if not option_text:
        return None
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, _slug(option_text) + ".jpg")
    if os.path.exists(path):
        return path

    prompt = STYLE.format(visual_for(option_text, hint))
    # Seed from the option so an image is stable across runs (and so Pollinations'
    # own cache can serve a repeat instantly instead of re-generating).
    seed = int(hashlib.sha1(option_text.lower().encode()).hexdigest()[:6], 16) % 100000
    from PIL import Image
    # The endpoint is free and strict: it 500s intermittently, and it 429s hard if
    # you push it. Six parallel workers got 198/200 rejected, so requests must stay
    # SERIAL and back off. A 429 means "wait", not "give up" — retrying too eagerly
    # just extends the throttle.
    for attempt in range(RETRIES):
        url = (ENDPOINT + urllib.parse.quote(prompt)
               + f"?width=512&height=512&nologo=true&safe=true&seed={seed + attempt}")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=TIMEOUT) as r:
                blob = r.read()
            if len(blob) < 2000:      # an error page, not an image
                time.sleep(BACKOFF)
                continue
            with open(path, "wb") as f:
                f.write(blob)
            with Image.open(path) as im:
                im.verify()
            return path
        except Exception as e:  # noqa: BLE001 - art is never worth failing a render
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            code = getattr(e, "code", None)
            time.sleep(BACKOFF * (4 if code == 429 else 1) * (attempt + 1))
    return None


if __name__ == "__main__":
    import sys
    import content
    opts, seen = [], set()
    for fmt in content.FORMATS:
        for row in content.FORMATS[fmt][2]:
            for o in (row[1], row[2]) if fmt == "trivia" else (row[0], row[1]):
                if o and o.lower() not in seen:
                    seen.add(o.lower())
                    opts.append(o)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(opts)
    for i, o in enumerate(opts[:limit], 1):
        got = fetch(o)
        print(f"{i:3}/{min(limit,len(opts))} {'OK  ' if got else 'FAIL'} {o[:40]:40} <- {visual_for(o)[:44]}")
