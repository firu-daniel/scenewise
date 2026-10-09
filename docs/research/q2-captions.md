# Q2 — Captions (English VOD, WebVTT)

Research date: 2026-10-08, revised the same day after review round 1 ([reviews/q2-review-r1.md](reviews/q2-review-r1.md)) and the final review round 2 ([reviews/q2-review-r2.md](reviews/q2-review-r2.md)). Every source in this document was read on 2026-10-08 unless a different date is given. Source IDs such as [S1] refer to the **Sources** section. [L1] refers to the small local checks described in section 10. Anything not verified is listed under **Open questions**.

Settled user decisions that apply here ([user-decisions.md](user-decisions.md)):
- **U4:** Parakeet-TDT-0.6b-v2 (CC-BY-4.0) is accepted as the default, with attribution in NOTICE and README, including a note of the ONNX conversion and quantisation. faster-whisper + large-v3-turbo (MIT) stays the fallback back end.
- **U3:** the operator (Expause) is EU-based.
- **U2:** the Python floor is 3.12.

---

## 1. Summary and recommendation

- **Model: NVIDIA `parakeet-tdt-0.6b-v2`** (English only, CC-BY-4.0, 0.6B parameters).
  - **WER:** 4.70 % average on the current Open ASR Leaderboard (2026-10-02 snapshot, CSV `avg` over 8 public English sets, four of them "Cleaned" variants) [S1][S2].
  - **Against Whisper:** better than every *openly runnable* Whisper variant on the board: distil-large-v3.5 5.40, whisper-large-v3 5.78, large-v3-turbo 6.36 [S2].
    - The one Whisper derivative that scores better is TheStageAI/thewhisper-large-v3-turbo (4.54) [S2]. It is excluded because it only runs through TheStage's proprietary SDK or Docker images with an online-checked access token, and its weight files are shipped as encrypted `.enc` blobs [S48].
  - **Speed inside onnx-asr on a desktop CPU:** about 9× faster than Whisper large-v3-turbo at default precision (36.8 vs 3.9 RTFx) and about 5.6× faster at int8 (30.5 vs 5.4) [S9].
    - That comparison uses onnx-asr's own Whisper ONNX path. It says nothing about the actual fallback, faster-whisper/CTranslate2 int8, which nobody has benchmarked against Parakeet on the same CPU (open question 3).
  - **Output:** native word, segment and character timestamps in NeMo, with punctuation and capitalisation [S6].
- **Runtime, behind a `SpeechRecognizer` port.** The model choice does not depend on the runtime.
  - **Primary ASR runtime, dev and prod: `sherpa-onnx` 1.13.8** (Apache-2.0, released 2026-09-10) with the int8 export `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` (CC-BY-4.0) [S38][S41]. **Used for ASR only** (and optionally audio tagging), not for VAD.
    - It returns token start times **and the TDT model's predicted durations** plus per-token log-probabilities, without patching [L1][S53]. A duration is the decoder's predicted frame advance: 0–4 frames of 80 ms, so **0–0.32 s per token, and it can be 0** [S53][L1]. It is a better end-time hint than start-only timing, not a measured word end; the cue builder still extends cue ends to the next pause or a minimum hold (T2 checks this against NeMo).
    - It ships wheels for CPython 3.10–3.14 on macOS arm64 and manylinux, and does not need Torch [S38]. It bundles its own onnxruntime 1.28.2, but scenewise still needs pip `onnxruntime` for the Silero loop and faster-whisper, so both builds are in the process; this was tested and works (section 5.1) [L1].
    - This is a thin margin over onnx-asr (section 5.1). The deciding factor is durations and log-probabilities out of the box.
  - **Tested second: `onnx-asr` 0.12.0** (MIT, 2026-07-15) with `onnxruntime` 1.30.0 and the `istupakov/parakeet-tdt-0.6b-v2-onnx` int8 export [S10][S11][S42].
    - It is pure Python and small enough to vendor. Its decoder already computes the TDT `step`, so returning durations would be a small patch.
    - Weak points: it returns token *start* times only [S42], its own VAD cuts speech runs at fixed 20 s offsets (irrelevant once scenewise owns segmentation) [S42][L1], and it has a single maintainer [S51].
  - **Reference oracle only (not shipped):** NeMo 3.0.0, or transformers 5.19.0 `ParakeetForTDT` (Torch). These are used to validate timestamps and WER offline [S7][S44].
- **VAD and segmentation: scenewise's own Silero v6.2 ONNX loop** on pip `onnxruntime` 1.30.0, about 40 lines (vendored from onnx-asr's MIT `models/silero.py` or written fresh). It yields per-frame speech probabilities and caps segments at about 30 s by cutting at the lowest-probability frame near the cap. sherpa-onnx's VAD cannot do this: it exposes no frame probabilities to Python and never forces a cut (a 55.6 s utterance stayed one segment) [S53][L1]. The model file is pinned from upstream `snakers4/silero-vad` tag v6.2 by sha256 (section 5.2).
- **Guard against silence and music:** run Silero VAD v6.2 (MIT) before ASR. Videos with no detected speech get no caption track and a `no_speech` flag.
  - **What the evidence covers.** Two separate experiments in Barański et al. [S19] must not be conflated:
    1. On pure non-speech audio with **no VAD**, Whisper large-v3 hallucinated on 40.3 % of 301,317 clips.
    2. On *speech* clips padded or overlaid with unseen non-speech sounds, the detected-hallucination rate was 21.3 % unprocessed, 12.5 % with WebRTC VAD and 0.2 % with Silero VAD (Table VII, non-overlapped case).
  - **No cited evidence covers music beds.** The paper removed all music, because "tagging was not reliable enough to discriminate between instrumental and vocal songs" [S19]. No source found measures ASR or VAD false positives on music, for Parakeet or for Silero. Silero's own release notes list "music with human voice-like instruments" as a known issue [S8].
  - Music beds are probably the commonest no-speech case on Expause, so a **music test set is an explicit acceptance item** (section 7, test plan T1).
  - **Music-bed flag (optional, first candidate):** sherpa-onnx's built-in `AudioTagging` with the AudioSet zipformer `sherpa-onnx-zipformer-small-audio-tagging-2024-04-15` (Apache-2.0 per its card, 27 MB int8). It runs in the same runtime, without Torch. Locally it tagged the synthetic music clip "Music" 0.87 and speech "Speech" 0.99, but also tagged digital silence "Music" 0.33–0.37, so it needs an energy gate [L1]. It can set a `music` flag or add a "[music]" cue on VAD-negative stretches. Real-music accuracy is part of T1.
- **Language-ID gate (required, because Parakeet v2 is English-only).**
  - Run `faster-whisper` 1.2.1 `detect_language(window, vad_filter=False)` with the multilingual **`tiny`** CTranslate2 checkpoint (MIT) on **scenewise's own VAD speech windows only**. `detect_language` always returns some label, even for silence or zero padding, so the caller must gate on VAD first [S14][L1].
  - A window counts as English when the argmax is "en" with p ≥ 0.5. That is **scenewise's own starting value**, tuned in T3. Locally, clean speech scored ≥ 0.98, and non-speech inputs scored 0.21–0.33 [L1].
  - **Caption the English windows whenever the video has at least about 2 s of English speech**, whatever share the other languages have. Flag the non-English and unknown windows in metadata. With less English speech than that, emit no track and set `language_unsupported`.
  - The full rule is in section 4.4.
  - Why this matters: locally, Parakeet v2 turned German speech into invented pseudo-English ("Gutentag und Hartslich Wilkmen…") [L1].
- **Fallback ASR:** `faster-whisper` 1.2.1 with `large-v3-turbo` (or `distil-large-v3.5`), `vad_filter=True` and `condition_on_previous_text=False`. Use it if Parakeet fails our tests, or if multilingual captions are wanted later [S13][S14].

---

## 2. Comparison table

**How to read the WER columns**

- **"WER 2026-10-02"** is the leaderboard CSV `avg` column at revision c23ca4f [S2].
  - It is the mean of 8 public sets: AMI-Cleaned, Earnings22-Cleaned-AA-chunked, Gigaspeech-Cleaned, LS clean, LS other, SPGISpeech, Voice Arena Monsoon and Voxpopuli-AA-Cleaned. Four of these are "Cleaned" variants.
  - I recomputed Parakeet v2's mean from the per-set columns: 4.7025.
- **The live Space's *displayed* default average differs.** It adds two private aggregate columns, "Private (scripted)" and "Private (conversational)". These are built from Appen, DataoceanAI and Voice Arena private sets (`init.py` `default_datasets`; `app.py` `APPEN_SCRIPTED` / `DATAOCEAN_SCRIPTED` / …). The changelog for 24 July 2026 says "Private data used in default average" [S1].
- **"WER 2026-07-24"** is the "avg cleaned" mean of 7 sets from the older CSV at revision 1d3e13c [S3]. It is filled for every model present in that snapshot. "absent" means the model was not on the board then.
- **The two WER columns are not comparable with each other** (different set lists and a changed normaliser).

**How to read the speed columns**

- **Leaderboard RTFx** is short-form only, measured on **1× H200**.
  - The Space changelog for 24 June 2026 says "Switch to H200 GPUs for eval" [S1]. The repo README lists the HF Jobs flavour as `h200 … 1x H200 (141 GB)` [S4].
  - The 2025 paper used an A100-80GB [S5].
  - These are large-batch GPU throughput figures, not small-GPU or CPU figures.
  - Long-form numbers (section 3) are WER only. Their hardware is not stated, and the README says long-form "will migrate to HF Jobs" [S4].
- **CPU and T4 RTFx** come from the onnx-asr benchmark page [S9]:
  - CPU: AMD Ryzen 7 9800X3D, onnxruntime CPU provider, given as "default / int8". The page does not label the default precision; it is presumably fp32.
  - T4: Colab, CUDA provider.
  - Batch size, dataset and onnx-asr version are not stated. Treat the numbers as relative.

| Model | WER 2026-10-02 | WER 2026-07-24 | Leaderboard RTFx (H200) | CPU RTFx default / int8 (9800X3D, onnx-asr) | T4 RTFx (onnx-asr) | Word timestamps | Language ID | Weights licence |
|---|---|---|---|---|---|---|---|---|
| nvidia/parakeet-tdt-0.6b-v2 | **4.70** | 5.39 | 6,025 | 36.8 / 30.5 | 57.6 (TensorRT fp16 237) | Native in NeMo (word, segment, char) [S6]. Token start + duration in sherpa-onnx [L1]. Token start only in onnx-asr [S42] | No; English only | CC-BY-4.0 [S6] |
| nvidia/parakeet-tdt-0.6b-v2 (fast-gpu-asr) | 4.68 | absent | 14,199 | n/a | n/a | as above | No | CC-BY-4.0 [S2] |
| nvidia/parakeet-tdt-0.6b-v3 | 4.86 | 5.66 | 6,076 | 35.4 / 31.4 | 57.5 (TensorRT fp16 232) | Native [S7] | Auto-detects among 25 EU languages; no language label exposed on the card [S7] | CC-BY-4.0 [S7] |
| nvidia/canary-qwen-2.5b | 4.43 | 5.06 | 867 | n/a | n/a | Not mentioned on card [S15] | No; English only | CC-BY-4.0 [S15] |
| nvidia/canary-1b-v2 | 5.71 | 6.39 | 1,825 | 8.3 / 14.9 | 21.4 | Native word and segment [S16] | Source language must be given [S16] | CC-BY-4.0 |
| nvidia/canary-1b-flash | removed | 5.78 | 2,126 (07-24) | n/a | n/a | (not re-verified) | (not re-verified) | CC-BY-4.0 [S3] |
| openai/whisper-large-v3 | 5.78 | 6.55 | 470 | n/a | n/a | Cross-attention DTW (`word_timestamps=True`) or WhisperX alignment | Yes (99 languages; 94.1 % average LID accuracy per [S22]) | Apache-2.0 on HF card [S2]; code MIT [S21] |
| openai/whisper-large-v3-turbo | 6.36 | 7.01 | 797 | 3.9 / 5.4 | 9.2 fp32 / 25.9 fp16 | As large-v3 [S17] | Yes [S17] | MIT [S17] |
| distil-whisper/distil-large-v3.5 | 5.40 | 6.10 | 879 | n/a | n/a | Segment-level; word-level via faster-whisper DTW | No; English only [S18] | MIT [S18] |
| TheStageAI/thewhisper-large-v3-turbo | 4.54 | absent | 1,181 | n/a | n/a | n/a | Yes | CC-BY-4.0, but proprietary SDK, token and encrypted weights [S48] |
| Qwen/Qwen3-ASR-1.7B-hf | **4.31** (best open-weights) | 4.99 | 820 | n/a | n/a | Only through the separate Qwen3-ForcedAligner-0.6B (≤5 min, 11 languages) [S22] | Yes (52 languages and dialects; 97.9 % LID) [S22] | Apache-2.0 |
| AutoArk-AI/ARK-ASR-0.6B (now `Edge0/ARK-ASR-0.6B`; ≈1.15B total parameters) | 4.56 | 5.14 | 663 | n/a | n/a | **Not documented** [S46] | 19 languages; no LID output documented [S46] | Apache-2.0, `trust_remote_code` [S46] |
| OpenMOSS-Team/MOSS-Transcribe-Diarize | 4.64 | absent | 381 | n/a | n/a | **Segment** start/end with speaker labels; no word level [S47] | 50+ languages [S47] | Apache-2.0, `trust_remote_code` [S47] |
| ibm-granite/granite-speech-4.1-2b | 4.62 | 4.90 | 546 | n/a | n/a | Only in the "-plus" variant [S23] | Not mentioned; 6 languages [S23] | Apache-2.0 [S23] |
| ibm-granite/granite-speech-5.0-470m-turboctc | 5.03 | absent | 20,946 | n/a | n/a | Not mentioned [S27] | No; English only | Apache-2.0 (the "-nc" variant is CC-BY-NC-SA) [S2][S27] |
| CohereLabs/cohere-transcribe-03-2026 | 4.67 | 5.20 | 907 | n/a | n/a | **Not supported** [S24] | **No**; language must be given [S24] | Apache-2.0, **gated** (HF `gated: auto`) |
| mistralai/Voxtral-Mini-3B-2507 | 5.54 | 6.01 | 181 | n/a | n/a | Not mentioned [S25] | Yes (8 languages) [S25] | Apache-2.0 |
| kyutai/stt-2.6b-en | 5.57 | 5.74 | 133 | n/a | n/a | Recoverable from stream offsets [S26] | No; English only | CC-BY-4.0 [S26] |
| moonshine-ai/moonshine-streaming-medium (was `usefulsensors/…`) | removed | 5.77 | 2,681 (07-24) | n/a | n/a | Not documented [S28] | No | MIT [S3][S28] |
| microsoft/Phi-4-multimodal-instruct | 5.02 | 5.42 | 163 | n/a | n/a | n/a | n/a | MIT [S2] |

