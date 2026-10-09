"""Minimal Silero VAD v6.2 ONNX loop (512-sample hop, 64-sample context), for the q11 gate numbers only."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort


class Silero:
    def __init__(self, path: Path):
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        self.s = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])

    def frame_probs(self, a: np.ndarray) -> np.ndarray:
        """Speech probability per 32 ms frame."""
        state, ctx, out = np.zeros((2, 1, 128), np.float32), np.zeros(64, np.float32), []
        a = np.pad(a, (0, -len(a) % 512))
        for i in range(0, len(a), 512):
            x = np.concatenate([ctx, a[i : i + 512]])[None, :]
            p, state = self.s.run(None, {"input": x, "state": state, "sr": np.array(16000, np.int64)})
            ctx = x[0, -64:]
            out.append(float(p[0, 0]))
        return np.array(out)
