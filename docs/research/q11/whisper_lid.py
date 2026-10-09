"""q11 prototype: Whisper-tiny language ID on plain onnxruntime + numpy (no PyAV, no CTranslate2).

The adapter proper is `log_mel` + `OrtWhisperLid`. Weights: onnx-community/whisper-tiny @ ff41770 (see
fetch_models.sh). Usage as a script: python -I whisper_lid.py MODEL_DIR WAV... (prints argmax, p, p(en)).
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort

SR, N_FFT, HOP, N_SAMPLES, N_FRAMES = 16_000, 400, 160, 480_000, 3000
SOT = "<|startoftranscript|>"


def _mel_filters(n_mels: int = 80) -> np.ndarray:
    """librosa.filters.mel(sr=16000, n_fft=400, n_mels=80, htk=False, norm="slaney"), as in Whisper."""
    def hz_to_mel(f):
        f = np.asanyarray(f, dtype=np.float64)
        return np.where(f >= 1000.0, 15.0 + np.log(np.maximum(f, 1e-10) / 1000.0) / (np.log(6.4) / 27.0), f / (200.0 / 3))

    def mel_to_hz(m):
        m = np.asanyarray(m, dtype=np.float64)
        return np.where(m >= 15.0, 1000.0 * np.exp((np.log(6.4) / 27.0) * (m - 15.0)), m * (200.0 / 3))

    fft_f = np.linspace(0, SR / 2, 1 + N_FFT // 2)
    mel_f = mel_to_hz(np.linspace(hz_to_mel(0.0), hz_to_mel(SR / 2), n_mels + 2))
    fdiff = np.diff(mel_f)
    ramps = mel_f[:, None] - fft_f[None, :]
    w = np.maximum(0, np.minimum(-ramps[:-2] / fdiff[:-1, None], ramps[2:] / fdiff[1:, None]))
    w *= (2.0 / (mel_f[2 : n_mels + 2] - mel_f[:n_mels]))[:, None]
    return w.astype(np.float32)


MEL = _mel_filters()


def log_mel(audio: np.ndarray, pad: str = "fw") -> np.ndarray:
    """Whisper log-mel of one window -> (80, 3000) float32.

    pad="fw" (default, faster-whisper 1.2.1 semantics): mel of the unpadded audio + 160 zero samples, then the
    *features* are zero-padded to 3000 frames (pad_or_trim). pad="openai": audio zero-padded to 30 s before the mel
    (openai-whisper / onnx-asr semantics); kept only for the comparison in q11 §3.
    """
    a = audio[:N_SAMPLES].astype(np.float32)
    a = np.pad(a, (0, 160)) if pad == "fw" else np.pad(a, (0, N_SAMPLES - len(a)))
    a = np.pad(a, (N_FFT // 2, N_FFT // 2), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(a, N_FFT)[::HOP][:-1]
    spec = np.abs(np.fft.rfft(frames * np.hanning(N_FFT + 1)[:-1], axis=-1)) ** 2
    lm = np.log10(np.maximum(MEL @ spec.T, 1e-10))
    f = ((np.maximum(lm, lm.max() - 8.0) + 4.0) / 4.0).astype(np.float32)[:, :N_FRAMES]
    return np.pad(f, ((0, 0), (0, N_FRAMES - f.shape[1])))


ENCODERS = {"int8": "encoder_model_int8.onnx", "fp32": "encoder_model.onnx", "fp16": "encoder_model_fp16.onnx"}
DECODERS = {"int8": "decoder_model_int8.onnx", "fp32": "decoder_model.onnx"}


class OrtWhisperLid:
    """Encoder + one decoder step from <|startoftranscript|>; softmax over the language tokens only."""

    def __init__(self, model_dir: Path, encoder: str = "fp32", decoder: str = "fp32", threads: int = 1):
        so = ort.SessionOptions()
        so.intra_op_num_threads, so.inter_op_num_threads = threads, 1
        prov = ["CPUExecutionProvider"]  # explicit: never CoreML (q2 §5.1)
        self.enc = ort.InferenceSession(str(model_dir / "onnx" / ENCODERS[encoder]), so, providers=prov)
        self.dec = ort.InferenceSession(str(model_dir / "onnx" / DECODERS[decoder]), so, providers=prov)
        gen = json.loads((model_dir / "generation_config.json").read_text())
        sot = json.loads((model_dir / "added_tokens.json").read_text())[SOT]
        # Guard (review r1 #20): a `.en` export has no language tokens and would silently return garbage.
        if not gen.get("is_multilingual") or gen.get("decoder_start_token_id") != sot:
            raise ValueError("generation_config.json is not a multilingual Whisper export with SOT start")
        self.sot = sot
        self.codes = [k[2:-2] for k in gen["lang_to_id"]]  # "<|en|>" -> "en"
        self.ids = np.array(list(gen["lang_to_id"].values()))

    def probs(self, windows: list[np.ndarray], batch_size: int = 1, pad: str = "fw") -> np.ndarray:
        """(len(windows), n_languages) softmax over the language tokens.

        q11 runs fp32/fp32 at batch_size=1: int8 scores depend on the other windows in the batch (q11 §3.3).
        """
        out = []
        for i in range(0, len(windows), batch_size):
            feats = np.stack([log_mel(w, pad) for w in windows[i : i + batch_size]])
            (hidden,) = self.enc.run(None, {"input_features": feats})
            ids = np.full((len(feats), 1), self.sot, dtype=np.int64)
            logits = self.dec.run(["logits"], {"input_ids": ids, "encoder_hidden_states": hidden})[0][:, -1, :]
            z = logits[:, self.ids].astype(np.float64)
            z = np.exp(z - z.max(axis=1, keepdims=True))
            out.append(z / z.sum(axis=1, keepdims=True))
        return np.concatenate(out)

    def identify(self, windows: list[np.ndarray], **kw) -> list[tuple[str, float, float]]:
        """Per window: (argmax language, its p, p(en))."""
        en = self.codes.index("en")
        return [(self.codes[r.argmax()], float(r.max()), float(r[en])) for r in self.probs(windows, **kw)]

    def top(self, row: np.ndarray, k: int = 3) -> str:
        return ", ".join(f"{self.codes[i]} {row[i]:.3f}" for i in np.argsort(row)[::-1][:k])


def read_wav(p: Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2, p
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


if __name__ == "__main__":
    model_dir, *wavs = map(Path, sys.argv[1:])
    lid = OrtWhisperLid(model_dir)
    for p in wavs:
        print(p.name, lid.identify([read_wav(p)])[0])
