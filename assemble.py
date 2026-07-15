"""Builds the full vertical Short: vote -> 3-2-1 countdown -> reveal, with narration.

Timeline
  intro   : options shown while the question is read
  3, 2, 1 : one second each, ticking badge
  reveal  : the percentages fill in while the result is read
"""
from __future__ import annotations
import glob
import os
import re
import subprocess
import tempfile

import card
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


def _spoken(item: content.Item) -> tuple[str, str]:
    """(question read during vote, result read on reveal)."""
    fmt = item.fmt
    if fmt == "trivia":
        q = f"{item.prompt} Is it {item.a}, or {item.b}? You have three seconds!"
        correct = item.a if item.correct == 0 else item.b
        r = f"The answer is {correct}! Did you get it right?"
    elif fmt == "higher_lower":
        q = f"Which is bigger? {item.a}, or {item.b}? Three seconds!"
        bigger = item.a if item.correct == 0 else item.b
        r = f"{bigger} is bigger! {max(item.a_pct, item.b_pct)} percent got it right."
    else:
        q = f"{item.prompt} {item.a}, or {item.b}? Comment your pick!"
        winner, wp = (item.a, item.a_pct) if item.a_pct >= item.b_pct else (item.b, item.b_pct)
        r = f"{wp} percent said {winner}!"
    return q, r


def build(items, out_path: str, background: str | None = None) -> str:
    if isinstance(items, content.Item):
        items = [items]
    work = tempfile.mkdtemp(prefix="short_")

    silence = os.path.join(work, "sil.mp3")
    subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "3.0", silence], capture_output=True)

    seg_specs = []          # (image_path, duration) in play order
    audio_pieces = []       # mp3s concatenated into the voice track
    cues = []               # (sfx_path, global_time)
    sfx = os.path.join(os.path.dirname(__file__), "assets")
    tick, ding = os.path.join(sfx, "tick.wav"), os.path.join(sfx, "ding.wav")
    has_sfx = os.path.exists(tick) and os.path.exists(ding)
    clock = 0.0             # running start time of the current round

    for n, item in enumerate(items):
        f_vote = card.render(item, os.path.join(work, f"{n}_vote.png"), countdown=None)
        f3 = card.render(item, os.path.join(work, f"{n}_c3.png"), countdown=3)
        f2 = card.render(item, os.path.join(work, f"{n}_c2.png"), countdown=2)
        f1 = card.render(item, os.path.join(work, f"{n}_c1.png"), countdown=1)
        f_reveal = card.render(item, os.path.join(work, f"{n}_reveal.png"), reveal=True)

        q_text, r_text = _spoken(item)
        q_mp3 = voice.say(q_text, os.path.join(work, f"{n}_q.mp3"))
        r_mp3 = voice.say(r_text, os.path.join(work, f"{n}_r.mp3"))
        intro = round(max(_dur(q_mp3), 1.5) + 0.4, 2)
        reveal_len = round(max(_dur(r_mp3), 2.0) + 0.9, 2)

        seg_specs += [(f_vote, intro), (f3, 1.0), (f2, 1.0), (f1, 1.0), (f_reveal, reveal_len)]
        audio_pieces += [q_mp3, silence, r_mp3]
        if has_sfx:
            cues += [(tick, clock + intro), (tick, clock + intro + 1), (tick, clock + intro + 2),
                     (ding, clock + intro + 3)]
        clock += intro + 3.0 + reveal_len

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

    a_list = os.path.join(work, "audio.txt")
    with open(a_list, "w") as f:
        for p in audio_pieces:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")
    voice_track = os.path.join(work, "voice.mp3")
    subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", a_list, "-c", "copy", voice_track],
                   capture_output=True)

    # audio track: voice + SFX cues mixed
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", seg_list, "-i", voice_track]
    for path, _ in cues:
        cmd += ["-i", path]
    if cues:
        parts, mix = [], ["[1:a]"]
        for j, (_, at) in enumerate(cues):
            idx = 2 + j
            d = int(at * 1000)
            parts.append(f"[{idx}:a]volume=0.85,adelay={d}|{d}[s{idx}]")
            mix.append(f"[s{idx}]")
        parts.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0[a]")
        cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
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
