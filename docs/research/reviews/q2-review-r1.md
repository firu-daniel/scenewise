# Review r1: q2-captions.md

Reviewer: fresh review agent (did not write the file). Every source below was re-opened on 2026-10-08. Where possible I re-checked against raw data rather than rendered pages: the leaderboard CSVs at the cited revisions, the Space's `init.py`/`app.py`, the PyPI JSON API, the HF model API, raw model-card READMEs, and the GitHub source of onnx-asr 0.12-era `main` and faster-whisper `v1.2.1`. The reviewed file was not edited.

Severity counts: wrong 6 · unsupported 4 · missing option 7 · design concern 7 · minor 10 (34 findings in total).

**Headline:** the leaderboard numbers are accurate: every WER and RTFx in the table re-checks against CSV revisions c23ca4f and 1d3e13c, and the 4.70 mean recomputes as 4.7025. Most package versions, dates and licences are correct. The main problems are these:

- (a) The summary misreads the Whisper-hallucination paper. The 0.2 % Silero figure comes from a different experiment from the 40.3 % figure, and that experiment excluded all music.
- (b) "Beats every Whisper variant" is false on the doc's own snapshot.
- (c) The "7–9× faster than Whisper" claim compares against onnx-asr's Whisper ONNX path, not against the faster-whisper fallback.
- (d) onnx-asr is effectively a one-person project, and its VAD and timestamp defaults have caption-relevant sharp edges.
- (e) Several viable options are missing: sherpa-onnx, transcribe.cpp, Parakeet in transformers, ARK-ASR-0.6B (Apache-2.0, 4.56 WER) and MOSS-Transcribe-Diarize.

## Findings

### Wrong

1. **"That beats every Whisper variant on the board: distil-large-v3.5 5.40, whisper-large-v3 5.78, large-v3-turbo 6.36"** (§1)
   → The same CSV (https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results/resolve/c23ca4f…/english_short_latest.csv, read 2026-10-08) has `TheStageAI/thewhisper-large-v3-turbo` at **4.539** (RTFx 1,180.62, cc-by-4.0). That is a Whisper-large-v3-turbo fine-tune, and it beats Parakeet v2's 4.7025. The doc itself mentions this model in §2 "Context".
   → **wrong**
   → Fix: "beats every *openly runnable* Whisper variant". Note that TheWhisper is excluded because it needs TheStage's SDK and an access token (see #20).

