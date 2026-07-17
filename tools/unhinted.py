"""Lists every option whose picture is generated from its bare label.

art.visual_for() falls back to the option text itself when no hint exists, so
"Jupiter" is sent to the image model as "cartoon sticker illustration of Jupiter"
and comes back as a ringed planet — i.e. Saturn — on a card asking which is
bigger. Only the would-you-rather pool was ever given hints; the other four
formats have been guessing.

Run: python tools/unhinted.py          (add --json to emit the work list)
"""
from __future__ import annotations
import json
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0])

import art  # noqa: E402
import card  # noqa: E402
import content  # noqa: E402


def rows_for(fmt: str):
    """(option, inline_art, factual_claim) for every option in a format's pool."""
    label, prompt, pool, mode = content.FORMATS[fmt]
    for row in pool:
        r = tuple(row) + ("",) * 6
        if fmt == "trivia":
            q, correct, wrong = r[0], r[1], r[2]
            yield correct, r[5], f"{q} -> CORRECT answer"
            yield wrong, r[6], f"{q} -> WRONG answer"
        elif mode == "factual":
            yield r[0], r[4], "the BIGGER of the pair"
            yield r[1], r[5], "the SMALLER of the pair"
        else:
            yield r[0], r[4], ""
            yield r[1], r[5], ""


def main() -> None:
    work, seen = [], set()
    for fmt in ("wyr", "this_or_that", "rank", "higher_lower", "trivia"):
        for option, inline, claim in rows_for(fmt):
            option = (option or "").strip()
            key = option.lower()
            if not option or key in seen:
                continue
            seen.add(key)
            if inline or key in art.ART_HINTS:
                continue
            if card._is_number(option):     # numbers get no art at all — nothing to draw
                continue
            work.append({"fmt": fmt, "option": option, "claim": claim})

    if "--json" in sys.argv:
        print(json.dumps(work, indent=1))
        return
    by_fmt: dict[str, int] = {}
    for w in work:
        by_fmt[w["fmt"]] = by_fmt.get(w["fmt"], 0) + 1
    print(f"{len(work)} options have NO art hint — their picture is a guess from the label\n")
    for fmt, n in sorted(by_fmt.items(), key=lambda kv: -kv[1]):
        print(f"  {fmt:14} {n:4}")
    print("\nexamples:")
    for w in work[:8]:
        print(f"  [{w['fmt']:12}] {w['option']!r}  {w['claim']}")


if __name__ == "__main__":
    main()
