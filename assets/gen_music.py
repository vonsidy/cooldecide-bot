"""Synthesizes an ORIGINAL, royalty-free background loop for the kids Shorts.

Original on purpose: real music (even a "free" YouTube rip) risks a copyright
claim, which on a monetized channel costs the revenue for that video.

Kept deliberately soft. The dark-ambient synth on the other channel came out
"ear piercing", so the brightness is capped here on purpose:
  * C major PENTATONIC — there is no dissonant interval available in the scale,
    so a random walk through it always sounds pleasant.
  * marimba/music-box voice: a sine plus a quiet 2nd harmonic, nothing higher.
  * every note gets a short attack ramp (no clicks) and an exponential decay.
  * a gentle one-pole low-pass shaves any remaining fizz.

Run:  python assets/gen_music.py     ->  assets/music.mp3  (seamless ~18s loop)
"""
import glob
import os
import subprocess
import wave

import numpy as np

SR = 44100
BPM = 104
BEAT = 60.0 / BPM
BARS, BEATS_PER_BAR = 8, 4
HERE = os.path.dirname(os.path.abspath(__file__))

# C major pentatonic — melody an octave up, bass down low.
MEL = {"C": 523.25, "D": 587.33, "E": 659.25, "G": 783.99, "A": 880.00}
BASS = {"C": 130.81, "A": 110.00, "F": 174.61, "G": 196.00}

# A simple, bouncy 8th-note pattern per bar, and the bass root under it.
PATTERN = [
    ("C", ["C", "E", "G", "E", "C", "E", "G", "A"]),
    ("A", ["A", "C", "E", "C", "A", "C", "E", "G"]),
    ("F", ["C", "D", "E", "G", "E", "D", "C", "D"]),
    ("G", ["D", "G", "A", "G", "E", "D", "C", "D"]),
]


def _pluck(freq: float, dur: float, amp: float, decay: float) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    wave_ = np.sin(2 * np.pi * freq * t) + 0.22 * np.sin(2 * np.pi * freq * 2 * t)
    env = np.exp(-t * decay)
    attack = np.minimum(1.0, t / 0.005)      # 5ms ramp so it never clicks
    return amp * wave_ * env * attack


def _lowpass(x: np.ndarray, cutoff: float = 3200.0) -> np.ndarray:
    """Gentle one-pole low-pass (vectorised via cumulative recursion is awkward,
    so use a short smoothing kernel — plenty for shaving fizz off sines)."""
    n = max(2, int(SR / cutoff))
    k = np.hanning(n * 2 + 1)
    k /= k.sum()
    return np.convolve(x, k, mode="same")


def build() -> np.ndarray:
    total = int(SR * BARS * BEATS_PER_BAR * BEAT) + SR
    buf = np.zeros(total + SR, dtype=np.float64)

    for bar in range(BARS):
        root, notes = PATTERN[bar % len(PATTERN)]
        bar_t = bar * BEATS_PER_BAR * BEAT

        # bass note on the downbeat, long and quiet
        b = _pluck(BASS[root], BEAT * 3.2, 0.32, 2.0)
        s = int(bar_t * SR)
        buf[s:s + len(b)] += b

        # 8th-note melody
        for i, nm in enumerate(notes):
            at = bar_t + i * (BEAT / 2)
            amp = 0.20 if i % 2 else 0.28          # accent the on-beats
            p = _pluck(MEL[nm], BEAT * 1.1, amp, 5.5)
            s = int(at * SR)
            buf[s:s + len(p)] += p

    loop_len = int(SR * BARS * BEATS_PER_BAR * BEAT)
    # Fold the tail (ringing past the loop point) back over the start, so looping
    # the file is seamless instead of chopping the last notes dead.
    tail = buf[loop_len:loop_len + SR].copy()
    out = buf[:loop_len]
    out[:len(tail)] += tail

    out = _lowpass(out)
    peak = np.max(np.abs(out)) or 1.0
    return (out / peak) * 0.5          # leave headroom; assemble sets final level


def main() -> None:
    audio = build()
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    wav_path = os.path.join(HERE, "music.wav")
    with wave.open(wav_path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    hits = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin\ffmpeg.exe"))
    ff = hits[0] if hits else "ffmpeg"
    mp3 = os.path.join(HERE, "music.mp3")
    subprocess.run([ff, "-y", "-i", wav_path, "-b:a", "192k", mp3], capture_output=True)
    os.remove(wav_path)
    print(f"wrote {mp3}  ({len(audio)/SR:.1f}s seamless loop)")


if __name__ == "__main__":
    main()
