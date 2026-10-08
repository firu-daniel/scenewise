# Review r2 (final): q2-captions.md

Reviewer: fresh review agent (did not write or previously review the file). All sources were re-opened on 2026-10-08. Raw data was used where possible: PyPI JSON, the HF model API, the sherpa-onnx v1.13.8 C++ and pybind source plus the 1.13.8 PyPI wheels (`sherpa-onnx` cp312 manylinux, `sherpa-onnx-core` manylinux), the onnx-asr 0.12.0 wheel, the transformers 5.19.0 wheel, faster-whisper `v1.2.1` source, the leaderboard CSVs c23ca4f and 1d3e13c, and the ARK-ASR, MOSS, MarbleNet and Silero cards. The reviewed file was not edited.

Severity counts: wrong 0 · unsupported 2 · missing option 1 · design concern 3 · minor 9 (15 findings in total).

## A. Round-1 resolutions

I re-checked all 34 resolutions in §8. Every "Fixed" item is reflected in the text, and the spot checks match their sources. For example:
- the 07-24 column (1d3e13c): ARK 5.14, Cohere 5.20, Granite 4.1 4.90, Qwen -hf 4.99, Kyutai 5.74, Phi-4 5.42, Voxtral 6.01;
- the TheWhisper row (4.539);
- the ARK and MOSS rows (4.559 / 663 and 4.636 / 381).

On the rejected or partly rejected items:
- **#9 (MarbleNet "NeMo 2.3"), rejection correct.** The card's README (lines 196–197) reads "**Runtime Engine(s):** NeMo-2.3.0". Round 1 was wrong.
- **#11 (sherpa-onnx "team-backed"), partial rejection mostly correct.** The GitHub contributors API shows csukuangfj 1,624 commits, then pkufool 18 and Wasser1462 16. The rejection does leave out one fact, though: the code is copyrighted by Xiaomi Corp. (for example `scripts/nemo/parakeet-tdt-0.6b-v2/run.sh`: "Copyright 2025 Xiaomi Corp. (authors: Fangjun Kuang)"). So the project has an employer behind it, but one committer. See finding 12.
- **#33 (Cloud Run L4 regions), the correction to the review is right.** The docs page (last updated 2026-10-07) lists L4 in asia-southeast1, asia-south1 (invitation only), europe-west1, europe-west4, us-central1 and us-east4. That is six regions. RTX PRO 6000 is in four regions, including europe-west4.

## B. Findings

### Unsupported

1. **Claim:** "On a no-speech music clip, Whisper LID still returned a label ('en', p = 0.256)" (§4.4.1). Also "faster-whisper `tiny` LID on the same clip returned 'en' … which shows that LID must not run on non-speech" (§4.1, §9 `detect_language(vad_filter=True)`).
   → **Source:** faster-whisper v1.2.1 source (https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py and `vad.py`, read 2026-10-08).
     - With `vad_filter=True`, `detect_language` calls `get_speech_timestamps`, then `collect_chunks`.
     - When no chunks are found, `collect_chunks` returns `[np.array([], dtype=np.float32)]`.
     - The features are then `pad_or_trim`-ed. So the model classified **30 s of zero padding**, not the music.
     - §4.1 and §9 report that Silero (same v6 model, same 0.5 threshold) found no speech in this clip. faster-whisper's internal VAD almost certainly removed everything too.
   → **unsupported.** The test does not show what Whisper LID does *on music*. What it shows is that `detect_language` always returns a label, even when its own VAD removed all audio.
   → **Correction:** describe the result as "LID on an empty (zero-padded) input after VAD returned 'en' 0.256; `detect_language` never signals 'no speech', so the caller must check VAD coverage first". For a music claim, re-run with `vad_filter=False`. The design conclusion (run LID only on VAD speech) still stands.

