"""How much does a window's p move under a feature perturbation far below float32 audio precision?

Run in the onnxruntime venv: python -I sensitivity.py MODEL_DIR AUDIO_DIR
Adds ±1e-5 uniform noise to the log-mel features (the features are in roughly [-1.5, 1.5]) and reports max |Δp|
over 5 draws, per encoder/decoder precision, batch = 1. Also checks run-to-run determinism.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from clips import all_clips  # noqa: E402
from whisper_lid import OrtWhisperLid, log_mel  # noqa: E402

clips = all_clips(Path(sys.argv[2]))
for v in ("int8/int8", "fp32/int8", "fp32/fp32"):
    enc, dec = v.split("/")
    lid = OrtWhisperLid(Path(sys.argv[1]) / "wt", encoder=enc, decoder=dec)

    def p_of(feats):
        (h,) = lid.enc.run(None, {"input_features": feats[None]})
        lg = lid.dec.run(["logits"], {"input_ids": np.array([[lid.sot]]), "encoder_hidden_states": h})[0][0, -1, lid.ids]
        z = np.exp(lg - lg.max()); return z / z.sum()

    worst, det = {}, 0.0
    for n, a in clips.items():
        f = log_mel(a); base = p_of(f)
        det = max(det, float(np.abs(p_of(f) - base).max()))
        rng = np.random.default_rng(42)
        worst[n] = max(float(np.abs(p_of((f + rng.uniform(-1e-5, 1e-5, f.shape)).astype(np.float32)) - base).max()) for _ in range(5))
    top = sorted(worst.items(), key=lambda t: -t[1])[:4]
    print(f"{v}: rerun max|Δp| {det:.4f}; perturbation max|Δp| {max(worst.values()):.4f}; worst clips "
          + ", ".join(f"{n} {d:.4f}" for n, d in top))
