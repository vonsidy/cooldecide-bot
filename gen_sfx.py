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


def make_tick() -> str:
    # bright, short countdown blip
    s = _tone(880, 0.12, decay=32, harmonics=(1.0, 0.25))
    return _save("tick.wav", s * 0.6)


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
    s = _tone(660, 0.07, decay=45, harmonics=(1.0,))
    return _save("pop.wav", s * 0.5)


if __name__ == "__main__":
    for f in (make_tick(), make_go(), make_ding(), make_pop()):
        print("wrote", f)
