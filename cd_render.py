"""CoolDecide browser renderer — drop-in for assemble.build(items, out_path).

DecideDeck's animation pipeline, reskinned to CoolDecide's template. Per round:
bot Item -> art via card.photo_for -> animated HTML (cd_anim.js) -> frames grabbed
in headless Chromium (cd_capture.js / Playwright) -> narration (cd_tts.py) ->
ffmpeg mux (music bed + tick/ding/whoosh/pop SFX, ducked under the voice).
Output: 1080x1920 H.264/AAC mp4. Everything downstream (meta, scheduler, upload,
dashboard) is unchanged — this only replaces the PIL renderer in card/assemble.
"""
from __future__ import annotations
import os, json, wave, tempfile, shutil, subprocess, datetime

import config
import card

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
FPS = 30
STEP = 0.55                 # seconds per 3-2-1 number (must match cd_anim.js STEP)
CD = 3 * STEP               # countdown length (1.65s)
REVEAL_HOLD = 2.05          # hold after the reveal lands
MUSIC = os.path.join(ASSETS, "music_A.mp3")

# header + sub per format, in CoolDecide's voice (all wyr in production).
HEAD = {
    "wyr": ("WOULD YOU RATHER", "PICK YOUR SIDE"),
    "this_or_that": ("THIS OR THAT", "PICK ONE"),
    "rank": ("WHO WOULD WIN?", "PICK THE WINNER"),
    "trivia": ("GUESS THE ANSWER", "PICK ONE"),
    "higher_lower": ("WHICH IS BIGGER?", "PICK ONE"),
}
NODE_PATH = os.getenv("CD_NODE_PATH", "/home/claude/.npm-global/lib/node_modules")


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _fit(p):
    # Square cartoon art / photos fill the panel (cover); wide brand logos show
    # whole (contain) so they aren't cropped to a sliver.
    p = p.replace("\\", "/")
    return "cover" if ("/assets/art/" in p or "/images/auto/" in p) else "contain"


def _wav_dur(p):
    with wave.open(p) as w:
        return w.getnframes() / w.getframerate()


def _narration(it, idx=0, total=1):
    # Reuse the bot's own phrasing so the whole question is read (item.prompt is
    # only the "Would you rather" prefix) AND the "on read"->"on red" respelling and
    # every other _SAY_AS fix apply here too.
    import assemble
    try:
        q, _ = assemble._spoken(it, idx, total)
        q = (q or "").strip()
        if q:
            return q
    except Exception:
        pass
    return f"Would you rather {it.a}, or {it.b}?"


