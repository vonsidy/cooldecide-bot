# CoolDecide bot

Automated YouTube Shorts channel. Two videos a day, posted by GitHub Actions.

**The README is stale** — it still says "Kids Fun Shorts" and describes a kids
channel. This file is current; prefer it.

## Where this runs

Cloudflare Worker (`cf-trigger/`, deployed from this repo) fires an hourly
`repository_dispatch` at GitHub Actions, which renders and uploads. **Nothing runs
on a laptop.** The bot keeps posting whether or not anyone has the repo cloned.

Credentials are GitHub Secrets (`ANTHROPIC_API_KEY`, `YT_CLIENT_SECRET_B64`,
`YT_TOKEN_B64`, `DASHBOARD_TOKEN`), decoded into the runner at post time. They are
write-only — you cannot read them back, only replace them.

## Audience: 13-17, both formats

Everything is written for teenagers. `_DILEMMA` in `generate.py` is explicit about
it (phones, the group chat, social media, an innocent crush) and `rank` matches.
Little-kid framing is a bug, not a style choice — recess, sticker charts, Minions
and Goombas all pull the model young and have been deliberately removed.

## What airs

```python
FORMAT_ROTATION = ["wyr", "wyr", "wyr", "rank"]
```

That list is the whole story — there is no env var and no filter. `wyr` is
WOULD YOU RATHER, `rank` is WHO WOULD WIN (nothing is ranked; the name is a
leftover). Both are *opinion* formats, which is the point: picking has to cost
something or nobody argues in the comments.

`this_or_that`, `trivia` and `higher_lower` still exist in `FORMATS` and still
work. They are kept for a possible second channel, not dead code. They are also
still kid-framed — teen-frame the prompt before airing one here. `trivia` and
`higher_lower` are *factual*: one answer is right, so they start no arguments.

Known quirk, not a bug: a 4-post cycle at 2 posts/day puts `rank` in the same slot
every time, so it always airs as the afternoon post. Changing that needs a cycle
length that is not a multiple of `POSTS_PER_DAY`.

## Verifying a prompt change — read this before tuning prompts

**A dry run cannot tell you whether a prompt change worked.** The workflow blanks
`ANTHROPIC_API_KEY` on dry runs to keep test renders free, so every dry run ships
the fallback pool in `content.py` rather than AI output. Tune a prompt, dry-run it,
and you are looking at the pool you did not touch.

Use the preview instead — one short Haiku call, no render, no upload, no state:

```bash
gh workflow run cooldecide.yml --ref <branch> \
  -f preview_questions=true -f preview_format=rank -f preview_topic=gaming
```

`preview_topic` matters. Production calls `generate(fmt, n, avoid=..., topic=...)`;
previewing without a topic is a different call, and unsteered the model reaches for
whatever characters the prompt names and hands the examples straight back. Leave it
blank only when you want the unsteered baseline.

Related trap: naming finished examples in a prompt gets those examples returned
verbatim. `rank` once listed "Goku vs Superman" and "Spider-Man vs Batman" — the
two most famous who-would-win arguments there are — and 6 of 10 generated rows came
back identical to the list. Name *characters*, specify the *shape*, and let the
model do the pairing.

## Conventions

- **Haiku for every Claude call** unless it provably needs more. `generate.MODEL`.
- **Batch items into one call.** One call per item spends most of the tokens
  re-sending the prompt.
- **Local ffmpeg has no freetype**, so `drawtext`/`subtitles` fail on a laptop.
  Overlays go through PIL.
- **Set `git config user.email`** to the GitHub-verified address. A default
  `you@YourMac.local` gets deploys rejected as *Blocked* with no error anywhere.
- Report times in Eastern.

## Checking on it

```bash
gh run list --limit 5                      # recent runs
python3 -c "import content; print(content.FORMAT_ROTATION)"
```

`dashboard/kids.json` holds every posted video with its view count — it is the
record of what actually aired, and it is committed by the bot on a cron
(`[skip ci]`), so expect a steady stream of data commits on `main`.
