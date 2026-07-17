"""Redraws the pictures that were generated from a bare option label.

Every option now carries an art hint, but the cache is keyed by the option's NAME,
so the old pictures — drawn before the hints existed — would be served forever. The
"Jupiter" card kept its ringed planet (i.e. Saturn) for exactly this reason.

This deletes those specific files so the next fetch redraws them from the hint, and
records the prompt in assets/art/prompts.json so a future hint change invalidates
itself instead of rotting silently.

Nothing here reviews the result. The new pictures MUST be eyeballed before they are
committed — see tools/contact_sheet.py, and the note in .gitignore.

    python tools/redraw.py            # what would be redrawn
    python tools/redraw.py --purge    # delete them
    python tools/redraw.py --draw     # delete AND redraw now (slow: serial + backoff)
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import art  # noqa: E402
import card  # noqa: E402
import content  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from unhinted import rows_for  # noqa: E402


def targets() -> list[tuple[str, str]]:
    """(option, hint) for options that HAVE a hint but whose cached art predates it."""
    out, seen = [], set()
    for fmt in ("wyr", "this_or_that", "rank", "higher_lower", "trivia"):
        for option, inline, _claim in rows_for(fmt):
            option = (option or "").strip()
            key = option.lower()
            if not option or key in seen or card._is_number(option):
                continue
            seen.add(key)
            hint = inline or art.ART_HINTS.get(key)
            if not hint:
                continue                      # nothing to improve on — see unhinted.py
            if art.is_stale(option, hint):    # manifest says it was drawn differently
                out.append((option, hint))
    return out


def main() -> None:
    work = targets()
    purge = "--purge" in sys.argv or "--draw" in sys.argv
    print(f"{len(work)} cached pictures were drawn from a bare label, not from their hint\n")
    for option, hint in work[:10]:
        print(f"  {option!r}\n      -> {hint}")
    if len(work) > 10:
        print(f"  ... and {len(work) - 10} more")
    if not purge:
        print("\n(dry run — pass --purge to delete, --draw to delete and redraw)")
        return

    for option, _hint in work:
        p = os.path.join(art.CACHE, art._slug(option) + ".jpg")
        try:
            os.remove(p)
        except OSError:
            pass
    print(f"\ndeleted {len(work)} stale pictures")

    if "--draw" not in sys.argv:
        return
    print("redrawing (serial — the endpoint 429s hard on any concurrency)\n")
    ok = 0
    for i, (option, hint) in enumerate(work, 1):
        got = art.fetch(option, hint)
        ok += bool(got)
        print(f"  [{i}/{len(work)}] {'ok  ' if got else 'FAIL'} {option}", flush=True)
    print(f"\nredrew {ok}/{len(work)} — NOW REVIEW THEM: python tools/contact_sheet.py")


if __name__ == "__main__":
    main()