**Context for the table**

- Proprietary APIs top the board, starting at zoom/scribe_v2_pro 3.59 [S2]. Hosted options are covered in section 3.5.
- The "(fast-gpu-asr)" rows came with the 25-09-2026 version ("Parakeet TDT with fast-asr-gpu decoding library") [S1]. I could not identify that library (open question 9).
- **Considered and set aside** (all from [S2]):
  - HojoAI/Hojo-ASR-V1: 4.33, Apache-2.0, 5.2B, RTFx 73. Too large and GPU-bound.
  - bosonai/higgs-audio-v3-stt: 4.39, Apache-2.0, 2.7B, RTFx 111. LLM decoder, GPU-bound.
  - AutoArk ARK-ASR-3B: 4.48, Apache-2.0, RTFx 481. Same remote-code stack as the 0.6B model, and larger.
  - nvidia/nemotron-speech-streaming-en-0.6b: 5.25, NVIDIA Open Model License, RTFx 1,167. Streaming model, a different licence and worse WER.
  - nvidia/parakeet-unified-en-0.6b: NVIDIA Open Model License, not on the board.

---

## 3. Per-model notes

### 3.1 NVIDIA Parakeet TDT 0.6B v2 and v3

**v2** [S6]
- English only, with punctuation and capitalisation.
- Up to 24 minutes in a single pass.
- `transcribe(..., timestamps=True)` returns word, segment and character timestamps.
- CC-BY-4.0, "ready for commercial and non-commercial use".
- The card lists NeMo 2.2 as the runtime.
- Noise table (MUSAN music and noise): average WER 6.05 on clean audio, 8.23 at 5 dB SNR, 11.88 at 0 dB. This measures WER with music *under speech*. It is not a test of false positives on music alone.
- The official repo contains only the `.nemo` file. There is no official transformers or GGUF checkpoint for v2 [S52].

**v3** [S7]
- 25 European languages, with automatic language detection.
- Word and segment timestamps.
- Up to 24 minutes with full attention on an A100, or 3 hours with local attention.
- CC-BY-4.0. The card lists NeMo 2.4.
- Its English WER is slightly worse than v2: 4.86 vs 4.70 [S2].
- The official repo now also ships `model.safetensors` for transformers (`AutoModelForTDT`; timestamps via `processor.decode(..., durations=...)`) and an official `q8_0.gguf` for **NeMo-Speech.cpp** [S7][S45].
- The card still says to install transformers from source. That is stale: `ParakeetForTDT` and `MODEL_FOR_TDT_MAPPING` ship in the transformers **5.19.0** release (2026-10-06) [S44].

**Both models**
- Long-form leaderboard (WER; hardware unstated) [S30]:

  | Model | Average | Without CORAAL |
  |---|---|---|
  | Parakeet v2 | 11.18 | 9.02 |
  | Parakeet v3 | 10.72 | 9.10 |
  | Whisper-large-v3-turbo | 11.01 | 8.72 |

  On long-form, Whisper is competitive.
- Neither card discusses hallucination on silence or music [S6][S7].
- **Licence obligations (CC-BY-4.0, accepted under U4):**
  - Credit NVIDIA as the creator.
  - Link the licence.
  - **State that changes were made**: our weights are an ONNX conversion plus an int8 quantisation. This is the CC-BY-4.0 §3(a)(1)(B) "indicate if You modified" requirement.
  - The ONNX re-exports are also tagged CC-BY-4.0 [S29][S41].
  - The captions themselves are model *output*. Attribution is generally not considered to attach to them, but that is part of the legal check in open question 11.
  - Draft NOTICE text is in section 5.3.

### 3.2 NVIDIA Canary

- **canary-qwen-2.5b** [S15]: best NVIDIA WER (4.43).
  - English only; trained on clips of 40 s or less, and accuracy may degrade on longer input.
  - Needs NeMo ≥2.5 from trunk and PyTorch 2.6+. The card does not mention timestamps.
  - Reports a "hallucination robustness" of 138.1 characters/minute on MUSAN noise.
- **canary-1b-v2** [S16]: 25 languages, word and segment timestamps.
  - Source language must be specified.
  - MUSAN hallucination metric is 134.7 characters/minute.
  - Slower than Parakeet on CPU inside onnx-asr (8.3 vs 36.8 default, 14.9 vs 30.5 int8) [S9].
- **canary-1b-flash** was removed from the current board. Its 2026-07-24 WER of 5.78 is no better than Parakeet v2 [S3].
- Verdict: no advantage over Parakeet for English captions.

### 3.3 Whisper family

- **openai-whisper `20250625`**, released 2025-06-26, MIT [S31]. It is the reference implementation, slowest, and Torch-based.
- **faster-whisper 1.2.1**, released 2025-10-31, MIT [S31][S13].
  - Uses CTranslate2 (4.8.2, 2026-08-31) and onnxruntime (for VAD). No Torch.
  - Commits continue (last push 2026-10-06), but there has been no release since 1.2.1 [S51].
  - Benchmarks [S13], on 13 minutes of audio:
    - large-v2 on an RTX 3070 Ti: fp16 1m03s, or 17 s with `batch_size=8`.
    - "small" on an i7-12700K, 8 threads, int8: 1m42s, or 51 s batched.
  - The `turbo` alias resolves to `mobiuslabsgmbh/faster-whisper-large-v3-turbo`, which now redirects to `dropbox-dash/faster-whisper-large-v3-turbo` (MIT) [S14][S52].
  - `WhisperModel.detect_language(audio, vad_filter=…, vad_parameters=…, language_detection_segments=1, language_detection_threshold=0.5)` returns `(language, probability, all_probabilities)`. This is used for the language-ID gate [S14][L1].
- **whisper.cpp v1.9.5**, released 2026-10-06, MIT [S32]. Built-in Silero VAD in ggml format (`silero-v6.2.0`, `--vad`).
  - Python bindings: `pywhispercpp` 1.5.1 (2026-08-22, MIT) [S31]. How well the bindings expose VAD and timestamps was not checked.
- **large-v3-turbo** [S17]: 809M parameters, with the decoder cut from 32 to 4 layers. MIT. The card itself warns about hallucination and repetition.
- **distil-large-v3.5** [S18]: English only, MIT. About 1.5× faster than turbo, with a CTranslate2 build `distil-large-v3.5-ct2`. Best openly runnable Whisper-family WER (5.40).
- **TheStageAI/thewhisper-large-v3-turbo** [S48]: a fine-tune with 4.54 WER and a CC-BY-4.0 tag. **Excluded.**
  - Access is only "via TheStage AI Python SDK (ElasticModels), the TheStage Apple SDK … or deployed as Docker containers".
  - It needs `thestage config set --access-token`, and the Apple SDK checks the token online.
  - The repo's weight files are encrypted `.enc` blobs per GPU type.
- **WhisperX 3.8.6** (2026-05-25, BSD-2-Clause) [S31][S20].
  - Adds wav2vec2 forced alignment for word timestamps.
  - It pins `torch~=2.8.0` and depends on `pyannote-audio>=4.0.0`, so it is heavy.
  - Words with characters outside the alignment dictionary ("2014.", "£13.60") get no timestamps [S20].

### 3.4 Newer contenders (as of Oct 2026)

- **Qwen3-ASR-1.7B-hf** [S22][S2]: best open-weights WER (4.31), Apache-2.0, LID 97.9 %.
  - The leaderboard row is the transformers-native `-hf` checkpoint, so plain transformers runs it. vLLM is not required.
  - Timestamps need a second model (ForcedAligner-0.6B, ≤5 min).
  - The `qwen-asr` package 0.0.6 pins `transformers==4.57.6` [S31], which conflicts with transformers 5.x.
  - CPU speed is unknown. GPU-oriented.
- **ARK-ASR-0.6B** [S46][S2]: WER 4.56 (better than Parakeet v2), Apache-2.0, 19 languages, RTFx 663.
  - **Size: ≈1.15B parameters in total**, despite the name. The leaderboard lists `Size (B)` = 1.15, and the card says "0.6B decoder LLM parameters, with a separate 0.6B-scale Whisper-style audio encoder"; `model.safetensors` is 2.6 GB [S2][S46].
  - The HF ID `AutoArk-AI/ARK-ASR-0.6B` now redirects to `Edge0/ARK-ASR-0.6B`. The model was created 2026-05-25. **The repo moved from an organisation to an individual account**, so who maintains it is a provenance question to settle before relying on it.
  - Architecture: Whisper-style encoder, MLP adapter and Qwen2 0.6B decoder. It is an LLM-style autoregressive model, so it carries hallucination risk. It needs transformers `trust_remote_code=True` and Torch.
  - Timestamps are **not documented**.
  - Community ONNX, GGUF and MLX conversions exist (OpenVoiceOS ONNX, an Edge0 int8 ONNX, maxffarrell GGUF, leope MLX) but were not evaluated.
  - Verdict: the best Apache-2.0 fallback candidate *if* timestamps can be obtained, for example with an external aligner. It is not a caption model as shipped.
- **MOSS-Transcribe-Diarize 0.9B** [S47][S2]: WER 4.64, Apache-2.0, 50+ languages, up to 90 minutes single-pass. Released 2026-07-09.
  - Joint transcription, diarization and **segment** timestamps (`segment.start, segment.end, segment.speaker, segment.text`).
  - "Can also emit acoustic event annotations", which is relevant to SDH-style cues such as [music] and [laughter] (open question 6).
  - Remote code. Recommended serving is SGLang Omni or vLLM. It also runs in transcribe.cpp ("diarize, segment timestamps") [S43].
  - No word timestamps, so it is not a primary caption model. It is worth a later look for event cues and speaker labels.
- **IBM Granite Speech:**
  - 4.1-2B (4.62) [S23]: punctuation and truecasing "with a simple prompt change" in all 6 languages; a `llama.cpp` / GGUF CPU path (`ibm-granite/granite-speech-4.1-2b-GGUF:Q8_0`); word timestamps only in the `-plus` variant (also in transcribe.cpp [S43]).
  - 4.1-2B-NAR: 4.67, RTFx 2,074.
  - 5.0-470m-turboctc [S27]: 5.03, RTFx 20,946, released 2026-08-25, English only, Apache-2.0. It runs in transformers ≥5.16 and has a GGUF/transcribe.cpp path. Its card documents neither timestamps nor punctuation.
