"""Central settings for the kids fun-Shorts bot.

Reads from environment first, then a local .env (gitignored). Kept flat (no
package) to match the rest of this project.
"""
from __future__ import annotations
import os

_HERE = os.path.dirname(__file__)


def _from_env_file(key: str) -> str | None:
    env = os.path.join(_HERE, ".env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or _from_env_file(key) or default


# --- YouTube upload -----------------------------------------------------------
# Same Google Cloud project/OAuth client as the Nyxtold bot, but a SEPARATE token
# (this bot posts to its own new channel). Files are gitignored.
YT_CLIENT_SECRETS = os.path.join(_HERE, "client_secret.json")
YT_TOKEN_FILE = os.path.join(_HERE, "yt_token.json")

# unlisted while testing; flip to "public" once you're happy with the output.
YT_PRIVACY = get("YT_PRIVACY", "unlisted")

# 24 = Entertainment. Good fit for fun quiz/would-you-rather Shorts.
YT_CATEGORY_ID = get("YT_CATEGORY_ID", "24")

# COPPA / "Made for Kids": if the channel is directed at children, YouTube
# requires this True — but that DISABLES comments, notifications, personalized
# ads (lower revenue) and some features. Many kid-APPEAL channels aimed at a
# general/family audience mark it False. This is YOUR call (see the notes I gave
# you); default False keeps engagement features on. Override with MADE_FOR_KIDS=1.
MADE_FOR_KIDS = get("MADE_FOR_KIDS", "0") == "1"

# Safety valve: never upload unless explicitly enabled (env or --upload flag).
UPLOAD = get("UPLOAD", "0") == "1"

# Channel self-commenting is OFF. A channel that comments on its own upload every
# single time — same shape of question, always within the same window — is a
# pattern YouTube can read as automation, and the account is worth more than the
# engagement bump. The delay (10-30 min) made it look less mechanical but didn't
# change that it happens on 100% of uploads. Owner's call: not worth the risk on a
# young channel. Flip to AUTO_COMMENT=1 to bring it back; both the queueing and the
# posting side check this, so turning it off also stops the queue growing.
AUTO_COMMENT = get("AUTO_COMMENT", "0") == "1"

# --- Video style --------------------------------------------------------------
# Narration is OFF: the format is "point at your pick", which works silently and
# reads as a game rather than a lecture. Audio is a music bed + countdown ticks +
# the reveal ding. Flip to 1 to bring the voice-over back.
ENABLE_VOICE = get("ENABLE_VOICE", "0") == "1"
# The QUESTION is read aloud every round ("Would you rather a pet shark, or a pet
# penguin?") — but nothing else is. The countdown and the reveal stay silent, so
# the voice sets up the choice and then gets out of the way.
ENABLE_QUESTION_VOICE = get("ENABLE_QUESTION_VOICE", "1") == "1"
# Kids' Shorts are read fast; the default TTS pace drags badly against a 3s timer.
EDGE_RATE = get("EDGE_RATE", "+25%")
# Ava: bright, young, natural female — fits a kids/teen channel and breaks from the
# over-used Andrew that half of faceless AI channels run (sounding generically-AI is
# its own small penalty). Override with EDGE_VOICE, e.g. en-US-AnaNeural (a younger
# child voice) or en-US-AndrewMultilingualNeural to revert.
EDGE_VOICE = get("EDGE_VOICE", "en-US-AvaMultilingualNeural")
ENABLE_MUSIC = get("ENABLE_MUSIC", "1") == "1"
# Music is the whole audio bed now (no voice competing), so it can sit up front —
# but under the ticks/ding, which carry the timing.
MUSIC_VOLUME = float(get("MUSIC_VOLUME", "0.55"))
SFX_VOLUME = float(get("SFX_VOLUME", "0.85"))
# The spoken title needs to win its 1 second: edge-tts lands ~-24dB mean, so it
# gets a lift AND the music drops out from under it.
INTRO_VOICE_GAIN = float(get("INTRO_VOICE_GAIN", "2.4"))
MUSIC_DUCK = float(get("MUSIC_DUCK", "0.16"))

# Silent-mode pacing (seconds). The vote phase is sized to READING time since
# there's no voice to set the pace.
READ_MIN, READ_MAX = 2.3, 4.3
# How long the result sits on screen before the next round. The reveal reads
# INSTANTLY — the bar fills and the number is right there — so this only needs to
# be long enough to register, not to read. At 2.9s it was a dead stare between
# every round; the ding already does the work of landing it.
# Countdown pacing. The 3-2-1 is dead air for retention if it drags: a viewer with
# nothing new happening scrolls. Tighter ticks keep the tension moving.
COUNTDOWN_STEP = float(get("COUNTDOWN_STEP", "0.7"))    # seconds per tick (was a flat 1.0)
# Gap between the spoken question ending and the countdown starting — small so the
# timer starts the instant the choice has landed, before attention drifts.
POST_VOICE_GAP = float(get("POST_VOICE_GAP", "0.2"))    # was 0.5
# Vote-card floor in question-voice mode. The voice paces the read, so it needn't
# linger as long as the silent-read floor (READ_MIN) — a shorter floor cuts the
# gap on quick questions instead of holding a static card.
VOICE_READ_MIN = float(get("VOICE_READ_MIN", "1.5"))

REVEAL_SECONDS = float(get("REVEAL_SECONDS", "1.9"))
# The result counts up over REVEAL_ANIM seconds instead of appearing finished.
# Taken from REVEAL_SECONDS, not added to it, so pacing doesn't regress.
REVEAL_FRAMES = int(get("REVEAL_FRAMES", "6"))
REVEAL_ANIM = float(get("REVEAL_ANIM", "0.5"))
# End card ("Comment which ones you picked!"). OFF: the Short is built to LOOP.
#
# A call-to-action card is a wall — it tells the viewer the video is over, and they
# swipe. Ending on the final reveal instead means the last frame runs straight back
# into the opening teaser, so a viewer who doesn't consciously decide to leave
# watches it twice. Shorts counts rewatches as watch time, so a clean loop is worth
# more reach than the comments the card was asking for — and the loop still asks
# the question, just by starting over instead of by saying so.
#
# The teaser at the top (TEASER_SECONDS) is the other half of this: it flashes the
# final round, which is exactly what the viewer has just seen resolved. Set to 1 to
# put the ask back.
ENABLE_OUTRO = get("ENABLE_OUTRO", "0") == "1"
# Floor only — the card actually lasts as long as the spoken ask plus OUTRO_TAIL.
# Keep it tight: once the ask has been said the card is doing nothing, and a Short
# that lingers on a static end card just gets swiped.
OUTRO_SECONDS = float(get("OUTRO_SECONDS", "1.7"))
OUTRO_TAIL = float(get("OUTRO_TAIL", "0.3"))
# Retention teaser: flash the FINAL (hardest) round's card for this long before
# round 1. Opens a loop ("can you get #3?") AND makes the Short loop seamlessly —
# the end card's "which did you pick?" wraps straight back into the tease of the
# question you just saw. Shorts counts rewatches, so loopability is pure reach.
# 0 disables it.
TEASER_SECONDS = float(get("TEASER_SECONDS", "0.8"))
# Owner's rule: every option panel shows REAL art — never an emoji stand-in. When
# a round's art can't be produced, the round itself is swapped for one whose art
# already exists (content.ensure_art) before anything renders.
ART_REQUIRED = get("ART_REQUIRED", "1") == "1"

# --- Motion -------------------------------------------------------------------
# Every frame drifts slowly instead of sitting still. The video was a slideshow of
# stills: nothing moved for the first 3.1s (the 0.8s teaser flash, then round 1's
# card while the question is read). A motionless opening frame reads as an image
# post on Shorts and gets swiped before the question lands, which wastes the hook
# copy entirely. Keep it SUBTLE — this should register as "alive", not as a zoom
# effect.
#
# The drift is ONE continuous cycle across the whole video, driven by absolute
# time (see assemble._motion_vf) — not a per-segment ramp. A per-segment ramp
# snapped back to 1.0 at every cut, which showed up as a skip between cards and as
# a shake on the reveal, where the count-up is six segments inside half a second.
# MOTION_MAX is the peak zoom; MOTION_PERIOD is how long one in-and-out breath
# takes. Longer period = calmer. Both are safe to tune without touching code.
MOTION_MAX = float(get("MOTION_MAX", "1.06"))       # peak zoom (6%)
MOTION_PERIOD = float(get("MOTION_PERIOD", "16"))   # seconds per in+out cycle
MOTION_FPS = int(get("MOTION_FPS", "30"))
