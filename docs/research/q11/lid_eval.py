"""q11 LID evaluation: per-window scores, batch independence, timing per encoder/decoder precision, VAD coverage.

Run in the onnxruntime venv: python -I lid_eval.py MODEL_DIR AUDIO_DIR [--variants int8/int8,fp32/int8,...]
MODEL_DIR is what fetch_models.sh filled (--with-fp16 for the fp16/int8 variant).
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from clips import all_clips, noise  # noqa: E402
from silero import Silero  # noqa: E402
from whisper_lid import SR, OrtWhisperLid  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("model_dir", type=Path)
ap.add_argument("audio_dir", type=Path)
ap.add_argument("--variants", default="int8/int8,fp32/int8,fp16/int8,fp32/fp32")
ap.add_argument("--reps", type=int, default=7)
ap.add_argument("--pad", default="fw", choices=["fw", "openai"], help="openai: audio padded to 30 s (comparison only)")
args = ap.parse_args()

clips = all_clips(args.audio_dir)
names = list(clips)
wins = [clips[n] for n in names]
loud = noise(1, sigma=0.5)

vad = Silero(args.model_dir / "silero_vad.onnx")
print("## VAD (Silero v6.2, threshold 0.5)")
print(f"{'clip':16s} {'dur':>5s} {'speech s':>8s} {'cover':>6s} {'mean p|sp':>9s} {'max p':>6s}")
for n in names:
    fp = vad.frame_probs(clips[n])
    sp = fp >= 0.5
    mean_sp = fp[sp].mean() if sp.any() else 0.0
    print(f"{n:16s} {len(clips[n]) / SR:5.1f} {sp.sum() * 512 / SR:8.2f} {sp.mean():6.2f} {mean_sp:9.2f} {fp.max():6.2f}")

for v in args.variants.split(","):
    enc, dec = v.split("/")
    lid = OrtWhisperLid(args.model_dir / "wt", encoder=enc, decoder=dec)
    single = lid.probs(wins, batch_size=1, pad=args.pad)
    batched = lid.probs(wins, batch_size=len(wins), pad=args.pad)
    paired = np.stack([lid.probs([w, loud], batch_size=2, pad=args.pad)[0] for w in wins])
    en = lid.codes.index("en")
    print(f"\n## encoder {enc} / decoder {dec}, padding {args.pad}")
    print(f"{'clip':16s} {'single window (top 3)':40s} {'p(en)':>6s} {'Δ batch':>8s} {'Δ paired':>8s}")
    for i, n in enumerate(names):
        db = np.abs(batched[i] - single[i]).max()
        dp = np.abs(paired[i] - single[i]).max()
        print(f"{n:16s} {lid.top(single[i]):40s} {single[i, en]:6.3f} {db:8.4f} {dp:8.4f}")
    print(f"max |Δp| vs single: batch of {len(wins)} {np.abs(batched - single).max():.4f}; "
          f"paired with loud noise {np.abs(paired - single).max():.4f}")
    w = clips["en"]
    lid.probs([w])  # warm-up
    t1 = []
    for _ in range(args.reps):
        t = time.perf_counter(); lid.probs([w]); t1.append(time.perf_counter() - t)
    t8 = []
    for _ in range(max(2, args.reps // 3)):
        t = time.perf_counter(); lid.probs([w] * 8, batch_size=8); t8.append((time.perf_counter() - t) / 8)
    print(f"time per window, 1 thread: batch 1 median {statistics.median(t1):.3f}s (min {min(t1):.3f}); "
          f"batch 8 {statistics.median(t8):.3f}s/window")
