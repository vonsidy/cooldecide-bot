"""Synthesizes the sound effects, so the project ships with its own royalty-free
SFX (no downloads). Run once to (re)generate assets/*.wav."""
from __future__ import annotations
import os
import wave
import numpy as np

SR = 44100
ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def _save(name: str, samples: np.ndarray) -> str:
    os.makedirs(ASSETS, exist_ok=True)
    samples = np.clip(samples, -1, 1)
    data = (samples * 32767).astype("<i2")
    path = os.path.join(ASSETS, name)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path


def _tone(freq: float, dur: float, decay: float = 20.0, harmonics=(1.0,)) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    wave_ = sum(amp * np.sin(2 * np.pi * freq * mult * t) for mult, amp in enumerate(harmonics, 1))
    return wave_ * np.exp(-decay * t)


def _chirp(f0: float, f1: float, dur: float, decay: float, curve: float = 1.0) -> np.ndarray:
    """A pitch-bending tone (f0 -> f1), for pops and whooshes."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    freq = f0 + (f1 - f0) * (t / dur) ** curve
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * np.exp(-decay * t)


def make_tick() -> str:
    # CoolDecide's own countdown tick: a round, warm 'boop' (not DecideDeck's sharp
    # click) — sine-based with a soft octave, quick decay. Bouncy, sticker-cartoon.
    s = _tone(1046.5, 0.10, decay=30, harmonics=(1.0, 0.35, 0.12))
    return _save("tick.wav", s * 0.55)


def make_go() -> str:
    # higher, brighter blip for the final "go"/reveal moment
    s = _tone(1320, 0.14, decay=26, harmonics=(1.0, 0.3))
    return _save("go.wav", s * 0.7)


def make_ding() -> str:
    # happy two-note chime on the reveal (C6 -> E6, bell-ish)
    a = _tone(1047, 0.28, decay=10, harmonics=(1.0, 0.5, 0.25))
    b = _tone(1319, 0.55, decay=8, harmonics=(1.0, 0.5, 0.25))
    out = np.zeros(int(SR * 0.62))
    out[: len(a)] += a
    off = int(SR * 0.12)
    out[off: off + len(b)] += b[: len(out) - off]
    return _save("ding.wav", out * 0.55)


def make_pop() -> str:
    # A rising 'bloop' — pitch bends UP, which reads as playful rather than the flat
    # blip DecideDeck uses. Fires when the result lands.
    s = _chirp(420, 900, 0.11, decay=26, curve=0.6)
    return _save("pop.wav", s * 0.5)


def make_whoosh() -> str:
    # Filtered-noise swish for the reveal transition, CoolDecide's own: soft noise
    # swelling then falling, no tonal component, so it never fights the fanfare.
    dur = 0.42
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    rng = np.random.default_rng(7)                 # fixed seed -> reproducible asset
    noise = rng.normal(0, 1, n)
    # crude one-pole lowpass that opens then closes, giving the swish its motion
    swell = np.sin(np.pi * t / dur) ** 1.6
    out = np.zeros(n)
    prev = 0.0
    for i in range(n):
        a = 0.02 + 0.35 * swell[i]                 # cutoff follows the swell
        prev = prev + a * (noise[i] - prev)
        out[i] = prev
    out *= swell
    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out = out / peak * 0.5
    return _save("whoosh.wav", out)


def make_winner() -> str:
    """The crown sting — a triumphant ascending fanfare into a shimmering major
    chord. Deliberately its OWN sound, not DecideDeck's two-note ding: a rising
    arpeggio (C-E-G-C) that lands on a held C-major chord with sparkle on top.

    NORMALIZED, not hard-clipped: the summed arpeggio + chord + sparkle used to
    exceed +/-1 at the peak and get clipped, which reads as harsh 'static' when
    played loud. Softer harmonics + a peak-normalize to 0.82 keep it clean at any
    volume."""
    total = int(SR * 1.2)
    out = np.zeros(total)
    # ascending arpeggio, bell-ish, quick (fewer/softer harmonics -> less harsh)
    arp = (523.25, 659.25, 783.99, 1046.50)          # C5 E5 G5 C6
    step = int(SR * 0.082)
    for i, f in enumerate(arp):
        note = _tone(f, 0.5, decay=9, harmonics=(1.0, 0.42, 0.2))
        off = i * step
        out[off: off + len(note)] += note[: total - off] * 0.55
    # final sustained major chord, rings out
    chord_off = 3 * step
    for f in (1046.50, 1318.51, 1567.98):            # C6 E6 G6
        c = _tone(f, 0.85, decay=4.0, harmonics=(1.0, 0.42, 0.18))
        out[chord_off: chord_off + len(c)] += c[: total - chord_off] * 0.3
    # sparkle: two high bells over the landing chord
    for i, f in enumerate((2093.0, 2637.0)):         # C7, E7
        s = _tone(f, 0.45, decay=11, harmonics=(1.0, 0.32))
        off = chord_off + int(SR * (0.04 + i * 0.06))
        out[off: off + len(s)] += s[: total - off] * 0.09
    # de-click the attack and fade the tail so it never clicks at either end
    env = np.ones(total)
    a = int(SR * 0.004); env[:a] = np.linspace(0, 1, a)
    fo = int(SR * 0.14); env[-fo:] = np.linspace(1, 0, fo)
    out *= env
    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out = out / peak * 0.82                       # normalize -> guaranteed no clip
    return _save("winner.wav", out)


if __name__ == "__main__":
    for f in (make_tick(), make_go(), make_ding(), make_pop(),
              make_whoosh(), make_winner()):
        print("wrote", f)
