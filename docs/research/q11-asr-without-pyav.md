# q11 — Captions without PyAV: language ID and the Whisper fallback

Research date: **2026-10-08** (round 1 revision the same day). Every source was read that day. Local checks ran on
macOS arm64 (Apple Silicon, CPU, one thread) in a scratch directory. The scripts behind §3 are kept in
[`q11/`](q11/README.md) and download the pinned weights themselves.

Context: the `asr` extra pins faster-whisper 1.2.1 for two jobs, the language-ID gate (q2 §4.4: Whisper `tiny` int8
`detect_language` on scenewise's VAD speech windows, p ≥ 0.5 per window, ≥ about 2 s of English) and the fallback
recogniser (large-v3-turbo, U4). faster-whisper hard-requires PyAV, whose wheels bundle GPL x264/x265 (q10). The goal
is a default install without PyAV. **U16 (2026-10-08) adopted this document's direction**: the fallback moves to an
opt-in `asr-whisper` extra that published images leave out, and the gate uses an in-house onnxruntime Whisper-tiny
adapter.

## 1. Summary and recommendation

- **LID: replace faster-whisper with a small in-house adapter that runs the Whisper `tiny` ONNX export directly on
  pip onnxruntime + numpy** (encoder + one decoder step from `<|startoftranscript|>`, softmax over the 99 language
  tokens). It implements the `LanguageIdentifier` port: the argmax language **and its probability** per window, plus
  the full distribution (the gate reads p(en) from it).
  - **Weights: the fp32 encoder and fp32 decoder** of `onnx-community/whisper-tiny` @
    `ff4177021cc41f7db950912b73ea4fdf7d01d8e7`: `onnx/encoder_model.onnx` (32.9 MB) + `onnx/decoder_model.onnx`
    (118.4 MB), plus `generation_config.json` (`lang_to_id`) and `added_tokens.json`. That is 151.3 MB against
    75.5 MB for the CT2 `model.bin` and 40.6 MB for the int8 pair. The int8 pair was the round-0 choice; it is
    dropped because its dynamic quantization makes a window's score depend on the other windows in its batch and
    on feature differences of 1e-5 (§3.3). fp32 is batch-invariant, insensitive to such differences, and on this
    machine also the fastest (0.115 s per window vs 0.13 s int8 and 0.29 s CT2).
  - **Batching:** the fp32 models give identical scores alone or in any batch (max |Δp| 0.0000), so the adapter may
    batch. It gains nothing on one thread (0.116 s per window at batch 8), so the default is **batch = 1**.
  - **Licence:** the weights are OpenAI's Whisper weights, released under **MIT** ("Whisper's code and model weights
    are released under the MIT License") [S1]. Two HF records disagree with or omit that: the `openai/whisper-tiny`
    card is tagged apache-2.0 [S2], and the onnx-community repo states no licence of its own (its card says only
    `base_model: openai/whisper-tiny`) [S3]. MIT governs; NOTICE credits OpenAI (MIT) and the onnx-community ONNX
    conversion. `base` (`onnx-community/whisper-base` @ `1846881b`) is the step up.
  - **Prototype:** [`q11/whisper_lid.py`](q11/whisper_lid.py), 89 non-blank, non-comment lines including WAV reading
    and the script entry point; the adapter proper is about 70 (a slaney mel filterbank and log-mel of about 35
    lines, the model of about 35). Its features match faster-whisper 1.2.1's `FeatureExtractor` to 8e-6, and on
    speech its scores match faster-whisper `tiny` int8 to within 0.001 (fp32; int8 within 0.004) (§3).
  - It drops ctranslate2, tokenizers and huggingface-hub from the LID path.
- **Gate rule (replaces q2 §4.4 step 4 for captioning):** a window counts as English when it holds **≥ 1.0 s of VAD
  speech and p(en) ≥ 0.5**; the video gets a track when those windows hold ≥ about 2 s of speech. VAD is the first
  defence (Silero found 0.00 s of speech in silence and white noise, 0.13 s in a music bed); p(en), not the argmax
  p, is the second, because white noise scores an *argmax* p of 0.48–0.57 (≥ 0.5 for most seeds on every backend) but p(en) only
  0.13–0.18
  (§3.4, §3.5).
- **sherpa-onnx's spoken-language ID cannot implement the port.** `SpokenLanguageIdentification.compute(stream) -> str`
  returns only the argmax language code; the C++ takes the arg-max of the raw decoder logits and never computes a
  probability; one stream per call, no batch [S4][S5]. This confirms q2 §4.4 step 3.
- **onnx-asr has no language-ID API.** Its Whisper models detect the language only internally, as a greedy
  decode of one token, to fill the prompt before transcribing; no probabilities, nothing returned [S6].
- **Fallback recogniser: keep faster-whisper + large-v3-turbo (U4) but in the opt-in `asr-whisper` extra, documented
  as bringing GPL code (PyAV); published images ship without it (U16).** faster-whisper cannot run without `av`
  being importable: `av>=11` is an unconditional `Requires-Dist`, and `faster_whisper/__init__.py` imports
  `faster_whisper.audio`, which runs `import av` at module load [S7][S8]. The PyAV-free alternatives (sherpa-onnx
  Whisper, onnx-asr Whisper) lose the per-token timestamps the `SpeechRecognizer` port needs, or need a re-export
  that was not tested here (§2.4).
- **Extras:** `asr` = sherpa-onnx, sherpa-onnx-core, onnx-asr, onnxruntime, numpy; new `asr-whisper` =
  faster-whisper. **Verified with uv 0.12.23** on a scratch copy: the relocked `asr` extra, and the full `-cpu` image
  set of extras (`service asr llm-anthropic vision gcs torch-cpu`), contain no `av`, `faster-whisper` or
  `ctranslate2` (the review re-ran this and also checked the `-cuda` set). `av` reappears only via `asr-whisper`
  (`uv tree --invert --package av` → `faster-whisper → scenewise (extra: asr-whisper)`) (§4).
- **Without `asr-whisper`, no GPL code is loaded into the scenewise process.** The image is not GPL-free: it still
  aggregates GPL packages, namely the base OS (bash, coreutils, dpkg, …) and the apt `ffmpeg` with its libav*,
  x264 and x265 shared libraries, which Ubuntu builds with `--enable-gpl`. ffmpeg runs only as a subprocess, but
  q10 §3 items 1, 2 (Ubuntu source packages) and 4 still apply to published images; U17 defers the choice between
  Ubuntu's ffmpeg and an LGPL-only build, and that choice does not remove the base-OS part. An image built with
  `asr-whisper` carries q10's obligations in full.

## 2. Options

### 2.1 sherpa-onnx spoken language identification (1.13.8, the latest on PyPI)

- **Python API** (introspected from the installed 1.13.8 wheel):
  `SpokenLanguageIdentificationWhisperConfig(encoder, decoder, tail_paddings=-1)`,
  `SpokenLanguageIdentificationConfig(whisper, num_threads=1, debug=False, provider="cpu")`,
  `SpokenLanguageIdentification(config)`, `.create_stream()`, `.compute(stream) -> str`. Input is a 16 kHz float32
  waveform through `stream.accept_waveform(sample_rate, samples)` [S4].
- **Output: the top label only.** The docstring of `compute` reads "A string representing the identified language code".
  In `offline-whisper-model.cc` `DetectLanguage` runs one decoder step from SOT and loops over the language token ids,
  keeping the largest raw logit; no softmax, no score. `spoken-language-identification-whisper-impl.h` maps the id to
  a code (empty string for an unknown id) [S5].
- **Models:** any multilingual Whisper export from sherpa-onnx's `export-onnx.py` ("Only whisper multilingual models
  can be used"): `csukuangfj/sherpa-onnx-whisper-tiny` @ `65176e2d` has `tiny-encoder.int8.onnx` (12.9 MB) and
  `tiny-decoder.int8.onnx` (89.9 MB); base, small, medium, large-v3 and turbo exports exist under the same account. The
  repos carry no model card or licence field; the weights are OpenAI's MIT weights [S1][S9].
- **Batching:** none; `compute` takes one stream.
- **Speed:** not measured (the model was not downloaded, since the API cannot meet the port).
- **Verdict: cannot implement `LanguageIdentifier`.** No probability means no threshold and no "unknown" label,
  which D21 requires. Could be used only if the rule dropped the probability, which q2 §4.1 argues against
  (`detect_language` always returns a label). Patching sherpa-onnx to return the softmax is a small upstream change
  but would be a C++ fork until released.

### 2.2 onnx-asr 0.12.0 (latest)

- `models/whisper.py`: `recognize_batch(..., language=None)`. Without a language it runs
  `self._decoding(encoding, [[<|startoftranscript|>]], 3)` (greedy argmax) and writes the resulting token into the
  transcribe prompt. The detected language is neither returned nor scored; `TimestampedResult` for Whisper holds text
  only [S6].
- `WhisperHf._encode` and `_decode` (private) do return logits, so an adapter could reach in, but that is private API
  and gives nothing the direct adapter in §2.3 does not.
- Useful pieces: `onnx_asr.preprocessors.numpy_preprocessor.WhisperPreprocessorNumpy` is a numpy log-mel, but it pads
  the waveform to 30 s before the mel (openai-whisper semantics, not faster-whisper's) and takes the max over the
  whole batch, so batched windows would influence each other's normalisation. The adapter below uses its own mel.
- **Verdict: transcription only; no LID probabilities.**

### 2.3 Direct onnxruntime Whisper-tiny first-token LID (recommended)

What the adapter does, per window (each window = the concatenated VAD spans, ≤ 30 s, 16 kHz float32):

1. Log-mel with faster-whisper 1.2.1's semantics: mel of the unpadded window plus 160 zero samples (Hann 400, hop 160,
   80 slaney filters, `log10(max(·, 1e-10))`, floor at max − 8, `(x + 4) / 4`), then zero-pad the *features* to 3000
   frames (`pad_or_trim`). This matters: openai-whisper and onnx-asr pad the *audio*, and that changes non-speech
   scores noticeably (§3.4).
2. `encoder_model.onnx` (fp32): `input_features [B, 80, 3000] → last_hidden_state [B, 1500, 384]`.
3. `decoder_model.onnx` (fp32, the no-cache decoder): `input_ids [[50258]] * B` + `encoder_hidden_states → logits
   [B, 1, 51865]`.
4. Gather the 99 ids in `generation_config.json` `lang_to_id`, softmax over them, and return argmax + p and the full
   distribution. Masking non-language tokens and taking the softmax is what openai-whisper's `detect_language` does;
   faster-whisper delegates to CTranslate2 `Whisper.detect_language`, whose results matched (§3).

- **Load-time guard:** assert `is_multilingual: true` and `decoder_start_token_id ==` the id of
  `<|startoftranscript|>` (50258) in the loaded files. The language ids are read from the file, so a later switch to
  `base` or `large-v3` (100 languages, adds `yue`) keeps working, but a `.en` export has no language tokens and would
  return garbage silently. The prototype does this.
- **Batch = 1 by default**; the batch dimension stays because the fp32 models are batch-invariant (§3.3). A contract
  test asserts that a window's p is identical alone and in a batch with a loud-noise window.
- **Dependencies:** onnxruntime and numpy only, both already in `asr`. stdlib `json`; no tokenizer.
- **Providers:** pass `providers=["CPUExecutionProvider"]` explicitly (q2 §5.1 CoreML note).
- **Size:** about 70 lines of adapter. It fits `adapters/asr/whisper_lid.py` well under `max_module_lines = 500`.
- **Files to pin and mirror** (sha256 verified against the download and HF's LFS ids; `q11/fetch_models.sh`):
  - `onnx/encoder_model.onnx` `6642befb640f950d4a8cbbd17834d59e7e75f575b81ccf213e06b050623ab1dd`
  - `onnx/decoder_model.onnx` `ab79e3f2a9a3d98f159f853a3172120a38af7eb5f7863d706aa7d39c228f009e`
  - `generation_config.json` `f5c67e5a4f7102f8cb4d058bc95da276bbc19eeec997267c3bb0f25ef68facd1`
  - `added_tokens.json` `9715fd2243b6f06a5858b5e32950d2853f73dd5bc201aafcf76f5082a2d8acd1`
  - For reference, the int8 pair: `onnx/encoder_model_int8.onnx` `03ff3c99…d336`, `onnx/decoder_model_int8.onnx`
    `2a160a2a…4f12`.
  - Alternative weights: sherpa-onnx's `tiny-encoder/decoder.int8.onnx` work with the same idea. That decoder takes
    a self-attention KV cache, cross K/V and an offset, so the code is a little longer, and it is int8 with the same
    batch coupling. No benefit.
- **Verdict: implements the port as specified** (argmax + p and the distribution per window), PyAV-free, MIT weights.

### 2.4 The fallback recogniser without PyAV

- **faster-whisper without `av`: not supported.** `requires_dist` for 1.2.1 (the latest release; 1.2.0, 1.1.1 and
  1.1.0 precede it) includes `av>=11` with no marker [S7]. `faster_whisper/__init__.py` line 1 is
  `from faster_whisper.audio import decode_audio`, and `audio.py` line 15 is `import av` [S8]. Tested: with
  faster-whisper installed `--no-deps` (no `av`), `import faster_whisper` fails with `No module named 'av'`. With a stub
  `sys.modules["av"]` injected first, `WhisperModel(...).detect_language(ndarray, vad_filter=False)` works, because
  arrays never reach `decode_audio` (`q11/ct2_reference.py`). That is a hack, and dropping `av` from the install
  would also need a uv `override-dependencies` entry that applies to scenewise's own lock only, not to anyone who
  `pip install`s the package. **Rejected.**
- **sherpa-onnx Whisper** (`OfflineRecognizer.from_whisper(..., enable_token_timestamps=False,
  enable_segment_timestamps=False)`, 1.13.8): no PyAV, already in `asr`. Token timestamps come from cross-attention
  DTW and the docstring says they "Require ONNX models exported with attention outputs"; the C++ skips DTW silently
  when the decoder has no attention output. The published `csukuangfj/sherpa-onnx-whisper-turbo` @ `2ca6ff69`
  (2024-10-02) predates that feature, so it probably needs re-exporting with the 1.13.8 script (not tested). Segment
  timestamps (Whisper's own `<|t|>` tokens) work without re-export [S10]. **Credible PyAV-free fallback, but unverified;
  see open question 1.**
- **onnx-asr Whisper** (`onnx-community/whisper-large-v3-turbo` via `WhisperHf`, or `whisper-ort` beam search):
  returns text only, with no token or segment timestamps [S6]. **Cannot feed `SpeechRecognizer`'s token contract.**
- **Opt-in extra (recommended, adopted as U16):** keep faster-whisper + large-v3-turbo exactly as U4 says, but in
  `asr-whisper`. The setting `asr.backend = "faster-whisper"` then needs that extra, and bootstrap's missing-extra
  error should name it and say that it brings PyAV (GPL x264/x265, q10).
- **What this does to U4:** the back end, its adapter and its config remain, so U4 holds to the letter. But published
  images ship no fallback recogniser, and `asr.backend = "faster-whisper"` fails at bootstrap there; the fallback
  exists only in self-built images (`SCENEWISE_EXTRAS=asr-whisper`, §4), which take on q10 §3. ARCHITECTURE §12 and
  the README should say so. If an in-image fallback is ever required, open question 1 is the route.

### 2.5 Other PyAV-free LID models

| Option | Licence | Languages / accuracy | Runtime | Verdict |
|---|---|---|---|---|
| Silero language classifier (`silero_lang_detector`, `silero_lang_detector_95`) | **None stated** on the wiki page | 4 languages "99%"; 95 languages "85%" (58 groups "90%") on their validation set; clips < 15–20 s | torch.hub, ONNX "option" | **Rejected.** The wiki page is headed "DEPRECATED"; silero-vad v6.2's `hubconf.py` exposes only `silero_vad`, and only `files/lang_dict_95.json` / `lang_group_dict_95.json` remain in the tree [S11][S12] |
| SpeechBrain `lang-id-voxlingua107-ecapa` @ `0253049a` | Apache-2.0 (card) | 107 languages; "Error rate: 6.7% on the VoxLingua107 development dataset"; returns posteriors | speechbrain 1.1.1, which requires `torch>=2.1.0` and `torchaudio>=2.1.0` | **Rejected for `asr`:** it would put torch into the captions path, which q8c §3 keeps torch-free. No maintained ONNX export was found [S13][S14] |
| Direct ORT Whisper `tiny` (§2.3) | MIT weights | Same model as today; large-v3 averages 94.1 % LID, `tiny` lower (q2 open question 5) | onnxruntime + numpy | **Chosen** |

## 3. Verification (local, 2026-10-08)

Everything in this section is produced by the scripts in [`q11/`](q11/README.md); `q11/README.md` says how to run
them. Environments: an `ort` venv (onnxruntime 1.30.0, numpy 2.5.3) and an `fw` venv (faster-whisper 1.2.1
`--no-deps` + ctranslate2 4.8.2, no `av`). Inputs (`make_clips.sh`, `clips.py`): macOS `say` at 16 kHz s16le, en
(Samantha, 5.7 s), de (Anna, 7.6 s), fr (Thomas, 5.1 s); 10 s of digital silence; 10 s of Gaussian noise σ 0.05 from
`np.random.default_rng(seed)`, seeds 0, 1, 2 (seed 0 is the clip q2 and round 0 used); a 10 s synthetic music bed
(triads with harmonics and a pulse); en and de mixed with noise (seed 7) at 10 dB and 0 dB SNR and with the music
bed at 10 dB. One window per clip, one thread.

Round-0 note: round 0's speech clips were not kept, so the speech rows below come from new `say` clips; the
non-speech inputs are the same (CT2 silence cy 0.282 and noise seed 0 nn 0.552 reproduce round 0 and q2 [L1]).
Round 0's ORT non-speech figures (silence en 0.302, noise nn 0.385) came from **one batch of five windows**, not
from single windows; they are withdrawn (review r1 #3, §8).

### 3.1 Features

`feature_parity.py`: the adapter's log-mel against faster-whisper's `pad_or_trim(FeatureExtractor()(a)[:, :3000])`,
max |Δ| ≤ 8.1e-6 over all 14 inputs (0.0 on silence, ≤ 3e-7 on noise). The reviewer's independent implementation
matched exactly (0.0).

### 3.2 LID results, single windows

Cells: argmax p · p(en). ORT columns use faster-whisper padding unless stated.

| Input | CT2 `tiny` int8 (faster-whisper, `av` stub) | ORT int8/int8 | **ORT fp32/fp32 (recommended)** | ORT int8, audio padded to 30 s |
|---|---|---|---|---|
| en | en 0.995 · 0.995 | en 0.992 · 0.992 | en 0.994 · 0.994 | en 0.997 · 0.997 |
| de | de 0.987 · 0.004 | de 0.983 · 0.007 | de 0.988 · 0.005 | de 0.979 · 0.012 |
| fr | fr 0.997 · 0.000 | fr 0.996 · 0.000 | fr 0.996 · 0.000 | fr 0.996 · 0.000 |
| silence | cy 0.282 · 0.238 | en 0.291 · 0.291 | en 0.233 · 0.233 | en 0.422 · 0.422 |
| noise seed 0 | **nn 0.552** · 0.129 | **nn 0.503** · 0.160 | **nn 0.548** · 0.142 | **nn 0.629** · 0.089 |
| noise seed 1 | **nn 0.509** · 0.152 | **nn 0.519** · 0.155 | **nn 0.540** · 0.145 | **nn 0.669** · 0.065 |
| noise seed 2 | **nn 0.506** · 0.139 | nn 0.480 · 0.182 | **nn 0.549** · 0.144 | **nn 0.693** · 0.059 |
| music bed | en 0.232 · 0.232 | en 0.282 · 0.282 | en 0.258 · 0.258 | jw 0.241 · 0.173 |
| en + noise 10 dB | en 0.995 · 0.995 | en 0.994 · 0.994 | en 0.996 · 0.996 | en 0.994 · 0.994 |
| en + noise 0 dB | en 0.670 · 0.670 | en 0.646 · 0.646 | en 0.641 · 0.641 | en 0.634 · 0.634 |
| en + music 10 dB | en 0.994 · 0.994 | en 0.992 · 0.992 | en 0.994 · 0.994 | en 0.995 · 0.995 |
| de + noise 10 dB | de 0.978 · 0.006 | de 0.978 · 0.004 | de 0.983 · 0.004 | de 0.981 · 0.004 |
| de + noise 0 dB | de 0.352 · 0.234 | de 0.341 · 0.244 | de 0.404 · 0.202 | de 0.622 · 0.100 |
| de + music 10 dB | de 0.988 · 0.005 | de 0.987 · 0.005 | de 0.991 · 0.004 | de 0.988 · 0.006 |

- **Speech:** fp32 agrees with CT2 to within 0.001 on the clean clips (int8 within 0.004).
- **White noise passes an argmax-p ≥ 0.5 rule on every backend:** CT2 3 of 3 seeds, ORT int8 2 of 3, ORT fp32 3 of
  3, audio-padded 3 of 3. The reviewer's single-window ORT int8 run gave silence en 0.291 (as here) and noise nn
  0.478 / 0.509 / 0.507 for seeds 0–2 (also ≥ 0.5 on 2 of 3). Its features equal faster-whisper's exactly; ours
  differ by ≤ 3e-7 on noise, and the int8 encoder turns that into the 0.025 gap (§3.3).
- **p(en) on non-speech is 0.13–0.29 with faster-whisper padding**, at most 0.29 (silence, int8) and at most 0.18
  on noise. Audio padding pushes silence to p(en) 0.42.
- Use faster-whisper padding (features zero-padded): with audio padding, silence rises to en 0.42 and noise to
  0.63–0.69.

### 3.3 Batch coupling and precision

`lid_eval.py` scores each input alone, in one batch of all 14, and paired with a loud-noise window (σ 0.5);
`sensitivity.py` adds ±1e-5 uniform noise to the features (5 draws). Sizes are the HF file sizes; time is the
median per window over 7 runs; RSS is the whole process (Python, numpy, onnxruntime, one window) from
`/usr/bin/time -l`.

| Encoder / decoder | Files | Time, batch 1 | Time, batch 8 (per window) | max \|Δp\| batch of 14 | max \|Δp\| paired with loud noise | max \|Δp\| ±1e-5 features | Peak RSS |
|---|---|---|---|---|---|---|---|
| int8 / int8 (round 0) | 40.6 MB | 0.137 s | 0.130 s | **0.169** (en + noise 0 dB) | 0.076 | 0.036 | 457 MB |
| fp32 / int8 | 63.4 MB | 0.125 s | 0.139 s | 0.018 | 0.021 | 0.027 | — |
| fp16 / int8 | 47.0 MB | 0.230 s | 0.249 s | 0.014 | 0.014 | — | — |
| **fp32 / fp32** | **151.3 MB** | **0.115 s** | 0.116 s | **0.0000** | **0.0000** | **0.0000** | 570 MB |
| CT2 int8 (faster-whisper) | 75.5 MB | 0.29 s | — | — | — | — | — |

- The cause is dynamic quantization: the int8 encoder has 18 `DynamicQuantizeLinear` and 24 `MatMulInteger` nodes
  (review r1 #10; the same count here), and `DynamicQuantizeLinear` computes one scale and zero point per tensor,
  across the whole batch. The int8 decoder is quantized the same way (25 and 40 occurrences of those op names in the
  file), which is why an fp32 encoder alone still leaves 0.018. Runs are deterministic (rerun Δ 0.0000 for every variant); the problem is the dependence on batch mates
  and on tiny input changes, worst on the inputs near a decision (noisy speech, noise).
- **Decision: fp32 encoder + fp32 decoder, batch = 1 by default.** It is the only variant whose scores do not move,
  it is the fastest here, and the cost is 110 MB more weights in the image (beside a 652 MB Parakeet encoder) and
  about 110 MB more peak RSS. int8 at batch = 1 would remove the batch coupling but keep the 0.036 sensitivity and
  gain no speed on this machine. The fp16 encoder is about twice as slow on this CPU.
- Not measured: linux/amd64. On x86 with VNNI, int8 may well be faster than fp32; even then the encoder runs once
  per window of up to 30 s, so fp32 stays affordable (open question 3).

### 3.4 VAD coverage

`lid_eval.py` runs a minimal Silero v6.2 loop (`silero.py`, threshold 0.5, 32 ms frames) over each whole input:

| Input | Speech (s) | Share of frames | Max frame p |
|---|---|---|---|
| en / de / fr | 5.54 / 7.42 / 4.93 | 0.96–0.97 | 1.00 |
| silence | 0.00 | 0.00 | 0.01 |
| noise seeds 0–2 | 0.00 | 0.00 | 0.04–0.05 |
| music bed | 0.13 | 0.01 | 0.88 |
| en / de + noise 0 dB | 5.31 / 7.20 | 0.93–0.94 | 1.00 |
| en / de + music 10 dB | 5.50 / 7.36 | 0.96 | 1.00 |

So on these inputs the VAD-first rule (q2 §4.4 step 1) already stops every non-speech input before LID, and the LID
scores above for non-speech describe what happens only when VAD fails, for example on a music bed with voice-like
instruments, which Silero lists as a known issue (q2 §3).

### 3.5 Gate rule (proposal; replaces q2 §4.4 step 4 for the captioning decision)

Per LID window (concatenated VAD speech, 3–30 s, as in q2 §4.4 step 2), with `vad_s` = seconds of frames with
Silero p ≥ 0.5 in the window and p(·) the adapter's distribution:

1. `vad_s < 1.0` → **unknown** (q2's "segments shorter than 1 s" made explicit in speech seconds).
2. `p(en) ≥ 0.5` → **English**.
3. otherwise, argmax p ≥ 0.5 → that language (metadata only: `partial_language`, `language_unsupported`);
   else **unknown**.

Video: `en_s` = Σ `vad_s` over English windows; `en_s ≥ 2.0 s` → emit a track with the English windows (q2 §4.4
step 5 unchanged).

Why this and not "argmax p ≥ 0.5":
- The gate's question is "is this English?", not "is this some language?". Since p(en) ≥ 0.5 implies the argmax is
  en, the rule only differs from q2's for non-English labels, which never produce captions.
- Non-speech that slips past VAD gets an argmax p of 0.48–0.57 (noise, ≥ 0.5 for most seeds on every backend) but
  p(en) of at most 0.18 on noise and 0.29 on silence or music: a margin of 0.21 below 0.5, against no margin for argmax p.
- English stays above: clean 0.99, with music at 10 dB 0.99, with noise at 0 dB SNR 0.64–0.67. German stays below:
  p(en) ≤ 0.012 clean, 0.20–0.24 at 0 dB.
- The VAD minimum does the first filtering (0.00 s on silence and noise, 0.13 s on music); requiring `vad_s` in
  speech seconds rather than window length keeps a window built from sparse false-positive frames from reaching
  LID at all.
- Both numbers (0.5 and 1.0 s) are starting values for T3, which should report p(en), not only the argmax p, on
  noise and music beds and on real non-English Expause clips.

### 3.6 Dependency resolution (uv 0.12.23)

On a scratch copy of `pyproject.toml` + `uv.lock`, with `faster-whisper` moved from `asr` to a new `asr-whisper`
extra:
- `uv lock`: resolved 130 packages; **no resolved version changes**. Only scenewise's own extras metadata changes:
  faster-whisper's marker (`extra == 'asr'` → `extra == 'asr-whisper'`), an `asr-whisper` group in scenewise's
  `[package.optional-dependencies]`, and `"asr-whisper"` in `provides-extras`.
- `uv export --frozen --no-dev --extra service --extra asr`: annotated-doc, annotated-types, anyio, certifi, click,
  fastapi, flatbuffers, h11, httpcore, httpx, idna, numpy, onnx-asr, onnxruntime, opentelemetry-api, packaging,
  pillow, protobuf, pydantic, pydantic-core, pydantic-settings, python-dotenv, sherpa-onnx, sherpa-onnx-core,
  starlette, structlog, typing-extensions, typing-inspection, uvicorn. **No `av`.**
- `uv export … --extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cpu` (the
  `-cpu` image set): **no `av`, `faster-whisper` or `ctranslate2`.** The reviewer found the same for the `-cuda` set
  (`torch-cu130`).
- `uv pip compile pyproject.toml --extra asr --universal -p 3.12`: 23 packages, no `av`.
- `uv tree --frozen --no-dev --invert --package av` → `av v19.0.1 ← faster-whisper v1.2.1 ← scenewise (extra:
  asr-whisper)`.
- Against today's lock, `--extra asr` loses av 19.0.1, ctranslate2 4.8.2, faster-whisper 1.2.1, tokenizers 0.23.2,
  huggingface-hub 1.33.0, hf-xet 1.7.0, filelock, fsspec, pyyaml, tqdm and colorama (Windows only). That is
  **85.5 MB** of manylinux x86_64 cp312 wheels (av 35.0 MB, ctranslate2 39.6 MB), before unpacking. click stays via
  uvicorn.

Not verified: linux/amd64 runs of the ORT adapter (speed, RSS); sherpa-onnx SLID and Whisper on real models; LID
accuracy on real clips (T3).

## 4. Extras change

```toml
[project.optional-dependencies]
asr = [                      # CPU only (q8c §3, D20, U4, U16, q11); no PyAV
  "sherpa-onnx>=1.13.8",
  "sherpa-onnx-core>=1.13.8",
  "onnx-asr>=0.12.0",        # no [hub], no [cpu]
  "onnxruntime>=1.30.0",     # Silero loop, Whisper-tiny LID (q11), onnx-asr
  "numpy>=2.5.3",
]
# Optional Whisper fallback recogniser (U4, U16). faster-whisper hard-requires PyAV, whose
# wheels bundle GPL x264/x265 (q10, q11): this extra brings GPL code into the environment.
asr-whisper = ["faster-whisper>=1.2.1"]
```

Other `pyproject.toml` lines that move with it:
- The `asr` comment (`# CPU only (q8c §3, D20, U4)`, line 30) gains U16/q11 as above.
- deptry `[tool.deptry.per_rule_ignores] DEP002` (line 249) lists `"faster-whisper"` under "item 1 (asr)": it stays
  in DEP002 until the fallback adapter imports it, but its comment moves to `asr-whisper`. Once it is imported,
  map `faster_whisper` in deptry's extras so DEP001/DEP003 stay clean.
- The import-linter contract "Driving side imports no ML or cloud SDK" forbids `ctranslate2` and `faster_whisper`
  for `scenewise.service` (lines 310–311): keep both entries; they still apply to `asr-whisper` builds.
- The relock adds `asr-whisper` to `provides-extras` (uv.lock line 2637) and to scenewise's optional-dependency
  groups; no locked version changes (faster-whisper 1.2.1, ctranslate2 4.8.2, av 19.0.1 when the extra is
  selected).

Images:
- `-cpu` / `-cuda` keep `--extra service --extra asr …` without `asr-whisper` (U16). A build argument (for example
  `SCENEWISE_EXTRAS`) can add it for adopters who want the fallback; that image then needs q10 §3's licence texts and
  source offer.
- Weights baked into the image: replace `Systran/faster-whisper-tiny` with the onnx-community fp32 encoder and
  decoder and the two JSON files (§2.3), all pinned by sha256; `dropbox-dash/faster-whisper-large-v3-turbo` is
  baked only into an `asr-whisper` image.
- CI: the T4 process smoke test (q2 §7) loses faster-whisper from the default job. Add a separate job with
  `--extra asr --extra asr-whisper` for the fallback contract suite.

## 5. Effect on ARCHITECTURE.md, q8c and other findings

These files are not edited here. Items for their authors:

- **ARCHITECTURE.md**
  - §ports: change the `LanguageIdentifier` comment from "faster-whisper `tiny`" to "Whisper `tiny` fp32 ONNX on
    onnxruntime (q11)". The signature is unchanged. `SpeechRecognizer`'s comment: faster-whisper "(extra
    `asr-whisper`)".
  - Captions row (about line 410): "a faster-whisper `tiny` language-ID gate" → "a Whisper `tiny` (ONNX) language-ID
    gate".
  - §12 extras table: the `asr` row loses faster-whisper ("Silero and Whisper-tiny LID on onnxruntime"). Add an
    `asr-whisper` row: "faster-whisper fallback (U4); brings PyAV, GPL x264/x265 (q10); not in published images
    (U16)". The note "`service + asr` pulls no torch and no `onnxruntime-gpu`, which avoids the clash with
    faster-whisper's hard…" holds, and now also "no PyAV".
  - §12 and the README: published images ship no fallback recogniser; adopters who need it build with
    `SCENEWISE_EXTRAS=asr-whisper` and take on q10 §3 (§2.4).
  - `adapters/asr/whisper_lid.py` keeps its name; it now imports onnxruntime and numpy, not faster_whisper.
- **q8c**
  - §2: the `LanguageIdentifier` docstring ("calls detect_language(audio=<ndarray>, vad_filter=False)") becomes:
    "runs the Whisper-tiny encoder and one decoder step on the concatenated spans and returns the softmax over language
    tokens". Windows and `LanguageGuess` are unchanged; `LanguageGuess` should carry p(en) (or the distribution) for
    the rule in §3.5.
  - §3: the `asr` row loses faster-whisper; add `asr-whisper`. The paragraph "PyAV becomes a transitive dependency …
    imported but never given input" is superseded: in the default install PyAV is absent. With `asr-whisper` it applies
    as written. The GPU-ASR constraint ("pip `onnxruntime` is always present (faster-whisper)") still holds, because
    Silero and LID use pip onnxruntime.
  - `asr.backend = "faster-whisper"` requires `asr-whisper`.
- **q2:** §4.4 step 3 (the model), its "reuses the fallback's dependency set" bullet; step 4's rule and its "every
  non-speech input scored 0.21–0.33" rationale, replaced by §3.5 here (white noise scores argmax 0.48–0.57, ≥ 0.5 for most
  seeds on every backend, up to 0.69 with audio padding; p(en) stays ≤ 0.29); §5.2's faster-whisper row ("LID gate + fallback ASR"
  → "fallback ASR, extra `asr-whisper`") and the Whisper tiny row; §5.3 NOTICE ("Language identification model":
  OpenAI Whisper tiny, MIT; ONNX conversion by onnx-community, whose repo states no licence); §6.2's 1.3 GB memory
  figure included CT2 tiny and will change; T3 should report p(en) on noise and music beds.
- **q10:** its premise ("the `asr` extra pins faster-whisper … loaded into the service process") applies only to
  `asr-whisper` builds. For default images it no longer covers PyAV, but its §3 obligations for the image's other
  GPL packages remain: the apt ffmpeg with its libav*, x264 and x265 libraries, and the base OS (§1 last bullet).
- **`src/scenewise/ports.py`** docstring at line 122 ("faster-whisper ``tiny`` language ID").
- **U4** stays satisfied in letter (faster-whisper + large-v3-turbo remains the fallback back end), opt-in and
  outside published images per U16.

## 6. Open questions

Round 0's open question 1 (make the fallback opt-in and exclude it from published images) is **closed by U16**.

1. If a PyAV-free fallback that is *in* the default images is wanted: test sherpa-onnx 1.13.8 Whisper turbo with
   `enable_token_timestamps=True` on a model re-exported with attention outputs (token timing vs NeMo, WER vs
   faster-whisper), and mirror that export.
2. T3 additions: tune the p(en) threshold and the 1.0 s / 2 s minimums (§3.5) on the fp32 backend, with noise and
   music beds and real non-English Expause clips; report p(en). Compare `tiny` and `base` ONNX.
3. Run the ORT adapter on linux/amd64 and record time per window and peak RSS for fp32 and int8 in the T4 smoke test.
4. Upstream: ask sherpa-onnx to return the language probabilities from `SpokenLanguageIdentification` (small C++
   change). That would let a second LID backend share the sherpa runtime, but it is not needed.

## 7. Sources (all read 2026-10-08)

- [S1] OpenAI Whisper README, "License: Whisper's code and model weights are released under the MIT License" —
  https://github.com/openai/whisper/blob/main/README.md
- [S2] `openai/whisper-tiny` HF API (`license: apache-2.0`, sha 169d4a43) — https://huggingface.co/api/models/openai/whisper-tiny
- [S3] `onnx-community/whisper-tiny` HF API, tree and card (sha ff417702, 2025-06-19; no licence field; card front
  matter only `base_model: openai/whisper-tiny`, `library_name: transformers.js`; LFS sha256 of
  `encoder_model.onnx`, `decoder_model.onnx` and the int8/fp16 files), `quantize_config.json`;
  `onnx-community/whisper-base` (sha 1846881b) — https://huggingface.co/onnx-community/whisper-tiny ,
  https://huggingface.co/onnx-community/whisper-base
- [S4] sherpa-onnx 1.13.8 wheel (PyPI, latest), pybind docstrings of `SpokenLanguageIdentification`,
  `SpokenLanguageIdentificationConfig`, `SpokenLanguageIdentificationWhisperConfig` — https://pypi.org/project/sherpa-onnx/1.13.8/
- [S5] sherpa-onnx v1.13.8 `sherpa-onnx/csrc/spoken-language-identification-whisper-impl.h` and
  `offline-whisper-model.cc` (`DetectLanguage`) —
  https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/sherpa-onnx/csrc/spoken-language-identification-whisper-impl.h ,
  https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/sherpa-onnx/csrc/offline-whisper-model.cc
- [S6] onnx-asr 0.12.0 wheel (PyPI, latest): `onnx_asr/models/whisper.py`, `preprocessors/numpy_preprocessor.py`,
  `loader.py` — https://pypi.org/project/onnx-asr/0.12.0/
- [S7] PyPI JSON for faster-whisper 1.2.1 (`requires_dist` includes `av>=11`; releases up to 1.2.1) —
  https://pypi.org/pypi/faster-whisper/1.2.1/json
- [S8] faster-whisper 1.2.1 wheel: `faster_whisper/__init__.py`, `audio.py` (line 15 `import av`), `transcribe.py`
  (`detect_language`), `feature_extractor.py` — https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1/faster_whisper
- [S9] `csukuangfj/sherpa-onnx-whisper-tiny` HF tree (sha 65176e2d; int8 encoder 12.9 MB, decoder 89.9 MB) —
  https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny
- [S10] sherpa-onnx v1.13.8 `offline-recognizer-whisper-impl.h` (DTW only when attention weights exist),
  `sherpa_onnx/offline_recognizer.py` `from_whisper` docstring; `csukuangfj/sherpa-onnx-whisper-turbo` (sha 2ca6ff69,
  2024-10-02) — https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/sherpa-onnx/csrc/offline-recognizer-whisper-impl.h ,
  https://huggingface.co/csukuangfj/sherpa-onnx-whisper-turbo
- [S11] Silero "Other Models" wiki (headed DEPRECATED; language classifiers) —
  https://github.com/snakers4/silero-vad/wiki/Other-Models
- [S12] silero-vad v6.2 `hubconf.py` and tree (GitHub API) — https://github.com/snakers4/silero-vad/blob/v6.2/hubconf.py
- [S13] `speechbrain/lang-id-voxlingua107-ecapa` card (sha 0253049a, Apache-2.0, 107 languages, 6.7 % error on the dev
  set) — https://huggingface.co/speechbrain/lang-id-voxlingua107-ecapa
- [S14] PyPI JSON for speechbrain 1.1.1 (`torch>=2.1.0`, `torchaudio>=2.1.0`) — https://pypi.org/pypi/speechbrain/json
- [S15] `Systran/faster-whisper-tiny` HF API and tree (sha d90ca5fe, tagged MIT; `model.bin` LFS sha256) —
  https://huggingface.co/Systran/faster-whisper-tiny
- [S16] Ubuntu noble `ffmpeg` `debian/rules` (`--enable-gpl`, `--enable-libx264`, `--enable-libx265` in the shared
  CONFIG), as read in review r1 #4 — https://git.launchpad.net/ubuntu/+source/ffmpeg/tree/debian/rules?h=ubuntu/noble
- [U16] `docs/research/user-decisions.md` U16 (2026-10-08): fallback opt-in in `asr-whisper`, left out of published
  images; LID on an in-house onnxruntime Whisper-tiny adapter. U17: Ubuntu ffmpeg for dev/CI, published-image
  ffmpeg decided later.
- [L1] Local runs, this document §3: the scripts in [`q11/`](q11/README.md) (`whisper_lid.py`, `clips.py`,
  `silero.py`, `feature_parity.py`, `ct2_reference.py`, `lid_eval.py`, `sensitivity.py`, `fetch_models.sh`,
  `make_clips.sh`), re-run from fresh venvs; and a uv 0.12.23 relock of a scratch copy of
  `pyproject.toml`/`uv.lock`.

## 8. Review round 1 — resolution

Review: [`reviews/q10-q11-review-r1.md`](reviews/q10-q11-review-r1.md). Findings 1, 2, 6–8, 13–16 and 18 concern q10
and are not handled here. Each q11 finding was re-checked before the change.

| # | Finding | Re-check | Resolution |
|---|---|---|---|
| 3 | ORT non-speech scores not reproducible as single windows | **Confirmed.** Round 0's script scored all five inputs in one batch; that run gave silence en 0.302 and noise nn 0.385. Single windows: silence en 0.291 (same as the reviewer), noise nn 0.503 / 0.519 / 0.480 (reviewer 0.478 / 0.509 / 0.507; the gap is int8 sensitivity to ≤ 3e-7 feature differences, §3.3) | §3.2 table rebuilt from single windows with seeds 0–2; both backends reach ≥ 0.5 on noise (int8 ORT 2 of 3 seeds in both runs, CT2 3 of 3); batch run withdrawn; the "not stable across builds" point is now "or across batch composition" (§3.3) |
| 4 | "Only GPL left is the apt ffmpeg CLI" overstated | **Confirmed** (Ubuntu builds libav* with `--enable-gpl` and x264/x265 [S16]; base OS is GPL) | §1 last bullet: "no GPL code is loaded into the scenewise process"; image still aggregates GPL packages; q10 §3 items 1, 2, 4 still apply; §5 q10 note changed |
| 5 | Prototype scripts not preserved | **Confirmed** (the round-0 scripts lived only in a scratch directory) | Scripts added under [`q11/`](q11/README.md) with a README (how to run, downloads, onnx-community's missing licence, OpenAI MIT); all §3 numbers re-run from them in fresh venvs; noise seeds recorded |
| 9 | pyproject lines missing from §4 | **Confirmed** (lines 30, 249, 310–311; uv.lock `provides-extras` line 2637) | §4 lists them |
| 10 | int8 batching changes scores | **Confirmed and extended:** batch of 14 moves p by up to 0.169 (int8/int8), 0.018 (fp32 encoder, int8 decoder), 0.0000 (fp32/fp32); ±1e-5 feature noise moves int8 by 0.036 | **fp32 encoder + fp32 decoder, batch = 1 by default** (§2.3, §3.3): batch-invariant, fastest here (0.115 s), +110 MB weights, +110 MB RSS. Contract test for batch invariance |
| 11 | Threshold rests on the backend; noise passes it | **Confirmed:** argmax p 0.48–0.57 on noise on every backend with faster-whisper padding (0.63–0.69 audio-padded); p(en) ≤ 0.18 on noise, ≤ 0.29 on silence/music; Silero gives 0.00 s speech on silence/noise | Gate rule in §3.5: `vad_s ≥ 1.0 s` and `p(en) ≥ 0.5` per window, `en_s ≥ 2 s` per video; T3 reports p(en) |
| 12 | Opt-in fallback vs U4; round-0 open question 1 already decided | **Confirmed** (U16) | U16 cited in the context, §1, §2.4, §4, §5; round-0 open question 1 closed (the rest renumbered); §2.4 states published images ship no fallback |
| 17 | "only lock change is faster-whisper's marker" | **Confirmed** | §3.6 reworded: no resolved version changes; extras metadata changes |
| 19 | "MIT/Apache-2.0 weights" conflicting | **Confirmed** | MIT (OpenAI) governs; HF apache-2.0 tag and onnx-community's missing licence noted; NOTICE credits the conversion (§1, §2.3, §5) |
| 20 | No guard against a `.en` export | Valid | Load-time assert of `is_multilingual` and `decoder_start_token_id`, and `generation_config.json` / `added_tokens.json` pinned by sha256 (§2.3); the prototype implements the guard |