- **Cohere Transcribe 03-2026** [S24]: 4.67, Apache-2.0, **gated**.
  - No timestamps and no language ID.
  - The card says it "is eager to transcribe, even non-speech sounds" and recommends a VAD. **Not suitable for captions.**
- **Voxtral Mini 3B** [S25]: 5.54, Apache-2.0, around 9.5 GB of GPU memory, no documented timestamps.
- **Kyutai stt-2.6b-en** [S26]: 5.57, streaming-oriented, 2.5 s delay, needs `moshi` or PyTorch.
- **Moonshine** [S28]: streaming and on-device oriented.
  - `moonshine-voice` 0.1.5 (2026-08-24). Core dependencies are NumPy and a few small libraries; **Torch appears only in the `lora` and `finetune` extras** [S31].
  - MIT for streaming models. Older non-English legacy models are non-commercial.
  - Word timestamps are not documented.

### 3.5 Hosted ASR (the brief allows cheap hosted options)

- **OpenAI:**
  - Prices per minute: `gpt-4o-mini-transcribe` $0.003, `gpt-transcribe` $0.0045, `whisper-1` / `gpt-4o-transcribe` $0.006 [S49].
  - For 5-minute videos that is $0.015–0.03 per video.
- **Mistral Voxtral API:** an EU vendor; the pricing page says speech is billed per minute, but the rate was not captured [S50].
- **Proprietary leaderboard leaders** (Zoom, ElevenLabs, AssemblyAI, Soniox …) [S1][S2]: not priced here.
- **Set aside for the default because:**
  - Local Parakeet is free per minute and measured at about 14–36× real time on one laptop CPU [L1].
  - Hosted ASR sends user audio to a third party, mostly US-based, which is a GDPR transfer question for an EU operator (U3).
  - Timestamp support varies and was not verified.
- It remains a possible adapter behind the `SpeechRecognizer` port.
- **Claude Haiku** is not an ASR option. I found no official documentation of audio input to the Claude API (open question 10).

---

## 4. Hallucination, VAD and language ID

### 4.1 Evidence

- **Whisper on non-speech** (Barański et al., ICASSP 2025, arXiv 2501.11378v1) [S19]. Two separate experiments:
  1. **Experiment 1: pure non-speech, no VAD.**
     - Data: 301,317 clips from AudioSet, MUSAN, UrbanSound8K and FSD50K, plus noise and silence.
     - Whisper large-v3 hallucinated on **40.3 %** of them (121,378) after delooping.
     - Top phrases were "thank you" (24.8 %) and "thanks for watching" (10.3 %).
     - **All music was removed from this dataset**, as was anything that might contain speech or singing.
  2. **§V / Table VII: speech plus non-speech.**
     - Data: 80 Common Voice speech clips, augmented before, after or overlaid with unseen non-speech sounds.
     - VAD segments were concatenated into one file before inference.
     - "Det. Hall." column, non-overlapped / overlapped:

       | Setup | Detected hallucinations |
       |---|---|
       | Unprocessed | 21.3 % / 20.3 % |
       | WebRTC VAD | 12.5 % / 15.4 % |
       | **Silero VAD** | **0.2 % / 0.2 %** |

     - Silero plus delooping plus a bag-of-hallucinations filter gave the lowest WER (6.5 vs 8.0 for Silero alone).
  - The 40.3 % and 0.2 % figures come from different experiments. **No "40.3 % → 0.2 %" comparison exists.**
- **Music: no evidence.**
  - No cited source measures ASR or VAD behaviour on music-only audio, with or without vocals.
  - The Parakeet MUSAN table [S6] measures WER *with* music under speech, not false positives.
  - Silero's v6.0 release notes list "music with human voice-like instruments" as a known persisting issue [S8].
  - Songs with lyrics will pass the VAD. That is arguably correct, but the quality of lyric transcription is unknown.
  - **This is an explicit acceptance test (T1 below).**
- **Model cards:**
  - Cohere warns that its model transcribes non-speech [S24].
  - Canary publishes a MUSAN characters/minute metric [S15][S16].
  - The Parakeet cards are silent on this [S6][S7].
- **Local smoke check [L1]** (synthetic, so weak evidence):
  - Input: a 60 s **synthetic** music-like signal (harmonic chords, noise "drums" and a vibrato lead line; *not* real music).
  - Silero v6.2 found no speech, in both runtimes.
  - Parakeet v2 without VAD returned an empty string, in both runtimes.
  - **Corrected in round 2.** Round 1 reported "LID on this clip returned en 0.256". That run used `detect_language(vad_filter=True)`; faster-whisper's internal VAD removed the whole clip, so the model classified 30 s of zero padding, not the music [S14]. Re-run with `vad_filter=False` on the actual audio: "ja" 0.213 (en 0.201, km 0.186). On 10 s of digital silence: "cy" 0.282. On linux/amd64 the same three inputs gave en 0.326, ja 0.248 and cy 0.234 [L1].
  - What this shows: `detect_language` **always returns a label** and never signals "no speech", even when its input is empty or non-speech. Its top probability on these non-speech inputs was 0.21–0.33, against ≥ 0.98 on clean speech. LID must therefore only run on VAD speech windows, and the caller must check VAD coverage itself.

### 4.2 VAD options

| VAD | Version (PyPI or release) | Licence | Dependency weight | Notes |
|---|---|---|---|---|
| **Silero VAD** | `silero-vad` 6.2.3, 2026-09-23. Model line v6.2 released 2025-11-06 [S8][S31] | MIT [S8] | The pip package requires torch. Use the ONNX file instead | <1 ms per 30 ms chunk on one CPU thread. **Pin the first-party file:** upstream `snakers4/silero-vad` tag `v6.2` (commit be95df9), `src/silero_vad/data/silero_vad.onnx`, sha256 `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3` (verified locally) [S8][L1]. It is byte-identical to `silero_vad.onnx` in the `istupakov/silero-vad-onnx` mirror (MIT, revision b3e3ee3), which also holds two other variants (`_16k_op15`, `_op18_ifless`). onnx-asr's `load_vad("silero")` **downloads** from that mirror; it is not bundled [S42][S52]. The same file loads in sherpa-onnx [L1]. Also bundled as `silero_vad_v6.onnx` in faster-whisper 1.2.1 and as ggml `silero-v6.2.0` in whisper.cpp [S14][S32] |
| pyannote segmentation-3.0 | `pyannote.audio` 4.0.7, 2026-06-30 [S31] | Weights MIT but **gated** (contact sharing) [S34] | Torch, heavy | Also available as an ONNX export in onnx-asr [S12] |
| webrtcvad | `webrtcvad` 2.0.10 (2017-01-07); `webrtcvad-wheels` 2.0.14.post1 (2026-10-02) [S31] | MIT | Tiny C extension | Left 12.5 % detected hallucinations in [S19] Table VII. Not recommended |
| NeMo Frame VAD MarbleNet v2.0 | Card: "Runtime Engine(s): NeMo-2.3.0"; install `nemo_toolkit['asr']` [S33] | NVIDIA Open Model License (commercial OK) [S33] | NeMo/Torch, or ONNX export | 91.5K parameters, 20 ms frames. No published comparison with Silero |
| faster-whisper `vad_filter` | 1.2.1 | MIT | onnxruntime | Uses the bundled Silero v6 ONNX. Defaults below |

**VAD segmentation behaviour per runtime (matters for cue boundaries)**

| | onnx-asr 0.12.0 `.with_vad()` [S42] | sherpa-onnx 1.13.8 `VoiceActivityDetector` [S39] | faster-whisper 1.2.1 `VadOptions` [S14] |
|---|---|---|---|
| threshold | 0.5 (`neg_threshold` = threshold − 0.15) | 0.5 | 0.5 |
| min silence | 100 ms | 0.5 s | 2000 ms |
| min speech | 250 ms | 0.25 s | 0 ms |
| speech pad | 30 ms | ≈0.31 s implicit lead-in (2 × 32 ms window + 250 ms min speech), 0 s tail (end placed at silence onset) [S39] | 400 ms |
| max speech | 20 s | 20 s | ∞ |
| **What happens past max** | **Hard cut at fixed 20 s offsets** (`while end - start > max_speech_duration: … start += max_speech_duration`). Locally it split a continuous 55 s utterance at exactly 12.48 → 32.48 s, mid-phrase [L1] | **Soft, unbounded**: once the buffer exceeds max, threshold rises to 0.9 and min silence drops to 0.1 s, so it cuts at the next low-probability frame *if one comes*. There is no upper bound: the buffer doubles when full ("Overflow! … No data loss!"), and a continuous TTS utterance stayed one 55.6 s segment [S39][L1]. The Python binding exposes only a boolean `is_speech`, no frame probabilities [S53] | n/a |

**Consequence: scenewise owns segmentation, with its own Silero loop.**
- scenewise runs the Silero v6.2 ONNX model itself, in a small loop on pip `onnxruntime` (512-sample hop, 64-sample context, recurrent state). onnx-asr's `models/silero.py` (MIT) is a ready template to vendor, with its MIT notice; depending on onnx-asr in prod just for this is not worth it. The loop ran at about 0.07 s per 30 s of audio on one thread [L1].
- It turns frame probabilities into speech runs (threshold 0.5, hysteresis, minimum speech and silence, small pads), then caps segments at about 30 s by cutting at the lowest-probability frame inside the last few seconds before the cap, never at a fixed offset.
- **sherpa-onnx's VAD is not used.** It cannot implement this rule: no frame probabilities reach Python, and it has no upper bound on segment length [S53][S39]. Its soft cut is therefore no longer a factor in the runtime choice.
- It passes the segments to the `SpeechRecognizer`. That keeps cue boundaries independent of the runtime.
- Why not one single pass: a 334 s utterance decoded in one pass needed **5.1 GB (onnx-asr) / 6.6 GB (sherpa-onnx) peak RSS** on macOS CPU [L1]. Unbounded segments are a memory risk on Cloud Run. The sizing figure for ≤30 s segments is in section 6.2.

### 4.3 Whisper decoding settings (fallback only)

Defaults below are identical in openai-whisper 20250625 and faster-whisper 1.2.1 `WhisperModel.transcribe` [S14][S21].

| Setting | Default | Recommendation |
|---|---|---|
| `vad_filter` | False (`WhisperModel`); True (`BatchedInferencePipeline`) | **True**. Consider `min_silence_duration_ms` ≈ 500 (the README example) instead of 2000 |
| `condition_on_previous_text` | True | **False**. It stops loops from spreading across windows. The batched pipeline hard-codes False [S14] |
| `no_speech_threshold` | 0.6 | Keep; tune on our data |
| `log_prob_threshold` | -1.0 | Keep |
| `compression_ratio_threshold` | 2.4 | Keep; it catches repetition loops |
| `hallucination_silence_threshold` | None | e.g. 2.0 s. Only works with `word_timestamps=True`. **The batched pipeline hard-codes `None`**, so the setting is silently ignored there [S14] |
| `temperature` | fallback schedule | Keep the fallback |
| Post-filter | n/a | Drop segments matching a bag-of-hallucinations list ("thank you", "thanks for watching", …) when VAD speech coverage is low [S19] |

### 4.4 Language-ID gate (specification)

> **Superseded in part by q11/U16 (2026-10-08).** Step 3's model is now an in-house onnxruntime Whisper-tiny adapter,
> not faster-whisper, and step 4's rule is ≥ 1.0 s of VAD speech and p(en) ≥ 0.5 per window (white noise scores an
> argmax p of 0.48–0.57); see [q11](q11-asr-without-pyav.md) §2.3, §3.5.

Parakeet v2 transcribes any speech as English. In the local test, German TTS came out as invented pseudo-English [L1]. The gate is therefore mandatory.

1. **Input: VAD speech only.** Never run LID on the whole track, and call `detect_language(window, vad_filter=False)` on scenewise's own VAD windows. `detect_language` never signals "no speech": with `vad_filter=True` on a clip its VAD fully removed, it classified 30 s of zero padding and still returned "en" 0.256; on the raw synthetic music it returned "ja" 0.213; on digital silence "cy" 0.282 [S14][L1]. Running faster-whisper's VAD a second time on windows that scenewise already cut adds nothing and risks the empty-input case.
2. **Windows.** Merge adjacent VAD segments into LID windows of 3–30 s. Whisper's LID reads one 30 s window. Segments shorter than 1 s that cannot be merged are labelled "unknown".
3. **Model.** `faster-whisper` 1.2.1 `WhisperModel("tiny", compute_type="int8").detect_language(window, vad_filter=False)`, using `Systran/faster-whisper-tiny` (MIT, revision d90ca5f, about 76 MB) [S14][S52].
   - It returns a full probability list. sherpa-onnx's Whisper LID returns only a language code with no probability, so it cannot be thresholded [S38].
   - `base` (`Systran/faster-whisper-base`, about 145 MB) is the step up if `tiny` misfires on Expause clips.
   - Locally, `tiny` took 0.4–0.9 s per clip and gave en 0.996 and de 0.999 on clean TTS, and en 0.979 on a 30 s English segment [L1].
   - Whisper large-v3 averages 94.1 % LID accuracy [S22]. `tiny` will be lower; its accuracy on short user clips is open question 5.
   - It reuses the fallback's dependency set (ctranslate2, av, tokenizers), so it adds no new stack.
