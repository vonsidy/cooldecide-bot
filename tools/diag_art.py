"""Diagnose WHY live art generation falls back to the emoji in the cloud.

Runs in CI (where pollinations is reachable) and prints, per option, exactly what
the endpoint returns and whether the vision-check accepts it — the data we can't get
from a sandbox that can't reach the endpoint. Writes to a THROWAWAY cache so it never
touches committed art.

    python tools/diag_art.py

It probes each option twice:
  * VERIFY_ART=0  -> isolates the ENDPOINT (does it return a real image at all?)
  * VERIFY_ART=1  -> adds the vision-check (does Claude reject the image?)
so a failure can be pinned on the endpoint vs. the safety-check.
"""
from __future__ import annotations
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import art  # noqa: E402

# A simple one (should be trivial to draw) plus the real round-2 options that showed
# up as emoji in the last test video.
OPTIONS = [
    ("a dragon", "a friendly green dragon"),
    ("1,000 newbie players using starter weapons", "a big crowd of cartoon gamers"),
    ("1 max-level player with legendary gear", "one hero in glowing legendary armour"),
]


def probe(verify: bool) -> None:
    art.DEBUG = True
    art.VERIFY_ART = verify
    art.reset_run()
    art.CACHE = tempfile.mkdtemp(prefix="diag_")
    art.MANIFEST = os.path.join(art.CACHE, "prompts.json")
    print(f"\n{'='*70}\nPROBE  VERIFY_ART={int(verify)}  PACE={art.PACE}  "
          f"MODEL={art.MODEL}  TOKEN={'set' if art.TOKEN else 'none'}\n{'='*70}", flush=True)
    for opt, hint in OPTIONS:
        p = art.fetch(opt, hint)
        got = bool(p) and os.path.exists(p)
        print(f"RESULT  {'REAL ART' if got else 'EMOJI FALLBACK':14} <- {opt}", flush=True)


if __name__ == "__main__":
    print("anthropic key present:", bool(os.getenv("ANTHROPIC_API_KEY")))
    probe(verify=False)   # endpoint only
    probe(verify=True)    # endpoint + vision-check
    print("\ndone", flush=True)
