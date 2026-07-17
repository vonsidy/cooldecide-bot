"""Lays the generated pictures out on labelled sheets so they can be reviewed by eye.

.gitignore promises every committed picture "has been reviewed by eye". That promise
was not kept — a ringed planet (Saturn) sat on the "Jupiter" card and a family of
three illustrated the answer "7", both committed, both live. The reason is simply
that there was no way to look at 400 pictures.

This makes one. Each tile is the picture with the option under it, so a wrong subject
is obvious at a glance. Review these BEFORE committing new art.

    python tools/contact_sheet.py            # only art drawn from a hint
    python tools/contact_sheet.py --all      # everything in the cache
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image, ImageDraw  # noqa: E402

import art  # noqa: E402
import card  # noqa: E402
from unhinted import rows_for  # noqa: E402

COLS, ROWS = 5, 6
TILE, LABEL, PAD = 300, 54, 10
OUT = os.path.join(os.path.dirname(__file__), "..", "output", "_review")


def entries() -> list[tuple[str, str, str]]:
    """(option, path, hint) for every option with a cached picture."""
    out, seen = [], set()
    for fmt in ("wyr", "this_or_that", "rank", "higher_lower", "trivia"):
        for option, inline, _claim in rows_for(fmt):
            option = (option or "").strip()
            key = option.lower()
            if not option or key in seen or card._is_number(option):
                continue
            seen.add(key)
            hint = inline or art.ART_HINTS.get(key, "")
            path = os.path.join(art.CACHE, art._slug(option) + ".jpg")
            if os.path.exists(path) and (hint or "--all" in sys.argv):
                out.append((option, path, hint))
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    items = entries()
    per = COLS * ROWS
    sheets = (len(items) + per - 1) // per
    w = COLS * (TILE + PAD) + PAD
    h = ROWS * (TILE + LABEL + PAD) + PAD

    for s in range(sheets):
        sheet = Image.new("RGB", (w, h), (24, 26, 34))
        d = ImageDraw.Draw(sheet)
        f = card._font("Anton-Regular.ttf", 20)
        for i, (option, path, _hint) in enumerate(items[s * per:(s + 1) * per]):
            cx, cy = i % COLS, i // COLS
            x = PAD + cx * (TILE + PAD)
            y = PAD + cy * (TILE + LABEL + PAD)
            try:
                im = Image.open(path).convert("RGB")
                im.thumbnail((TILE, TILE), Image.LANCZOS)
                sheet.paste(im, (x + (TILE - im.width) // 2, y + (TILE - im.height) // 2))
            except Exception:  # noqa: BLE001
                d.rectangle((x, y, x + TILE, y + TILE), fill=(80, 30, 30))
            text = option if len(option) <= 30 else option[:29] + "…"
            d.text((x + 4, y + TILE + 6), text.upper(), font=f, fill=(240, 240, 240))
        out = os.path.join(OUT, f"sheet_{s + 1:02d}.png")
        sheet.save(out)
        print(f"  {out}  ({min(per, len(items) - s * per)} pictures)")

    print(f"\n{len(items)} pictures across {sheets} sheets — LOOK AT EVERY ONE.")
    print("A picture that isn't unmistakably its label is a bug: fix the hint in")
    print("art.py, then: python tools/redraw.py --draw")


if __name__ == "__main__":
    main()