4. **Per-window label.** scenewise takes the returned argmax language and its probability p. If p ≥ 0.5 the window gets that label; otherwise it is "unknown".
   - **0.5 is scenewise's own starting value**, not a faster-whisper default. (faster-whisper's `language_detection_threshold` is an early-stop criterion across several 30 s segments, `>` not `≥`, and has no effect with `language_detection_segments=1` [S14].)
   - Why 0.5 is a reasonable start: in the local runs, clean speech scored 0.98–0.999 and every non-speech input scored 0.21–0.33 [L1]. 0.5 sits between the two groups. Real short, noisy or accented clips will fall in between, so T3 tunes it.
   - **"unknown" windows are not captioned** in the default rule. The round-1 idea of rescuing them with Parakeet's mean token log-probability is **not part of the rule**. One local data point is encouraging: English TTS gave a mean token log-probability of −0.012 and the German TTS pseudo-English −0.477 [L1]. That is one synthetic pair, so the separation is a T3 measurement, not a rule.
5. **Video-level rule (mixed or code-switched language).** Let `en_s` be the total speech duration in windows labelled English.
   - **`en_s` ≥ about 2 s:** emit a track with cues for the English windows only, **whatever share the other languages have**. If any window is non-English or unknown, set `partial_language: true` and list the detected languages and their durations in metadata. (An SDH-style "[speaking German]" cue is a later option.)
   - **`en_s` < about 2 s:** emit **no track**. Set `language_unsupported: <dominant language>`, or `language_unknown` if no window got a confident label.
   - This replaces the round-1 share rule (E ≥ 0.5), which dropped all captions for a video with 45 % English speech and kept them at 55 %. That cut-off had no Expause use case behind it. The absolute minimum only stops one stray English word from producing a track.
   - Both numbers (0.5 and about 2 s) are starting points, to be tuned on Expause clips (T3). Whether a mostly non-English video *should* get partial English captions is a product decision (open question 13).
6. **Later alternative:** if EU-language captions are wanted rather than suppressed, swap the model to **parakeet-tdt-0.6b-v3**. Its English WER is 4.86 vs 4.70, it uses the same runtimes and the same licence, and the gate becomes a routing decision. v3 does not expose its detected language [S7], so Whisper LID would still be needed for labelling.

### 4.5 Policy for scenewise (Parakeet primary)

1. Decode the audio to 16 kHz mono, then run Silero VAD v6.2 in scenewise's own loop (threshold 0.5).
2. If total speech is below about 1 s (to be tuned), emit **no caption track** and set `no_speech`.
3. Segment as described in section 4.2: scenewise's own Silero loop, lowest-probability cuts, segments of about 30 s or less.
   - Optional: run the audio tagger (section 1) on VAD-negative stretches longer than a few seconds and set a `music` flag or a "[music]" cue (T1 decides).
