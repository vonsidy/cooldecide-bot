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

    python tools/preview_questions.py [n] [fmt] [topic]

`topic` matters more than it looks. content.several() calls generate() with a topic
AND an avoid-list; this tool used to call it with neither, so the two disagreed about
what the prompt does. Untopiced, the model has nothing steering it and reaches for
whatever characters the prompt names — a rank preview came back 6/10 verbatim
examples, which reads as a broken prompt but is an artifact of previewing it in a way
production never runs it. Pass a topic to see what actually ships. Left off, it still
shows the unsteered baseline, which is the honest worst case.
"""
from __future__ import annotations
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
fmt = sys.argv[2] if len(sys.argv) > 2 else "wyr"
topic = sys.argv[3] if len(sys.argv) > 3 else None

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
_steer = f", topic={topic!r}" if topic else ", NO topic (unsteered baseline)"
print(f"asking for {n} '{fmt}' questions with the CURRENT prompt{_steer}...\n")
rows = generate.generate(fmt, n, topic=topic)

if not rows:
    print("API works, but generate() still returned [] — so the fault is in the")
    print("prompt, the reply, or the parsing. Re-running the SAME call with the")
    print("error visible to say which:\n")
    prompt = generate.build_prompt(fmt, n, topic=topic)
    msg = client.messages.create(
        model=generate.MODEL, max_tokens=1400,
        temperature=0.4 if fmt in generate.FACTUAL else 1.0,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    print(f"--- stop_reason: {msg.stop_reason} | output tokens: {msg.usage.output_tokens}")
    print(f"--- RAW REPLY ({len(raw)} chars) " + "-" * 44)
    print(raw if len(raw) <= 4000 else raw[:4000] + "\n…[truncated]")
    print("-" * 70)
    try:
        parsed = generate._rows_from_json(raw, fmt)
        print(f"\n_rows_from_json parsed {len(parsed)} rows from that.")
        if not parsed:
            print("So the JSON was readable but every row lacked the required fields.")
    except Exception:
        print("\n_rows_from_json RAISED on that reply — this is the swallowed error:\n")
        traceback.print_exc()
    raise SystemExit(1)

print(f"{len(rows)} questions:\n")
for i, r in enumerate(rows, 1):
    print(f"{i:2}. {r[0]}")
    print(f"    vs  {r[1]}")

print("\nNothing was rendered, uploaded, or written to the dashboard.")
