# Kids Fun Shorts — countdown & reveal

Automated faceless Shorts for a young audience. All content is **original** (we
write it), so it can monetize — no clips, no copyright risk. Standalone project,
not connected to any other bot.

## The format
Show two things → a **3-second countdown** → **reveal a percentage for each side**
(made up on purpose — it's for fun and to make kids comment their pick).

Five formats rotate so every day is fresh:
- **Would You Rather** — silly dilemmas (money vs dragon, Minecraft vs Roblox…)
- **This or That** — quick preferences
- **Who Would Win** — matchups
- **Which is Bigger** — factual, correct answer marked ✅
- **Guess the Answer** — trivia, correct answer marked ✅

## Pipeline (built + verified)
- `content.py` — the five pools + `daily_item(fmt, date)` (stable per day, fresh
  each day). Opinion formats use a made-up % split; factual ones mark the correct
  answer and show "% who got it right".
- `card.py` — renders the 1080×1920 frames: vote, countdown (3/2/1), and reveal
  (percentage bars fill in). Emoji + bright kid-friendly style.
- `voice.py` — edge-tts narration (free).
- `assemble.py` — stitches vote → countdown → reveal with narration into a
  1080×1920 h264 mp4. Verified end to end.
- `run.py` — daily entry point. `python run.py`

## To go live (your setup, same as the Nyxtold bot)
1. Make a **new YouTube channel** + Google OAuth (only you can do this).
2. Drop `youtube_upload.py` from the Nyxtold repo in and point it at the new
   channel's token; call it at the end of `run.py`.
3. Schedule daily via GitHub Actions, like the other bot.