4. Run the language-ID gate (section 4.4).
5. Transcribe the English segments with Parakeet v2 through the `SpeechRecognizer` port. The port returns tokens with start times, an end hint where the runtime provides one (sherpa-onnx: start + predicted TDT duration, 0–0.32 s; onnx-asr: none, so the next token's start), and per-token log-probabilities.
6. Group tokens into words (SentencePiece "▁" / leading-space boundary). A word's end is its last token's end hint, extended to the next pause or a minimum hold, because a TDT duration is a predicted frame advance, not a measured word end. Build WebVTT cues of at most about 42 characters × 2 lines and at most about 7 s, breaking at punctuation or pauses. Drop low-confidence or very short isolated segments.

---

## 5. Runtimes and versions

### 5.1 Runtime comparison for Parakeet v2

| Runtime | Version (date) | Licence | Torch? | Parakeet v2 weights | Timestamps | VAD | Maintenance [S51] | Verdict |
|---|---|---|---|---|---|---|---|---|
| **sherpa-onnx** | **1.13.8** (2026-09-10) [S38] | Apache-2.0 | No. Bundles its own onnxruntime (the dylib carries "1.28.2") [L1] | `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8`, CC-BY-4.0, revision 1ab9323 (2025-08-16). Encoder 652 MB. fp16 and fp32 variants exist [S40][S41] | **Token start + TDT duration** (`result.timestamps`, `result.durations`). `result.words` is empty for this model [L1] | Silero and TEN VAD; soft but unbounded split past max, boolean output only [S39][S53]. **Not used by scenewise** | 15.2k stars, 1,752 forks; releases about every 1–2 weeks through September (1.13.6 2026-08-18, 1.13.7 2026-09-01, 1.13.8 2026-09-10), none since (4 weeks; last push 2026-10-05). Commits are concentrated: csukuangfj 1,624, next contributor 18. Code is © Xiaomi Corp. (authors' employer). Weights live in the personal HF account `csukuangfj` | **Primary (ASR only)** |
| **onnx-asr** | **0.12.0** (2026-07-15) [S11] | MIT | No (NumPy core; extras add onnxruntime and huggingface-hub) | `istupakov/parakeet-tdt-0.6b-v2-onnx`, CC-BY-4.0, revision 0bbb45a (2026-02-17). int8 encoder 652 MB; fp32 2.4 GB [S29][S52] | **Token start only** (`TimestampedResult.timestamps`, "Tokens timestamp list"). The TDT duration is used for decoding but not returned [S42] | Silero (downloaded) and pyannote; **hard 20 s cut** [S42] | 382 stars; istupakov 215 commits, others ≤9; last commit 2026-08-16; releases 0.11.0 (2026-03-23) → 0.12.0. Excludes onnxruntime 1.24.1, 1.25.*, 1.26.0 [S11] | **Tested second.** Small and vendorable |
| transcribe.cpp (`transcribe-cpp`) | 0.3.1 (PyPI and GitHub, 2026-10-04) [S43] | MIT | No (ggml; CPU, Metal, CUDA, Vulkan) | `handy-computer/parakeet-tdt-0.6b-v2-gguf`, CC-BY-4.0, "Validated against the NeMo reference" [S43] | Token timestamps | Not documented in the README | Created 2026-04-07; 2.0k stars; three releases in two weeks. The bindings README still says "Status: in development" | Watch. Too young for prod |
| HF transformers | 5.19.0 (2026-10-06) [S44] | Apache-2.0 | **Yes** | v3 official `model.safetensors`; for v2 only third-party conversions (e.g. `nithinraok/parakeet-tdt-0.6b-v2-hf`, mis-tagged Apache-2.0; the CC-BY-4.0 obligations still apply) [S7][S52] | Token + `durations` via `processor.decode` [S7] | None | Hugging Face | Reference/eval only |
| NeMo (`nemo-toolkit`) | 3.0.0 (2026-08-07) [S31] | Apache-2.0 | **Yes** (torch ≥2.6) | Official `.nemo` | **Native word / segment / char** [S6] | Separate (MarbleNet) | NVIDIA; NVIDIA-NeMo/Speech has 18.6k stars, active | **Timestamp/WER oracle** in offline eval only |
| NeMo-Speech.cpp | v0.2.0 (2026-10-02), CLI, no PyPI [S45] | Apache-2.0 | No (ggml) | Lists **v3** (official GGUF), not v2 | Subtitles mentioned | Silero | NVIDIA, created 2026-07-15 | Watch (relevant if moving to v3) |
| parakeet-mlx | 0.5.3 (2026-10-01) [S35] | Apache-2.0 | No (MLX) | MLX conversions | Word, with VTT output | None | Single maintainer | Dev eyeballing only |

**Why sherpa-onnx is the primary, and why not onnx-asr (re-decided in round 2)**

After round 2, two of the three round-1 arguments fell away:
- **VAD splitting is no longer a factor.** scenewise runs its own Silero loop (section 4.2), so neither runtime's VAD is used.
- **"No onnxruntime pin juggling" was mostly illusory.** faster-whisper 1.2.1 requires `onnxruntime>=1.14,<2` [S31], and the Silero loop needs it too. So pip `onnxruntime` 1.30.0 is always installed, and sherpa-onnx adds a second, bundled onnxruntime 1.28.2.
  - **Is that a problem? Tested: no.** sherpa-onnx links its own copy by name. macOS: `_sherpa_onnx…so` needs `@rpath/libonnxruntime.dylib` from `sherpa_onnx/lib/`, while pip onnxruntime's is `@rpath/libonnxruntime.1.dylib` (file `libonnxruntime.1.30.0.dylib`); the install names differ. Linux (manylinux x86_64 wheels): sherpa's `libonnxruntime.so` has SONAME `libonnxruntime.so` and is what `_sherpa_onnx…so` needs; pip onnxruntime's `libonnxruntime.so.1.30.0` has SONAME `libonnxruntime.so.1`, and its Python module `onnxruntime_pybind11_state…so` has **no** `DT_NEEDED` on any libonnxruntime (the runtime is linked into it). So the dynamic loader never confuses the two [L1].
  - Loading pip onnxruntime 1.30.0, sherpa-onnx 1.13.8 and faster-whisper 1.2.1 in one process, in both import orders, worked on macOS arm64 and linux/amd64 and gave the same outputs [L1]. Keep this as a CI smoke test (both import orders, linux/amd64).
  - The remaining cost is size: two copies of the onnxruntime library in the image.

What remains:
- **For sherpa-onnx:** TDT durations and per-token log-probabilities come out of the box, and the project has the larger user base (15.2k stars) and an employer (Xiaomi) behind its main author.
  - The durations are model-predicted frame advances of 0–0.32 s, not measured word ends (section 1), but they are still a better cue-end hint than nothing.
  - It also offers audio tagging in the same runtime (section 1).
- **For onnx-asr:** it is pure Python, MIT and vendorable; it needs no second onnxruntime; and its decoder already computes the TDT `step`, so returning durations is a small patch.
- **Equal:** speed (both about 30–44 RTFx on short clips on an Apple M4 CPU, 14–17 RTFx for a single 334 s pass) [L1]; bus factor (one dominant committer each).

**Decision: sherpa-onnx primary, onnx-asr second, unchanged, but on a thin margin.** The deciding factor is unpatched durations and log-probabilities. Both runtimes run the same Parakeet v2 weights behind the `SpeechRecognizer` port, and CI runs both on the same fixtures, so switching is cheap. Whether to flip to a vendored, patched onnx-asr to save the second onnxruntime and the native dependency is open question 14.

**Other runtime notes**
- **Platform defaults.** On macOS, onnx-asr's default providers include **CoreML**. In the first run that made a 60 s clip take 54.7 s (RTFx 1.1) instead of 1.6–1.9 s on `CPUExecutionProvider` [L1]. Always pass `providers=["CPUExecutionProvider"]` (or the CUDA provider) explicitly, also for the Silero loop.
- **GPU builds.** The PyPI `sherpa-onnx-core` 1.13.8 wheels are CPU-only. CUDA builds come only from k2-fsa's own wheel index (for example `sherpa_onnx-1.13.8+cuda12.cudnn9.onnxruntime1.28.2-cp312-cp312-linux_x86_64.whl`), not PyPI [S54]. No sherpa-onnx GPU throughput was measured.
- **Bus factor.** Both projects are dominated by one committer. The "team-backed" description of sherpa-onnx in review round 1 overstates it, but the code is © Xiaomi Corp., so the main author has an employer behind the work.
  - sherpa-onnx released every 1–2 weeks through September, with none since 1.13.8 (4 weeks) while commits continue.
  - Its weights live in a personal HF account (`csukuangfj`), and so do onnx-asr's (`istupakov`). **Mirror every pinned weight file into scenewise-controlled storage** (an object-store bucket or a scenewise HF org) and verify sha256 on download.
  - Exits: sherpa-onnx is native code, so "vendor if abandoned" does not apply. The options are a source build (Apache-2.0, CMake) or switching to the onnx-asr adapter. onnx-asr can be vendored.

### 5.2 Pinned versions

> **Superseded in part by q11/U16 (2026-10-08).** faster-whisper is the fallback only, in the opt-in `asr-whisper`
> extra (PyAV, GPL x264/x265: [q10](q10-pyav-ffmpeg-licence.md)); the LID weights are `onnx-community/whisper-tiny` @
> `ff41770` fp32 ONNX, not `Systran/faster-whisper-tiny` ([q11](q11-asr-without-pyav.md) §2.3, §4).

From the PyPI JSON API, GitHub releases and the HF model API, read 2026-10-08 [S31][S52].

| Package or artefact | Pin | Released | Licence | Torch? | Role |
|---|---|---|---|---|---|
| **sherpa-onnx** | **==1.13.8** (with `sherpa-onnx-core==1.13.8`) | 2026-09-10 | Apache-2.0 | No | Primary ASR runtime (and optional audio tagging); its VAD is not used. Bundles onnxruntime 1.28.2. PyPI wheels are CPU-only; cp310–cp314, macOS arm64/x86_64, manylinux x86_64/aarch64 |
| Parakeet v2 int8 (sherpa) | `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` @ `1ab9323565ddb038682214b292f588070a538ce2` | 2025-08-16 | CC-BY-4.0 | — | Primary weights. sha256 prefixes (local download): encoder `a32b12d17bbbc309…`, decoder `b6bb64963457237b…`, joiner `7946164367946e7f…`, tokens `ec182b70dd42113a…` [L1] |
| **onnx-asr** | **==0.12.0** | 2026-07-15 | MIT | No | Second runtime (CI-tested) |
| onnxruntime | ==1.30.0 | 2026-09-10 | MIT | No | **Always installed:** scenewise's Silero loop, faster-whisper (LID; it requires `onnxruntime>=1.14,<2`), and onnx-asr. **Requires Python ≥3.11** (fine for the 3.12 floor). Co-exists with sherpa's bundled 1.28.2 (tested, section 5.1) |
| Parakeet v2 int8 (onnx-asr) | `istupakov/parakeet-tdt-0.6b-v2-onnx` @ `0bbb45a3365852604aef28b538a8f066f4ccaa85` | 2026-02-17 | CC-BY-4.0 | — | Second-runtime weights |
| Silero VAD v6.2 ONNX | Upstream `snakers4/silero-vad` tag `v6.2` (commit `be95df9152c0d7618fa1edfeb296fc3dae32376f`), `src/silero_vad/data/silero_vad.onnx`, sha256 `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3` | 2025-11-06 | MIT | — | scenewise's own VAD loop. Byte-identical to `istupakov/silero-vad-onnx` @ b3e3ee3 `silero_vad.onnx` [S8][L1] |
| **faster-whisper** | **==1.2.1** | 2025-10-31 | MIT | No | LID gate + fallback ASR. Depends on ctranslate2, tokenizers, onnxruntime, av, huggingface-hub |
| ctranslate2 | ==4.8.2 | 2026-08-31 | MIT | No | |
| Whisper tiny (CT2) | `Systran/faster-whisper-tiny` @ `d90ca5fe260221311c53c58e660288d3deb8d356` | 2023-11-23 | MIT | — | LID. `model.bin` sha256 prefix `dcb76c6586fc06cb…` [L1] |
| Whisper large-v3-turbo (CT2) | `dropbox-dash/faster-whisper-large-v3-turbo` @ `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf` | 2025-11-05 | MIT | — | Fallback ASR |
| Audio tagger (optional) | `k2-fsa/sherpa-onnx-zipformer-small-audio-tagging-2024-04-15` @ `c24f9d0fdf7d0b8c0c4f9733aa0cac51fda10c95` (`model.int8.onnx`, 27 MB, sha256 prefix `69304b8a1b96bbe6…`) | 2024-04-15 | Apache-2.0 (card) | — | Music-bed flag candidate (T1). Trained on AudioSet [S55][L1] |
| numpy | ==2.5.3 | 2026-09-06 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | — | Requires Python ≥3.12 |

**Other packages (not chosen)**

| Package | Version | Released | Licence | Torch? | Notes |
|---|---|---|---|---|---|
| transcribe-cpp | 0.3.1 | 2026-10-04 | MIT | No | Native wheel `transcribe-cpp-native` |
| silero-vad | 6.2.3 | 2026-09-23 | MIT | **Yes** (torch ≥1.12) | Use the ONNX file instead |
| parakeet-mlx | 0.5.3 | 2026-10-01 | Apache-2.0 | No (MLX) | Apple GPU; `--output-format vtt` [S35] |
| nemo-toolkit | 3.0.0 | 2026-08-07 | Apache-2.0 | Yes (≥2.6) | Eval oracle |
| transformers | 5.19.0 | 2026-10-06 | Apache-2.0 | Yes (extra) | Ships `ParakeetForTDT` [S44] |
| whisperx | 3.8.6 | 2026-05-25 | BSD-2-Clause | Yes (pinned ~=2.8.0) | Python <3.14 |
| openai-whisper | 20250625 | 2025-06-26 | MIT | Yes | |
| pywhispercpp | 1.5.1 | 2026-08-22 | MIT | No | whisper.cpp v1.9.5 (2026-10-06) |
| mlx-whisper | 0.4.3 | 2025-08-29 | MIT | Yes (dependency) | |
| torch | 2.14.1 | 2026-09-30 | `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` | — | |
| moonshine-voice | 0.1.5 | 2026-08-24 | MIT | No (torch only in `lora`/`finetune` extras) | |
| qwen-asr | 0.0.6 | 2026-01-30 | Apache-2.0 | Yes | Pins `transformers==4.57.6` |

Locally, `faster-whisper` 1.2.1 resolved `huggingface-hub` to 1.33.0 even though 2.1.1 is the latest [L1]. Pin it explicitly in the lock file.

**Mirror the weights.** Every pinned weight file above lives in an account scenewise does not control, several of them personal (`csukuangfj`, `istupakov`). Copy each pinned file into scenewise-controlled storage (an object-store bucket or a scenewise HF org), record the full sha256 in the lock manifest, and verify it at image build. Bake the files into the image; nothing is downloaded at runtime.

### 5.3 Licence summary and NOTICE

> **Superseded in part by q11/U16 (2026-10-08).** The language-ID model is OpenAI Whisper tiny (MIT) as converted to
> ONNX by onnx-community, whose repo states no licence ([q11](q11-asr-without-pyav.md) §1, §5).

- Code: sherpa-onnx Apache-2.0 (bundled onnxruntime MIT); onnx-asr MIT (and the vendored Silero loop, if taken from its `models/silero.py`); onnxruntime MIT; faster-whisper and CTranslate2 MIT.
- Weights: Parakeet v2 CC-BY-4.0 (attribution and indication of changes); Silero v6.2 MIT; Whisper tiny and large-v3-turbo MIT (OpenAI weights, CTranslate2 conversions also tagged MIT); audio tagger (optional) Apache-2.0.
- MIT and Apache-2.0 require their notices to travel with copies, so the NOTICE must carry them **if the weights are baked into a distributed image** (they are, section 5.2).
- **Draft NOTICE entries:**

  > **Speech recognition model.** NVIDIA Parakeet TDT 0.6B v2 (https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2), © NVIDIA Corporation, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). **Modified:** converted from NeMo to ONNX and quantised with dynamic int8 weight quantisation (ONNX Runtime `quantize_dynamic`) by the sherpa-onnx project (https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8; conversion script https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8/scripts/nemo/parakeet-tdt-0.6b-v2). [Alternative runtime: converted to ONNX and int8-quantised by istupakov, https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx.] No warranty.
  >
  > **Voice activity detection model.** Silero VAD v6.2 (https://github.com/snakers4/silero-vad), Copyright (c) 2020-present Silero Team, MIT License. [Full MIT licence text.]
  >
  > **Language identification and fallback ASR models.** OpenAI Whisper tiny and large-v3-turbo weights (https://github.com/openai/whisper), Copyright (c) 2022 OpenAI, MIT License; CTranslate2 conversions `Systran/faster-whisper-tiny` and `dropbox-dash/faster-whisper-large-v3-turbo` (MIT). [Full MIT licence text.]
  >
  > [If the audio tagger is shipped: `sherpa-onnx-zipformer-small-audio-tagging-2024-04-15` by the k2-fsa project, Apache License 2.0.]

  - The sherpa model docs say "This model is converted from https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2" and link the conversion script [S40].
  - The conversion script at tag v1.13.8 calls `onnxruntime.quantization.quantize_dynamic`, with `QuantType.QUInt8` weights for the encoder and `QInt8` for the decoder and joiner [S56]. The link is pinned to the tag, not `master`.
  - The istupakov card says "converted to ONNX format for onnx-asr" and includes the NeMo export code [S29]. Its quantisation method was not checked, so that entry says "int8-quantised" generically.

---

## 6. Recommendation for dev and prod

All ASR goes through a `SpeechRecognizer` port:
- Input: 16 kHz mono float32 segments.
- Output: tokens with start seconds, an optional end hint (sherpa-onnx: start + predicted TDT duration), and log-probabilities.

Adapters:
- `SherpaOnnxParakeetRecognizer` (primary).
- `OnnxAsrParakeetRecognizer` (second, run in CI on the same fixtures).
- `FasterWhisperRecognizer` (fallback).

VAD (scenewise's own Silero loop on pip onnxruntime), segmentation, the LID gate, the optional music tagger and cue building live in scenewise, not in the adapters.

### 6.1 Development (macOS Apple Silicon laptop, CPU)

- **Model:** `parakeet-tdt-0.6b-v2` int8, pinned revisions from section 5.2.
- **Runtime:** `sherpa-onnx==1.13.8` (`OfflineRecognizer.from_transducer(..., model_type="nemo_transducer")`), ASR only.
- **VAD:** scenewise's Silero v6.2 loop on `onnxruntime==1.30.0` with `providers=["CPUExecutionProvider"]`.
  - Measured on an M4 CPU: about 32 RTFx on a 12.6 s clip with 4 threads, and 13.8 RTFx for a single 334 s pass [L1].
- **Second runtime:** `onnx-asr==0.12.0` with `onnxruntime==1.30.0`, passing `providers=["CPUExecutionProvider"]` explicitly (section 5.1). Measured 30–36 RTFx [L1].
- **LID:** `faster-whisper==1.2.1` with `tiny` int8.
- **Optional:** `parakeet-mlx` 0.5.3 for quick VTT eyeballing on the Apple GPU. It is a different runtime from prod.

### 6.2 Production (Cloud Run, EU region)

- **Default: Cloud Run CPU, with the same model and runtime as dev.**
  - At about 14–36 RTFx on one modern laptop CPU [L1], a 5-minute video needs roughly 10–20 s of compute. This is an extrapolation; Cloud Run vCPU throughput is unmeasured (open question 2).
  - CPU instances scale to zero cheaply. Speech-free videos exit after VAD alone.
  - **Memory: about 1.3 GB peak RSS per worker process** with Parakeet int8 (sherpa, 4 threads), Silero, Whisper tiny int8 and the audio tagger all loaded, after one 30 s speech segment through VAD, LID and ASR. Measured on linux/amd64 (Docker, `python:3.12-slim`, emulated on Apple Silicon, so the timings from that run are meaningless; the memory figure is not affected): 1.04 GB resident after loading, 1.33 GB peak after the segment [L1]. macOS arm64 gave 1.8–2.3 GB `ru_maxrss` for the same steps. A 2 GiB Cloud Run instance is the floor and 4 GiB leaves headroom; confirm on Cloud Run (open question 2).
  - Run the audio tagger in chunks of about 10 s or less: one 60 s call raised peak RSS from 1.5 to 2.6 GB [L1].
  - The 5.1–6.6 GB peaks for one 334 s single pass [L1] are only the reason for the ≈30 s cap, not a sizing figure.
  - Bake the model files into the image from scenewise's mirror, verifying sha256 (section 5.2). onnx-asr would otherwise download the Silero VAD and Parakeet weights from the hub at first use [S42].
- **When to use GPU:** only if volume justifies it [S36]:
  - GPU services need **instance-based billing**, and "minimum instances are charged at the full rate even when idle".
  - **Zonal redundancy is on by default**, "with additional cost per GPU second".
  - L4 needs at least 4 CPU / 16 GiB.
  - L4 is in six regions, including **europe-west1 (Belgium) and europe-west4 (Netherlands)**; asia-south1 is by invitation only. RTX PRO 6000 is in four regions, including europe-west4.
  - GPU services can scale to zero, and drivers start in about 5 s.
  - On a T4, onnx-asr Parakeet reaches 57.6 RTFx on CUDA and 237 with TensorRT fp16 [S9]. The leaderboard's "(fast-gpu-asr)" stack reaches 14,199 RTFx on an H200 [S2].
  - sherpa-onnx on GPU needs the CUDA wheels from k2-fsa's own index, not PyPI, and no sherpa-onnx GPU throughput was measured [S54]. On GPU, onnx-asr with `onnxruntime-gpu` from PyPI may be the simpler adapter.
- **Why not Whisper as the primary:**
  - Higher WER: turbo 6.36 and large-v3 5.78 vs 4.70 [S2].
  - Slower: 5.6–9× slower inside onnx-asr on CPU [S9]. faster-whisper int8 is untested against Parakeet (open question 3).
  - Documented non-speech hallucination [S17][S19].
- **Why not Qwen3-ASR, ARK-ASR or MOSS despite better WER:**
  - They are autoregressive LLM-decoder models on a Torch stack.
  - Timestamps need an extra aligner (Qwen), are undocumented (ARK), or are segment-level only (MOSS) [S22][S46][S47].
  - ARK-ASR-0.6B (Apache-2.0) is the first alternative to test if CC-BY attribution ever becomes a problem.

---

## 7. Open questions and test plan

**Test plan (acceptance before shipping)**

- **T1, music and no-speech.** Assemble a clip set:
  - (a) instrumental music beds;
  - (b) music with vocals or lyrics;
  - (c) music under speech;
  - (d) ambient noise and silence;
  - (e) real Expause speech-free clips, with permission.

  For each, measure the Silero speech ratio and whether Parakeet emits non-empty text, with and without VAD. Compare with Whisper-turbo using the [S19] counting method. Also run the sherpa-onnx audio tagger on the VAD-negative stretches and measure how well its "Music" score separates (a)/(b) from (d). Locally it scored digital silence "Music" 0.33–0.37, as high as or above "Silence" [L1], so the flag needs an energy (RMS) gate as well as a score threshold. Use only clips with a known licence, such as MUSAN music (CC) or the FMA subset with per-track licences; check each.
- **T2, timestamps.** On a speech fixture, compare cue start and end times from sherpa-onnx (start + predicted duration, 0–0.32 s per token and sometimes 0) and onnx-asr (start only) against NeMo 3.0.0's native word timestamps. Tune the cue builder's end extension (to the next pause, or a minimum hold).
- **T3, LID.** Run `tiny` and `base` on real Expause clips (short, noisy, accented, code-switched) and tune the p ≥ 0.5 window threshold and the ≈2 s English minimum in section 4.4. Also measure Parakeet's mean token log-probability on English vs non-English speech windows, and check whether it separates them at all. Locally one TTS pair gave −0.012 (English) vs −0.477 (German) [L1]; that is not enough to build a rule on.
- **T4, process smoke test (CI, linux/amd64).** Load pip onnxruntime, sherpa-onnx and faster-whisper in one process in both import orders, run one fixture through Silero, LID and both ASR adapters, and record peak RSS. Fail the build if outputs differ from the golden file or peak RSS exceeds the instance budget.

**Open questions**

1. **Parakeet on non-speech and music:** there is no published rate. The local synthetic test was clean [L1]; real music is untested (T1).
2. **Cloud Run CPU throughput:** what RTFx does sherpa-onnx Parakeet reach on 2, 4 or 8 vCPUs, and what do cold start and model load add? Is int8 WER acceptable compared with fp32 (sherpa also ships an fp16 export) [S40]? Cloud Run prices were not captured.
3. **Head-to-head with the fallback:** Parakeet (sherpa-onnx int8) vs faster-whisper int8 `turbo` / `distil-large-v3.5` on the same CPU. The onnx-asr ratios [S9] do not cover CTranslate2.
4. **Word grouping and cue boundaries:** how accurate are the word times rebuilt from sherpa's token start + predicted duration (T2)? What are the right segmentation cap and the search window for the lowest-probability cut (section 4.2)?
5. **LID accuracy on short user clips:** `tiny` vs `base`; how often "unknown" occurs; thresholds (T3). What does Parakeet v2 do on accented English (false non-English)?
6. **Music, lyrics and event cues:** do we want lyric captions, and how good is Parakeet on sung vocals? Should captions carry SDH-style event cues ([music], [laughter])? If so, evaluate the sherpa-onnx AudioSet tagger first (same runtime, Apache-2.0, 27 MB; T1), then MOSS-Transcribe-Diarize's acoustic-event output [S55][S47].
7. **ARK-ASR-0.6B (≈1.15B total) as an Apache-2.0 alternative:** who maintains it now that the repo moved from `AutoArk-AI` to the `Edge0` account? Can its timestamps be recovered (an aligner, or its decoder's audio positions)? How does it behave on silence and music? What is its CPU speed via the community ONNX/GGUF builds?
8. **Granite-speech-5.0-470m-turboctc** (Apache-2.0, 5.03 WER, very fast): punctuation, casing, timestamps and CPU speed are undocumented.
9. **"fast-gpu-asr":** which decoding library does the leaderboard's 25-09-2026 entry refer to? It matters only if we go GPU.
10. **Claude audio input:** I found no official statement that the Claude API accepts audio. Irrelevant with local ASR, but unverified.
11. **CC-BY-4.0:** legal sign-off on the NOTICE wording (section 5.3), on where Expause shows the credit, and on confirming that caption outputs carry no attribution duty. Not a blocker (U4).
12. **Mistral Voxtral API price and timestamp support,** if an EU hosted fallback is wanted.

**User decisions left open after the final round**

13. **Partial English captions on mostly non-English videos.** The default rule (section 4.4) captions English windows whenever there are at least about 2 s of English speech, so a video with 10 % English gets a track covering only that 10 %, with `partial_language: true`.
    - *For:* every English sentence a viewer hears is captioned; the rule is symmetric and has no arbitrary share cut-off.
    - *Against:* a track that covers a small part of the speech may look broken to viewers. A share minimum (for example "caption only if English ≥ 30 % of speech") avoids that, at the cost of dropping real English captions.
    - Decide: absolute minimum only (the default), or also a share minimum, and at what value.
14. **Primary runtime: sherpa-onnx, or a vendored and patched onnx-asr.**
    - *sherpa-onnx (the default):* durations and log-probabilities without patching, larger user base, an employer behind the main author, and audio tagging in the same runtime. Costs: a native dependency that cannot be vendored, a second bundled onnxruntime (tested harmless; about 29 MB on disk on macOS, and the whole linux x86_64 `sherpa-onnx-core` wheel is 10.6 MB compressed), weights in a personal account (mitigated by mirroring), and no release for 4 weeks.
    - *onnx-asr:* pure Python, MIT, vendorable, one onnxruntime. Costs: a small patch to return TDT durations, which scenewise would own; a single maintainer; and the audio tagger would need its own loop on onnxruntime.
    - Both stay CI-tested behind the port, so either choice can be reversed cheaply.
15. **"unknown"-language windows.** The default drops them: no captions, with a flag. That loses English in very short or noisy windows that `tiny` cannot label confidently.
    - *Option A:* keep dropping them (safe against pseudo-English from non-English speech).
    - *Option B:* caption them if Parakeet's mean token log-probability passes a threshold, and only after T3 shows the log-probability separates English from non-English on Expause clips.
    - *Option C:* move up to `base` for LID (about 145 MB), which should produce fewer unknowns.
16. **Music flag or "[music]" cue.** Ship the AudioSet tagger now as a metadata-only `music` flag, ship it as visible "[music]" cues, or wait for T1. The model is Apache-2.0 per its card but was trained on AudioSet, which is built from YouTube clips. Whether that training-data provenance matters to Expause is a legal call, like open question 11.

---

## 8. Review round 1 — resolution

Every finding was re-checked against its source on 2026-10-08.

| # | Finding (short) | Resolution |
|---|---|---|
| 1 | "Beats every Whisper variant" is false (TheWhisper 4.54) | **Fixed.** Now reads "every openly runnable Whisper variant"; TheWhisper excluded with reasons (proprietary SDK, access token, encrypted `.enc` weights) [S48][S2] |
| 2 | 40.3 % and 0.2 % come from different experiments | **Fixed.** §1 and §4.1 now separate experiment 1 (no VAD, pure non-speech) from Table VII (speech plus non-speech; 21.3 / 12.5 / 0.2, and the overlapped column) [S19] |
| 3 | [S19] excluded music | **Fixed.** Quoted the exclusion; stated plainly that no cited source covers music beds; added test T1 and open question 1 [S19] |
| 4 | Private sets are not just Appen | **Fixed.** Now names Appen, DataoceanAI and Voice Arena private aggregates, plus the 24 July "Private data used in default average" [S1] |
| 5 | 07-24 column inconsistent | **Fixed.** Every row filled from 1d3e13c where present ("absent" otherwise); note rewritten [S3] |
| 6 | moonshine-voice Torch "?" | **Fixed.** "No (torch only in `lora`/`finetune` extras)" [S31] |
| 7 | "7–9× faster" unsupported; wrong comparator | **Fixed.** Now ≈9× default / ≈5.6× int8 *inside onnx-asr*, with the caveat about faster-whisper; open question 3. The page labels the column "default", not "fp32", so I say "default (presumably fp32)" [S9] |
| 8 | H200 has a primary source | **Fixed.** Cite the Space changelog for 24 June 2026; long-form hardware caveated; hardware part of the old open question closed [S1][S4] |
| 9 | "NeMo 2.3" for MarbleNet unsupported | **Rejected.** The card states "Runtime Engine(s): NeMo-2.3.0" in its model-details section [S33]. The citation is now explicit |
| 10 | Parakeet v3 transformers path missing | **Fixed.** Added the transformers path (and noted the "install from source" text is stale: `ParakeetForTDT` ships in 5.19.0) plus the official GGUF / NeMo-Speech.cpp [S7][S44][S45] |
| 11 | sherpa-onnx missing | **Fixed and adopted as primary** (§5.1, §6). Partly rejected: the "backed by a team rather than one person" claim. Contributor data shows csukuangfj 1,624 commits vs 18 for the next contributor [S51] |
| 12 | transcribe.cpp missing | **Fixed.** Added to §5.1 (0.3.1, MIT, token timestamps, young) [S43] |
| 13 | ARK-ASR-0.6B missing | **Fixed.** Verified 4.56 / Apache-2.0 / 19 languages / RTFx 663; the ID now redirects to `Edge0/ARK-ASR-0.6B`; no timestamps documented; remote code [S46][S2] |
| 14 | MOSS-Transcribe-Diarize missing | **Fixed.** Verified 4.64 / Apache-2.0 / 0.9B / 50+ languages; segment-level timestamps only; acoustic events → open question 6 [S47] |
| 15 | Other omitted models | **Fixed.** One-line "considered and set aside" list in §2 [S2] |
| 16 | fast-gpu-asr rows | **Fixed.** Row added; library unidentified → open question 9 [S1][S2] |
| 17 | Hosted ASR not compared | **Fixed.** §3.5: OpenAI per-minute prices; Mistral as EU vendor (price not captured); reasons set aside [S49][S50] |
| 18 | LID gate under-specified | **Fixed.** §4.4: VAD-only input, 3–30 s windows, faster-whisper `tiny` int8 with p ≥ 0.5, video-level E ≥ 0.5 rule, v3 alternative; locally sanity-checked [L1][S14][S22] |
| 19 | onnx-asr VAD cuts at fixed 20 s | **Fixed.** Confirmed in 0.12.0 source and reproduced locally (cut at 12.48 → 32.48 s); scenewise owns segmentation (§4.2) [S42][L1] |
| 20 | onnx-asr token start times only | **Fixed.** Confirmed in source; sherpa-onnx returns durations (verified locally); a deciding factor in the runtime choice [S42][L1] |
| 21 | Single-runtime lock-in | **Fixed.** `SpeechRecognizer` port with primary, second and fallback adapters (§6) |
| 22 | onnx-asr bus factor | **Fixed.** Risk stated with GitHub data; onnx-asr demoted to tested second; pins and vendoring noted [S51][S11] |
| 23 | CC-BY obligations under-stated | **Fixed.** "Indicate changes" obligation plus draft NOTICE text naming the converter and the int8 quantisation (§5.3) [S40][S29] |
| 24 | Batched pipeline ignores `hallucination_silence_threshold` | **Fixed.** Noted in §4.3; confirmed in 1.2.1 source [S14][L1] |
| 25 | "8 cleaned sets" | **Fixed.** "8 public sets, four of them Cleaned variants" |
| 26 | Qwen row is `-hf`; qwen-asr pins transformers 4.57.6 | **Fixed** [S2][S31] |
| 27 | Moonshine ID | **Fixed.** `moonshine-ai/moonshine-streaming-medium` (HF API redirect) [S52] |
| 28 | Cohere gated | **Fixed.** "(gated)" added (HF `gated: auto`) [S52] |
| 29 | macOS claim miscited | **Fixed.** Cited the README; also confirmed locally on an M4, plus the CoreML default-provider pitfall [S9][L1] |
| 30 | Silero not bundled in onnx-asr | **Fixed.** Downloaded from `istupakov/silero-vad-onnx` (v6.2, MIT); pre-fetch into the image [S42][S52] |
| 31 | torch licence | **Fixed.** PyPI `license_expression` quoted [S31] |
| 32 | Close TheWhisper question | **Fixed.** Closed and excluded [S48] |
| 33 | Cloud Run GPU billing, redundancy, regions | **Fixed,** with a correction to the review: L4 is in **six** regions (one invite-only), not five; EU regions named [S36] |
| 34 | Granite 4.1 punctuation and GGUF | **Fixed** [S23] |

---

## 9. Review round 2 — resolution

Final round. Every finding was re-checked against its source, or re-tested locally, on 2026-10-08. Anything still unsettled is in section 7 as a user decision (open questions 13–16).

| # | Finding (short) | Resolution |
|---|---|---|
| 1 | "LID returned en 0.256 on music" ran on zero padding | **Fixed.** Confirmed: the run used `vad_filter=True`, and faster-whisper's VAD had removed the whole clip. The claim is withdrawn. Re-tested with `vad_filter=False`: music → ja 0.213 / 0.248, digital silence → cy 0.282 / 0.234 (macOS / linux). The conclusion now rests on "`detect_language` always returns a label" (§4.1, §4.4.1, §10) [S14][L1] |
| 2 | p ≥ 0.5 misattributed to `language_detection_threshold` | **Fixed.** Confirmed: that parameter is a strict `>` early stop across segments, inert with one segment. 0.5 is now scenewise's own starting value, applied with `≥` throughout. It is justified by the local gap between clean speech (≥ 0.98) and non-speech (0.21–0.33), and tuned in T3 (§4.4.4) [S14][L1] |
| 3 | Cut rule cannot be built on sherpa's VAD | **Fixed.** Confirmed locally: the 1.13.8 binding exposes only a boolean `is_speech` on `VadModel` and segment queues on `VoiceActivityDetector`, with no frame probabilities [S53]. scenewise runs its own Silero loop on pip onnxruntime (vendor onnx-asr's MIT `models/silero.py` or write about 40 lines; tested locally). sherpa is used for ASR only, and its VAD is no longer a reason for the runtime choice (§1, §4.2, §5.1) |
| 4 | Two onnxruntime builds in one process; "no pin juggling" illusory | **Fixed and tested.** Accepted that pip onnxruntime 1.30.0 is always present (faster-whisper requires it; so does the Silero loop). Checked how sherpa bundles its copy: it is linked by its own name (macOS `@rpath/libonnxruntime.dylib`; Linux SONAME `libonnxruntime.so`), while pip's is `libonnxruntime.1.dylib` / `libonnxruntime.so.1`, and pip's Python module links ORT internally. Loading all three packages in one process worked in both import orders on macOS arm64 and linux/amd64. **Not a problem**; the cost is about 29 MB of duplicate library. CI smoke test T4 added; §5.2 role corrected [L1][S31] |
| 5 | Asymmetric E ≥ 0.5 rule; untested log-prob fallback | **Fixed.** Rule replaced: caption the English windows whenever English speech is at least about 2 s, flag the rest, and emit no track only without English (§4.4.5). The log-probability fallback was dropped from the rule. A first measurement was taken (EN −0.012 vs DE pseudo-English −0.477, one TTS pair) and the real test moved to T3. The remaining product choices are open questions 13 and 15 [L1] |
| 6 | TDT durations overstated | **Fixed.** Confirmed in source [S53] and locally: durations are argmax frame advances of 0–0.32 s, and some are 0 (8 of 85 tokens on the German clip). Now described as "model-predicted, 0–0.32 s per token". The cue builder extends ends to the next pause or a minimum hold (§1, §4.5, T2) [L1] |
| 7 | §1 "splits softly at the next pause" contradicts §4.2 | **Fixed.** §1 no longer credits sherpa's VAD. §4.2 says "soft, unbounded" and cites the buffer doubling and the 55.6 s segment [S39][L1] |
| 8 | sherpa-onnx audio tagging missing | **Fixed.** Added as the first music-bed and event-cue candidate (§1, §4.5, T1, open questions 6 and 16). Licence checked: Apache-2.0 on the HF card (repo c24f9d0) and in the tarball README. Tested locally: synthetic music → "Music" 0.87, speech → "Speech" 0.99. But digital silence → "Music" 0.33–0.37, so an energy gate is needed; and a 60 s call raised peak RSS by about 1 GB, so tag in ≤10 s chunks [S55][L1] |
| 9 | NOTICE: quantisation method, `master` link, MIT notices | **Fixed.** Verified `quantize_dynamic` (QUInt8 encoder, QInt8 others) in the script at tag v1.13.8. NOTICE now says "dynamic int8 weight quantisation (ONNX Runtime `quantize_dynamic`)", links the tag, and adds the MIT notices for Silero ("Copyright (c) 2020-present Silero Team") and Whisper ("Copyright (c) 2022 OpenAI"), plus the tagger if shipped (§5.3) [S56][S8][S21] |
| 10 | Pin Silero from upstream | **Fixed.** Downloaded `src/silero_vad/data/silero_vad.onnx` at tag v6.2 (commit be95df9). Its sha256 `1a153a22…88e3` matches the istupakov mirror byte for byte. It is pinned by tag, commit and sha256 (§5.2) [S8][L1] |
| 11 | sherpa CUDA wheels are not on PyPI | **Fixed.** Confirmed: PyPI has only CPU `sherpa-onnx-core` wheels; k2-fsa's index lists `…+cuda12.cudnn9.onnxruntime1.28.2…` and `cuda13` builds. Noted in §5.1, §5.2 and §6.2, together with "no sherpa GPU throughput measured" [S54] |
| 12 | Bus factor incomplete | **Fixed.** Added the Xiaomi copyright (verified in `run.sh` at v1.13.8), the release gap (v1.13.6 08-18, v1.13.7 09-01, v1.13.8 09-10, none since), the personal HF account hosting the weights, mirroring of every pinned weight with sha256 checks, and the exits (source build or the onnx-asr adapter; no vendoring of native code) (§5.1, §5.2) [S51] |
| 13 | ARK-ASR is ≈1.15B, and its repo moved | **Fixed.** Confirmed `Size (B)` = 1.15 in the c23ca4f CSV. §2, §3.4 and open question 7 now say ≈1.15B total and flag the `AutoArk-AI` → `Edge0` move as a provenance question [S2][S46] |
| 14 | Peak RSS for a ≤30 s segment | **Fixed (measured).** linux/amd64 (Docker, emulated), with Parakeet int8, Silero, Whisper tiny and the tagger all loaded: 1.04 GB resident after load, **1.33 GB peak** after one 30 s segment. Recommendation: 2 GiB floor, 4 GiB with headroom, to be confirmed on Cloud Run (§6.2). The 334 s figures are kept only as the reason for the cap [L1] |
| 15 | "speech pad: n/a" for sherpa | **Fixed.** Confirmed in `voice-activity-detector.cc`: start = `Tail − 2·WindowSize − MinSpeechDurationSamples` (≈0.31 s implicit lead-in), end at silence onset (0 s tail). Table updated, though sherpa's VAD is no longer used [S39] |

**Section D (coherence).** Accepted. The runtime decision was re-argued in §5.1 on what remains: unpatched durations and log-probabilities, user base and employer backing, against a native dependency, a duplicate onnxruntime and a single committer. The result is unchanged: sherpa-onnx primary, onnx-asr tested second, on a margin now stated as thin. The flip option is open question 14.

---

## 10. Local check [L1]

- **Where:** scripts and outputs in the session scratchpad (`…/scratchpad/q2/`), not in the repo. Run 2026-10-08 on an Apple M4 (macOS) with Python 3.12 (uv).
- **Packages:** sherpa-onnx 1.13.8, onnx-asr 0.12.0, onnxruntime 1.30.0, faster-whisper 1.2.1, ctranslate2 4.8.2.
- **Models:** the pinned revisions in §5.2.
- **Audio (no third-party clips):**
  - English and German speech synthesised with macOS `say` (voices Samantha and Anna).
  - A 55 s continuous English utterance (`say -r 230`), also concatenated ×6 to 334 s.
  - A 60 s numpy-generated *synthetic* music-like signal.
- **What it shows:**
  - API behaviour (durations, VAD splitting, providers, LID outputs) and rough speed and memory.
  - It shows **nothing** about WER or about real-music behaviour.

| Check | sherpa-onnx | onnx-asr |
|---|---|---|
| EN 12.6 s, RTFx | 32.3 (4 threads) | 34–36 (CPU provider); 6.9 with default providers incl. CoreML |
| Token timing | start + duration (0.16, 0.16, 0.08 …) | start only |
| Text detail | "was £13.60" | "was£13.60" (missing space) |
| DE speech (English-only model) | "Gutentag und Hartslich Wilkmen…" | same, as pseudo-English |
| Synthetic music, no VAD | "" | "" (54.7 s with CoreML; 1.6–1.9 s on CPU) |
| Silero on synthetic music | no segments | no segments |
| 55 s continuous speech, default VAD | 1 segment (0–55.6 s) | cut at 12.48 and a fixed 20 s cut to 32.48 |
| 334 s single pass | RTFx 13.8, peak RSS 6.56 GB (8 threads) | RTFx 16.8, peak RSS 5.10 GB |

faster-whisper `tiny` int8 `detect_language(vad_filter=True)`: EN → en 0.996; DE → de 0.999; synthetic music → en 0.256 (top-3 en/cy/nn). **Round 2 correction:** the music figure is LID on zero padding, because faster-whisper's internal VAD removed the whole clip (section 4.1).

**Round 2 re-tests** (script `scripts/r2_measure.py` in the scratchpad; same synthetic audio; run on macOS arm64 and in Docker `python:3.12-slim` linux/amd64 with 4 CPUs, emulated on the M4; pip `onnxruntime` 1.30.0 + `sherpa-onnx` 1.13.8 + `faster-whisper` 1.2.1 in one process, in both import orders):

| Check | macOS arm64 | linux/amd64 (emulated) |
|---|---|---|
| Both onnxruntime builds in one process, both import orders | works, same outputs | works, same outputs |
| Shared-library names | sherpa `@rpath/libonnxruntime.dylib` vs pip `@rpath/libonnxruntime.1.dylib` | sherpa SONAME `libonnxruntime.so` vs pip `libonnxruntime.so.1`; pip's Python module has no `DT_NEEDED` on either |
| RSS after loading Parakeet int8 (sherpa, 4 threads), Silero (own loop), Whisper tiny int8, audio tagger | `ru_maxrss` 1.5–2.1 GB | 1.04–1.06 GB resident (peak 1.12) |
| Peak after one 30 s speech segment (Silero → LID → Parakeet) | 1.8–2.3 GB | **1.33 GB** |
| Peak after tagging 60 s in one call | 2.8–3.7 GB | 2.57 GB |
| Own Silero loop, 30 s | 0.07 s | (emulated; timing meaningless) |
| Parakeet, 30 s segment | 0.76–1.24 s (RTFx 24–39) | (emulated; timing meaningless) |
| LID `vad_filter=False`: EN / DE / 30 s EN segment | en 0.996 / de 0.999 / en 0.979 | en 0.995 / de 0.998 / en 0.980 |
| LID on synthetic music, `vad_filter=True` (zero padding) | en 0.256 | en 0.326 |
| LID on synthetic music, `vad_filter=False` | ja 0.213 (en 0.201) | ja 0.248 (en 0.162) |
| LID on 10 s digital silence, `vad_filter=False` | cy 0.282 | cy 0.234 |
| Parakeet mean token log-prob, EN / DE TTS | −0.012 / −0.477 | −0.012 / −0.474 |
| TDT durations seen (s) | EN {0.08–0.32}, no zeros; DE {0–0.32}, 8 of 85 zero | same |
| Audio tagger top label: synthetic music / EN speech / digital silence | Music 0.872 / Speech 0.985 / Silence 0.536 (Music 0.327) | Music 0.870 / Speech 0.986 / **Music 0.365** (Silence 0.267) |
| Silero v6.2 sha256, upstream tag v6.2 vs istupakov mirror | identical, `1a153a22…` | — |

The macOS `ru_maxrss` is a process high-water mark that includes allocator caching, so the linux `VmHWM` figure is the one for sizing. Linux timings are meaningless because the x86_64 code ran under emulation.

---

## 11. Sources (all read 2026-10-08)

- [S1] Open ASR Leaderboard Space, `init.py` version registry (latest "02-10-2026"; 25-09-2026 "Parakeet TDT with fast-asr-gpu decoding library"; 31-07-2026 "Remove older models"; `default_datasets` with "Private (scripted)" / "Private (conversational)") and `app.py` (APPEN_* / DATAOCEAN_* / Voice Arena private sets; changelog "24 June 2026 — … Switch to H200 GPUs for eval", "24 July 2026 — … Private data used in default average") — https://huggingface.co/spaces/hf-audio/open_asr_leaderboard (Space lastModified 2026-10-02)
- [S2] Leaderboard results CSV, revision c23ca4f (2026-10-02) — https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results/resolve/c23ca4f10e5f1a77c9fd3b41e17cd06a04f0f56c/english_short_latest.csv
- [S3] Leaderboard results CSV, revision 1d3e13c (24-07-2026 version) — https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results/resolve/1d3e13c97cd949c6e11f6bc872c20299145cd80a/english_short_latest.csv
- [S4] huggingface/open_asr_leaderboard GitHub README (HF Jobs, 1× H200; long-form "will migrate to HF Jobs") — https://github.com/huggingface/open_asr_leaderboard
- [S5] Open ASR Leaderboard paper, arXiv 2510.06961v3 (10 Dec 2025; A100-80GB) — https://arxiv.org/html/2510.06961v3
- [S6] nvidia/parakeet-tdt-0.6b-v2 model card — https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- [S7] nvidia/parakeet-tdt-0.6b-v3 model card (release 08/14/2025; transformers `AutoModelForTDT`; NeMo-Speech.cpp `q8_0.gguf`; repo lastModified 2026-08-05) — https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- [S8] Silero VAD repo, LICENSE (MIT) and releases v6.0 (2025-08-26), v6.2 (2025-11-06), v6.2.1–6.2.3 (2026) — https://github.com/snakers4/silero-vad , https://api.github.com/repos/snakers4/silero-vad/releases
- [S9] onnx-asr README ("Works on Windows, Linux, and macOS on x86 and Arm CPUs, with support for CUDA, TensorRT, CoreML, …") and benchmarks (9800X3D default/int8; T4; Orange Pi; RTX 5070 Ti) — https://github.com/istupakov/onnx-asr , https://istupakov.github.io/onnx-asr/benchmarks/
- [S10] onnx-asr docs home — https://istupakov.github.io/onnx-asr/
- [S11] onnx-asr on PyPI (0.12.0, 2026-07-15; onnxruntime exclusions) — https://pypi.org/pypi/onnx-asr/json
- [S12] onnx-asr usage (VAD: silero / pyannote; `.with_timestamps()`; "You will most likely need to adjust VAD parameters") — https://istupakov.github.io/onnx-asr/usage/
- [S13] faster-whisper README (benchmarks, VAD, batched pipeline) — https://github.com/SYSTRAN/faster-whisper
- [S14] faster-whisper v1.2.1 source: `vad.py`, `transcribe.py` (`detect_language`; batched pipeline hard-codes `condition_on_previous_text=False`, `hallucination_silence_threshold=None`), `utils.py`, `assets/silero_vad_v6.onnx` — https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1/faster_whisper
- [S15] nvidia/canary-qwen-2.5b model card — https://huggingface.co/nvidia/canary-qwen-2.5b
- [S16] nvidia/canary-1b-v2 model card — https://huggingface.co/nvidia/canary-1b-v2
- [S17] openai/whisper-large-v3-turbo model card — https://huggingface.co/openai/whisper-large-v3-turbo
- [S18] distil-whisper/distil-large-v3.5 model card — https://huggingface.co/distil-whisper/distil-large-v3.5
- [S19] Barański et al., "Investigation of Whisper ASR Hallucinations Induced by Non-Speech Audio", arXiv 2501.11378v1 (Jan 2025); §II-A music exclusion, §II-B experiment 1, §V-A / Table VII — https://arxiv.org/html/2501.11378v1
- [S20] WhisperX README — https://github.com/m-bain/whisperX
- [S21] openai/whisper LICENSE (MIT), `transcribe.py` at v20250625, model card — https://github.com/openai/whisper
- [S22] Qwen/Qwen3-ASR-1.7B model card (LID table: Whisper-large-v3 average 94.1 %, Qwen3-ASR-1.7B 97.9 %) — https://huggingface.co/Qwen/Qwen3-ASR-1.7B
- [S23] ibm-granite/granite-speech-4.1-2b model card (2026-04-29; punctuation/truecasing by prompt; llama.cpp GGUF) — https://huggingface.co/ibm-granite/granite-speech-4.1-2b
- [S24] CohereLabs/cohere-transcribe-03-2026 model card (gated) — https://huggingface.co/CohereLabs/cohere-transcribe-03-2026
- [S25] mistralai/Voxtral-Mini-3B-2507 model card — https://huggingface.co/mistralai/Voxtral-Mini-3B-2507
- [S26] kyutai/stt-2.6b-en model card — https://huggingface.co/kyutai/stt-2.6b-en
- [S27] ibm-granite/granite-speech-5.0-470m-turboctc model card (2026-08-25; "RTFx measured on 1 H200") — https://huggingface.co/ibm-granite/granite-speech-5.0-470m-turboctc
- [S28] Moonshine repo — https://github.com/moonshine-ai/moonshine
- [S29] istupakov/parakeet-tdt-0.6b-v2-onnx card ("converted to ONNX format for onnx-asr", export code) and HF model API licence tags for it and siblings — https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx
- [S30] Long-form leaderboard CSV, revision 4f164c2 — https://huggingface.co/datasets/hf-audio/leaderboard_longform/resolve/4f164c2c904b630d9777323b5d2e7f1f549d0143/longform_latest.csv
- [S31] PyPI JSON API for every package in section 5 — https://pypi.org/pypi/<package>/json
- [S32] whisper.cpp README (VAD section) and releases (v1.9.5, 2026-10-06), LICENSE MIT — https://github.com/ggml-org/whisper.cpp
- [S33] nvidia/Frame_VAD_Multilingual_MarbleNet_v2.0 model card ("Runtime Engine(s): NeMo-2.3.0"; NVIDIA Open Model License) — https://huggingface.co/nvidia/Frame_VAD_Multilingual_MarbleNet_v2.0
- [S34] pyannote/segmentation-3.0 model card — https://huggingface.co/pyannote/segmentation-3.0
- [S35] parakeet-mlx README — https://github.com/senstella/parakeet-mlx
- [S36] Cloud Run GPU docs ("Last updated 2026-10-07"; instance-based billing; zonal redundancy; regions) — https://docs.cloud.google.com/run/docs/configuring/services/gpu
- [S37] speechbrain/lang-id-voxlingua107-ecapa model card — https://huggingface.co/speechbrain/lang-id-voxlingua107-ecapa
- [S38] sherpa-onnx: GitHub repo and releases (v1.13.8, 2026-09-10); PyPI 1.13.8 (2026-09-10, depends on `sherpa-onnx-core==1.13.8`); wheel `sherpa_onnx-1.13.8-cp312-cp312-macosx_11_0_arm64.whl` inspected (`offline_recognizer.py` `from_transducer(model_type=…)`; result fields `timestamps`, `durations`, `words`, `lang`; `SpokenLanguageIdentification.compute()` → language code only) — https://github.com/k2-fsa/sherpa-onnx , https://pypi.org/pypi/sherpa-onnx/json
- [S39] sherpa-onnx v1.13.8 `voice-activity-detector.cc` (threshold → 0.90 and min silence → 0.1 s once the buffer exceeds `max_speech_duration`) — https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/sherpa-onnx/csrc/voice-activity-detector.cc
- [S40] sherpa-onnx NeMo transducer model docs ("This model is converted from https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2"; conversion script; int8/fp16/fp32 variants) — https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html
- [S41] HF model API, csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8 (cc-by-4.0; files and sizes) — https://huggingface.co/api/models/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8
- [S42] onnx-asr 0.12.0 wheel source: `vad.py` (`_merge_segments` defaults and fixed-offset loop), `asr.py` (`TimestampedResult`, transducer decode), `models/silero.py`, `resolver.py` (`"silero": "istupakov/silero-vad-onnx"`), `loader.py` (default providers = all available) — https://files.pythonhosted.org/packages/6a/60/2fa469a2ee674c35ab48821a1039762ae7b9d0b88188ac1012e779477f76/onnx_asr-0.12.0-py3-none-any.whl
- [S43] transcribe.cpp README (model/capability table; MIT; bindings) and `bindings/python/README.md`; PyPI `transcribe-cpp` 0.3.1 (2026-10-04); handy-computer/parakeet-tdt-0.6b-v2-gguf card ("timestamps: token", "Validated against the NeMo reference") — https://github.com/handy-computer/transcribe.cpp , https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v2-gguf
- [S44] transformers 5.19.0 wheel (`models/parakeet/*`, `MODEL_FOR_TDT_MAPPING_NAMES` → `ParakeetForTDT`) — https://pypi.org/project/transformers/5.19.0/
- [S45] NVIDIA NeMo-Speech.cpp README (supported models incl. Parakeet TDT 0.6B v3; Silero VAD; subtitles) and releases (v0.1.0 2026-08-19, v0.2.0 2026-10-02) — https://github.com/NVIDIA/NeMo-Speech.cpp
- [S46] ARK-ASR-0.6B model card (`AutoArk-AI/ARK-ASR-0.6B` → `Edge0/ARK-ASR-0.6B`; Apache-2.0; created 2026-05-25; Whisper-style encoder + Qwen2 decoder; `trust_remote_code`) — https://huggingface.co/AutoArk-AI/ARK-ASR-0.6B
- [S47] OpenMOSS-Team/MOSS-Transcribe-Diarize model card (Apache-2.0; 50+ languages; 90 min; segment start/end/speaker; acoustic events; SGLang/vLLM) — https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize
- [S48] TheStageAI/thewhisper-large-v3-turbo model card (SDK/Docker access; access token; online token check) and file listing (`free/…/*.enc`) — https://huggingface.co/TheStageAI/thewhisper-large-v3-turbo
- [S49] OpenAI API pricing (transcription models per minute) — https://developers.openai.com/api/docs/pricing
- [S50] Mistral pricing page ("speech models are per minute"; no rate shown) — https://mistral.ai/pricing
- [S51] GitHub REST API repo, contributor and release data for istupakov/onnx-asr, k2-fsa/sherpa-onnx, handy-computer/transcribe.cpp, SYSTRAN/faster-whisper, NVIDIA-NeMo/Speech, NVIDIA/NeMo-Speech.cpp — https://api.github.com/repos/<owner>/<repo>
- [S52] HF model API (revision SHAs, lastModified, licence tags, gated flags, redirects) for every model ID pinned or renamed in this document — https://huggingface.co/api/models/<id>
- [S53] sherpa-onnx v1.13.8 source and the installed 1.13.8 binding: `offline-transducer-greedy-search-nemo-decoder.cc` (TDT `skip` = argmax over `num_durations` duration logits, "skip can be 0"; `ys_log_probs`), `python/csrc` VAD bindings (`VadModel`: `is_speech`, `window_size`, min-duration getters; `VoiceActivityDetector`: `accept_waveform`, `empty`, `front`, `pop`, `flush`, `reset`, `is_speech_detected`, `current_segment`), and the `OfflineRecognitionResult` fields (`durations`, `timestamps`, `tokens`, `words`, `ys_log_probs`, `lang`, …) — https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8/sherpa-onnx
- [S54] sherpa-onnx CUDA install page (k2-fsa wheel index; `sherpa_onnx-1.13.8+cuda12.cudnn9.onnxruntime1.28.2-cp312-cp312-linux_x86_64.whl`, `+cuda13…`) and PyPI `sherpa-onnx-core` 1.13.8 file list (CPU-only manylinux2014 wheels) — https://k2-fsa.github.io/sherpa/onnx/cuda.html , https://pypi.org/pypi/sherpa-onnx-core/1.13.8/json
- [S55] sherpa-onnx audio tagging docs and model `k2-fsa/sherpa-onnx-zipformer-small-audio-tagging-2024-04-15` (HF API: sha c24f9d0, `license: apache-2.0`; release tarball `audio-tagging-models/…2024-04-15.tar.bz2` with `model.int8.onnx`, `class_labels_indices.csv`; README links icefall PR 1421) — https://k2-fsa.github.io/sherpa/onnx/audio-tagging/index.html , https://huggingface.co/k2-fsa/sherpa-onnx-zipformer-small-audio-tagging-2024-04-15
- [S56] sherpa-onnx `scripts/nemo/parakeet-tdt-0.6b-v2/export_onnx.py` at tag v1.13.8 (`quantize_dynamic`, `QuantType.QUInt8` for the encoder, `QInt8` otherwise) and `run.sh` ("Copyright 2025 Xiaomi Corp. (authors: Fangjun Kuang)") — https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8/scripts/nemo/parakeet-tdt-0.6b-v2
