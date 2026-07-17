"""Fails if a card draws anything into YouTube's UI zones.

The card is a PNG and always looked fine on its own — the bug only existed on
YouTube, where the player's controls sit over the top of the frame and the channel
handle + video title + description sit over the bottom. Two videos shipped with the
format name under the pause button and the call-to-action under the title bar
before anyone noticed, because nothing here was checking.

Method: render the card, render the bare background gradient, and diff them. Any
pixel that differs inside the reserved bands is content the viewer will never see.
Run: python tools/safe_area_check.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageChops  # noqa: E402

import card  # noqa: E402
import content  # noqa: E402

TOL = 12          # per-channel diff that counts as "something was drawn here"
OUT = os.path.join(os.path.dirname(__file__), "..", "output", "_safecheck")


def violations(png: str) -> dict:
    """Rows of drawn content inside the reserved bands, per edge."""
    im = Image.open(png).convert("RGB")
    bare = card._gradient(card.BG_TOP, card.BG_BOT).convert("RGB")
    diff = ImageChops.difference(im, bare).convert("L").point(lambda v: 255 if v > TOL else 0)
    out = {}
    for name, box in (("top", (0, 0, card.W, card.SAFE_TOP)),
                      ("bottom", (0, card.SAFE_BOTTOM, card.W, card.H))):
        region = diff.crop(box)
        bbox = region.getbbox()
        if bbox:
            out[name] = {"px": sum(region.point(lambda v: v // 255).getdata()),
                         "worst_row": (bbox[1] + box[1]) if name == "top" else (bbox[3] + box[1])}
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    fails = 0
    for fmt in ("wyr", "this_or_that", "rank", "higher_lower", "trivia"):
        it = content.daily_item(fmt, "2026-07-16")
        for label, kw in (("vote", {"countdown": 3}), ("reveal", {"reveal": True})):
            for topic in ("", "SPACE EDITION"):     # the topic badge makes the header taller
                card.set_topic_label(topic)
                png = os.path.join(OUT, f"{fmt}_{label}{'_topic' if topic else ''}.png")
                card.render(it, png, **kw)
                bad = violations(png)
                tag = f"{fmt:13} {label:6} {'topic' if topic else '     '}"
                if bad:
                    fails += 1
                    print(f"  FAIL  {tag}  {bad}")
                else:
                    print(f"  ok    {tag}")
    card.set_topic_label("")

    # the end card is drawn by a different function with its own hardcoded layout,
    # so it needs checking too — it is not covered by render()'s safe-area maths.
    for fmt in ("wyr", "trivia"):
        it = content.daily_item(fmt, "2026-07-16")
        png = os.path.join(OUT, f"outro_{fmt}.png")
        card.outro(it, png)
        bad = violations(png)
        if bad:
            fails += 1
            print(f"  FAIL  outro {fmt:9}         {bad}")
        else:
            print(f"  ok    outro {fmt:9}")

    print()
    print(f"safe box: y {card.SAFE_TOP} .. {card.SAFE_BOTTOM}   ->  "
          + ("ALL CLEAR" if not fails else f"{fails} FRAMES DRAW UNDER YOUTUBE'S UI"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
