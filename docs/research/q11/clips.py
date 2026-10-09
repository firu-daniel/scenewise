"""Test inputs for the q11 scripts: the `say` clips (make_clips.sh) plus synthetic non-speech and noisy speech."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from whisper_lid import SR, read_wav


def noise(seed: int, sigma: float = 0.05, seconds: float = 10.0) -> np.ndarray:
    """Gaussian white noise; seed 0 is the clip q11 round 0 and q2 used (np.random.default_rng(seed))."""
    return (sigma * np.random.default_rng(seed).standard_normal(int(SR * seconds))).astype(np.float32)


def music(seconds: float = 10.0) -> np.ndarray:
    """Synthetic music bed: I-V-vi-IV triads, 4 harmonics each, 1 chord/s, plus a 2 Hz kick-like pulse."""
    t = np.arange(int(SR * seconds)) / SR
    chords = [(261.63, 329.63, 392.0), (196.0, 246.94, 293.66), (220.0, 261.63, 329.63), (174.61, 220.0, 261.63)]
    y = np.zeros_like(t)
    for k in range(int(seconds)):
        seg = (t >= k) & (t < k + 1)
        for f in chords[k % 4]:
            for h in range(1, 5):
                y[seg] += np.sin(2 * np.pi * f * h * t[seg]) / h
    y += 0.8 * np.sin(2 * np.pi * 55 * t) * np.exp(-((t * 2) % 1) * 12)
    return (0.1 * y / np.abs(y).max()).astype(np.float32)


def mix(speech: np.ndarray, bed: np.ndarray, snr_db: float) -> np.ndarray:
    bed = np.resize(bed, len(speech))
    gain = np.sqrt((speech**2).mean() / (bed**2).mean() / 10 ** (snr_db / 10))
    return (speech + gain * bed).astype(np.float32)


def all_clips(audio_dir: Path) -> dict[str, np.ndarray]:
    sp = {n: read_wav(audio_dir / f"{n}.wav") for n in ("en", "de", "fr")}
    c = dict(sp)
    c["silence"] = np.zeros(SR * 10, np.float32)
    for s in range(3):
        c[f"noise{s}"] = noise(s)
    c["music"] = music()
    for n in ("en", "de"):
        c[f"{n}+noise 10dB"] = mix(sp[n], noise(7), 10)
        c[f"{n}+noise 0dB"] = mix(sp[n], noise(7), 0)
        c[f"{n}+music 10dB"] = mix(sp[n], music(), 10)
    return c
