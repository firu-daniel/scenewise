# q11 scripts: Whisper-tiny language ID on onnxruntime

Prototype and checks behind [`../q11-asr-without-pyav.md`](../q11-asr-without-pyav.md) §2.3 and §3. Research
material only: not part of the package, not run in CI.

| File | What it does | venv |
|---|---|---|
| `fetch_models.sh` | Downloads the pinned weights and checks their sha256 | — |
| `make_clips.sh` | Makes the en/de/fr speech clips with macOS `say` (macOS only) | — |
| `whisper_lid.py` | The adapter prototype (`log_mel`, `OrtWhisperLid`) | ort |
| `clips.py`, `silero.py` | Synthetic inputs (silence, noise seeds 0–2, music bed, noisy speech); a minimal Silero v6.2 loop | ort |
| `feature_parity.py` | `log_mel` vs faster-whisper 1.2.1's features | fw |
| `ct2_reference.py` | faster-whisper `tiny` int8 (CTranslate2) `detect_language`, without PyAV (an `av` stub) | fw |
| `lid_eval.py` | VAD coverage, per-window scores and p(en), batch independence and timing per encoder/decoder precision | ort |
| `sensitivity.py` | Score change under a ±1e-5 feature perturbation, per precision | ort |

Run (from this directory; `$W` is any scratch directory outside the repository):

```sh
./fetch_models.sh "$W/models" --with-fp16 --with-ct2   # downloads, see below
./make_clips.sh "$W/audio"
uv venv -p 3.12 "$W/ort" && uv pip install -p "$W/ort" onnxruntime==1.30.0 numpy==2.5.3
uv venv -p 3.12 "$W/fw"  && uv pip install -p "$W/fw" --no-deps faster-whisper==1.2.1 \
  && uv pip install -p "$W/fw" ctranslate2==4.8.2 onnxruntime==1.30.0 numpy==2.5.3 tokenizers==0.23.2 huggingface-hub==1.33.0 tqdm
"$W/ort/bin/python" -I lid_eval.py "$W/models" "$W/audio"            # add --pad openai for the audio-padded variant
"$W/ort/bin/python" -I sensitivity.py "$W/models" "$W/audio"
"$W/fw/bin/python"  -I feature_parity.py "$W/audio"
"$W/fw/bin/python"  -I ct2_reference.py "$W/models" "$W/audio"
```

Downloads (all pinned by revision and sha256 in `fetch_models.sh`):
- `onnx-community/whisper-tiny` @ `ff4177021cc41f7db950912b73ea4fdf7d01d8e7`: fp32 encoder and decoder (151.3 MB,
  the q11 choice), the int8 pair (40.6 MB, round 0), two JSON files, and with `--with-fp16` the fp16 encoder
  (16.5 MB).
  **The repository states no licence of its own**; its card says only `base_model: openai/whisper-tiny`. The weights
  are OpenAI's Whisper weights, which OpenAI releases under the **MIT** licence (openai/whisper README); the
  `openai/whisper-tiny` HF card is tagged apache-2.0.
- `Systran/faster-whisper-tiny` @ `d90ca5fe` (`--with-ct2`, 75.5 MB, tagged MIT).
- Silero VAD v6.2 `silero_vad.onnx` from `snakers4/silero-vad` @ `be95df91` (MIT).

The speech clips are TTS, the noise and music are synthetic; the numbers are a sanity check of the adapter, not a
measure of LID accuracy (that is T3). Timings were taken on macOS arm64, one thread.
