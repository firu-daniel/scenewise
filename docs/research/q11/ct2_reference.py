"""Reference: faster-whisper 1.2.1 `tiny` int8 (CTranslate2) detect_language on the same inputs, without PyAV.

Run in the faster-whisper venv: python -I ct2_reference.py MODEL_DIR AUDIO_DIR
"""
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import faster_whisper  # noqa: F401
except ModuleNotFoundError as e:
    print("plain import fails:", e)
    for m in [k for k in sys.modules if k.startswith("faster_whisper")]:
        del sys.modules[m]
    sys.modules["av"] = types.ModuleType("av")  # stub: arrays never reach decode_audio
from faster_whisper import WhisperModel  # noqa: E402

from clips import all_clips  # noqa: E402

m = WhisperModel(str(Path(sys.argv[1]) / "fwt"), device="cpu", compute_type="int8", cpu_threads=1)
for name, a in all_clips(Path(sys.argv[2])).items():
    t = time.perf_counter()
    lang, p, allp = m.detect_language(a, vad_filter=False)
    pen = dict(allp)["en"]
    top = ", ".join(f"{lg} {q:.3f}" for lg, q in allp[:3])
    print(f"{name:16s} {lang} {p:.3f}  p(en) {pen:.3f}  [{top}]  {time.perf_counter() - t:.2f}s")