def build(items, out_path: str, background: str | None = None) -> str:
    import content
    if isinstance(items, content.Item):
        items = [items]
    work = tempfile.mkdtemp(prefix="cd_")
    frames = os.path.join(work, "frames")
    os.makedirs(frames, exist_ok=True)
    voice = getattr(config, "EDGE_VOICE", "en-US-AvaMultilingualNeural")
    rate = getattr(config, "EDGE_RATE", "+25%")
    # One palette per video (CoolDecide's identity — a Short reads as one thing),
    # chosen the same way the PIL renderer does.
    pal = card.palette_for(datetime.date.today().isoformat(), items[0].fmt, 0)
    env = dict(os.environ)
    if os.path.isdir(NODE_PATH):
        env["NODE_PATH"] = NODE_PATH

    rounds, durs, vls, voices = [], [], [], []
    for i, it in enumerate(items):
        a_img = card.photo_for(it.a, getattr(it, "a_art", "") or None)
        b_img = card.photo_for(it.b, getattr(it, "b_art", "") or None)
        if not (a_img and b_img):
            raise RuntimeError(f"round {i}: missing art for "
                               f"{it.a!r}({bool(a_img)}) / {it.b!r}({bool(b_img)})")
        mp3 = os.path.join(work, f"v{i}.mp3")
        wav = os.path.join(work, f"v{i}.wav")
        subprocess.run(["python3", os.path.join(HERE, "cd_tts.py"),
                        mp3, voice, rate, _narration(it, i, len(items))], check=True, env=env)
        subprocess.run(["ffmpeg", "-y", "-i", mp3, "-ac", "1", "-ar", "44100", wav],
                       capture_output=True)
        d = _wav_dur(wav); durs.append(d); voices.append(wav)
        vl = round(_clamp(d + 0.55, 1.6, 4.6), 2); vls.append(vl)
        head, sub = HEAD.get(it.fmt, HEAD["wyr"])
        rounds.append({
            "pal": pal, "head": head, "sub": sub,
            "la": it.a, "lb": it.b, "imgA": a_img, "imgB": b_img,
            "fitA": _fit(a_img), "fitB": _fit(b_img),
            "pa": int(it.a_pct), "pb": int(it.b_pct),
            "win": "A" if it.a_pct >= it.b_pct else "B", "vl": vl,
        })

    rj = os.path.join(work, "rounds.json")
    with open(rj, "w") as f:
        json.dump(rounds, f)
    subprocess.run(["node", os.path.join(HERE, "cd_anim.js"), rj, work],
                   check=True, env=env)

    offset = 0
    round_start = []
    for i, vl in enumerate(vls):
        secs = round(vl + CD + REVEAL_HOLD, 2)
        round_start.append(offset / FPS)
        subprocess.run(["node", os.path.join(HERE, "cd_capture.js"),
                        os.path.join(work, f"round_{i}.html"), frames,
                        str(FPS), str(secs), "1", str(offset)], check=True, env=env)
        offset += round(secs * FPS)
    total = offset / FPS

    ticks, dings, whooshes, pops, vcues, ducks = [], [], [], [], [], []
    for i, vl in enumerate(vls):
        rs = round_start[i]
        for k in range(3):
            ticks.append(round(rs + vl + k * STEP, 3))
        dings.append(round(rs + vl + CD, 3))
        whooshes.append(round(rs + vl + CD, 3))
        pops.append(round(rs + vl + CD + 0.55, 3))
        vs = round(rs + 0.15, 3)
        vcues.append((voices[i], vs))
        ducks.append((rs, round(vs + durs[i] + 0.2, 3)))

    _mux(frames, vcues, ticks, dings, whooshes, pops, ducks, total, out_path)
    shutil.rmtree(work, ignore_errors=True)
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 10000):
        raise RuntimeError("cd_render produced no output")
    return out_path


def _mux(frames, vcues, ticks, dings, whooshes, pops, ducks, total, out_path):
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.png"),
           "-stream_loop", "-1", "-i", MUSIC,
           "-i", os.path.join(ASSETS, "tick.wav"), "-i", os.path.join(ASSETS, "ding.wav"),
           "-i", os.path.join(ASSETS, "whoosh.wav"), "-i", os.path.join(ASSETS, "pop.wav")]
    v0 = 6
    for wav, _ in vcues:
        cmd += ["-i", wav]

    fc, labels = [], []

    def emit(src, cues, vol, tag):
        n = len(cues)
        fc.append(f"[{src}:a]asplit={n}" + "".join(f"[{tag}s{i}]" for i in range(n)))
        for i, c in enumerate(cues):
            ms = int(c * 1000)
            fc.append(f"[{tag}s{i}]adelay={ms}|{ms},volume={vol}[{tag}{i}]")
            labels.append(f"{tag}{i}")

    emit(2, ticks, 0.9, "t")
    emit(3, dings, 0.9, "d")
    emit(4, whooshes, 0.5, "w")
    emit(5, pops, 0.5, "p")
    for i, (wav, vs) in enumerate(vcues):
        ms = int(vs * 1000)
        fc.append(f"[{v0+i}:a]adelay={ms}|{ms},volume=1.5[v{i}]")
        labels.append(f"v{i}")

    duck = "+".join(f"between(t,{s},{e})" for s, e in ducks) or "0"
    fc.append(f"[1:a]volume='if(gt({duck},0),0.16,0.5)':eval=frame[mus]")
    mix = "[mus]" + "".join(f"[{l}]" for l in labels)
    fc.append(f"{mix}amix=inputs={len(labels)+1}:normalize=0[mx]")
    fc.append(f"[mx]afade=t=out:st={total-0.4:.2f}:d=0.4[aout]")

    cmd += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]",
            "-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg mux failed:\n" + r.stderr[-1500:])


if __name__ == "__main__":
    import content
    date = datetime.date.today().isoformat()
    items = content.several("wyr", date, 2)
    if getattr(config, "ART_REQUIRED", True):
        items = content.ensure_art(items, "wyr")
    for i, it in enumerate(items, 1):
        print(f"  round {i}: {it.a} ({it.a_pct}%) vs {it.b} ({it.b_pct}%)")
    out = os.path.join(HERE, "output", "cd_sample.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build(items, out)
    print("built", out, os.path.getsize(out) // 1024, "KB")
