"""Builds the full vertical Short: vote -> 3-2-1 countdown -> reveal, with narration.

Timeline
  intro   : options shown while the question is read
  3, 2, 1 : one second each, ticking badge
  reveal  : the percentages fill in while the result is read
"""
from __future__ import annotations
import glob
import os
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
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 2.0


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


def build(item: content.Item, out_path: str, background: str | None = None) -> str:
    work = tempfile.mkdtemp(prefix="short_")
    # frames
    f_vote = card.render(item, os.path.join(work, "vote.png"), countdown=None)
    f3 = card.render(item, os.path.join(work, "c3.png"), countdown=3)
    f2 = card.render(item, os.path.join(work, "c2.png"), countdown=2)
    f1 = card.render(item, os.path.join(work, "c1.png"), countdown=1)
    f_reveal = card.render(item, os.path.join(work, "reveal.png"), reveal=True)

    # narration
    q_text, r_text = _spoken(item)
    q_mp3 = voice.say(q_text, os.path.join(work, "q.mp3"))
    r_mp3 = voice.say(r_text, os.path.join(work, "r.mp3"))
    q_len = max(_dur(q_mp3), 1.5)
    r_len = max(_dur(r_mp3), 2.0)

    intro = round(q_len + 0.4, 2)     # question over the vote screen
    reveal_len = round(r_len + 0.8, 2)

    # image track via concat demuxer (durations in seconds)
    concat = os.path.join(work, "frames.txt")
    with open(concat, "w") as f:
        for path, d in [(f_vote, intro), (f3, 1.0), (f2, 1.0), (f1, 1.0), (f_reveal, reveal_len)]:
            f.write(f"file '{path.replace(os.sep, '/')}'\nduration {d}\n")
        f.write(f"file '{f_reveal.replace(os.sep, '/')}'\n")   # concat needs the last frame repeated

    # audio: question, then 3s of silence for the countdown, then the result
    silence = os.path.join(work, "sil.mp3")
    subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "3.0", silence], capture_output=True)
    a_list = os.path.join(work, "audio.txt")
    with open(a_list, "w") as f:
        for p in (q_mp3, silence, r_mp3):
            f.write(f"file '{p.replace(os.sep, '/')}'\n")
    voice_track = os.path.join(work, "voice.mp3")
    subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", a_list, "-c", "copy", voice_track],
                   capture_output=True)

    total = round(intro + 3.0 + reveal_len, 2)
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", concat, "-i", voice_track]
    filt = f"[0:v]scale={W}:{H},fps=30,format=yuv420p[v]"
    cmd += ["-filter_complex", filt, "-map", "[v]", "-map", "1:a",
            "-t", str(total), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg failed:\n{res.stderr[-1500:]}")
    return out_path


if __name__ == "__main__":
    it = content.daily_item("wyr", "2026-07-16")
    out = os.path.join(os.path.dirname(__file__), "output", "short.mp4")
    build(it, out)
    print("built", out, f"({os.path.getsize(out)//1024} KB)")
