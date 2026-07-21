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
# Retention teaser: flash the FINAL round's card before round 1. OFF (0).
#
# It was meant to open a curiosity loop, but it spends the single most valuable
# frame on the wrong thing. The viewer's first sight is a question they can't
# answer yet, with a "BET YOU CAN'T CHOOSE" line over it — a hook that announces
# itself as a hook, which a scroller is trained to swipe. Then at 0.8s it vanishes
# and a DIFFERENT question appears, so anyone who did start reading is interrupted
# and has to start over. Owner's call, and the right one: open on round 1: a real
# question they can answer immediately, about their phone or their crush or school,
# earns the stop on relevance instead of asking for it.
#
# Removing the outro made it redundant anyway. The loop used to be
# end-card -> teaser; now it is final reveal -> teaser, which showed the last
# round's question again immediately after revealing its answer. Without the teaser
# the loop lands on round 1 — a new question right after a resolved one, which is
# the wrap that actually invites a rewatch.
#
# Set to 0.8 to bring it back.
TEASER_SECONDS = float(get("TEASER_SECONDS", "0"))
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
# The motion is a JELLY BOUNCE on each beat, not a slow drift. A new card or a
# countdown tick pops in slightly oversized and wobbles down to rest — the springy
# feel of a hand-edited Short, rather than a documentary pan. Owner's call: the
# slow zoom read as tasteful but sleepy.
#
# Beats are marked per segment in assemble.build (the 3rd element of seg_specs).
# The reveal count-up is deliberately NOT a beat: it is REVEAL_FRAMES segments
# inside half a second, and bouncing each one is what read as a shake. Those frames
# ride the tail of the preceding bounce.
#
#   zoom = MOTION_BASE + JELLY_POP * e^(-t/JELLY_DECAY) * cos(2*PI*t/JELLY_WOBBLE)
#
# JELLY_POP must stay BELOW MOTION_BASE-1.0: zoompan clamps zoom to >= 1, so a
# trough under 1.0 flattens into a stutter on exactly the springy frames.
#   bigger POP    = more bounce
#   longer DECAY  = wobbles for longer before settling
#   longer WOBBLE = slower, looser jelly; shorter = tighter, snappier
# A bounce alone still left the frame dead: the spring settles in ~0.8s but a card
# is up for ~2.3s, so most of its screen time was motionless — the "boring text
# just standing there" problem. DRIFT and SWAY run on absolute time and never
# settle, so the frame is always moving; the bounce rides on top as the punch.
#
# Peak zoom is MOTION_BASE+DRIFT_AMOUNT+JELLY_POP and is a CROP — push it too far
# and it eats the title. Trough is MOTION_BASE-DRIFT_AMOUNT-JELLY_POP and must stay
# above 1.0 or zoompan clamps it and the bounce stutters.
MOTION_BASE = float(get("MOTION_BASE", "1.055"))    # zoom the motion oscillates around
JELLY_POP = float(get("JELLY_POP", "0.035"))        # overshoot on the beat
JELLY_DECAY = float(get("JELLY_DECAY", "0.26"))     # seconds for the bounce to settle
JELLY_WOBBLE = float(get("JELLY_WOBBLE", "0.36"))   # seconds per wobble
DRIFT_AMOUNT = float(get("DRIFT_AMOUNT", "0.014"))  # never-stopping breath
DRIFT_PERIOD = float(get("DRIFT_PERIOD", "7"))      # seconds per breath
SWAY_PIXELS = float(get("SWAY_PIXELS", "26"))       # x/y float, in 2x source pixels
SWAY_PERIOD = float(get("SWAY_PERIOD", "9"))        # seconds per sway cycle
MOTION_FPS = int(get("MOTION_FPS", "30"))

# --- Panel entrance ------------------------------------------------------------
# The frame-level motion above moves the card as one flat image, so both boxes
# always travel together. This slides them in from OPPOSITE sides a beat apart, so
# they read as two separate objects — the thing that actually makes a Short look
# edited rather than animated.
#
# Sideways on purpose: the panels sit 16px under the header and just above the
# footer pill, so a vertical entrance slides a box straight over the title (tried
# it; it looks broken). Off the sides there is nothing to collide with.
#
# Frames are rendered by card.render rather than moved by a filter, because only
# card.render knows where the panels are. A cached render is ~35ms, so this costs
# about a second on a build that already takes minutes. Set PANEL_ENTRANCE=0 to
# turn it off. Skipped automatically when a round's intro is too short to hold it.
PANEL_ENTRANCE = float(get("PANEL_ENTRANCE", "0.6"))   # seconds of entrance (must cover STAGGER + settle)
PANEL_SLIDE_PX = float(get("PANEL_SLIDE_PX", "680"))   # how far off-frame it starts
PANEL_STAGGER = float(get("PANEL_STAGGER", "0.09"))    # how far B lags A
PANEL_SPRING = float(get("PANEL_SPRING", "0.10"))      # settle time — must land ~0 by PANEL_ENTRANCE or the static card snaps
PANEL_WOBBLE = float(get("PANEL_WOBBLE", "0.42"))      # overshoot period
