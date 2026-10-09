"""Feature parity: whisper_lid.log_mel vs faster-whisper 1.2.1's pad_or_trim(FeatureExtractor()(a)[:, :3000]).

Run in the faster-whisper venv: python -I feature_parity.py AUDIO_DIR   (the script puts its own directory on sys.path).
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules["av"] = types.ModuleType("av")  # faster-whisper imports av at load; arrays never reach decode_audio
from faster_whisper.audio import pad_or_trim  # noqa: E402
from faster_whisper.feature_extractor import FeatureExtractor  # noqa: E402

import numpy as np  # noqa: E402

from clips import all_clips  # noqa: E402
from whisper_lid import log_mel  # noqa: E402

fe = FeatureExtractor()
worst = 0.0
for name, a in all_clips(Path(sys.argv[1])).items():
    ref = pad_or_trim(fe(a)[:, :3000])
    d = float(np.abs(ref - log_mel(a)).max())
    worst = max(worst, d)
    print(f"{name:16s} max|Δ| {d:.2e}")
print(f"worst {worst:.2e}")
