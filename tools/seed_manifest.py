"""Records what each already-cached picture was drawn from — once.

The prompt manifest starts empty, which would read as "unknown" for all 395 existing
pictures and flag every one as stale. Most are fine: their hint has not changed, so
the prompt that made them is the prompt we would use today.

The exception is the options that had NO hint until now. Those were drawn from their
bare label — "cartoon sticker illustration of Jupiter" — which is why the Jupiter
card shows a ringed planet. This seeds the manifest with the truth for both groups,
so tools/redraw.py redraws exactly the wrong ones and nothing else.

Which options were previously hint-less is read from git (the committed art.py), not
guessed. Run once: python tools/seed_manifest.py
"""
from __future__ import annotations
import ast
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import art  # noqa: E402
import card  # noqa: E402
from unhinted import rows_for  # noqa: E402


def committed_hint_keys() -> set[str]:
    """The ART_HINTS keys as of the last commit — i.e. before this session's work."""
    src = subprocess.run(["git", "show", "HEAD:art.py"], capture_output=True, text=True,
                         encoding="utf-8", cwd=os.path.join(os.path.dirname(__file__), "..")).stdout
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "ART_HINTS" for t in node.targets):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise SystemExit("could not find ART_HINTS in the committed art.py")


def main() -> None:
    old_keys = committed_hint_keys()
    print(f"art.py at HEAD had {len(old_keys)} hints; it now has {len(art.ART_HINTS)}\n")

    manifest, bare, kept, seen = {}, 0, 0, set()
    for fmt in ("wyr", "this_or_that", "rank", "higher_lower", "trivia"):
        for option, inline, _claim in rows_for(fmt):
            option = (option or "").strip()
            key = option.lower()
            if not option or key in seen or card._is_number(option):
                continue
            seen.add(key)
            slug = art._slug(option)
            if not os.path.exists(os.path.join(art.CACHE, slug + ".jpg")):
                continue
            if inline or key in old_keys:
                # had a hint when it was drawn, and that hint hasn't changed
                manifest[slug] = art.STYLE.format(inline or art.ART_HINTS[key])
                kept += 1
            else:
                # drawn from the bare label — this is the broken group
                manifest[slug] = art.STYLE.format(option)
                bare += 1

    with open(art.MANIFEST, "w", encoding="utf-8") as f:
        import json
        json.dump(manifest, f, indent=1, sort_keys=True, ensure_ascii=False)

    print(f"  {kept:4} drawn WITH a hint that still matches -> left alone")
    print(f"  {bare:4} drawn from a BARE LABEL              -> now detected as stale")
    print(f"\nwrote {art.MANIFEST}")
    print("next: python tools/redraw.py")


if __name__ == "__main__":
    main()
