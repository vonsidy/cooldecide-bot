"""Print what generate.py actually writes — no render, no upload, no state change.

Exists because a dry run cannot answer "did my prompt change work?". The workflow
deliberately blanks ANTHROPIC_API_KEY on dry runs so test renders stay free, which
means every dry run ships content.py's fallback pool rather than AI output. Tuning a
prompt and then dry-running it shows you the pool you didn't change.

This calls the generator directly and prints the rows. One short Haiku call, a
fraction of a cent, and the questions are visible before anything is committed or
posted. Run it from the workflow with preview_questions=true.

    python tools/preview_questions.py [n] [fmt]
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
fmt = sys.argv[2] if len(sys.argv) > 2 else "wyr"

if not generate.available():
    print("NO API KEY — generate.available() is False.")
    print("In CI that means the ANTHROPIC_API_KEY secret didn't reach this step.")
    raise SystemExit(1)

print(f"asking for {n} '{fmt}' questions with the CURRENT prompt...\n")
rows = generate.generate(fmt, n)

if not rows:
    # [] is generate()'s catch-all for every failure, so say so rather than
    # implying the prompt produced nothing interesting.
    print("generator returned [] — an API error, or every row failed validation.")
    raise SystemExit(1)

print(f"{len(rows)} questions:\n")
for i, r in enumerate(rows, 1):
    print(f"{i:2}. {r[0]}")
    print(f"    vs  {r[1]}")

print("\nNothing was rendered, uploaded, or written to the dashboard.")
