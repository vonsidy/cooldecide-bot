"""Builds the full vertical Short: vote -> 3-2-1 countdown -> reveal, with narration.

Timeline
  intro   : options shown while the question is read
  3, 2, 1 : one second each, ticking badge
  reveal  : the percentages fill in while the result is read
"""
from __future__ import annotations
import glob
import os
import random
import re
import subprocess
import tempfile

import card
import config
import content
import voice

W, H = 1080, 1920


def _ffmpeg() -> str:
    hits = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin\ffmpeg.exe"))
    return hits[0] if hits else "ffmpeg"


FF = _ffmpeg()
FFPROBE = FF.replace("ffmpeg.exe", "ffprobe.exe")


def _dur(path: str) -> float:
    # edge-tts mp3s often carry no duration in their header, so decode to measure.
    out = subprocess.run([FF, "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    last = None
    for m in re.finditer(r"time=(\d+):(\d+):(\d+\.\d+)", out.stderr):
        h, mm, s = m.groups()
        last = int(h) * 3600 + int(mm) * 60 + float(s)
    return last if last else 2.0


# --- Retention scaffolding -----------------------------------------------------
# Each round used to be self-contained (ask -> count -> reveal -> done), which
# gives a viewer nothing to stay for once round 1 pays off. So round 1 now opens a
# loop that only closes at the END ("the last one splits everyone"), and the
# comment ask happens ONCE, on the final reveal, where it's earned — not chanted
# every round where it's just noise.
_HOOKS_OPINION = [
    "Careful — the last one splits everyone.",
    "Pick fast. Number three is the one nobody agrees on.",
    "Be honest on these. The last one is brutal.",
]
_HOOKS_FACTUAL = [
    "Almost nobody gets all three. How many can you get?",
    "These get harder. The last one beats most people.",
    "Most people fail number three. Ready?",
]
_CTA_OPINION = [
    "Comment which ones you picked. I bet you're in the minority on one.",
    "Disagree? Say it in the comments.",
    "Comment your picks — let's see who's with you.",
]
_CTA_FACTUAL = [
    "How many did you get? Comment your score!",
    "Comment your score out of three. Be honest!",
    "Got all three? Prove it in the comments.",
]


# Homographs the TTS gets wrong, respelled for the EAR only. These never touch the
# on-screen text — card.render draws item.a / item.b directly, so the caption stays
# spelled correctly while the voice says the right word.
#
# "left on read" is the live example: `read` here is the past participle and should
# rhyme with "red", but nothing in the spelling tells edge-tts that, so it says
# "reed" and the line lands wrong. It came from the generator rather than the
# curated bank, so it can reappear in any freshly-written question — which is why
# this is a rule and not a one-off edit to a pool entry.
_SAY_AS = [
    (re.compile(r"\bon read\b", re.I), "on red"),          # left/leave someone on read
    (re.compile(r"\bread receipts?\b", re.I), "red receipts"),
]


def _say(text: str) -> str:
    """Respell for pronunciation. Audio only — never the caption."""
    for pattern, replacement in _SAY_AS:
        text = pattern.sub(replacement, text)
    return text


def _spoken(item: content.Item, idx: int = 0, total: int = 1) -> tuple[str, str]:
    """(question read during vote, result read on reveal).

    idx/total drive the hook (first round) and the comment ask (last round).
    """
    rng = random.Random()
    fmt = item.fmt
    factual = item.correct is not None

    # No invented "% got it right" on questions that have a real answer — see the
    # note in card._panel. The answer is the payoff.
    if fmt == "trivia":
        q = f"{item.prompt} Is it {item.a}, or {item.b}?"
        correct = item.a if item.correct == 0 else item.b
        r = f"It's {correct}! Did you get it?"
    elif fmt == "higher_lower":
        q = f"Which is bigger? {item.a}, or {item.b}?"
        bigger = item.a if item.correct == 0 else item.b
        r = f"{bigger} is bigger! Did you get it?"
    else:
        # "Would you rather X" runs straight on, but "Which do you pick X" /
        # "Who would win X" need the comma or the TTS gabbles them together.
        join = " " if fmt == "wyr" else ", "
        q = f"{item.prompt}{join}{item.a}, or {item.b}?"
        winner, wp = (item.a, item.a_pct) if item.a_pct >= item.b_pct else (item.b, item.b_pct)
        r = f"{wp} percent said {winner}."

    # The hook/CTA scaffolding belongs to the fully-narrated mode. In question-only
    # mode the voice reads the choice and stops — bolting "The last one is brutal"
    # onto every round just makes the line long and the timer late.
    if config.ENABLE_VOICE:
        if idx == 0:
            q = f"{rng.choice(_HOOKS_FACTUAL if factual else _HOOKS_OPINION)} {q}"
        if idx == total - 1:
            r = f"{r} {rng.choice(_CTA_FACTUAL if factual else _CTA_OPINION)}"
    return _say(q), _say(r)


# One spoken line at the very start, naming the game. Everything after it is
# silent — the point is to orient a scroller in the first second, not to narrate.
_INTRO_LINE = {
    "wyr": "Would you rather?",
    "this_or_that": "This, or that?",
    "rank": "Who would win?",
    "higher_lower": "Which one is bigger?",
    "trivia": "Quiz time!",
}


def _link_or_copy(src: str, dst: str) -> None:
    """Cheap duplicate for frames that don't change (teaser / outro stills)."""
    import shutil
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def _panel_dy(abs_s: float, since_beat: float, which: int) -> float:
    """Vertical offset for one panel — its own float, plus the shared beat squash.

    Two layers, and the point of both is that the boxes are never doing the same
    thing at the same moment:

      BOB    a slow rise-and-fall on its own period per panel, on ABSOLUTE time.
             The periods are deliberately not multiples of each other, so the two
             boxes drift in and out of phase instead of locking together.
      SQUASH on each beat the panels move TOWARD each other and spring back —
             panel A down, panel B up — like the card compressing. Toward, because
             that is where the room is: the 200px VS gap. Outward would push panel
             A into the title and panel B into the footer pill within a few pixels.

    Both layers are RECTIFIED so each panel only ever moves into the gap — panel A
    strictly down, panel B strictly up, never past its resting position. That is not
    a stylistic choice: a signed oscillation of this size sends panel A 25px up into
    a 16px gap and it clips the title. Rectifying keeps every pixel of travel inside
    the 200px the layout actually has spare.

    Kept deliberately small. The whole point of the effect is that the frame feels
    alive; the moment a box moves far enough to make its label hard to track, it has
    cost more than it bought.
    """
    import math
    period = config.BOB_PERIOD_A if which == 0 else config.BOB_PERIOD_B
    phase = 0.0 if which == 0 else math.pi / 2          # never peak together
    # 0.5-0.5cos: a sine rectified to 0..1, so the float only ever goes gap-ward.
    bob = config.BOB_PIXELS * (0.5 - 0.5 * math.cos(
        2 * math.pi * abs_s / period + phase))
    # (1+cos) likewise: starts at full squash, wobbles down to nothing, never negative.
    squash = (config.SQUASH_PIXELS
              * math.exp(-since_beat / config.SQUASH_DECAY)
              * (1 + math.cos(2 * math.pi * since_beat / config.SQUASH_WOBBLE)))
    total = bob + squash
    return total if which == 0 else -total


def _slide_in(t: float) -> float:
    """How far off-centre a panel still is, t seconds into its entrance.

    Starts a full PANEL_SLIDE_PX out and springs to 0 with a slight overshoot, so
    the box arrives with weight instead of gliding to a stop. Before its own start
    (t < 0, the staggered second panel) it is still parked off-frame.
    """
    import math
    if t <= 0:
        return config.PANEL_SLIDE_PX
    off = (config.PANEL_SLIDE_PX * math.exp(-t / config.PANEL_SPRING)
           * math.cos(2 * math.pi * t / config.PANEL_WOBBLE))
    return off if abs(off) > 1 else 0.0


def _read_seconds(item: content.Item) -> float:
    """How long to hold the vote card, sized to how much there is to READ.

    With narration off nothing paces the video for us, so a long trivia question
    can't get the same beat as "Pizza / Burgers" or it flies past unread.
    """
    text = f"{item.prompt} {item.a} {item.b}" if item.fmt == "trivia" else f"{item.a} {item.b}"
    secs = 1.9 + 0.045 * len(text)
    return round(min(max(secs, config.READ_MIN), config.READ_MAX), 2)


def build(items, out_path: str, background: str | None = None) -> str:
    if isinstance(items, content.Item):
        items = [items]
    work = tempfile.mkdtemp(prefix="short_")

    seg_specs = []          # (image_path, duration) in play order
    audio_pieces = []       # mp3s concatenated into the voice track (voice mode)
    cues = []               # (sfx_path, global_time)
    sfx = os.path.join(os.path.dirname(__file__), "assets")
    tick, ding = os.path.join(sfx, "tick.wav"), os.path.join(sfx, "ding.wav")
    has_sfx = os.path.exists(tick) and os.path.exists(ding)
    clock = 0.0             # running start time of the current round

    silence = None
    if config.ENABLE_VOICE:
        silence = os.path.join(work, "sil.mp3")
        subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-t", "3.0", silence], capture_output=True)

    # Spoken questions are kept OUT of `cues` because they need their own
    # treatment: edge-tts comes out quiet (~-24dB mean), so at SFX gain a line
    # sits level with the music bed and is effectively inaudible.
    voice_cues: list[tuple[str, float]] = []   # (mp3, start time)
    ducks: list[tuple[float, float]] = []      # windows where the music drops

    # ---- retention teaser: flash the FINAL round before round 1 ---------------
    # Items arrive sorted easiest -> hardest, so items[-1] is the payoff. Skipped
    # in full-voice mode: its audio track is a blind concat with no clock offsets,
    # and the teaser would shift the video 0.8s out from under it. Never fatal —
    # a broken teaser must not cost the day's upload.
    if (len(items) >= 2 and config.TEASER_SECONDS > 0 and not config.ENABLE_VOICE):
        try:
            last = items[-1]
            # A concrete curiosity line over the (visible) real options beats a bare
            # "#3" ordinal — the scroller's first frame gets a real question, not noise.
            tease = content.teaser_hook(last.a, last.correct is not None)
            f_tease = card.teaser(last, os.path.join(work, "teaser.png"), tease)
            seg_specs.append((f_tease, config.TEASER_SECONDS, True))
            clock += config.TEASER_SECONDS
        except Exception as e:  # noqa: BLE001
            print("  (teaser skipped:", e, ")")

    for n, item in enumerate(items):
        # Escalation label: an on-screen promise that the video keeps getting
        # better — the visible version of the narrated hook. Same label on every
        # frame of the round, or the layout jumps mid-round (see card.render).
        if len(items) >= 2 and n == len(items) - 1:
            round_label = ("ALMOST NOBODY GETS THIS" if item.correct is not None
                           else "THIS ONE SPLITS EVERYONE")
        elif n == 0 and item.fmt != "trivia":
            # Round 1's pill was blank — its strongest visual slot, wasted, on the
            # exact frame where stay/swipe is decided. Fill it with a clean identity/
            # side-pick dare so a passive scroller reflexively answers (never a fake
            # stat). Rotated per video so it isn't a byte-identical template. Skipped
            # for trivia, whose header already carries the full (tall) question.
            round_label = content.onscreen_hook(item.a, item.correct is not None)
        elif n >= 1:
            round_label = "GETS HARDER"
        else:
            round_label = ""
        # Round 1 opens with the clock ALREADY RUNNING instead of a neutral "VS".
        # The countdown was the only thing on screen creating urgency and it did not
        # appear until ~3.1s — after the stay/swipe decision has been made. The chip
        # is the same size and position either way (card.render just swaps the glyph),
        # so nothing jumps when it starts ticking; the viewer simply meets a timer on
        # frame 1 rather than a label. Later rounds keep "VS" — they already have the
        # viewer, and the versus framing is the format's identity.
        def _state(**kw):
            """A frame's worth of card.render arguments, minus the motion offsets.

            Nothing is rendered here any more. Each panel now carries its own
            motion, so a state can no longer be a single still held for N frames —
            every frame is a fresh render with its own offsets (see the frame walk
            below). This just records WHAT to draw; when and where is decided later.
            """
            return dict(item=item, round_label=round_label, **kw)

        st_vote = _state(countdown=(3 if n == 0 else None), slide=True)
        st_3 = _state(countdown=3)
        st_2 = _state(countdown=2)
        st_1 = _state(countdown=1)
        # Opinion reveals COUNT UP: a few frames of the bar growing and the number
        # climbing, so the result lands as an event instead of just being there.
        # Factual reveals are a single frame — CORRECT!/NOPE has nothing to count.
        anim = []
        if item.correct is None and config.REVEAL_FRAMES > 1:
            for k in range(1, config.REVEAL_FRAMES):
                anim.append(_state(reveal=True, grow=k / config.REVEAL_FRAMES))
        st_reveal = _state(reveal=True)

        if config.ENABLE_VOICE:
            q_text, r_text = _spoken(item, n, len(items))
            q_mp3 = voice.say(q_text, os.path.join(work, f"{n}_q.mp3"))
            r_mp3 = voice.say(r_text, os.path.join(work, f"{n}_r.mp3"))
            intro = round(max(_dur(q_mp3), 1.5) + 0.4, 2)
            reveal_len = round(max(_dur(r_mp3), 2.0) + 0.9, 2)
            audio_pieces += [q_mp3, silence, r_mp3]
        elif config.ENABLE_QUESTION_VOICE:
            # Read the question, then shut up: the card is held exactly as long as
            # the line takes (plus a beat), so the timer starts the moment the
            # choice has landed.
            q_text, _ = _spoken(item, n, len(items))
            try:
                q_mp3 = voice.say(q_text, os.path.join(work, f"{n}_q.mp3"))
                qlen = _dur(q_mp3)
                intro = round(max(qlen + config.POST_VOICE_GAP, config.VOICE_READ_MIN), 2)
                voice_cues.append((q_mp3, clock))
                ducks.append((clock, clock + qlen + 0.3))
            except Exception as e:  # noqa: BLE001 - never fail a render over TTS
                print("  (question voice skipped:", e, ")")
                intro = _read_seconds(item)
            reveal_len = config.REVEAL_SECONDS
        else:
            intro = _read_seconds(item)
            reveal_len = config.REVEAL_SECONDS

        # The count-up eats from the reveal's own time, so pacing is unchanged.
        step = config.REVEAL_ANIM / max(len(anim), 1) if anim else 0.0
        hold = round(reveal_len - step * len(anim), 2)
        # Faster countdown (config.COUNTDOWN_STEP per tick): the 3-2-1 is dead air
        # for retention if it drags. The tick/ding SFX and the running clock use the
        # same step so audio stays locked to the visual countdown.
        cd = config.COUNTDOWN_STEP


        # 3rd element = "this is a beat" — the panels squash toward each other and
        # spring back. The count-up frames are the one place it must be False: they
        # are REVEAL_FRAMES states inside half a second, and re-triggering on each
        # is what read as a shake. They ride the tail of the "1" beat instead.
        seg_specs += [(st_vote, intro, True),
                      (st_3, cd, True), (st_2, cd, True), (st_1, cd, True)]
        seg_specs += [(p, step, False) for p in anim]
        # The reveal does NOT bounce. It used to, and it landed wrong: the count-up
        # frames deliberately don't retrigger, so the whole run-up is smooth, and
        # then a bounce fired on the final frame — a jolt arriving out of nowhere
        # exactly where the eye is fixed on the number. The reveal already has its
        # payoff in the ding and the bar filling; it doesn't need a shove too.
        seg_specs.append((st_reveal, max(hold, 0.6), False))
        if has_sfx:
            cues += [(tick, clock + intro), (tick, clock + intro + cd),
                     (tick, clock + intro + 2 * cd), (ding, clock + intro + 3 * cd)]
        clock += intro + 3 * cd + reveal_len

    # ---- end card: ask for the comment while they still care ------------------
    if config.ENABLE_OUTRO and items:
        last = items[-1]
        factual = last.correct is not None
        f_out = card.outro(last, os.path.join(work, "outro.png"))
        line = ("Comment how many you got right!" if factual
                else "Comment which ones you picked!")
        olen = 0.0
        if config.ENABLE_QUESTION_VOICE or config.ENABLE_VOICE:
            try:
                o_mp3 = voice.say(line, os.path.join(work, "outro.mp3"))
                olen = _dur(o_mp3)
                voice_cues.append((o_mp3, clock + 0.15))
                ducks.append((clock, clock + olen + 0.45))
            except Exception as e:  # noqa: BLE001
                print("  (outro voice skipped:", e, ")")
        outro_len = round(max(olen + config.OUTRO_TAIL, config.OUTRO_SECONDS), 2)
        seg_specs.append((f_out, outro_len, True))
        clock += outro_len

    total = round(clock, 2)

    def _frame_motion() -> str:
        """Slow drift and sway over the finished frame sequence.

        The BOUNCE used to live here and no longer does — it moved onto the panels,
        which is the whole point of rendering per frame: a filter over the finished
        frame can only move the card as one flat image, so anything applied here is
        something both boxes do identically. What is left is the gentle whole-frame
        float that carries the composition; the character comes from the panels.

        Runs on `on`, the absolute output frame index, so there is nothing to reset
        and no seam anywhere — the segment boundaries that used to need careful
        offsetting are gone entirely.

        The source is upscaled first because zoompan quantises its offsets to whole
        source pixels — drifting a 1080-wide still directly visibly judders.
        """
        fps = config.MOTION_FPS
        base, drift, dper = config.MOTION_BASE, config.DRIFT_AMOUNT, config.DRIFT_PERIOD
        sway, sper = config.SWAY_PIXELS, config.SWAY_PERIOD
        t = f"(on/{fps})"
        z = f"{base:.4f}+{drift:.4f}*sin(2*PI*{t}/{dper})"
        x = f"iw/2-(iw/zoom/2)+{sway:.1f}*sin(2*PI*{t}/{sper})"
        y = f"ih/2-(ih/zoom/2)+{sway:.1f}*cos(2*PI*{t}/{sper * 1.6:.2f})"
        return (f"scale={W * 2}:{H * 2},"
                f"zoompan=z='{z}':d=1:x='{x}':y='{y}'"
                f":s={W}x{H}:fps={fps},setsar=1")

    fps = config.MOTION_FPS
    since_beat = 0.0         # since the last beat — the panels' squash rides this
    abs_s = 0.0              # absolute video time — the bob and the drift never reset
    frame_i = 0
    for st, dur, beat in seg_specs:
        if beat:
            since_beat = 0.0
        n_frames = max(1, int(round(dur * fps)))
        for k in range(n_frames):
            t_in = k / fps
            dst = os.path.join(work, f"f{frame_i:05d}.png")
            if isinstance(st, str):
                # Teaser / outro are pre-rendered by a different card function and
                # have no panels to move — hold the still.
                if k == 0:
                    _link_or_copy(st, dst)
                else:
                    _link_or_copy(os.path.join(work, f"f{frame_i - 1:05d}.png"), dst)
            else:
                kw = {k2: v for k2, v in st.items() if k2 not in ("item", "slide")}
                # Entrance only exists on the vote state, and only at its start.
                slide = st.get("slide") and t_in < config.PANEL_ENTRANCE
                card.render(
                    st["item"], dst, **kw,
                    a_dx=-_slide_in(t_in) if slide else 0.0,
                    b_dx=_slide_in(t_in - config.PANEL_STAGGER) if slide else 0.0,
                    a_dy=_panel_dy(abs_s, since_beat, 0),
                    b_dy=_panel_dy(abs_s, since_beat, 1),
                )
            frame_i += 1
            since_beat += 1.0 / fps
            abs_s += 1.0 / fps

    # ---- audio: music bed + tick/ding cues (+ voice only if re-enabled) -------
    # One encode over the rendered frame sequence, instead of a clip per segment.
    # Every frame is already its own PNG (the panels move per frame), so there is
    # nothing left to hold or concatenate — and this drops hundreds of ffmpeg
    # invocations to one.
    cmd = [FF, "-y", "-framerate", str(config.MOTION_FPS),
           "-i", os.path.join(work, "f%05d.png")]
    parts, labels = [], []
    idx = 1

    music = os.path.join(sfx, "music.mp3")
    if config.ENABLE_MUSIC and os.path.exists(music):
        # -stream_loop repeats the ~18s loop to cover any length; -t below cuts it.
        cmd += ["-stream_loop", "-1", "-i", music]
        if ducks:
            # Drop the bed under every spoken question, then bring it back. Without
            # this the music and the (quiet) TTS sit at the same level and neither
            # wins — measured at 0.9dB apart, i.e. inaudible.
            windows = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in ducks)
            parts.append(
                f"[{idx}:a]volume='if(gt({windows},0),{config.MUSIC_DUCK},"
                f"{config.MUSIC_VOLUME})':eval=frame[m]")
        else:
            parts.append(f"[{idx}:a]volume={config.MUSIC_VOLUME}[m]")
        labels.append("[m]")
        idx += 1

    for vpath, at in voice_cues:
        # aresample: edge-tts is 24kHz mono and everything else is 44.1k — amix
        # wants them matched. Gain lifts the quiet TTS clear of the bed.
        cmd += ["-i", vpath]
        d = int(at * 1000)
        parts.append(f"[{idx}:a]aresample=44100,volume={config.INTRO_VOICE_GAIN},"
                     f"adelay={d}|{d}[v{idx}]")
        labels.append(f"[v{idx}]")
        idx += 1

    if config.ENABLE_VOICE and audio_pieces:
        a_list = os.path.join(work, "audio.txt")
        with open(a_list, "w") as f:
            for p in audio_pieces:
                f.write(f"file '{p.replace(os.sep, '/')}'\n")
        voice_track = os.path.join(work, "voice.mp3")
        subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", a_list,
                        "-c", "copy", voice_track], capture_output=True)
        cmd += ["-i", voice_track]
        parts.append(f"[{idx}:a]volume=1.0[v]")
        labels.append("[v]")
        idx += 1

    for path, at in cues:
        cmd += ["-i", path]
        d = int(at * 1000)
        parts.append(f"[{idx}:a]volume={config.SFX_VOLUME},adelay={d}|{d}[s{idx}]")
        labels.append(f"[s{idx}]")
        idx += 1

    vf = f"[0:v]{_frame_motion()}[v]"
    if labels:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0[mixed]")
        parts.append("[mixed]alimiter=limit=0.95[a]")   # stop the mix clipping
        # -vf and -filter_complex are mutually exclusive, so the video chain joins
        # the complex graph rather than sitting alongside it.
        cmd += ["-filter_complex", ";".join([vf] + parts), "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", vf, "-map", "[v]", "-an"]
    cmd += ["-t", str(total), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", out_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg failed:\n{res.stderr[-1800:]}")
    return out_path


if __name__ == "__main__":
    items = content.several("wyr", "2026-07-16", 3)   # 3 rounds in one video
    out = os.path.join(os.path.dirname(__file__), "output", "short.mp4")
    build(items, out)
    print("built", out, f"({os.path.getsize(out)//1024} KB) with {len(items)} rounds")
