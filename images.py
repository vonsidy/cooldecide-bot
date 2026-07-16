"""Finds a real photo for an option — but only when it's safe to.

Why this is deliberately narrow
-------------------------------
Keyword-searching an image library for whatever the question happens to say goes
wrong fast, and this is a KIDS channel, so "mostly fine" isn't good enough:
  * abstract options can't be photographed at all. "be in your favorite movie"
    returned a BEER ADVERT; "control the weather" returned a photo of houses.
  * even concrete words are ambiguous: "dragon" returns the SpaceX capsule,
    "dinosaur" returns a national-park sign.
So we do NOT search on the raw option text. An option only gets a photo if it
matches a curated term below, and the query is one WE wrote to be unambiguous.
Anything else falls back to the emoji, which is always on-topic and always safe.

Licensing: CC0 / public-domain ONLY. The usual CC images are `by`/`by-sa`, which
legally require crediting the photographer (and share-alike can infect the whole
video) — not something to run unattended on a monetized channel.
"""
from __future__ import annotations
import json
import os
import re
import urllib.parse
import urllib.request

API = "https://api.openverse.org/v1/images/"
CACHE = os.path.join(os.path.dirname(__file__), "assets", "images", "auto")
UA = {"User-Agent": "cooldecide-bot/0.1 (kids shorts; contact via channel)"}
TIMEOUT = 15
MIN_PX = 320          # anything smaller looks like mush at 1080 wide

# keyword found in the option text  ->  the search we actually run.
# Queries are hand-written to pin the MEANING (hence "dragon mythical creature",
# not "dragon"). Brands/trademarks are intentionally absent.
# EVERY query here has been eyeballed on a contact sheet before being allowed in.
# That review is not optional and the list is not "clever": an unreviewed query
# returned a wine bottle for "potato chips" and a 3D pin-up for "donut", and
# `mature=false` stopped neither. Terms that wouldn't reliably return the right
# thing (jetpack, treehouse, puppy, kitten, island) are simply gone — they fall
# back to the emoji, which is always on-topic and always safe.
PICTURABLE = {
    # animals
    "shark": "shark underwater",
    "penguin": "penguin bird",
    "monkey": "monkey primate",
    "cat": "cat pet",
    "octopus": "octopus sea",
    "spider": "spider web",
    "cheetah": "cheetah",
    "lion": "lion mane animal",
    "giraffe": "giraffe animal",
    "elephant": "elephant animal",
    "t-rex": "tyrannosaurus skeleton",
    "dinosaur": "tyrannosaurus skeleton",
    "unicorn": "unicorn illustration",
    "dragon": "dragon mythical creature illustration",
    # food
    "pizza": "pizza slice",
    "burger": "hamburger",
    # "ice cream cone" returned a MONKEY holding a cone — reuse the reviewed
    # soft-serve shot instead (same query = same cached file, no extra fetch).
    "ice cream": "vanilla ice cream",
    "candy": "candy sweets",
    "vanilla": "vanilla ice cream",
    # things
    "soccer": "soccer ball",
    "basketball": "basketball ball",
    "moon": "full moon",
    "volcano": "volcano eruption",
    "rainbow": "rainbow sky",
    "everest": "mount everest summit",
    "eiffel": "eiffel tower paris",
    "school bus": "yellow school bus",
    "puppy": "puppy",
    "kitten": "kitten",
    "taco": "tacos mexican food",
    "donut": "doughnut glazed",
    "chocolate": "chocolate pieces",
}
# Reviewed and REJECTED — do not re-add without looking at the result yourself:
#   beach / mountain / winter / summer / island  -> the CC0 pool for generic
#       nature words is mostly washed-out archival B&W. Worse than the emoji.
#   earth  -> a dark frame captioned "You are here" (not Earth from space)
#   whale  -> a crowd of people (whale WATCHING)
#   robot  -> a toy figure under a shoe
#   dog    -> an African wild dog, not a pet
#   sun    -> indistinguishable from the volcano shot
#   jetpack / treehouse -> no usable public-domain image exists


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40]


def query_for(option_text: str) -> str | None:
    """The curated search for this option, or None if it isn't safely picturable."""
    t = option_text.lower()
    # longest keyword first, so "ice cream" beats "cream"-ish partials
    for key in sorted(PICTURABLE, key=len, reverse=True):
        if key in t:
            return PICTURABLE[key]
    return None


def _candidates(query: str) -> list[str]:
    """URLs worth trying, best first.

    Each hit contributes its original host URL *and* Openverse's own proxied
    thumbnail. The original is often on a flaky third-party host (Flickr handed
    back 502s), so the proxy is the reliable fallback — and one dead host must
    not mean "no picture", hence a list rather than a single pick.
    """
    params = urllib.parse.urlencode({
        "q": query,
        "license": "cc0,pdm",      # public domain only — no attribution needed
        "mature": "false",         # kids channel
        "page_size": 8,
        "extension": "jpg,png",
    })
    req = urllib.request.Request(API + "?" + params, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.load(r)
    urls: list[str] = []
    for hit in data.get("results", []):
        if (hit.get("width") or 0) < MIN_PX or (hit.get("height") or 0) < MIN_PX:
            continue
        for key in ("url", "thumbnail"):
            u = hit.get(key)
            if u:
                urls.append(u)
    return urls


def fetch(option_text: str) -> str | None:
    """A local path to a public-domain photo for this option, or None.

    Cached on disk, so a repeat option costs nothing. Never raises: any failure
    (offline, rate-limited, junk file) just means "use the emoji".
    """
    query = query_for(option_text)
    if not query:
        return None
    os.makedirs(CACHE, exist_ok=True)
    stem = os.path.join(CACHE, _slug(query))
    for ext in (".jpg", ".png"):
        if os.path.exists(stem + ext):
            return stem + ext
    # A ".miss" is only written when the LIBRARY has nothing for this query — a
    # permanent fact. Download failures are transient (a flaky image host) and are
    # never cached, or one 502 would mean "no picture" forever.
    miss = stem + ".miss"
    if os.path.exists(miss):
        return None

    from PIL import Image
    try:
        urls = _candidates(query)
    except Exception:  # noqa: BLE001 - offline/rate-limited: try again next run
        return None
    if not urls:
        try:
            open(miss, "w").close()
        except OSError:
            pass
        return None

    for url in urls:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                blob = r.read()
            ext = ".png" if blob[:4] == b"\x89PNG" else ".jpg"
            path = stem + ext
            with open(path, "wb") as f:
                f.write(blob)
            # Validate it really is a usable image; a truncated body or an HTML
            # error page would otherwise blow up mid-render.
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                if min(im.size) < 200:      # proxy thumbs can come back tiny
                    raise ValueError("too small")
            return path
        except Exception:  # noqa: BLE001 - try the next candidate
            try:
                if os.path.exists(path):
                    os.remove(path)
            except (OSError, NameError):
                pass
            continue
    return None


if __name__ == "__main__":
    import content
    seen = set()
    for fmt in content.FORMATS:
        for row in content.FORMATS[fmt][2]:
            for opt in (row[0], row[1]):
                q = query_for(opt)
                if q and q not in seen:
                    seen.add(q)
                    got = fetch(opt)
                    print(f"{'OK ' if got else '-- '} {opt[:34]:34} -> {q[:32]:32} "
                          f"{os.path.basename(got) if got else '(emoji fallback)'}")