2. **Claim:** "Take the argmax language if p ≥ 0.5 (faster-whisper's own `language_detection_threshold` default)" (§4.4.4). This is given as the rationale for the gate threshold.
   → **Source:** same file, `detect_language`.
     - `language_detection_threshold` is an *early-stop* criterion over successive 30 s segments: `if language_probability > language_detection_threshold: break`. Note the strict `>`.
     - Otherwise the function falls back to a majority vote. Either way it returns the argmax language.
     - With `language_detection_segments=1` (the default, and the spec's usage), the threshold has no effect at all.
   → **unsupported** (the rationale borrows a parameter that has different meaning). The number may still be fine.
   → **Correction:** present 0.5 as scenewise's own starting value, applied by scenewise to the returned probability. Use one comparison operator throughout, and tune it in T3. Do not attribute it to faster-whisper.

### Design concerns

3. **Claim:** "scenewise runs Silero itself, through sherpa-onnx's VAD or its own ONNX loop. It caps segments at about 30 s by cutting at the lowest-probability frame inside the last few seconds" (§4.2).
   → **Source:** sherpa-onnx v1.13.8 pybind source (https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8/sherpa-onnx/python/csrc, read 2026-10-08).
     - `VoiceActivityDetector` exposes only `accept_waveform`, `empty`, `pop`, `front`, `flush`, `reset`, `is_speech_detected` and `current_segment`.
     - `VadModel` exposes `is_speech` (a bool), `window_size` and the min-duration getters. **No per-frame probability is exposed to Python.**
     - The C++ `VoiceActivityDetector::Impl` also puts **no upper bound** on segment length. Its `CircularBuffer::Push` doubles capacity when full and logs "Overflow! … No data loss!". The default `buffer_size_in_seconds` is 60. The 55.6 s single segment in §9 is the expected behaviour, not an edge case.
   → **design concern.** The stated cut rule cannot be implemented "through sherpa-onnx's VAD". Only the own-ONNX-loop path works.
   → **Correction:** commit to one approach: scenewise's own Silero ONNX loop on pip onnxruntime, which emits frame probabilities. onnx-asr's `models/silero.py` (MIT) already yields per-frame `p` and can be vendored. Then use sherpa-onnx for ASR only. State that sherpa's soft cut is no longer a factor in choosing the runtime: §5.1 "Better VAD splitting" becomes irrelevant, and the decision rests on TDT durations.

4. **Claim:** "No onnxruntime pin juggling. sherpa-onnx bundles onnxruntime" (§5.1). Also the onnxruntime 1.30.0 role "For onnx-asr" (§5.2).
   → **Source:** PyPI JSON for faster-whisper 1.2.1 (https://pypi.org/pypi/faster-whisper/1.2.1/json, read 2026-10-08) has `requires_dist` including `onnxruntime<2,>=1.14`. The `sherpa-onnx-core` 1.13.8 manylinux wheel ships `sherpa_onnx/lib/libonnxruntime.so`, whose version string is `1.28.2`.
     - The LID gate is mandatory and uses faster-whisper. The own-Silero loop from #3 also needs onnxruntime.
     - So prod **always** carries pip onnxruntime 1.30.0 *and* sherpa's bundled 1.28.2, in the same process.
   → **design concern.** The claimed advantage is mostly illusory. Two onnxruntime builds in one interpreter is usually fine, but nothing in the document tests it.
   → **Correction:**
     - Change the §5.2 role to "faster-whisper (LID), the Silero loop, and onnx-asr".
     - Reword the §5.1 bullet: "sherpa-onnx's ORT is isolated, but pip onnxruntime is still required".
     - Add a CI smoke test that loads sherpa-onnx, onnxruntime and faster-whisper in one process on linux/amd64.

5. **Claim:** the §4.4.5 video-level rule (E ≥ 0.5 → track with English cues only; E < 0.5 → no track), plus §4.4.4 "Treat 'unknown' as English only if Parakeet's mean token log-probability … passes a threshold".
   → **Source:** the document itself. No source or measurement supports either part.
     - **The rule is asymmetric.** A video with 45 % English speech loses its English captions entirely. A video with 55 % English speech gets them.
     - **The log-probability fallback has not been checked against the one case that motivates it.** §9 shows that German TTS decodes to fluent pseudo-English ("Gutentag und Hartslich Wilkmen…"), but no log-probabilities were recorded for it. Both runtimes expose them: sherpa `ys_log_probs`, populated in `offline-transducer-greedy-search-nemo-decoder.cc`; onnx-asr `need_logprobs`.
   → **design concern.** Short or noisy clips will often get "unknown" from `tiny`, so the fallback will decide many real cases.
   → **Correction:**
     - Either make the rule purely per-window (caption the English windows whenever any exist, and add flags), or justify the 0.5 video cut-off from Expause use cases.
     - Add to T3: measure Parakeet's mean token log-probability on English vs non-English speech, and check whether it separates them at all, before relying on it.

### Missing option

8. **sherpa-onnx's built-in audio tagging** (`AudioTagging`, `OfflineZipformerAudioTaggingModelConfig` in the 1.13.8 Python package; docs https://k2-fsa.github.io/sherpa/onnx/audio-tagging/index.html, read 2026-10-08).
   - It runs an AudioSet zipformer model (`sherpa-onnx-zipformer-small-audio-tagging-2024-04-15`). Its examples include Music and Laughter.
   - It runs in the already-chosen primary runtime, with no Torch.
   - The document only names MOSS-Transcribe-Diarize or "a separate audio tagger" for event cues (OQ6). It offers nothing for flagging music beds (T1).
   → **missing option**
   → **Correction:** add it as the first candidate for (a) a `music` flag or "[music]" cue on VAD-negative stretches and (b) the T1 analysis. Check the model's licence before adopting it.

(Numbers 6, 7 and 9–15 are minor and are listed below. The numbering is kept continuous across the file.)

### Minor

6. **Claim:** "It returns token start times and TDT durations, so cue end times are real rather than guessed" (§1).
   → **Source:** sherpa-onnx v1.13.8 `offline-transducer-greedy-search-nemo-decoder.cc` (read 2026-10-08).
     - The duration is `skip = argmax(duration_logits)` over the model's duration set. `num_durations = output_size − vocab_size` = 5, i.e. 0–4 frames of 80 ms. The note "skip can be 0" is in the code.
     - `Convert` multiplies by the frame shift.
     - So a duration is the decoder's predicted frame advance: it can be 0 and is capped at 0.32 s.
   → **minor** (overstated). It is still better than start-only timing.
   → **Correction:** describe durations as "model-predicted, 0–0.32 s per token". The cue builder should extend a cue's end to the next pause or a minimum hold. T2 already measures this against NeMo.

7. **Claim:** "Its Silero VAD wrapper splits over-long speech softly, at the next pause" (§1).
   → **Source:** see #3. There is no upper bound, and §9 itself shows a 55.6 s segment.
   → **minor**
   → **Correction:** in §1 add "but never forces a cut (55.6 s stayed one segment)", so the summary agrees with §4.2.

9. **Claims:** "Neither card states the quantisation method. The NOTICE should say 'int8-quantised' generically" (§5.3). The NOTICE also links the conversion script on `master`.
   → **Source:** https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/nemo/parakeet-tdt-0.6b-v2/export_onnx.py (read 2026-10-08) uses `onnxruntime.quantization.quantize_dynamic` with `weight_type=QuantType.QUInt8` for the encoder and `QInt8` for the others.
   → **minor**
   → **Correction:**
     - The NOTICE can say "dynamic int8 weight quantisation (ONNX Runtime `quantize_dynamic`)".
     - Pin the script link to tag `v1.13.8` rather than `master`.
     - The NOTICE draft also lacks the MIT notices for the Silero and Whisper (tiny, turbo) weights. These are needed if the weights are baked into a distributed image.

10. **Claim:** Silero v6.2 ONNX pinned from `istupakov/silero-vad-onnx` @ b3e3ee3 (§4.2, §5.2).
    → **Source:** the upstream `snakers4/silero-vad` tag `v6.2` ships `src/silero_vad/data/silero_vad.onnx` (MIT). Its sha256 is `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3`, **identical** to istupakov's `silero_vad.onnx` (HF LFS oid). The istupakov repo also holds two other variants (`_16k_op15`, `_op18_ifless`).
    → **minor**
    → **Correction:** pin the first-party file by tag and sha256, or keep the mirror but name the file and the sha256.

11. **Claim:** the GPU path (§6.2) cites only onnx-asr T4 numbers. sherpa-onnx is "the same runtime as dev".
    → **Source:** PyPI `sherpa-onnx-core` 1.13.8 wheels are CPU-only. The CUDA builds come from k2-fsa's own index (https://k2-fsa.github.io/sherpa/onnx/cuda.html, read 2026-10-08), e.g. `sherpa_onnx-1.13.8+cuda12.cudnn9.onnxruntime1.28.2-cp312-cp312-linux_x86_64.whl`. They are not on PyPI.
    → **minor**
    → **Correction:** note this. Note too that no sherpa-onnx GPU throughput was measured.

12. **Bus factor** (§5.1, "Both projects are dominated by one committer … sherpa-onnx has the far larger user base and release cadence").
    → **Source:** GitHub API, read 2026-10-08.
      - Releases: v1.13.6 2026-08-18, v1.13.7 2026-09-01, v1.13.8 2026-09-10, and **none since** (4 weeks).
      - 23 commits since 2026-09-10, csukuangfj 8 of them. Last push 2026-10-05.
      - Copyright Xiaomi Corp. (see section A).
      - Weights live in the personal HF account `csukuangfj`.
    → **minor.** The treatment is mostly honest, but incomplete.
    → **Correction:**
      - Add the Xiaomi employer backing (a point in sherpa's favour).
      - Soften "every 1–2 weeks" to "every 1–2 weeks through September".
      - Mirror the pinned weights into scenewise-controlled storage.
      - Note that sherpa is native code, so "vendor if abandoned" does not apply. The exits are a source build (Apache-2.0, CMake) or the onnx-asr adapter.

13. **Claim:** "ARK-ASR-0.6B … Qwen2 0.6B decoder" (§2, §3.4). The name suggests a 0.6B model.
    → **Source:**
      - Leaderboard CSV c23ca4f, `Size (B)` = **1.15**.
      - The card (https://huggingface.co/Edge0/ARK-ASR-0.6B, read 2026-10-08): "0.6B decoder LLM parameters, with a separate 0.6B-scale Whisper-style audio encoder"; `model.safetensors` is 2.6 GB.
      - The 19 languages, Apache-2.0, `trust_remote_code` and lack of documented timestamps are all confirmed. So are the community ONNX, GGUF and MLX conversions (OpenVoiceOS, Edge0 int8 ONNX, maxffarrell GGUF, leope MLX).
    → **minor**
    → **Correction:** say "≈1.15B total". Also note that the repo moved from the AutoArk-AI org to the `Edge0` account, which is a provenance question to settle before relying on it.

14. **Claim:** "Size memory for segments of 30 s or less. A full 5.5-minute single pass peaked at 5–6.6 GB" (§6.2; §4.2: 5.1 / 6.6 GB).
    → **Source:** the numbers are internally consistent with §9: sherpa 6.56 GB with 8 threads, onnx-asr 5.10 GB. But they were measured on macOS with different thread counts, and they are not the figure needed for sizing.
    → **minor**
    → **Correction:** record the peak RSS for a ≤30 s segment with all resident models loaded (Parakeet int8, Silero, Whisper tiny) on linux/amd64. That is the Cloud Run memory number. Keep the 334 s figure only as the reason for the cap.

15. **Claim:** the §4.2 table, sherpa-onnx "speech pad: n/a".
    → **Source:** `voice-activity-detector.cc` v1.13.8. A segment starts at `Tail − 2·WindowSize − MinSpeechDurationSamples`. That is an implicit lead-in of about 64 ms + 250 ms ≈ 0.31 s at the default settings. The end is placed at silence onset (`Tail − MinSilenceDurationSamples`).
    → **minor**
    → **Correction:** write "≈0.31 s lead-in (implicit), 0 s tail" instead of "n/a".

## C. New claims verified correct

- **sherpa-onnx 1.13.8**
  - PyPI upload 2026-09-10T17:00. Depends only on `sherpa-onnx-core==1.13.8` (2026-09-10).
  - Licence Apache-2.0 (GitHub API; PyPI text "Apache licensed").
  - Wheels cp37/38–cp314 (the document's "3.10–3.14" is conservative), macOS arm64/x86_64/universal2, manylinux x86_64/aarch64.
  - Bundled ORT 1.28.2.
  - 15,165 stars, 1,752 forks.
  - The Python result exposes `timestamps`, `durations`, `ys_log_probs`, `words` and `lang`.
  - TDT durations are filled by the NeMo greedy decoder when `IsTDT()`.
  - `SpokenLanguageIdentification.compute()` returns `std::string` only.
  - Silero defaults are 0.5 / 0.5 s / 0.25 s / max 20 s. Past max, threshold → 0.90 and min silence → 0.1 s (`new_threshold_`, `new_min_silence_duration_s_`).
  - TEN VAD is supported.
- **csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8:** sha `1ab9323565ddb038682214b292f588070a538ce2`, lastModified 2025-08-16, cc-by-4.0, `encoder.int8.onnx` 652,184,296 bytes. The fp16 and fp32 sibling repos exist. The conversion script path exists.
- **onnx-asr 0.12.0**
  - 2026-07-15, MIT.
  - `TimestampedResult.timestamps` "Tokens timestamp list". The TDT `step` is consumed in decoding and not returned.
  - `_merge_segments` defaults are 250 ms / 20 s / 100 ms / 30 ms, with a fixed-offset `while` loop.
  - `neg_threshold = threshold − 0.15`.
  - Default providers are `rt.get_available_providers()`, which includes CoreML on macOS. The onnxruntime exclusions are confirmed.
- **onnxruntime 1.30.0:** 2026-09-10, MIT, `requires_python >=3.11`. cp312 wheels for macOS 14 arm64 and manylinux_2_28 x86_64/aarch64.
- **Silero v6.2:** release 2025-11-06. Mirror revision b3e3ee3 (2026-03-22, MIT, "version 6.2"). silero-vad 6.2.3 released 2026-09-23.
- **faster-whisper 1.2.1:** the `detect_language` signature and return tuple match §3.3. `Systran/faster-whisper-tiny` @ d90ca5f (2023-11-23, MIT, 75.5 MB). `dropbox-dash/faster-whisper-large-v3-turbo` @ 0a363e9 (2025-11-05, MIT).
- **ARK-ASR-0.6B:** 4.559 / RTFx 663 / apache-2.0 / 19 languages. `AutoArk-AI/…` redirects to `Edge0/…`, created 2026-05-25.
- **MOSS-Transcribe-Diarize:** 4.636 / 381 / apache-2.0 / 0.91B / 50+ languages. Released 2026-07-09 (repo created 2026-05-19). 90 min single-pass; `segment.start/end/speaker/text`; "can also emit acoustic event annotations". SGLang Omni is recommended, with vLLM as an alternative.
- **transformers 5.19.0:** 2026-10-06. Ships `models/parakeet/*` and `MODEL_FOR_TDT_MAPPING_NAMES` → `ParakeetForTDT`.
- **Other packages:** transcribe-cpp 0.3.1 (2026-10-04); nemo-toolkit 3.0.0 (2026-08-07); huggingface-hub latest 2.1.1.
- **CC-BY-4.0 §3(a)(1)(B):** correctly identified as the "indicate if You modified … and retain an indication of any previous modifications" clause. The NOTICE draft satisfies it.

## D. Coherence of the recommendation

The overall design holds together: Parakeet v2 behind a `SpeechRecognizer` port, sherpa-onnx primary, onnx-asr tested second, faster-whisper for LID and fallback, and scenewise-owned VAD, segmentation and cue building.

The deciding argument for sherpa over onnx-asr is TDT durations, and the source confirms it. The other two arguments are weaker than stated:
- the VAD argument is moot once scenewise owns segmentation, and sherpa cannot supply the frame probabilities the cut rule needs (#3);
- the onnxruntime argument largely disappears because faster-whisper pulls in onnxruntime anyway (#4).

So the margin between the two runtimes is thin. Note also that onnx-asr's decoder already computes `step`, so returning durations from it would be a small patch to a vendorable MIT codebase. That makes keeping it as the tested second runtime the right call.

The bus-factor treatment is honest about the commit concentration. It should add the employer backing, the current release gap and the weight-hosting risk (#12).
