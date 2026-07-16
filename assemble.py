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
    return q, r


# One spoken line at the very start, naming the game. Everything after it is
# silent — the point is to orient a scroller in the first second, not to narrate.
_INTRO_LINE = {
    "wyr": "Would you rather?",
    "this_or_that": "This, or that?",
    "rank": "Who would win?",
    "higher_lower": "Which one is bigger?",
    "trivia": "Quiz time!",
}


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

    for n, item in enumerate(items):
        f_vote = card.render(item, os.path.join(work, f"{n}_vote.png"), countdown=None)
        f3 = card.render(item, os.path.join(work, f"{n}_c3.png"), countdown=3)
        f2 = card.render(item, os.path.join(work, f"{n}_c2.png"), countdown=2)
        f1 = card.render(item, os.path.join(work, f"{n}_c1.png"), countdown=1)
        # Opinion reveals COUNT UP: a few frames of the bar growing and the number
        # climbing, so the result lands as an event instead of just being there.
        # Factual reveals are a single frame — CORRECT!/NOPE has nothing to count.
        anim = []
        if item.correct is None and config.REVEAL_FRAMES > 1:
            for k in range(1, config.REVEAL_FRAMES):
                anim.append(card.render(item, os.path.join(work, f"{n}_rev{k}.png"),
                                        reveal=True, grow=k / config.REVEAL_FRAMES))
        f_reveal = card.render(item, os.path.join(work, f"{n}_reveal.png"), reveal=True)

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
                intro = round(max(qlen + 0.5, config.READ_MIN), 2)
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
        seg_specs += [(f_vote, intro), (f3, 1.0), (f2, 1.0), (f1, 1.0)]
        seg_specs += [(p, step) for p in anim]
        seg_specs.append((f_reveal, max(hold, 0.6)))
        if has_sfx:
            cues += [(tick, clock + intro), (tick, clock + intro + 1), (tick, clock + intro + 2),
                     (ding, clock + intro + 3)]
        clock += intro + 3.0 + reveal_len

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
        seg_specs.append((f_out, outro_len))
        clock += outro_len

    total = round(clock, 2)

    # Each frame becomes its own short clip, then the CLIPS are concatenated. The
    # concat *demuxer* handles videos correctly (it silently drops an image's
    # duration, and -loop image inputs into a concat *filter* only emitted the
    # first frame — both dead ends, hence per-segment clips).
    seg_list = os.path.join(work, "segs.txt")
    with open(seg_list, "w") as lst:
        for i, (path, d) in enumerate(seg_specs):
            seg = os.path.join(work, f"seg{i}.mp4")
            r = subprocess.run([FF, "-y", "-loop", "1", "-i", path, "-t", f"{d}", "-r", "30",
                                "-vf", f"scale={W}:{H},setsar=1", "-pix_fmt", "yuv420p",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", seg],
                               capture_output=True, text=True)
            if not os.path.exists(seg):
                raise RuntimeError(f"segment {i} failed:\n{r.stderr[-800:]}")
            lst.write(f"file '{seg.replace(os.sep, '/')}'\n")

    # ---- audio: music bed + tick/ding cues (+ voice only if re-enabled) -------
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", seg_list]
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

    if labels:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0[mixed]")
        parts.append("[mixed]alimiter=limit=0.95[a]")   # stop the mix clipping
        cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-an"]
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