2. **"Whisper large-v3 produced text for 40.3 % of 301k non-speech clips. With Silero VAD in front, the hallucination rate fell to 0.2 % (webrtcvad: 12.5 %)"** (§1 summary)
   → arXiv 2501.11378v1 (https://arxiv.org/html/2501.11378v1, read 2026-10-08):
     - The 40.3 % (121,378 of 301,317) comes from **experiment 1**, which used pure non-speech audio with **no VAD at all**.
     - The 0.2 % / 12.5 % / 21.3 % figures come from **Table VII (experiment in §V)**. That experiment used *speech* clips augmented with unseen non-speech audio from freenoise.org. The metric is the "Det. Hall." column (BoH-detected hallucinations), NO split. Its baseline is 21.3 %, not 40.3 %.
     - VAD segments were concatenated into one file before inference.
     - So "fell from 40.3 % to 0.2 %" is not a comparison the paper makes.
   → **wrong** (§4's table itself is correct and correctly labelled. Only the §1 sentence conflates the two experiments.)
   → Fix: "On pure non-speech audio, Whisper large-v3 hallucinated on 40.3 % of 301k clips. On speech padded or overlaid with non-speech, the detected-hallucination rate was 21.3 % without VAD, 12.5 % with WebRTC VAD and 0.2 % with Silero VAD (Table VII)."

3. **Implicit claim that [S19] covers music** (§1 "Guard against silence and music", §4 Evidence)
   → Same paper, §II-A: "Based on the provided tags, all audio files that could include speech, human voices and singing, were removed from the dataset. **We also removed all music** since tagging was not reliable enough…"
   → **wrong** (by implication). For Expause, music beds are probably the commonest no-speech case, and the cited evidence does not cover them.
   → Fix: say explicitly that no cited source measures ASR or VAD false-positives on music. Add music-only and music-with-vocals clips as an explicit test set in open question 1/6.

4. **"The live Space's displayed average also folds in two private Appen sets"** (§2, and open question 9)
   → Space `init.py`, version "02-10-2026" (https://huggingface.co/spaces/hf-audio/open_asr_leaderboard, lastModified 2026-10-02T14:13Z, read 2026-10-08): `default_datasets` ends with `"Private (scripted)", "Private (conversational)"`. In `app.py`, these are aggregates built from **Appen, DataoceanAI and Voice Arena private sets** (APPEN_SCRIPTED / APPEN_CONVERSATIONAL / VOICEARENA_CONVERSATIONAL, `create_private_data_dataframe` "merging Appen and DataoceanAI"). The changelog for 24 July 2026 says "Private data used in default average."
   → **wrong** (detail)
   → Fix: "two private aggregate columns (scripted and conversational) built from Appen, DataoceanAI and Voice Arena private data".

5. **Table, "WER 2026-07-24" column shows "n/a" for Qwen3-ASR-1.7B, granite-speech-4.1-2b, Cohere, Voxtral, Kyutai and Phi-4**
   → The 1d3e13c CSV (read 2026-10-08) has values for all of them:

     | Model | 07-24 value |
     |---|---|
     | Qwen3-ASR-1.7B | 5.02 (the -hf variant is 4.99) |
     | granite-speech-4.1-2b | 4.90 |
     | Cohere | 5.20 |
     | Voxtral-Mini-3B | 6.01 |
     | Kyutai | 5.74 |
     | Phi-4-multimodal | 5.42 |

     The column note also says the old column is "only for models that the 2026-07-31 update removed", yet it is filled for Parakeet, Canary and Whisper.
   → **wrong** (inconsistent table)
   → Fix: either fill every row from 1d3e13c or blank all rows except the removed models, and make the note match.

6. **`moonshine-voice` "Torch? = ?"** (§5)
   → PyPI JSON (https://pypi.org/pypi/moonshine-voice/json, read 2026-10-08): core deps are `numpy, sounddevice, requests, tqdm, filelock, platformdirs, google-crc32c`. Torch appears only in the `lora` and `finetune` extras.
   → **wrong** (an unknown that is easily resolved)
   → Fix: "No (torch only in `lora`/`finetune` extras)".

### Unsupported

7. **"roughly 7–9× faster than Whisper large-v3-turbo on the same CPU runtime"** (§1), **"About 9× slower on CPU"** (§6), **"Best English WER per CPU-second … 36.8 vs Whisper-turbo 3.9"** (§6)
   → onnx-asr benchmarks (https://istupakov.github.io/onnx-asr/benchmarks/, read 2026-10-08), 9800X3D:
     - fp32: Parakeet v2 36.8 vs turbo 3.9 (9.4×).
     - **int8: Parakeet v2 30.5 vs turbo 5.4 (5.6×)**.

     No configuration gives 7×. More importantly, this compares against **onnx-asr's own Whisper ONNX path**. The doc's actual fallback is faster-whisper/CTranslate2 int8, which is not benchmarked here, so the ratio says little about the fallback.
   → **unsupported**
   → Fix: "≈9× (fp32) / ≈5.6× (int8) faster than turbo *inside onnx-asr*. faster-whisper int8 was not compared." Add a head-to-head against faster-whisper int8 `turbo`/`distil-large-v3.5` to open question 3.

8. **"Leaderboard RTFx was measured on 1× H200 … according to IBM's model card"**; open question 9 says "RTFx hardware is stated as H200 only through IBM's card"
   → Space `init.py` changelog (read 2026-10-08): "**24 June 2026** — … Switch to H200 GPUs for eval". The GitHub README lists the HF Jobs flavour `h200 … 1x H200 (141 GB)` and notes "Long-form evaluations will migrate to HF Jobs in the near future".
   → **unsupported** as stated (the claim is true, but the primary source exists and was missed). The long-form RTFx is *not* necessarily H200.
   → Fix: cite the Space changelog, close open question 9's hardware part, and caveat the long-form RTFx hardware.

9. **"NeMo Frame VAD MarbleNet v2.0 | NeMo 2.3 [S33]"** (§4 VAD table)
   → The model card (https://huggingface.co/nvidia/Frame_VAD_Multilingual_MarbleNet_v2.0, read 2026-10-08) says `pip install -U nemo_toolkit['asr']` and gives no NeMo version. Its HF licence tag is `other` (NVIDIA Open Model License, "ready for commercial use"), which matches.
   → **unsupported**
   → Fix: drop "2.3" or cite where it comes from.

10. **"Parakeet v3 … Auto-detects among 25 EU languages, but no label is exposed (unverified)"**
    → The card (read 2026-10-08) says "The model automatically detects the language of the audio and transcribes it without requiring additional prompting." It shows no language-output API, which is consistent with the claim. But the card also now documents a **transformers** path (`AutoModelForTDT`, timestamps via `processor.decode(..., durations=...)`, "Until Parakeet TDT is part of an official Transformers release … install from source").
    → **unsupported/incomplete** (the claim is fine; the missing runtime path is covered in #21)
    → Fix: keep the claim, and add the transformers runtime as an option.

### Missing options

11. **sherpa-onnx as the Parakeet runtime** (only "not evaluated in depth" in §5)
    → k2-fsa/sherpa-onnx: 15,164 stars, Apache-2.0, release v1.13.8 on 2026-09-10 (GitHub API, read 2026-10-08). It ships `sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` (cc-by-4.0, HF `csukuangfj/…`) and has Silero VAD integration. It is backed by the k2/Next-gen Kaldi team rather than one person.
    → **missing option** (directly addresses the onnx-asr bus-factor risk in #22)
    → Fix: evaluate it alongside onnx-asr, checking word versus token timestamps, the VAD API and CPU RTFx. Keep the model choice runtime-agnostic.

12. **transcribe.cpp / GGUF Parakeet**
    → `handy-computer/parakeet-tdt-0.6b-v2-gguf` (cc-by-4.0, `timestamps: token`, "Validated against the NeMo reference"). The `handy-computer/transcribe.cpp` repo is MIT with 1,996 stars and was created 2026-04-07. It runs on CPU, Metal, CUDA and Vulkan with no Python at runtime. The same tool is IBM's documented path for granite-speech-5.0-turboctc (§3 mentions it only for Granite).
    → **missing option**
    → Fix: list it as a C++/no-Python alternative runtime for Parakeet.

13. **AutoArk-AI/ARK-ASR-0.6B: WER 4.56 (better than Parakeet v2), Apache-2.0, 19 languages, RTFx 663**
    → 2026-10-02 CSV. The card (https://huggingface.co/AutoArk-AI/ARK-ASR-0.6B, read 2026-10-08) describes a Whisper-style encoder plus a Qwen2 0.6B decoder, run through transformers `trust_remote_code`. It is an LLM-style AED, so it carries hallucination risk, and the card does not document timestamps.
    → **missing option** (an Apache-2.0 alternative if CC-BY attribution is a problem; open question 8 only names Granite)
    → Fix: add it to the table, noting "no timestamps documented, remote code".

14. **OpenMOSS-Team/MOSS-Transcribe-Diarize: WER 4.64, Apache-2.0, 0.9B, 50 languages**
    → The card (read 2026-10-08) claims "long-form multi-speaker transcription, diarization, timestamps, and **acoustic event awareness**" (transformers remote code, vLLM/SGLang). Sound-event tags such as [music] or [laughter] are a caption feature (SDH) that the doc never discusses.
    → **missing option**
    → Fix: add it to the table and add an open question on whether scenewise captions should carry non-speech event cues.

15. **Other open-weights models omitted from the table:** HojoAI/Hojo-ASR-V1 (4.33, Apache-2.0, 5.2B, RTFx 73), bosonai/higgs-audio-v3-stt (4.39, Apache-2.0, 2.7B, RTFx 111), AutoArk ARK-ASR-3B (4.48), nvidia/nemotron-speech-streaming-en-0.6b (5.25, NVIDIA Open Model License, RTFx 1,167), and nvidia/parakeet-unified-en-0.6b (2026-04-07, NVIDIA Open Model License, offline and streaming, not on the board).
    → 2026-10-02 CSV; HF API (`author=nvidia`, sorted by createdAt).
    → **missing option** (low priority: the large ones are GPU-bound, and the NVIDIA ones carry a different licence)
    → Fix: add one line saying these were considered and set aside, with reasons.

16. **The leaderboard's own "parakeet-tdt-0.6b-v2 (fast-gpu-asr)" row: WER 4.675, RTFx 14,199** (v3: 4.71 / 13,155)
    → 2026-10-02 CSV.
    → **missing option / minor**. This is relevant to "When to use GPU" (§6).
    → Fix: mention it and find out which inference stack "fast-gpu-asr" refers to.

17. **Cheap hosted ASR** (the brief allows "cheap hosted ones")
    → §3 dismisses hosted fallback because "local ASR is good enough" and compares no hosted ASR APIs, such as hosted Whisper or Parakeet endpoints or the proprietary leaders on the board.
    → **missing option** (low priority)
    → Fix: add one line naming 2–3 hosted options and why they were set aside (cost per minute, data leaving infrastructure).

### Design concerns

18. **The English-only model plus language-ID gate is sound, but the gate is under-specified.**
    → Points to settle:
      - Whisper LID needs a second Whisper model loaded just for LID. That adds weight unless it is a tiny or base checkpoint.
      - faster-whisper 1.2.1 has `WhisperModel.detect_language(..., vad_filter=…, language_detection_segments, language_detection_threshold=0.5)` (source, read 2026-10-08), which the doc does not mention.
      - Whisper-large-v3 LID averages **94.1 %**, against Qwen3-ASR-1.7B's 97.9 % (Qwen3-ASR card LID table, read 2026-10-08). That is a 1-in-17 miss rate before any music or short-clip effects.
      - The gate must run on VAD speech only, never on music.
      - The doc does not define what happens for mixed or code-switched videos, or how much non-English speech is "too much".
    → **design concern**
    → Fix:
      - Specify that the gate runs after VAD on the concatenated speech, using a small Whisper (tiny or base) through faster-whisper or onnx-asr, with a probability threshold.
      - Decide the policy for mixed-language videos (per-segment decisions versus the whole video).
      - Measure the cost on Expause clips.
      - Note that parakeet-v3 is an alternative for EU languages at almost no WER cost (4.86 vs 4.70) if non-English EU speech should be captioned rather than suppressed.

19. **onnx-asr VAD defaults will cut words at cue boundaries.**
    → `src/onnx_asr/vad.py` (GitHub main, read 2026-10-08): `_merge_segments` defaults are `min_speech_duration_ms=250, max_speech_duration_s=20, min_silence_duration_ms=100, speech_pad_ms=30`. Any speech run longer than 20 s is chopped at **fixed 20 s offsets** (`while end - start > max_speech_duration: yield …; start += max_speech_duration`), not at a silence. The usage page warns that "You will most likely need to adjust VAD parameters to get the correct results."
    → **design concern**. For continuous talking-head speech, words get split at 20 s boundaries.
    → Fix: add VAD-parameter tuning, and possibly scenewise-side re-segmentation at low-probability frames, to open question 4.

20. **onnx-asr timestamps are token *start* times only, relative to the VAD segment.**
    → `asr.py` `TimestampedResult`: `timestamps: list[float]  # "Tokens timestamp list"`, computed as `window_step * subsampling_factor * indices`, with no end times or durations, even though TDT predicts durations. Open question 4 correctly says "token" but does not mention the missing end times.
    → **design concern**. WebVTT cue end times will be inferred from the next token or the segment end.
    → Fix: add this to open question 4. NeMo, transformers (`durations=`) and parakeet-mlx (`AlignedToken`) do expose word or token alignments with durations.

21. **Single-runtime lock-in on an immature package.** Parakeet v2/v3 now also run in HF transformers (`AutoModelForTDT`, per the v3 card), in sherpa-onnx, in transcribe.cpp GGUF, in MLX and in NeMo.
    → **design concern**
    → Fix: put the ASR backend behind an interface so the runtime can be swapped without changing the model choice.

22. **onnx-asr maintenance / bus factor.**
    → GitHub API (read 2026-10-08): istupakov/onnx-asr has 382 stars and 34 forks. The contributors are `istupakov` 215 commits, dependabot 9, and four others with 1–3 each. That makes it effectively a single maintainer. Its last commit was 2026-08-16. Releases: 0.11.0 (2026-03-23) → 0.12.0 (2026-07-15).
    → For comparison:
      - faster-whisper: 25.7k stars, commits up to 2026-10-06, but **no release since 1.2.1 on 2025-10-31**.
      - NVIDIA NeMo: 18.6k stars, repo now NVIDIA-NeMo (`NVIDIA/NeMo` redirects to `NVIDIA-NeMo/Speech`), active.
      - sherpa-onnx: 15.2k stars, active.
    → onnx-asr's PyPI metadata also excludes `onnxruntime 1.24.1, 1.25.*, 1.26.0`, which shows it is sensitive to onnxruntime releases. The doc names no maintenance risk at all.
    → **design concern**
    → Fix: state the risk, pin onnx-asr and onnxruntime, keep sherpa-onnx or transformers as a tested second backend, and note that onnx-asr is MIT and small enough to vendor if it is abandoned.

23. **CC-BY-4.0 is acceptable, but the obligations are under-stated.**
    → CC-BY-4.0 allows commercial use. It requires attribution, a licence link, and **an indication of whether changes were made**. Using an ONNX re-export (and an int8 quantisation) is an adaptation. Captions are model *outputs*, and attribution is generally not considered to attach to them. The doc only says "attribution in our docs and NOTICE".
    → **design concern** (minor)
    → Fix: in the NOTICE, credit NVIDIA, link the licence, and state "converted to ONNX by istupakov; int8-quantised", if int8 is used. Keep the open legal check, but it is not a blocker.

24. **The faster-whisper fallback settings partly conflict with the batched pipeline.**
    → faster-whisper v1.2.1 `transcribe.py` (read 2026-10-08): `BatchedInferencePipeline.transcribe` hard-codes `condition_on_previous_text=False` **and `hallucination_silence_threshold=None`** (around lines 546–547). It defaults to `vad_filter=True`. `WhisperModel.transcribe` defaults to `vad_filter=False`.
    → **design concern / minor**. The §4 recommendation `hallucination_silence_threshold ≈ 2.0` is silently ignored if the batched pipeline is used.
    → Fix: note this in the decoding-settings table.

### Minor

25. **"8 public 'cleaned' English sets"**. Only AMI, Earnings22, Gigaspeech and Voxpopuli are "Cleaned" variants. LS clean, LS other, SPGISpeech and Voice Arena Monsoon are not. → **minor**. Fix: "8 public English sets (four of them 'Cleaned' variants)".

26. **"Qwen/Qwen3-ASR-1.7B" in the table**. The 2026-10-02 row is **`Qwen/Qwen3-ASR-1.7B-hf`** (the transformers-native checkpoint, 4.311). This matters for the claim that Qwen is "GPU-oriented … vLLM-heavy": the -hf checkpoint runs in plain transformers. Note also that `qwen-asr` 0.0.6 pins `transformers==4.57.6` (PyPI, read 2026-10-08), which conflicts with the transformers 5.x listed in §5. → **minor**. Fix: rename the row and mention both points.

27. **"usefulsensors/moonshine-streaming-medium"**. The HF API redirects to **`moonshine-ai/moonshine-streaming-medium`** (MIT). → **minor**. Fix: update the ID.

28. **Cohere Transcribe licence "Apache-2.0"**. This is correct, but the repo is **gated**: HF API `gated: auto`, and the card says "you have to accept the conditions to access its files". → **minor**. Fix: add "(gated)".

29. **"It runs on macOS Arm and x86 CPUs, CUDA and TensorRT [S9]"**. The benchmarks page [S9] lists no macOS hardware; its only Arm machine is an Orange Pi Zero 3. The claim is supported by the README instead: "Works on Windows, Linux, and macOS on x86 and Arm CPUs, with support for CUDA, TensorRT, CoreML, DirectML, ROCm, and WebGPU". → **minor** (miscitation). Fix: cite the README, and note CoreML as a possible Apple-silicon path for dev.

30. **"It has Silero VAD built in (`load_vad("silero")`)"**. It is not bundled: it is downloaded from HF `istupakov/silero-vad-onnx`, MIT, "version 6.2", last modified 2026-03-22. → **minor**. Fix: say it is downloaded from the hub, so the Cloud Run image must pre-fetch it, and record that it is v6.2 (which matches the §1 recommendation).

31. **"torch 2.14.1 … BSD-style"**. PyPI `license_expression` is "Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT". → **minor**. Fix: "BSD-3-Clause (plus bundled components)", or quote the expression.

32. **Open question 7 (TheStageAI TheWhisper) can be closed.** The card (https://huggingface.co/TheStageAI/thewhisper-large-v3-turbo, read 2026-10-08) says models are used "via TheStage AI Python SDK (ElasticModels), the TheStage Apple SDK … or deployed as Docker containers", and requires a "TheStage AI Access Token Setup" (`thestage config set --access-token`). The Apple SDK checks the token online. → **minor**. Fix: exclude it as "needs a proprietary SDK and access token".

33. **Cloud Run GPU paragraph**. The docs (https://docs.cloud.google.com/run/docs/configuring/services/gpu, "Last updated 2026-10-07", read 2026-10-08) also state: instance-based billing is mandatory; zonal redundancy is on by default "with additional cost per GPU second"; and region limits apply (L4 in five regions, RTX PRO 6000 in four). → **minor**. Fix: add these, because they affect the "scale to zero" cost story.

34. **"Granite 4.1-2B … Language ID: Not mentioned"** and **"turboctc … Timestamps and punctuation are undocumented"**.
    - Granite 4.1's card does say it does punctuation and truecasing by prompt, and it has a **GGUF / llama.cpp CPU path** (`ibm-granite/granite-speech-4.1-2b-GGUF:Q8_0`).
    - The turboctc card (read 2026-10-08) indeed documents neither timestamps nor punctuation, so that part is fine.

    → **minor**. Fix: add the Granite 4.1 punctuation and GGUF notes.

## Claims verified correct (brief)

- **Leaderboard 2026-10-02 (CSV c23ca4f), WER and RTFx:**
  - Parakeet v2 4.70 / 6,025; v3 4.86 / 6,076.
  - canary-qwen 4.43 / 867; canary-1b-v2 5.71 / 1,825.
  - whisper-large-v3 5.78 / 470; turbo 6.36 / 797; distil-large-v3.5 5.40 / 879.
  - Qwen3-ASR-1.7B(-hf) 4.31 / 820, the best open-weights model (only proprietary models rank above it).
  - granite-4.1-2b 4.62 / 546; 4.1-2b-nar 4.67 / 2,074; turboctc 5.03 / 20,946; turboctc-nc 4.84, cc-by-nc-sa.
  - Cohere 4.67 / 907; Voxtral-Mini 5.54 / 181; Kyutai 5.57 / 133; Phi-4 5.02 / 163.
  - zoom/scribe_v2_pro 3.59 is the top proprietary entry; TheWhisper 4.54 / 1,181, CC-BY-4.0.
  - The mean of the 8 public columns recomputes to 4.7025 for Parakeet v2.
- **Leaderboard 2026-07-24 (CSV 1d3e13c):** v2 5.39, v3 5.66, canary-qwen 5.06, canary-1b-v2 6.39, canary-1b-flash 5.78 / 2,126, large-v3 6.55, turbo 7.01, distil 6.10, moonshine-streaming-medium 5.77 / 2,681. The "avg cleaned" mean uses 7 sets.
- **Space versions:** the 31-07-2026 "Remove older models" entry and the 02-10-2026 latest are both confirmed in `init.py`, and the 02-10 version points at revision c23ca4f.
- **Long-form CSV 4f164c2:** v2 11.18 (9.02), v3 10.72 (9.10), turbo 11.01 (8.72).
- **Leaderboard paper** arXiv 2510.06961: A100-SXM4-80GB.
- **Licences (HF API tags):**
  - CC-BY-4.0: Parakeet v2/v3, the istupakov ONNX exports, canary-qwen, canary-1b-v2, canary-1b-flash, Kyutai.
  - Apache-2.0: whisper-large-v3 (on the HF card), Qwen3-ASR, Granite 4.1 and turboctc, Voxtral, Cohere, SpeechBrain VoxLingua107.
  - MIT: turbo, distil-large-v3.5 and its ct2 build, Phi-4, Moonshine (MIT, except legacy non-English models, which are non-commercial), pyannote segmentation-3.0 (MIT and gated).
- **Parakeet v2 card:** 24 min single pass; word, segment and char timestamps; "commercial/non-commercial use"; NeMo 2.2; MUSAN SNR table 6.05 / 8.23 / 11.88.
- **Parakeet v3 card:** 25 languages with automatic detection; word and segment timestamps; 24 min (A100) or 3 h with local attention; NeMo 2.4; release 08/14/2025.
- **Canary cards:**
  - canary-qwen: English-only; 40 s training max; NeMo trunk / ≥2.5 and PyTorch 2.6+; MUSAN 138.1 chars/min; no timestamps mentioned.
  - canary-1b-v2: `source_lang` required; word and segment timestamps; MUSAN 134.7.
- **Whisper-family cards:** turbo has 809M parameters and a 32→4 layer decoder, and warns about hallucination and repetition. distil-large-v3.5 is "~1.5x faster than Whisper-Large-v3-Turbo", English-only, MIT.
- **Qwen3-ASR card:** 52 languages and dialects; LID average 97.9 %; ForcedAligner 0.6B for ≤5 min in 11 languages; transformers and vLLM backends.
- **Other cards:**
  - Granite 4.1: word timestamps only in -plus.
  - turboctc: release 2026-08-25, "RTFx measured on 1 H200" as of 2026-10-02, transformers ≥5.16.0, transcribe.cpp GGUF.
  - Cohere: no timestamps, no automatic LID, "eager to transcribe, even non-speech sounds", recommends VAD.
  - Voxtral: ~9.5 GB GPU, 8 languages, auto LID.
  - Kyutai: English-only, 2.5 s delay, timestamps from stream offset.
  - VoxLingua107: 6.7 % dev error.
- **PyPI versions and dates:** all match.
  - onnx-asr 0.12.0 (2026-07-15, MIT, NumPy-only core, extras cpu/gpu/hub, Python ≥3.10).
  - onnxruntime 1.30.0 (2026-09-10, Python ≥3.11).
  - faster-whisper 1.2.1 (2025-10-31; ctranslate2, tokenizers, onnxruntime, av).
  - ctranslate2 4.8.2 (2026-08-31).
  - silero-vad 6.2.3 (2026-09-23, requires torch; onnxruntime optional from 6.2.1, torchaudio optional from 6.2.3).
  - parakeet-mlx 0.5.3; nemo-toolkit 3.0.0 (torch ≥2.6.0); sherpa-onnx 1.13.8.
  - whisperx 3.8.6 (torch~=2.8.0, pyannote-audio ≥4.0.0, Python <3.14).
  - openai-whisper 20250625; pywhispercpp 1.5.1; mlx-whisper 0.4.3 (requires torch); transformers 5.19.0; torch 2.14.1; qwen-asr 0.0.6; pyannote.audio 4.0.7; webrtcvad 2.0.10 and webrtcvad-wheels 2.0.14.post1.
- **Silero VAD:** MIT; v6.0 on 2025-08-26 with known issue "music with human voice-like instruments"; v6.2 on 2025-11-06; <1 ms per 30+ ms chunk on one CPU thread.
- **whisper.cpp** v1.9.5 (2026-10-06) with `--vad` and ggml `silero-v6.2.0`.
- **faster-whisper v1.2.1 source:** bundles `silero_vad_v6.onnx`. VadOptions defaults are `threshold=0.5`, `min_speech_duration_ms=0`, `min_silence_duration_ms=2000`. `vad_filter` defaults to False in `WhisperModel` and True in the batched pipeline. Decoding defaults: 0.6, -1.0, 2.4, `condition_on_previous_text=True`, `hallucination_silence_threshold=None`. The `turbo` alias points to mobiuslabsgmbh, which redirects to dropbox-dash. The README example uses `min_silence_duration_ms=500`, and the 13-minute benchmarks are 1m03s / 17 s and 1m42s / 51 s.
- **WhisperX README:** the "2014." / "£13.60" caveat.
- **parakeet-mlx:** writes VTT with word timestamps.
- **onnx-asr README:** "maximum audio length for most models is 20–30 seconds".
- **onnx-asr usage page:** `.with_vad()` and `.with_timestamps()` chain; it returns tokens, timestamps and log-probs; pyannote is available as an ONNX export.
- **onnx-asr benchmarks:** CPU 36.8 / 35.4 / 8.3 / 3.9; T4 57.6 / 57.5 / 21.4 / 9.2–25.9; TensorRT T4 fp16 237.2 / 232.3. Batch size, dataset and version are indeed unstated.
- **Cloud Run GPU:** L4 needs a minimum of 4 CPU / 16 GiB (8 / 32 recommended); RTX PRO 6000 is available; services scale to zero; drivers start in ~5 s.
- **arXiv 2501.11378:** 40.3 % of 301,317; "thank you" 24.76 % and "thanks for watching" 10.32 %; Table VII values 21.3 / 12.5 / 0.2. Silero plus deloop and BoH gives the lowest WER (6.5 vs 8.0 for Silero alone).
