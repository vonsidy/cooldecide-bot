"""Print what generate.py actually writes — no render, no upload, no state change.

Exists because a dry run cannot answer "did my prompt change work?". The workflow
deliberately blanks ANTHROPIC_API_KEY on dry runs so test renders stay free, which
means every dry run ships content.py's fallback pool rather than AI output. Tuning a
prompt and then dry-running it shows you the pool you didn't change.

generate.generate() ends in a bare `except Exception: return []`, which is right for
production — a broken API must not cost the day's upload — but useless for debugging,
because an auth failure, a timeout and "every row failed validation" all look the same
from outside. So this makes the call ITSELF here, with the error visible, and only
then hands off to the real function. When the two disagree, the fault is in parsing
or validation rather than the API.

    python tools/preview_questions.py [n] [fmt]
"""
from __future__ import annotations
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
fmt = sys.argv[2] if len(sys.argv) > 2 else "wyr"

key = generate._api_key()
if not key:
    print("NO API KEY — generate._api_key() returned nothing.")
    print("In CI that means the ANTHROPIC_API_KEY secret didn't reach this step.")
    raise SystemExit(1)
print(f"key present (len {len(key)}, starts {key[:7]}…)\n")

# ---- 1. is the API reachable at all? --------------------------------------
# Deliberately outside generate()'s try/except so a credit, auth or model-name
# problem prints as itself instead of arriving as an empty list.
try:
    import anthropic
    client = anthropic.Anthropic(api_key=key, max_retries=1, timeout=60.0)
    ping = client.messages.create(
        model=generate.MODEL, max_tokens=16,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
    )
    print(f"API reachable — {generate.MODEL} replied "
          f"{''.join(b.text for b in ping.content if getattr(b, 'type', '') == 'text')!r}\n")
except Exception:
    print("API CALL FAILED — this is the error generate() would have swallowed:\n")
    traceback.print_exc()
    raise SystemExit(1)

# ---- 2. what does the real function produce? ------------------------------
print(f"asking for {n} '{fmt}' questions with the CURRENT prompt...\n")
rows = generate.generate(fmt, n)

if not rows:
    print("API works, but generate() still returned [] — so the model replied and")
    print("every row was rejected by _rows_from_json/validation. That is a PROMPT or")
    print("PARSING problem, not a connectivity one.")
    raise SystemExit(1)

print(f"{len(rows)} questions:\n")
for i, r in enumerate(rows, 1):
    print(f"{i:2}. {r[0]}")
    print(f"    vs  {r[1]}")

print("\nNothing was rendered, uploaded, or written to the dashboard.")
