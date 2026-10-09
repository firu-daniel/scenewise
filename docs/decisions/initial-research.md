# scenewise: initial research decisions

Status: Part 1 (research) complete, 2026-10-08. Part 2: steps 1–3 done on 2026-10-08 (section 8); steps 4–6 and
research question 9 are still to do. q10, q11, U16 and U17 (the PyAV licence and captions without PyAV) were added the
same day.

scenewise is an open-source, self-hosted Python service that understands video: captions, summaries, chapters, a
moderation second opinion and labels. Adopters run it in their own cloud and pay their own costs. Expause is its first
consumer, through an adapter that Expause builds on its own side.

This document records what the research decided and why. It does not repeat the research: every section links to the
findings file that holds the detail.

- **Findings** (all final after two review rounds): [`docs/research/`](../research/), files `q1-…` to `q8c-…`. q8c
  ([q8c-reconciliation.md](../research/q8c-reconciliation.md)) reconciles the earlier findings with each other before
  the skeleton is built; where it supersedes a passage of q1–q8b, q8c governs (its §9 lists every such passage).
- **Later findings** (final after one review round, 2026-10-08):
  [q10-pyav-ffmpeg-licence.md](../research/q10-pyav-ffmpeg-licence.md) (the licence of the FFmpeg in PyAV's wheels and
  of apt ffmpeg in the images) and [q11-asr-without-pyav.md](../research/q11-asr-without-pyav.md) (language ID and the
  Whisper fallback without PyAV; its scripts are in `docs/research/q11/`). Where they and U16/U17 supersede q2 or q8c
  (the LID backend, the `asr` extra, PyAV), they govern.
- **Decisions the user took during the research** (U1–U17 and U13a) and **orchestrator defaults** (D2–D31, with
  gaps explained in section 4.2):
  [`user-decisions.md`](../research/user-decisions.md). Both override anything in the findings files.
- **Questions still open**: [`open-decisions.md`](../research/open-decisions.md), summarised in section 7 below.
- **Sources.** Every external source cited here was read on **2026-10-08**; the findings files record the date for each
  one. Section 9 lists them. Citations in the text look like `[q2 §5.2]` (a findings file and section) or name the
  source directly.
- **Estimates.** Every cost figure is an estimate of AI processing cost only (scenewise's own compute for local models,
  hosted-model fees, and instance time billed while waiting for a hosted API). Storage, egress, Cloud Tasks and
  Expause's own compute are excluded, as the brief requires.

**Glossary.**

| Term | Meaning |
|---|---|
| ASR | Automatic speech recognition (speech to text) |
| VAD | Voice activity detection: finds the stretches of audio that contain speech |
| LID | Language identification |
| WER | Word error rate; lower is better |
| RTFx | Inverse real-time factor: seconds of audio processed per second of compute; higher is faster |
| GVI | Google Video Intelligence API, Expause's current label and explicit-content signal (deprecated, section 5) |
| CAS | Compare-and-swap: a write that succeeds only if the stored object has not changed since it was read |
| Likelihood buckets | Google's five-step scale `VERY_UNLIKELY`, `UNLIKELY`, `POSSIBLE`, `LIKELY`, `VERY_LIKELY` |
| U*n* / D*n* | A user decision / an orchestrator default (section 4) |
| E*n* | An Expause issue found while reading its code (section 6) |
| C*n* | A verified constraint of Expause's current pipeline, numbered in q1 §8.1 |
| T1–T4 | The captions tests q2 defines (music, timestamps, language ID, process smoke test; section 7.2) |
| OQ*n* | An open question in the cited findings file (for example q4 OQ3) |
| S*n* | A numbered source in the cited findings file's source list |
| L1 | A local measurement run for the cited findings file (section 9) |

---

## 1. Decisions at a glance

### 1.1 Per stage

| Stage | Model | Runtime | Where it runs | The sentence that decides it |
|---|---|---|---|---|
| **Captions** (roadmap 1) | NVIDIA **Parakeet-TDT-0.6b-v2** int8 (CC-BY-4.0, attribution per U4), behind **Silero VAD v6.2** and a **Whisper `tiny` language-ID gate** (fp32 ONNX on onnxruntime, in-house adapter; q11, U16). Fallback: faster-whisper `large-v3-turbo` (MIT), **opt-in** extra `asr-whisper`, not in published images (U16) | **sherpa-onnx 1.13.8** (D20), ASR only; scenewise's own Silero loop on onnxruntime 1.30.0; onnx-asr 0.12.0 CI-tested as the second runtime | Inside the scenewise Cloud Run CPU service (dev: the same stack on a macOS CPU) | Parakeet beats every openly runnable Whisper variant on the Open ASR Leaderboard (4.70% average WER vs 5.40–6.36%), runs about 5.6–9× faster than Whisper large-v3-turbo on CPU in the same runtime (5.6× at the int8 precision scenewise ships), and has native timestamps, which the few lower-WER models lack [q2 §1–§2]. Hosted Gemini 3.1/3.5 Flash-Lite captions are a close call on cost that the Cloud Run benchmark decides (section 7.1) [q7 §1]. |
| **Summaries + chapters** (roadmap 2) | **Claude Haiku 5.5** (`claude-haiku-5-5`), thinking disabled, effort `low`, structured output. Self-hosters and dev: **Qwen3.5-4B** (Apache-2.0) through an OpenAI-compatible local server | `anthropic` SDK with `AnthropicVertex`, **synchronous** (U5, U6) | Hosted: **Vertex AI EU multi-region** endpoint for Expause (U5), called from the Cloud Run service | Haiku costs about $0.00075 per video including the billed wait, about 17× less than a single-stream Qwen3.5-4B on Cloud Run CPU; a batched vLLM server on an L4 is unmeasured, with at most about $10/month at stake. Small local models score lower on zero-shot chaptering than larger hosted models, and Haiku 5.5 itself has no published chaptering benchmark, so the summaries eval decides quality (section 7.4) [q7 §1, §6, §7; q3 §Summary item 2]. |
| **Moderation second opinion** (roadmap 3) | Tier 1 on every frame: **Freepik/nsfw_image_detector** (MIT) + **SigLIP 2 zero-shot** prompts for violence, gore and weapons. Tier 2 on ambiguous or flagged frames only: a promptable guard, **Shieldstral-1.0-3B** (Apache-2.0) or **ShieldGemma 2 4B** (Gemma terms), not yet chosen (section 7). Optional third opinion: Haiku 5.5 | Local; guard out of process (q7 assumes a llama.cpp server) | Inside the Cloud Run CPU service | scenewise may only add an escalation, never clear content (U1), so it needs cheap local per-frame scores that map onto Google's Likelihood buckets, and Haiku cannot carry it: Anthropic documents that Claude does not process explicit images that violate its Usage Policy, so Haiku cannot be relied on for the sexual category (whether it refuses to classify or only declines to describe is untested, q4 OQ3) [q4 §Summary, S21]. |
| **Labels** (roadmap 4) | **SigLIP 2 ViT-B/16** (Apache-2.0) zero-shot against an **adopter-supplied taxonomy**; optional pooled video embedding from the same pass. Optional "rich tags" tier: Haiku 5.5 | `open_clip_torch` 3.3.0 on torch 2.14.1 (CPU) | Inside the Cloud Run CPU service | Every option costs under 5 cents per video, so cost does not decide. Gemini Embedding 2 also gives zero-shot labels from adopter text plus an embedding in one pass, but only a local open-weight model *combines* that with keeping data in the operator's infrastructure and no vendor lock-in on stored vectors [q5 §1, §5a, §5b]. |
| **Translation** (roadmap 5) | **Deferred.** When scheduled: source-language transcript → LLM translation with context, original cue timings kept. Hosted: Haiku 5.5; local: Qwen3, Gemma 4 or Seed-X | n/a | n/a | Whisper only translates into English, the best-known dedicated MT models are non-commercial or exclude the EU, and the commercially clean ones have no evidence on short informal speech, so nothing should be built before Expause names target languages and an evaluation set exists [q6 §Summary]. |

### 1.2 Runtime, cost and architecture

| Topic | Decision | The sentence that decides it |
|---|---|---|
| **Runtime overall** | One **Cloud Run service on CPU** in an EU Tier-1 region (europe-west1, or wherever Expause's buckets are), request-based billing, minimum 0 instances, **4 vCPU / 16 GiB to start, 8 GiB if the benchmark peak with the guard loaded stays below about 6 GiB**, `max_jobs = 1`, fed by Cloud Tasks through a **synchronous push handler** (U6). Weights baked into the image; two image variants, `-cpu` and `-cuda`, from one Dockerfile | Uploads are sporadic at these volumes, and only a scale-to-zero CPU service with request-based billing avoids paying for idle instances while still returning results within minutes; batch modes would save at most about $54–106/month at the largest cell and need intake code q8a does not have [q7 §1, open question 3]. |
| **Monthly AI cost** | **$1.89 / $3.11 / $16.28 / $25.23 / $131.15 / $218.46** for the six cells (table 1.3). Range across half and double the assumed CPU speed: **$1.28 to $420.62** | Cost is small at every volume in the grid, and the biggest uncertainty is Cloud Run CPU speed, so the first engineering task is a one-hour Cloud Run benchmark [q7 §1, open question 1]. |
| **Architecture style** | **Ports and adapters with a functional core and an imperative shell**, in idiomatic Python: `src/` layout, one distribution, layers `service > (adapters \| app) > ports > domain`, `typing.Protocol` ports only at I/O and model boundaries, plain functions for stages, frozen dataclasses for values, pydantic only at the boundary, one composition root, no DI framework | It gives a reviewer testable seams and a one-way dependency rule that import-linter can enforce, without Java-style ceremony: a Protocol exists only where there are two real implementations or a fake is needed [q8a §0, §2.2; q8b §3]. |

### 1.3 Monthly AI cost grid (recommended setup: Cloud Run CPU + Haiku 5.5, Vertex EU price, free tier off)

| Monthly active users | Posting rate | Videos/month | Video-hours/month | CPU speed ×1 | ×0.5 (half as fast) | ×2 (twice as fast) |
|---|---|---|---|---|---|---|
| 1,000 | 3% | 129.9 | 10.8 | **$1.89** | $3.10 | $1.28 |
| 1,000 | 5% | 216.5 | 18.0 | **$3.11** | $5.13 | $2.10 |
| 10,000 | 3% | 1,299.0 | 108.2 | **$16.28** | $28.41 | $10.21 |
| 10,000 | 5% | 2,165.0 | 180.4 | **$25.23** | $45.45 | $15.13 |
| 100,000 | 3% | 12,990.0 | 1,082.5 | **$131.15** | $252.45 | $70.51 |
| 100,000 | 5% | 21,650.0 | 1,804.2 | **$218.46** | $420.62 | $117.38 |

Source: output of `python3 -I docs/research/q7_cost_grid.py` [q7 §6, "Totals overview" and "Sensitivity"]. At 8 GiB
instead of 16 GiB every CPU cell falls by 14–15% ($1.62 to $187.43). With the Cloud Run free tier on, the two 1k cells
fall to about $0.05–0.08/month [q7 §7].

The grid predates U14: it still charges a Haiku summary and its 3 s billed wait on the 40% of videos without
speech, which get no summary in v1. It is therefore conservative by about $0.00025 per video on average, about
$5/month at 100k × 5% [q7 §5 step 6; U14]. Set the no-speech summary share to 0 at the next re-run.

**Where the numbers are weakest** [q7 §1]: two pure guesses, Freepik on CPU and the tier-2 guard, make up 61% of the
local CPU seconds per video, and every M4 measurement passes through one guessed M4-to-Cloud-Run factor (2.5). The
benchmark in section 7 replaces them.

---

## 2. Cost-grid parameters and how to recompute

All inputs are named constants at the top of [`docs/research/q7_cost_grid.py`](../research/q7_cost_grid.py) (stdlib
only). Change a constant, then run:

```
python3 -I docs/research/q7_cost_grid.py
```

It prints the per-stage tables for every runtime column, the totals, the sensitivity rows and the crossovers. The
figures in section 1.3 reproduce exactly (checked 2026-10-08).

### 2.1 Volume parameters (from the brief)

| Constant | Value | Meaning |
|---|---|---|
| `MAU_VALUES` | 1,000 / 10,000 / 100,000 | Monthly active users |
| `POSTING_RATES` | 0.03 / 0.05 | Share of MAU who post |
| `VIDEOS_PER_POSTER_PER_MONTH` | **4.33** | 1 video a week per poster × 4.33 weeks/month |
| `AVG_VIDEO_MIN` | **5** | Average video length, minutes |
| `ACTIVE_HOURS_PER_DAY` | 16 (guess) | Spreads uploads over the day; sets cold-start probability and batch slots |

Videos per month = MAU × posting rate × 4.33. Example: 1,000 × 0.03 × 4.33 = 129.9 videos = 10.8 video-hours.

### 2.2 Content parameters (all guesses until Expause supplies data, section 7)

| Constant | Value | Meaning |
|---|---|---|
| `AUDIO_VIDEO_SHARE` | 0.90 | Videos with an audio stream (Expause does not persist `hasAudio`, E9) |
| `SPEECH_VIDEO_SHARE` | 0.60 | Videos that pass the VAD gate; ASR runs only on these |
| `SPEECH_FRACTION` | 0.70 | Share of a speech video that is speech (210 s of a 5-min video, 7 LID windows of ≤30 s) |
| `FRAME_INTERVAL_S` | 10 s → 30 frames | Expause's preview interval for 1–5-minute videos [q1 §3.1] |
| `ESCALATED_FRAME_SHARE` | 0.02 | Frames sent to the tier-2 guard |
| Summary tokens | 2,450 in / 300 out (speech); 1,160 / 150 (no speech) | Speech: q3 scenario A ÷ 12 videos per hour; no speech: a guess, and not spent in v1 (U14; section 1.3) |

### 2.3 Stage parameters

| Constant | Value | Kind | Stage |
|---|---|---|---|
| `CLOUD_SLOWDOWN_VS_M4` | 2.5 | guess | All CPU steps measured on an Apple M4 |
| `CPU_SPEED_FACTOR` | 1.0 (0.5 and 2 in the sensitivity rows) | knob | Scales every CPU step |
| `PARAKEET_M4_RTFX_4T` | 32.3 → RTFx 12.9 on 4 vCPU | measured on M4 [q2 L1] | Captions |
| `VAD_RTS_1THREAD` × `VAD_CLOUD_EFFICIENCY` | 165 × 0.7 | measured (Silero V5) × guess | Captions |
| `LID_S_PER_WINDOW_M4` | 0.65 s × 7 windows × 2.5 | measured × guess | Captions |
| `SIGLIP_MS_M4` | 37 + 5.4 + 3.5 = 45.9 ms → 115 ms | measured [q5 §3] | Labels, moderation |
| `FREEPIK_MS_M4` | 400 ms → 1.0 s | **guess** | Moderation tier 1 |
| `GUARD_S_PER_FRAME_CPU` | 20 s | **guess** | Moderation tier 2 |
| `DECODE_S_CPU` / `TEXT_EMBED_S_CPU` | 4 s / 0.5 s | guess | Shared (the transcript embedding is not built in v1, so its 0.5 s is conservative; Q5) |
| `HAIKU_WAIT_S` | 3 s | guess | Summaries (billed wait) |
| `COLD_START_S_CPU` | 35 s (10 s image + 9.9 s model load × 2.5) | derived | Overhead |
| `CPU_VCPU` / `CPU_GIB` / `CPU_GIB_SMALL` | 4 / 16 / 8 | decision / sensitivity | Shape |
| `HAIKU_PRICE_MULT` | 1.10 | Vertex EU premium [q7 S25, S27] | Summaries |
| `APPLY_FREE_TIER` | False | Cloud Run free tier is per billing account | All |

Prices (Cloud Run Tier 1, Haiku 5.5, Gemini 3.x Flash-Lite, Speech-to-Text V2, Compute Engine) are constants too, with
their sources in q7 §5.

**After the Cloud Run benchmark** (section 7.1): set `CLOUD_SLOWDOWN_VS_M4`, `FREEPIK_MS_M4`, `GUARD_S_PER_FRAME_CPU`,
the cold-start inputs `CPU_IMAGE_START_S` and `OTHER_MODELS_LOAD_S_M4` (`COLD_START_S_CPU` is derived from them),
and `CPU_GIB`, then re-run. **When Expause supplies its content mix**: set the content constants.

---

## 3. Answers to the research questions

### Q1. Input contract and the Expause adapter

**Decision.**

- **What scenewise accepts, per stage** [q1 §4]:

  | Stage | Needs | Input kinds |
  |---|---|---|
  | captions | audio | one video or audio file; fMP4/MPEG-TS segments (inline ≤ 200, or a list by reference); an **HLS** manifest; or `none` |
  | summary, chapters | the transcript (v1 is speech-only, U14; visual input arrives with roadmap item 4), plus optional title/description/tags | — |
  | moderation, labels | visual | a video (sampled every `interval_s`); frames with explicit times; interval thumbnails from a URI template; **raw sprite sheets with grid, tile size, interval, start offset and optional count supplied explicitly** |

  Requests are a versioned pydantic `JobRequest` (`schema_version: "1"`, caller-chosen `job_id`, `extra="forbid"`).
  Inputs are URIs, fetched through scenewise's own storage port under an allow-list (`gs://` on configured buckets,
  `https://` on configured hosts, no redirects, no private addresses; `file://` only in CLI mode). ffmpeg never sees a
  remote URL. Encrypted inputs are refused. v1 narrows q1's types: **HLS only, no DASH; frame sampling by file and
  interval, no `scene`** (D10).
- **What it returns** [q1 §5]: a small **job record** (`status.json`, written with compare-and-swap in GCS) and, under an
  attempt-scoped prefix, `result.json` plus **`captions.vtt`** (W3C WebVTT, presentation-timeline times). The record
  carries `schema_version`, `scenewise_version` and an optional `external_ref` (D9). Errors carry a code and one of
  three categories: `input` (never retried), `retryable`, `internal`. A missing input gets its own code,
  `input_unavailable` (D7).
- **Captions run over one continuous track, never per 6-second segment** [q1 §6].
- **Sprite sheets**: the caller supplies grid, tile, interval and offset from the Transcoder job config; scenewise never
  infers them [q1 §7].
- **Trigger and results** (the Expause side, built later in Expause) [q1 §8]:
  - The Transcoder job gets one extra standalone audio-only MP4 mux stream (`scenewise_audio.mp4`, not in any
    manifest).
  - Expause's success handler copies that file and the raw sprite sheets to a private staging bucket and enqueues one
    Cloud Task with a generic `JobRequest` (about 1–2 KB). It never throws, has a 15 s budget, and is skipped once the handler has used more than 120 s [q1 §8.3]. The encryption loop
    deletes the copied sources unread.
  - `POST /v1/jobs` is a **synchronous Cloud Tasks push handler** (q8a §6): it answers when the job is terminal.
    Idempotency key `job_id = "um-{mediaId}-r{rev}"`.
  - Expause reads `status.json` and `result.json` from GCS on an `onObjectFinalized` event, plus a **mandatory daily
    reconciliation** through `GET /v1/jobs/{id}`. An HTTP callback is optional and only a hint.
- **Audio-less videos** [q1 §9]: `captions = {status: "skipped", reason: "no_audio_stream"}`, no VTT; the job still
  succeeds and the visual stages still run.

**Key evidence.**

- One 104 s TTS clip cut into Expause-style 6 s fMP4 AAC segments (local experiment, Apple M4, faster-whisper 1.2.1,
  2026-10-08; indicative only): per-segment transcription made 26 errors in 349 words (7.4% WER) with `base.en` and 45
  (12.9%) with `small.en`; the stitched track made 0.9–1.1% and 1.4–1.7% [q1 §6.2, L1].
- Expause's Transcoder writes separate fMP4 audio in 6 s segments, and writes **no** audio stream for an audio-less
  source (`transcoding/app_transcoding.ts:910-935`, read at Expause HEAD `32ed0bf18`) [q1 §3.1].
- An audio stream in a Transcoder job that has video "counts as complimentary"; "the charge is based only on the video
  class" (Transcoder pricing, https://cloud.google.com/transcoder/pricing) [q1 S15].
- "The maximum task size is 100KB" (Cloud Tasks `tasks.create`,
  https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks/create), so long segment
  lists go by reference [q1 S13].
- URI allow-listing follows the OWASP SSRF cheat sheet
  (https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) [q1 S21].

**Rejected, and why** [q1 §8.2, §11; q8a §12, Q-12, Q-16, Q-17].

| Option | Why rejected |
|---|---|
| Per-segment ASR | About one extra error per segment boundary, and no context at segment start |
| Stitching in Expause's 180 s success handler (download 900 segments, or GCS `compose`) | On the critical path to publishing: the handler has a 180 s timeout with no retry, and anything that fails before encryption leaves the media unencrypted and unpublished (q1 C1, C2) |
| scenewise reading segments straight from the transcoder prefix | Races the encryption loop, which deletes them within minutes |
| Triggering from the end of the encryption loop | Exposed to Expause issue E7 (the `encrypt_video/{uid}` overwrite; Expause issues are listed in section 6) |
| Delaying encryption until AI is done | Publishing must not wait for AI |
| Decrypting from the CDN | Couples an open-source service to Expause's key scheme; kept only as an adapter-side backfill option (D31) |
| An Expause-shaped route or `adapters/expause/` in scenewise | scenewise contains no consumer code; Expause sends the generic contract |
| 202 + scenewise-owned queue | Needs a second queue and always-on CPU, and ends Cloud Tasks' retry for the actual work |
| At-least-once callbacks with a retry scheduler | The record is the source of truth; best-effort callback plus reconciliation is one mechanism |
| Inferring sprite geometry from `media.duration` | That is exactly Expause's bug E1 |

Detail: [q1-input-contract.md](../research/q1-input-contract.md).

### Q2. Captions (roadmap item 1)

**Decision** [q2 §1, §6; q8c §2, §3, §5; q11 §1, §3.5; U16].

| | Development (macOS Apple Silicon, CPU) | Production (Cloud Run CPU, EU) |
|---|---|---|
| Model | Parakeet-TDT-0.6b-v2 int8, pinned revision | same |
| Runtime | sherpa-onnx 1.13.8, ASR only | same |
| VAD | scenewise's own Silero v6.2 ONNX loop on onnxruntime 1.30.0 (`CPUExecutionProvider` set explicitly), runs cut at ≤ 30 s at the lowest-probability frame, then merged into ≤ 30 s recognition segments across gaps < 2 s (q8c §2) | same |
| Language-ID gate | In-house adapter: Whisper `tiny` fp32 encoder + decoder (`onnx-community/whisper-tiny` @ `ff41770`, MIT per OpenAI Whisper) on pip onnxruntime + numpy, one decoder step, softmax over the language tokens; batch = 1 by default; VAD speech windows only. A window is English if it holds ≥ 1.0 s of VAD speech and p(en) ≥ 0.5; English windows are captioned when they total ≥ 2 s of speech (D19); "unknown" windows dropped and flagged (D21) [q11 §2.3, §3.5; U16]. Replaces faster-whisper `tiny` `detect_language` with argmax p ≥ 0.5: white noise reaches argmax p 0.48–0.57, but p(en) ≤ 0.18 | same |
| Fallback | faster-whisper `large-v3-turbo` (or `distil-large-v3.5`), `vad_filter=False` (spans already VAD-cut, q8c §2), `condition_on_previous_text=False`. **Opt-in** extra `asr-whisper`: faster-whisper hard-requires PyAV, whose wheels bundle GPL x264/x265 (q10); published images leave it out (U16) | self-built images only |
| No speech | No VTT; the stage is `skipped` with reason `no_speech` (D23, confirmed by q8c §5) | same |

q8c refines three rows [q8c §2]: VAD runs are cut at ≤ 30 s and then **merged** into recognition segments of up to
30 s across pauses shorter than 2 s (`merge_gap`), never across a dropped non-English piece; the language-ID adapter
sees only concatenated speech spans; and the fallback runs with `vad_filter=False`, because its spans are already
VAD-cut (superseding q2 §4.3's `vad_filter=True`; the table above already shows the reconciled values).

All ASR goes through a `SpeechRecognizer` port, with VAD and language ID behind their own ports (Q8); onnx-asr 0.12.0
is a second adapter run on the same fixtures in CI, so the runtime choice is reversible. In v1 every ASR runtime runs
on CPU, in both images [q8c §3]. Weights are mirrored into scenewise-controlled storage, verified by sha256 and baked
into the image. Parakeet's CC-BY-4.0 attribution, including the ONNX conversion and int8 quantisation, goes in NOTICE
and README (U4). Music handling (an AudioSet tagger flag or "[music]" cues) waits for test T1 (D22).

**Close call, the benchmark decides: hosted Gemini 3.1 / 3.5 Flash-Lite captions** on Vertex EU, behind the same VAD
gate. Local is 1.6× / 1.4× cheaper at CPU speed ×1, but both Gemini models are cheaper at ×0.5, so the Cloud Run
benchmark settles local vs Gemini (section 7.1). Gemini would also change the product (multilingual captions without the
LID gate), its word-timestamp quality is unverified, and whether Gemini 3.x is served on the `eu` endpoint is open
(q7 OQ9) [q7 §1, §7].

**Key evidence.**

| Claim | Evidence | Source |
|---|---|---|
| WER | Parakeet v2 4.70% average over 8 public English sets; distil-large-v3.5 5.40, whisper-large-v3 5.78, large-v3-turbo 6.36 | Open ASR Leaderboard results CSV, revision c23ca4f (2026-10-02 snapshot), https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results/resolve/c23ca4f10e5f1a77c9fd3b41e17cd06a04f0f56c/english_short_latest.csv [q2 S2] |
| CPU speed | In onnx-asr on a Ryzen 7 9800X3D: Parakeet 36.8 vs turbo 3.9 RTFx (default), 30.5 vs 5.4 (int8) | https://istupakov.github.io/onnx-asr/benchmarks/ [q2 S9] |
| Local speed and memory | sherpa-onnx int8 about 32 RTFx on a 12.6 s clip (M4, 4 threads); peak RSS 1.33 GB for the whole audio stack on linux/amd64 | local check, 2026-10-08 [q2 §6.1, §6.2, §10 L1] |
| Timestamps | Native word, segment and character timestamps in NeMo; sherpa-onnx returns token starts plus TDT durations (0–0.32 s per token) and log-probabilities | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2 [q2 S6]; https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8/sherpa-onnx [q2 S53] |
| Silence and hallucination | Whisper large-v3 without VAD hallucinated on 40.3% of 301,317 non-speech clips; on padded speech clips the rate was 21.3% unprocessed, 12.5% with WebRTC VAD, 0.2% with Silero VAD. Music was excluded from that study, so no source covers music beds | Barański et al., arXiv 2501.11378v1, https://arxiv.org/html/2501.11378v1 [q2 S19] |
| Why an LID gate | Parakeet v2 is English-only; locally it turned German speech into invented pseudo-English | [q2 §1, L1] |
| Licence | Parakeet v2 weights CC-BY-4.0; Silero MIT; Whisper weights (and their ONNX and CTranslate2 conversions) MIT; sherpa-onnx Apache-2.0. PyAV's bundled FFmpeg is effectively GPL-3.0-or-later (x264/x265), hence U16 | [q2 §5.3; q10 §1; q11 §1] |

**Rejected, and why** [q2 §2, §5.1, §6.2].

| Option | Why rejected |
|---|---|
| Whisper (`openai-whisper`, `faster-whisper`, `whisper.cpp`) as primary | Higher WER (5.78–6.36), 5.6–9× slower on CPU in onnx-asr, documented non-speech hallucination. Kept as the fallback |
| Distil-Whisper as primary | 5.40 WER, English-only, word timestamps only through faster-whisper alignment; kept as a fallback model option |
| TheStageAI thewhisper-large-v3-turbo (4.54) | Runs only through a proprietary SDK with an online-checked token and encrypted weights |
| Qwen3-ASR-1.7B (4.31), ARK-ASR-0.6B (4.56), MOSS-Transcribe-Diarize (4.64) | Autoregressive LLM decoders on Torch; timestamps need a separate aligner (Qwen), are undocumented (ARK) or segment-level only (MOSS) |
| Canary-Qwen-2.5B, Canary-1b-v2 | Canary-Qwen: timestamps not on the card; Canary-1b-v2: higher WER (5.71) and the source language must be given |
| Cohere Transcribe | Gated, no timestamps, no language ID |
| onnx-asr as primary | Token start times only (a durations patch scenewise would own), single maintainer; kept as the CI-tested second runtime (D20) |
| transcribe.cpp | Three releases in two weeks, bindings "in development"; watch |
| NeMo / transformers in production | Torch; used only as the offline timestamp and WER oracle |
| sherpa-onnx's own VAD | No frame probabilities and no forced cut (a 55.6 s utterance stayed one segment) |
| `silero-vad` from PyPI | Requires torch; the ONNX file is used instead |
| Hosted captions on Speech-to-Text V2 | Standard is about 13× local (Q7) |

Detail: [q2-captions.md](../research/q2-captions.md).

### Q3. Summaries and chapters (roadmap item 2)

**Decision** [q3 §Summary; U5, U6, U7, U14; q8c §5, §7.1].

- **Expause: Claude Haiku 5.5, synchronous**, through **Vertex AI's EU multi-region endpoint** (U5). One Anthropic-SDK
  adapter supports both `Anthropic` (first-party) and `AnthropicVertex`; provider and region are deployment settings.
  Send `thinking: {"type": "disabled"}` and `output_config.effort: "low"`, use structured outputs, end with a user turn,
  and select content blocks by `type`. Batch is not built in v1 (U6).
- **Dev and self-hosters on CPU: Qwen3.5-4B** (Apache-2.0) through an OpenAI-compatible local server (llama.cpp
  or Ollama; vLLM for the GPU escalation tier) with JSON-schema output and thinking off. With frame labels and enough hardware, prefer Qwen3.5-9B or
  Qwen3.6-35B-A3B.
- **One provider interface** (prompt, schema, validator) with three back ends: Anthropic, a local runtime, and any
  OpenAI-compatible hosted endpoint. A Python validator enforces the chapter rules no schema can express (first chapter
  at 0, strictly ascending, each ≥ 10 s, ≥ 3 chapters, within the duration); on failure, chapters are dropped, not the
  summary.
- **Cost per video-hour (Haiku 5.5, first-party list price):** about **$0.0047 synchronous**, $0.0024 with Batch
  (scenario A: 150 wpm, transcript plus timestamps, thinking disabled). Vertex EU adds 10% [q7 §2.3].
- **Minimum length (U7):** chapters only for videos **≥ 120 s with ≥ 3 valid chapters**; a summary only from **about 40
  transcript words**. Both thresholds are configurable and re-tuned on real samples. Below them the stage is `skipped`
  with reason `below_minimum` (q8c §5; this replaces q3's `chapters: []`).
- **v1 summaries and chapters are speech-only (U14).** Without a transcript, or under about 40 words, the summary is
  `skipped / below_minimum`, so audio-less, silent and music-only videos get no summary in v1; `inputs_used` is
  `["transcript"]` (plus `"context"`), never `"frames"` [q8c §5]. This narrows q1 §9 and q3's visual fall-through.
- **Frame labels, later: as a secondary input**, in a separately marked block (`VISUAL LABELS (automatic, may be wrong)`),
  never moderation labels, with `basis: "speech" | "visual" | "both"` in the output. They, and visual-only summaries
  with a tested label-based rule, arrive with roadmap item 4 (U14; q8c §5 gives a starting rule).
- **Refusals:** `TextGenerator.generate` returns a `Generation(text, model, refused)`; the Anthropic adapter sets
  `refused` from `stop_reason == "refusal"`. A refusal fails the stage with `InternalError("model_refused")`, is logged,
  and is never retried; `FallbackTextGenerator` passes it through unchanged, and it is checked before any JSON parse or
  repair retry [q8c §7.1; D18]. Server-side `fallbacks` are never sent.

**Key evidence.**

| Claim | Evidence | Source |
|---|---|---|
| Price | Haiku 5.5 $0.10 in / $0.50 out per MTok (prompts ≤ 100k); Batch 50% off; Haiku 4.5 $1 / $5 | https://platform.claude.com/docs/en/about-claude/pricing [q3 S1] |
| Vertex EU | Regional and multi-region endpoints carry a 10% premium; Haiku 5.5 is served on global, US and EU multi-region | https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai [q7 S25]; https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-5-5 [q7 S26]; https://cloud.google.com/vertex-ai/generative-ai/pricing [q7 S27] |
| Thinking off | "`thinking: {"type": "disabled"}` at `high` effort or below" is allowed on Haiku 5.5 | https://platform.claude.com/docs/en/build-with-claude/effort [q3 S35] |
| Chaptering quality | Zero-shot Llama-3.1-8B 29.5 F1 on VidChapters-7M; GPT-4o-mini 31.2, Gemini-2.0-Flash 40.2 on a 10% subset; speech + captions beats speech alone zero-shot (29.9 vs 22.7); with captions a 3B model gains nothing while 8B gains about 4 F1 | Chapter-Llama, CVPR 2025, https://arxiv.org/html/2504.00072v1 [q3 S14] |
| Chapter rules | First timestamp 00:00, at least three timestamps, each chapter ≥ 10 s | YouTube Help, https://support.google.com/youtube/answer/9884579 [q3 S16] |
| Licences | Qwen3/3.5/3.6/3.8 Apache-2.0, verified per checkpoint (some are not permissive and excluded, for example Qwen3.8-Flash-Next); Gemma 4 Apache-2.0; Llama 3.2 and 4 AUPs withhold multimodal rights from EU-based companies | Hugging Face model API per checkpoint, https://huggingface.co/api/models/<id> [q3 S38]; https://huggingface.co/Qwen/Qwen3.5-4B [q3 S10]; https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html [q3 S11]; https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/USE_POLICY.md [q3 S19]; https://github.com/meta-llama/llama-models/blob/main/models/llama4/USE_POLICY.md [q3 S21] |
| Refusals | Haiku 5.5 can return `stop_reason: "refusal"`; "server-side fallback isn't available" | https://platform.claude.com/docs/en/models/haiku-5-5/whats-new-haiku-5-5 [q3 S5a]; https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback [q3 S43] |

**Rejected, and why** [q3; q7 §7].

| Option | Why rejected |
|---|---|
| A local LLM as Expause's default | A single-stream local LLM costs about 17× Haiku per video on Cloud Run CPU (wait included) and about 3× on a fully busy L4; a batched vLLM server is unmeasured (at most about $10/month at stake). Small local models score lower on zero-shot chaptering than larger hosted models; Haiku 5.5 has no published chaptering benchmark, so the summaries eval checks quality (section 7.4) [q3 §Summary item 2; q7 §7] |
| Message Batches for fresh uploads | Results can take up to 24 h; saves about $0.0002 per video; and U6 keeps v1 synchronous |
| Haiku 4.5 | 10× the price of Haiku 5.5; its 4,096-token cache minimum means the prompt prefix never caches |
| Llama 3.2 / 4 as default | Attribution and AUP obligations, and the EU multimodal carve-out excludes an EU operator (U3) |
| Gemma 3 and earlier | Gemma Terms flow-down obligations; Gemma 4 (Apache-2.0) removes the issue |
| LiquidAI LFM2.5, non-permissive Qwen checkpoints | Not Apache/MIT |
| FrogNano-4B | A coding agent, "not designed or evaluated as a general-purpose assistant" |
| Hosted open-weight models via OpenRouter as primary | 0.6–4.6× Haiku's price, none cheaper than Haiku Batch; kept as an option for self-hosters without a GPU |
| Gemini 2.5 Flash-Lite (listed by q3 as an unevaluated price comparison) | Retires on Vertex AI on 2026-10-20; any Gemini Flash-Lite figure in this document uses 3.1 or 3.5 [q4 S46; q5 S52] |

Detail: [q3-summaries-chapters.md](../research/q3-summaries-chapters.md).

### Q4. Moderation second opinion (roadmap item 3)

**Decision** [q4 §Summary, §Likelihood mapping, §Combination rule; U1, U8; q8c §4.2, §7.2].

- **scenewise may only escalate a video; it never clears one** (U1).
- **Tier 1, every sampled frame, local CPU:** Freepik/nsfw_image_detector (four graded levels that map almost directly
  onto Google's Likelihood buckets); Marqo/nsfw-image-detection-384 as the small fallback; SigLIP 2 zero-shot prompts for
  violence, gore and weapons (no accuracy evidence until evaluated). The SigLIP prompts go through the same
  `ZeroShotLabeller` port as labels, with a moderation prompt set from `domain/moderation.py`; no new port. Without a
  labeller those categories are reported as absent, not hidden [q8c §7.2].
- **Tier 2, ambiguous or flagged frames only:** a promptable guard with a continuous yes/no score, Shieldstral-1.0-3B or ShieldGemma 2
  4B (model choice still open, section 7.5). Nemotron 3.5 Content Safety is dropped until NVIDIA's licence naming is
  clarified (D24). **Wiring** [q8c §4.2]: its own `ImageGuard` port (`p_yes(frame, policies) -> list[float]`, P(yes)
  renormalised over the yes/no tokens), implemented by `adapters/llm/openai_guard.py` against a guard server in a
  separate process (llama.cpp `llama-server` or vLLM), not through `TextGenerator`, because its input is an image and
  its output a probability read from `top_logprobs`. It adds no Python dependency (httpx). Whether the chosen server
  returns `top_logprobs` for image + text requests is verified with item 3.
- **Optional third opinion: Haiku 5.5**, for non-sexual categories and context, with frames passed through
  `TextRequest.images` (no new port) [q8c §4.2]. A refusal means "escalate to a human", never a verdict.
- **Optional, off by default: OpenAI `omni-moderation-latest`** as a zero-cost hosted tier-2 / third opinion. It is not a
  candidate primary, and it is off by default because frames leave the operator's infrastructure [q4 §Hosted options].
- **Mapping:** scenewise emits `sexual`, `violence_gore`, `weapons`, `dangerous` separately, bucketed to
  `VERY_UNLIKELY … VERY_LIKELY` (starting cut-offs for probability models: < 0.15, 0.15–0.35, 0.35–0.60, 0.60–0.85,
  ≥ 0.85; recalibrated on data). Video likelihood is the max over frames, with a persistence guard (a single-frame LIKELY
  becomes POSSIBLE unless a neighbour is ≥ POSSIBLE). Raw score, model version and threshold-set version are always
  stored.
- **Combination rule (primary-agnostic):**

  | Primary (per covered category) | scenewise | Action |
  |---|---|---|
  | any | within ±1 bucket | agreement; Expause's rule decides |
  | ≤ UNLIKELY | ≥ LIKELY | escalate to human review |
  | POSSIBLE | ≥ LIKELY | escalate, high priority |
  | ≥ LIKELY | ≤ UNLIKELY | primary's rule applies; logged as disagreement; never auto-restored |
  | any | Haiku refusal or tier-2 VERY_LIKELY | escalate |
  | category not covered by the primary | ≥ LIKELY | escalate to human |

  Modes: `advisory` (default) and `max` (opt-in after the shadow evaluation shows acceptable precision). A mode in
  which scenewise is primary is not offered.
- **Evaluation uses public benchmarks only**, run by an authorised operator outside the repo; the repo holds only code,
  dataset identifiers and metrics, and CI uses benign synthetic fixtures. The primary evaluation is a **shadow run inside
  Expause** against moderator decisions. Anything suspected to involve a minor leaves the scenewise path for Expause's
  CSAM procedure; scenewise does not classify age.

**Key evidence.**

| Claim | Evidence | Source |
|---|---|---|
| Claude may be used for moderation | Content moderation, including images, is a documented use case; the Usage Policy prohibits *generating* sexual content, not classifying it | https://platform.claude.com/docs/en/about-claude/use-case-guides/content-moderation [q4 S20]; https://www.anthropic.com/legal/aup [q4 S19] |
| But not for explicit images | Claude "does not process inappropriate or explicit images that violate the Acceptable Use Policy". Whether Haiku refuses to classify such frames or only declines to describe them is untested (q4 OQ3) | https://platform.claude.com/docs/en/build-with-claude/vision [q4 S21] |
| Haiku cost | About $0.0004–0.0009 per video for 3–10 preview thumbnails (432×768, 448 tokens each) | arithmetic on [q4 S21, S25] |
| Freepik | MIT, EVA-02 base at 448 px; internal benchmark only; 28 ms per image on an RTX 3090; no CPU figure exists | https://huggingface.co/Freepik/nsfw_image_detector/raw/main/README.md [q4 S10] |
| Guards | Shieldstral Apache-2.0, continuous renormalised P(yes), vendor-reported F1 (UnsafeBench 81.8); ShieldGemma 2 under Gemma terms, three trained policies | https://huggingface.co/mistralai/Shieldstral-1.0-3B [q4 S12]; https://arxiv.org/html/2504.01081 [q4 S15] |
| Likelihood enum | `LIKELIHOOD_UNSPECIFIED`, `VERY_UNLIKELY` … `VERY_LIKELY`; Google publishes no numeric thresholds | https://docs.cloud.google.com/video-intelligence/docs/reference/rest/v1/Likelihood [q4 S26a] |
| Expause today | `blocked` only at `VERY_LIKELY` `pornographyLikelihood` | Expause `common/app_constants.ts:209-216, :229` [q1 §3.3] |

**Rejected, and why** [q4 §Summary item 4, §Hosted options].

| Option | Why rejected |
|---|---|
| NudeNet | Licence conflict (GitHub AGPL-3.0, PyPI MIT; Ultralytics YOLOv8 weights) |
| Llama Guard 4 | 38% single-image F1 on Meta's own test set; multimodal rights withheld from EU-based companies (U3) |
| LlavaGuard | Weights licence not stated; weak on UnsafeBench in the ShieldGemma 2 report |
| OpenNSFW2 | Baseline only (2016 Yahoo weights) |
| Nemotron 3.5 Content Safety | Inconsistent licence names, no continuous score (D24) |
| AWS Rekognition, Azure AI Content Safety | Paid or quota-capped, another vendor, frames leave Google Cloud, nothing the local options lack (Hive and Sightengine were set aside on the same grounds without being researched) |
| Cloud Vision SafeSearch as a scenewise tier | A Google signal beside a Google primary; errors may correlate. It is Expause's primary instead (U8) |
| Haiku as the main second opinion | Anthropic documents that Claude does not process explicit images that violate its Usage Policy, so Haiku cannot be relied on for the sexual category (refuse vs only decline to describe is untested, q4 OQ3); cost is not the blocker |

Detail: [q4-moderation.md](../research/q4-moderation.md).

### Q5. Labels for recommendations (roadmap item 4)

**Decision** [q5 §1, §6; U10; q8c §4.1, §4.3, §7.4, §7.5].

- **Labels are the primary output; embeddings are opt-in.** One open-weight contrastive model embeds every preview
  thumbnail; the adopter's taxonomy is scored against cached text embeddings; the result is up to `top_k` labels
  `{id, name, score_max, score_mean, calibrated}`. The pooled, L2-normalised video embedding comes from the same pass and
  is returned only on request until Expause confirms its recommender uses dense vectors. A transcript text embedding
  (`multilingual-e5-small` or `bge-m3`, both MIT) is a separate opt-in vector, **not built in v1**: it gets no port
  until Expause's recommender consumes vectors (q8c §7.5; q5 OQ11). q7 still costs its 0.5 s guess, which is
  conservative.
- **Default model: SigLIP 2 ViT-B/16** through `open_clip_torch` 3.3.0. Small option: SigLIP 2 B/32-256; alternative:
  PE-Core-B/16; 9:16 option for evaluation: SigLIP 2 NaFlex B/16 via transformers.
- **The taxonomy is data, not code.** Taxonomy files are **TOML** (parsed with stdlib `tomllib`, validated by pydantic
  in `app/contract/taxonomy.py`), read and parsed once at start-up by `service/bootstrap.py`, so a malformed taxonomy
  is a `ConfigurationError`; this replaces q5's YAML, which the `app` allow-list cannot parse [q8c §7.4]. A request
  selects one with `StageOptions.labels_taxonomy` (optional only when exactly one is configured) and may override its
  `top_k` with `labels_max` [q8c §7.5]. Labels have `id`, `name`, `prompts`, optional `parent` and `external_id`;
  global `templates` and `top_k`. Thresholds live in a sidecar written only by
  `scenewise calibrate`, keyed to model, taxonomy hash, preprocessing and score statistic; a mismatched entry is ignored.
  Uncalibrated labels are emitted only when they stand out from the video's other labels (robust z-score ≥ `z_min`,
  default 2.0). No built-in vocabulary ships.
- **Port and wire shape** [q8c §4.1, §7.5]: `ZeroShotLabeller.score(frames, prompts, *, embeddings=False) ->
  LabelScores(model_id, preprocess, cosines, score_transform, embeddings)`, so the domain gets both the cosines (for
  the z-score) and the model's score transform (for calibrated thresholds). The v1 wire `Label` is q5's object
  `{id, name, path, score_max, score_mean, frames, calibrated, external_id}`, replacing q1's `Label{name, confidence,
  segments, source}`. `scenewise calibrate` is a CLI subcommand over `app/calibrate.py` and `domain/calibration.py`,
  wired with its own `CalibrationDeps(store, images, labeller)` (q8c §4.3).
- **Visual-only summaries** (U14): item 4 also defines the tested label-based rule that lets summaries run without
  speech (Q3).
- **Expause: calibrate first** (U10). Uncalibrated labels are stored for shadow comparison only; one `scenewise
  calibrate` run (Haiku-bootstrapped labels, human spot-check) is part of the Expause integration.
- **Haiku 5.5 is an optional "rich tags" tier**, per request or per deployment. **Storage is the adopter's**: scenewise
  returns vectors with `{model_id, dim, normalised, pooling}`.

**Key evidence.**

| Claim | Evidence | Source |
|---|---|---|
| What Expause uses today | Only the top-10 `entity.description` names from `segmentLabelAnnotations`, stored as `contentTags`; confidence only sorts | Expause `transcoding/app_transcoding.ts:420-445` [q5 S53] |
| SigLIP 2 B/16 | 78.2% ImageNet-1k zero-shot; multilingual text tower; Apache-2.0 weights; 768-d | https://arxiv.org/html/2502.14786 [q5 S6]; https://huggingface.co/api/models/google/siglip2-base-patch16-224 [q5 S8]; open_clip model configs at v3.3.0, https://github.com/mlfoundations/open_clip/tree/v3.3.0/src/open_clip/model_configs [q5 S45] |
| Speed | Median 37 ms per image (M4, 4 threads, batch 16, synthetic input) | local benchmark, 2026-10-08 [q5 §3] |
| Per-video cost (K = 12 thumbnails) | Local SigLIP 2 ≈ $0.00013; Haiku 5.5 ≈ $0.00053; Gemini Embedding 2 ≈ $0.0014; Video Intelligence ≈ $0.0083; Cloud Vision labels ≈ $0.018 | computed [q5 §5b]. q5 used 4 vCPU / 8 GiB and a 2.0 slowdown; with q7's 16 GiB and 2.5 the local figure rises about 46% and no conclusion changes [q7 open question 14] |
| Embeddings | The YouTube paper shows averaging learned **ID** embeddings works, not that frame-content embeddings help | https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/45530.pdf [q5 S20] |
| Firestore vectors | `flat` index only; kNN billed per 100 index entries read; no Dart/Flutter client support | https://firebase.google.com/docs/firestore/vector-search [q5 S21]; https://firebase.google.com/docs/firestore/pricing [q5 S22] |

**Rejected, and why** [q5 §1, §3].

| Option | Why rejected |
|---|---|
| MobileCLIP / MobileCLIP2, DFN | Apple ML Research licence: research only (https://raw.githubusercontent.com/apple/ml-mobileclip/main/LICENSE_MODELS) |
| MetaCLIP 2, jina-clip-v2 | CC-BY-NC-4.0 |
| OpenAI CLIP weights | Policy choice: the model card puts "any deployed use case" out of scope |
| Perception-LM | Non-Apache licence, built on Llama (U3); only PE-Core is used |
| SigLIP 2 So400m | 84.1% but about 0.7–0.85 s per image on the M4; too slow for CPU serving at volume |
| Video-native models (VideoPrism, InternVideo2) | Expause sends previews 2–60 s apart, with little temporal continuity to exploit |
| Vertex `multimodalembedding@001` | Retires 2027-04-01; text capped at 32 tokens |
| Gemini 2.5 Flash-Lite as a tagging tier | Retires on Vertex 2026-10-20; the Google alternative is 3.1 Flash-Lite |
| Absolute score thresholds without calibration | SigLIP scores are independent sigmoid scores, not calibrated probabilities |

Detail: [q5-labels.md](../research/q5-labels.md).

### Q6. Other languages (roadmap item 5)

**Decision: defer** [q6 §Summary]. When the item is scheduled, the default path is source-language transcript (with
timings) → LLM translation with a window of cues and stable cue IDs → original cue timings kept. Translate from the
source transcript, not through an English pivot (D28). Hosted: Haiku 5.5; local: Qwen3, Gemma 4 or Seed-X. TranslateGemma
is not adopted (D26). Whether Haiku runs with thinking off or on at low effort is decided by a pilot (D27).

Because Parakeet v2 is English-only, any non-English source transcript needs a multilingual ASR (the faster-whisper
fallback, or Canary-1b-v2 for European languages, which needs the source language given) [q2 §1, §2; q6 §Summary, OQ5;
D28].

**Key evidence.**

| Claim | Evidence | Source |
|---|---|---|
| Whisper alone cannot | Whisper's translate task is X→English only; `turbo` "is not trained for translation tasks" | https://arxiv.org/html/2212.04356v1 [q6 S1]; https://github.com/openai/whisper [q6 S2] |
| NLLB-200, SeamlessM4T v2 | Weights CC-BY-NC-4.0 | https://huggingface.co/facebook/nllb-200-distilled-600M [q6 S3]; https://huggingface.co/facebook/seamless-m4t-v2-large [q6 S6] |
| Hunyuan-MT / HY-MT1.5 | Licence "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA" | https://huggingface.co/tencent/Hunyuan-MT-7B/raw/main/License.txt [q6 S24] |
| Clean options | MADLAD-400 Apache-2.0; Opus-MT CC-BY-4.0; Seed-X OpenMDW-1.0 (commercial use allowed); Canary-1b-v2 CC-BY-4.0, En↔24 European languages | https://huggingface.co/google/madlad400-3b-mt [q6 S8]; https://github.com/Helsinki-NLP/Opus-MT [q6 S11]; https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B/raw/main/LICENSE [q6 S36]; https://huggingface.co/nvidia/canary-1b-v2 [q6 S23] |
| Cost | Haiku 5.5 about $0.015–0.034 per target language per video-hour (thinking off); Google Translation about $1.08/h; DeepL about $1.49/h overage | arithmetic [q6]; https://cloud.google.com/translate/pricing [q6 S30] |

**Rejected, and why.** NLLB-200, SeamlessM4T v2, TowerInstruct/Tower+, Aya Expanse: non-commercial. Hunyuan-MT and
HY-MT1.5: EU territorial exclusion (U3). TranslateGemma: Gemma Terms flow-down, Google's remote-restriction right and a
2K-token input (D26). Character-priced MT APIs: about 30–100× Haiku 5.5. Meta Omnilingual MT: Meta's page linked no weights or
licence as of 2026-10-08 [q6 S21].

Detail: [q6-translation.md](../research/q6-translation.md).

### Q7. Where it runs and what it costs

**Decision** [q7 §1; U5, U6].

| Item | Decision |
|---|---|
| Runtime per stage | Captions, moderation (tiers 1 and 2), labels, decode and the optional transcript embedding: local, **in one Cloud Run CPU service**. Summaries and chapters: **Haiku 5.5 via Vertex AI EU, synchronous**, called in the same request after captions and labels. Translation: deferred |
| Service shape | Request-based billing, minimum 0, 4 vCPU / 16 GiB to start (8 GiB if the measured peak with the guard loaded stays below about 6 GiB; a separate guard service if it exceeds 16 GiB), `max_jobs = 1`, Cloud Run concurrency = `max_jobs`, Cloud Tasks `dispatchDeadline` 1800 s |
| Model weights | **Baked into the image** (weights about 3–5 GB, below Google's "less than 10 GB" guidance for image-baked models); never downloaded from the Hub in production. Two image variants from one Dockerfile and one pinned weights layer: `-cpu` and `-cuda` (cu130). In `-cuda` only the vision models use the GPU; ASR, VAD and LID stay on CPU, which affects only the L4 job mode v1 does not build [q8c §3, §7.8] |
| GitHub Actions | **CI and project-related evaluation only** (tests, public-benchmark regressions, ONNX conversion, image builds). Not for Expause backfills, which go to a Cloud Run job in Expause's project |
| Latency-tolerant modes | Hourly CPU or L4 jobs and Delayed Jobs are cheaper but need a batch intake q8a does not have; **not built in v1 (U6)** |

**Memory, reconciled.** q2 measured the whole audio stack at **1.33 GB peak RSS** (linux/amd64, one 30 s segment) and
calls 2 GiB the floor for audio alone [q2 §6.2]. q7 estimates the full job (guard VLM with KV cache, SigLIP image tower
with torch, Freepik, e5-small, the input file in Cloud Run's in-memory filesystem) at about 5–7 GB. So: **start at
16 GiB, drop to 8 GiB if the benchmark peak with the guard loaded is below about 6 GiB** [q7 §3]. (q5's cost table used
8 GiB; q7 governs.)

**Where each choice stops being the cheapest** (video-hours per month, at CPU speed ×0.5 / ×1 / ×2; the grid cells sit
at 11, 18, 108, 180, 1,082 and 1,804) [q7 §6 "Crossovers", §7]:

| Comparison | Second option becomes cheaper at | Reading |
|---|---|---|
| Local LLM vs Haiku (summaries) | Haiku is cheaper than a single-stream local LLM at every volume: about 17× vs CPU Qwen, about 3× vs a busy L4 | A batched vLLM server in the L4 job could break even; unmeasured, at most about $10/month at stake |
| Local CPU vs hosted captions (Gemini 3.1 / 3.5 Flash-Lite on Vertex EU, same VAD gate) | Local is 1.6× / 1.4× cheaper at ×1; **both Gemini models are cheaper at ×0.5** | A close call the benchmark decides; Speech-to-Text V2 standard is about 13× local |
| Haiku vs local (moderation, labels) | Haiku is cheaper than CPU per video (2.5×, 1.2×), dearer than L4 | Not a substitute: explicit images are outside what Claude processes (moderation; q4 OQ3) and no embedding (labels) |
| CPU service → CPU hourly job | Every volume | Needs the batch intake and up to about 2 h latency; excluded in v1 by U6 |
| CPU service → L4 hourly job | ≥ 1 / 19 / 73 h | Same conditions, plus a CPU fallback for the 3-GPU quota |
| CPU hourly job → L4 hourly job | ≥ 1 / 61 / 318 h | The most fragile crossover; do not build the L4 path before the benchmark |
| CPU service → e2 VM + Haiku | 464–794 h and ≥ 940 h / 921–1,593 h and ≥ 1,849 h / 1,777–3,165 h and ≥ 3,566 h | Brings VM operations; the CPU job is cheaper than both |
| All-local CPU → L4 service | ≥ 1,230 / 2,646 / 6,225 h | Only if the L4 is never idle |
| All-local CPU → g2 spot VM | ≥ 613 / 1,230 / 2,468 h | Fixed $325/month, pre-emptible |

**Key evidence.**

| Claim | Evidence | Source |
|---|---|---|
| Request-based billing | Billed while starting, shutting down and serving; 4 vCPU / 16 GiB = $0.000136/s in Tier 1 | https://cloud.google.com/run/pricing [q7 S1] |
| GPU services | Instance-based billing required; L4 in europe-west1 and europe-west4; idle GPU instances kept up to 10 minutes | https://docs.cloud.google.com/run/docs/configuring/services/gpu [q7 S3]; https://docs.cloud.google.com/run/docs/about-instance-autoscaling [q7 S29] |
| Memory limits | 4 vCPU allows 2–16 GiB; files written to the filesystem count against memory | https://docs.cloud.google.com/run/docs/configuring/services/memory-limits [q7 S23] |
| Model loading | Baking into the image is "best suited for smaller models less than 10 GB" | https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices [q7 S4] |
| Haiku residency | First-party `inference_geo` is `global` or `us` only, and `us` is the only workspace geo; Vertex EU multi-region keeps processing in the EU | https://platform.claude.com/docs/en/build-with-claude/data-residency [q7 S24]; https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-5-5 [q7 S26] |
| Delayed Jobs | Preview; provisioning up to 12 h; 12 h total task runtime | https://docs.cloud.google.com/run/docs/delayed-jobs [q7 S22] |
| GitHub Actions | GPU runner $0.052/min (about 3× a Cloud Run L4 per hour); terms restrict hosted runners to activity related to the software project | https://docs.github.com/en/billing/reference/actions-runner-pricing [q7 S13]; https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features [q7 S12] |

**Rejected, and why** [q7 §1–§3]. A Cloud Run GPU service ($24–642/month in the grid, mostly idle L4 time). Always-on VMs
(g2-standard-4 $542/month on demand, about $325 spot; e2-standard-4 $108/month; no scale to zero, more operations). A
Cloud Run worker pool (always-on, pull-based). One service per stage (more cold starts and decodes). Downloading weights
from the Hub at start-up ("reliability risk"). GitHub Actions for production work.

Detail: [q7-runtime-cost.md](../research/q7-runtime-cost.md) and the script
[q7_cost_grid.py](../research/q7_cost_grid.py).

### Q8. Architecture and tooling

**Decision: layout and style** [q8a §0–§5; q8c §0–§7].

- **`src/scenewise/`, one distribution, one import package**, no uv workspace in v1. The real split is light vs heavy
  dependencies, which extras express.
- **Layers** (top to bottom): `service` (HTTP routes, CLI, composition root, settings, logging) → `adapters` (driven
  port implementations only) | `app` (use cases, orchestration and the versioned pydantic wire contract `app/contract/`)
  → `ports` (Protocols) → `domain` (frozen, slotted dataclasses and pure functions, stdlib only). `adapters` and `app` are
  independent siblings (q8b's erratum to q8a §1.5). Only `service/bootstrap.py` imports adapters, lazily.
- **No consumer code**: there is no `adapters/expause/`.
- **Where the line is** against Java-style ceremony [q8a §2.2]:

  | Construct | Use it when | Not for |
  |---|---|---|
  | `Protocol` (port) | An I/O or model boundary with ≥ 2 real implementations, or one that needs a fake in tests | Pure functions, values, config, use cases |
  | Class with `__init__` | It owns a resource with a lifecycle (a loaded model, a client, a lock) | Stateless logic |
  | Plain function | Every stage, every domain transformation, the runner, the delivery protocol | — |
  | Frozen dataclass | Values and the `Dependencies` bundle | Untrusted input (pydantic at the boundary) |
  | Inheritance | The error categories, `BaseSettings`/`BaseModel` | Sharing code between back ends |
  | Factory | One function, `bootstrap.build_dependencies(settings)`, with a `match` per back end | Registries, plugins |
  | DI container, service locator | Never in v1 | — |

- **Ports** (one `ports.py`, split at about 200 lines, or started as a `ports/` package of one module per port kind if
  the first draft exceeds that): `BlobStore`, `MediaTool` (ffmpeg/ffprobe; `audio_track` pinned to 16 kHz mono
  `pcm_s16le` WAV by its contract test), `ImageReader` (Pillow), `VoiceActivityDetector`, `LanguageIdentifier`,
  `SpeechRecognizer`, `TextGenerator`, `ImageModerator`, `ZeroShotLabeller`, `Notifier`: **ten**, plus
  `WriteConflictError` (renamed from q8a's `WriteConflict`, D2). `ImageGuard` is the eleventh, added with roadmap
  item 3 [q8c §6.3 item 14].
- **Speech, reconciled** [q8c §1–§2]:
  - `VoiceActivityDetector.speech_probabilities(track) -> SpeechProbabilities` (Silero; per-hop P(speech)) and
    `LanguageIdentifier.identify(track, windows) -> list[LanguageGuess]` (Whisper `tiny` ONNX, q11; argmax and p per
    window, a window being speech spans the adapter concatenates) are the two new ports.
  - `SpeechRecognizer.transcribe(track: Path, segments: Sequence[TimeSpan], *, language: str) ->
    list[RecognizedSegment]`: the boundary is the one WAV plus spans; adapters slice and convert to float32 and give
    faster-whisper arrays, never paths. Out come tokens with absolute start, optional end hint and log-probability;
    `domain/captions.py` builds words and extends word ends.
  - The policy is pure, stdlib-only code in a new **`domain/speech.py`**: hysteresis runs, ≤ 30 s cuts at the
    lowest-probability hop, LID windows of 3–30 s of speech, the language rule (D19, D21, `"und"` for unknown), the
    **merge of kept pieces into recognition segments of up to 30 s** across gaps under 2 s, and generic chunking. `app`
    calls the recogniser in chunks of ≤ 300 s of segment audio and LID in batches of 10 windows, checking the deadline
    between calls. The three speech ports travel together as `Speech(vad, lid, recognizer)` in `app/deps.py`. The music
    tagger gets no port until T1 (D22).
- **Stage outcomes** [q8c §5]: a tagged union `Succeeded | Skipped(reason) | LanguageSkipped(reason, report) |
  Failed(error_code, detail)` inside `StageOutcome`, with `Literal` subsets of a closed `SkipReason` enum (seven values,
  including `no_speech`, `language_unsupported`, `language_unknown` and `below_minimum`), so invalid status/reason pairs
  are unrepresentable. The wire `status`, `reason` and `error` are derived in `app/contract/mapping.py`; a succeeded
  stage never carries a reason. Captions gain two additive wire fields, `partial_language` and `detected_languages`
  (q8c §7.3).
- **Text generation** [q8c §7.1]: `TextGenerator.generate(request) -> Generation(text, model, refused)`; new error code
  `model_refused`. **Labels**: `ZeroShotLabeller.score(...) -> LabelScores` (Q5). **Taxonomies**: TOML (Q5).
- **Smaller contract changes** [q8c §6.3]: `JobRecord` gains `schema_version`, `scenewise_version` and a leniently
  parsed `external_ref` (D9); `max_jobs` defaults to 1 everywhere (GPU deployments set 2); bodies over 1 MiB get 413
  (`request_too_large`) before parsing, with no record; settings `asr.backend` is `sherpa-onnx | onnx-asr |
  faster-whisper | none`, with no ASR device in v1.
- **Design principles, each with a scenewise example** [q8a §3]: single responsibility (`domain/captions.py` only turns a
  transcript into cues and WebVTT); open/closed (a new back end is a module plus one `case` in bootstrap); Liskov (every
  `SpeechRecognizer` returns absolute, non-decreasing seconds, checked by one shared contract test); interface
  segregation (`ImageReader` is separate from `MediaTool`, so sprite inputs need no ffmpeg); dependency inversion (`app`
  depends on `ports.SpeechRecognizer`, never on the runtime); composition over inheritance (`FallbackTextGenerator` wraps
  two generators); functional core / imperative shell (playlist parsing is pure, `app/audio.py` does the reads).
- **Domain model and boundaries** [q8a §5]: stage, job, inputs (audio and visual source unions mirroring q1), results
  (transcript, cues, summary, chapters, moderation and label results, stage outcomes) live in `domain/`; pydantic models
  live only in `app/contract/` and `app/llm_output.py` (structural parsing of LLM JSON with one repair retry).
- **Concurrency** [q8a §6.3]: a synchronous push handler; the event loop hands each job to one worker thread
  (`anyio.to_thread.run_sync`); Cloud Run concurrency = `max_jobs` does admission, with a non-blocking
  `CapacityLimiter` as a safety net (429). Model adapters hold a `threading.Lock` only around inference. ffmpeg runs as a
  killable subprocess. Scale by instance; no process pools; GIL build in v1. Vision runs in-process, and GIL contention
  is measured before considering a subprocess (D11).
- **Configuration, logging, errors** [q8a §7–§8]: pydantic-settings 2.15.0 (`SCENEWISE_` prefix, `__` nesting), built
  once and passed to bootstrap; structlog 26.1.0 JSON logs with Cloud Run trace fields, binding `job_id`, `stage`,
  `attempt`; **logs never contain transcript text or signed URIs, enforced by a test (D8)**. Four error categories,
  `InputError`, `RetryableError`, `InternalError`, `ConfigurationError`, with leaf classes only where the HTTP mapping
  differs; a stage failure gives a `partial` job, never a whole-job retry.
- **ffmpeg** [q8a §9.1–§9.2]: system binaries through `subprocess` (argv list, timeouts), checked at start-up with
  `shutil.which` and a version probe; declared in README, Dockerfile and the start-up check, not in a PEP 725
  `[external]` table while that PEP is a Draft.
- **Heavy dependencies** [q8a §9.4 as amended by q8c §3]: the base install has no torch, and neither does the `asr`
  extra. Extras: `service`, `asr`, `llm-anthropic`, `vision`, `gcs`, plus **one** accelerator selector pair
  `torch-cpu`/`torch-cu130`, declared as uv `conflicts`. `cu130` matches the Cloud Run 580 driver. Changes from q8a:
  - **One CPU-only `asr` extra** holds sherpa-onnx, onnx-asr (no `[hub]`, no `[cpu]`), onnxruntime, faster-whisper and
    numpy, because the LID gate needs faster-whisper on every captions job; `asr-whisper` and the `ort-cpu`/`ort-cu130`
    pair are removed. faster-whisper hard-requires pip `onnxruntime`, so `onnxruntime-gpu` must never sit next to it
    [q8c X1]. **v1 ASR runs on CPU in both images; GPU ASR is out of v1**, and its packaging route is to be researched
    only if a GPU deployment or the L4 job mode is built.
  - **PyAV becomes a transitive dependency** (faster-whisper requires `av>=11`) and is imported, but never given
    input: faster-whisper adapters receive decoded arrays only, enforced by contract tests. This supersedes q8a §9.1's
    "PyAV is not even a transitive dependency"; ffmpeg stays the only decoder.
  - **Superseded by q11 and U16 (2026-10-08):** faster-whisper leaves `asr` for an opt-in `asr-whisper` extra, so the
    default install has no PyAV (the PyAV rule above applies to `asr-whisper` only); LID runs on an in-house
    onnxruntime Whisper-tiny adapter. pip `onnxruntime` stays in `asr` (Silero, LID), so the `onnxruntime-gpu`
    constraint holds.
  - `llm-anthropic` becomes `["anthropic[vertex]>=1.12"]` (U5, q7 §2.3); Pillow becomes a base dependency (D3);
    CTranslate2 (CUDA 12) runs on CPU (D12); google-auth stays in `gcs`, and bootstrap checks the import, not the
    extra, when `callback_auth = oidc` (q8c §8, q8b OQ12).

**Decision: tooling and gates** [q8b §0, §14; U11, U13; q8c §6.1–§6.2, §8].

| Gate | Tool and setting |
|---|---|
| Types | mypy 2.4.0 `strict` over `src`, `tests`, `scripts`, pydantic plugin, `disallow_any_explicit` in the core; `ignore_missing_imports` only for seven untyped heavy libraries (onnxruntime, faster_whisper, ctranslate2, sherpa_onnx, open_clip, torchvision, google.cloud; q8c §6.1 item 5). No second checker in CI |
| Lint and format | ruff 0.16.10, `select = ["ALL"]` with six justified ignores, **line length 88** (U11) |
| Complexity | C901 ≤ 8; args ≤ 5; positional ≤ 3 in `src`; branches ≤ 10; returns ≤ 6; statements ≤ 40 |
| Dependency direction | import-linter 2.15: layers `service > (adapters \| app) > ports > domain` (exhaustive, `exhaustive_ignores = ["__main__"]`), independent adapter kinds, `adapters` protected (only bootstrap), a custom allow-list contract (stdlib only in domain and ports; stdlib + pydantic + structlog in app), and a forbidden list of ML/cloud SDKs for `service` (`sherpa_onnx` added and the `bootstrap -> onnxruntime` ignore removed, so only bootstrap's torch probe stays exempt; q8c §6.1 item 8) |
| Module size | A custom script, **500 physical lines** for `src`, `tests` and `scripts` (ruff has no too-many-lines rule); replaces q8a's 400 |
| Coverage | Core (`domain`, `app`, `ports`) **100% line + branch, measured from unit tests only**; overall ≥ 90% in the PR tier; heavy adapters omitted from the PR gate and reported in the models job (D4) |
| Suppression control | `scripts/check_suppressions.py`: file-level directives and coverage pragmas banned everywhere; no line-level `noqa` / `type: ignore` in the core; elsewhere each needs `# why:` and the total equals a committed budget; every tool is run with its config pinned to `pyproject.toml`, and stray config files fail CI |
| Tests | pytest 9.1.1 strict, `filterwarnings = error`, pytest-timeout, pytest-randomly; contract-test mixins per port; e2e on ffmpeg-generated media (no downloaded clips); one opt-in `model` marker only in `tests/contract`; **no skipped or xfailed test in any CI job**; hypothesis for pure functions |
| Other | `uv lock --check` + `UV_LOCKED=1`, a lock-routing script (`check_lock.sh`: no torch and no `onnxruntime-gpu` in `service + asr`, q8c item 9), deptry, vulture (confidence 60), typos, zizmor (offline in the merge gate, online in the nightly job: q8c §8 keeps this for q8b OQ13, because online checks would make the gate depend on GitHub's API); a failing nightly `supply-chain` job |
| Gate ownership | CODEOWNERS (`@firu-daniel`, D5) on `pyproject.toml`, `uv.lock`, `scripts/`, `vulture_whitelist.py`, `.github/`, `**/conftest.py`. CODEOWNERS lists only these gate files, and a ruleset on the default branch requires code-owner review, so the review binds on gate-file changes. **How it binds (U13, option A′ of q8c §8):** agent PRs run on GitHub Actions are opened by GitHub Actions, so their author is `github-actions[bot]`, not the maintainer, and the maintainer's approval counts (this mechanism is U13's; q8c evaluated only a bot account or an App, so it is confirmed in Part 2 step 1 when the ruleset is set up). **U13a:** PRs from local harness runs are opened by the maintainer and so are maintainer-authored; one that touches gate files cannot merge normally and needs the logged admin bypass, on purpose: the forced bypass is the signal that an agent changed a gate; the only bypass actor is the Repository admin role (the maintainer alone in this personal repository), in "For pull requests only" mode, so each bypass shows in the PR and the audit log |
| Hooks | One `.pre-commit-config.yaml`, runnable with `pre-commit` or `prek` (D6); CI is the gate |

**CI without downloads at test time** [q8b §6; q8c §7.6]: the PR tier runs fakes and light adapters; the models job
(main, nightly, or a PR label) runs real adapters offline (`HF_HUB_OFFLINE=1`) with every model it loads pinned by repo,
revision, file list and sha256 in `tests/models.lock` and cached: both Parakeet int8 exports, Whisper `tiny` (LID and
the fallback recogniser contract), Silero via its HF mirror, and the tiny vision models, about 1.4 GB in all.
`large-v3-turbo` is not used in CI. The models job also runs q2's T4 (three runtimes in one process, both import
orders, peak RSS). The GCS contract test uses an in-memory fake (D4).

**Comparison with real projects** [q8a §11] (layouts read through the GitHub API on 2026-10-08):

| Project | What scenewise takes | What it avoids |
|---|---|---|
| faster-whisper (`9fa78645d7`) | A narrow, easily wrapped API | A 1,952-line `transcribe.py` and `utils.py` |
| WhisperX (`771b4a14a9`) | uv index routing for torch | torch in base dependencies; a Python upper bound |
| LiteLLM (`7a659973e3`) | One module per provider | 9,435-line `main.py`, 15,234-line `router.py`, a 449 KB `utils.py` |
| vLLM (`7d47ac2ddb`) | Entry points separated from the engine | — |
| Pydantic AI (`f55bb8a6fd`) | One adapter module and one extra per back end | A workspace, which only several published packages justify |
| Warehouse / PyPI (`14b79b44aa`) | Explicit interface modules, storage behind an interface | The `pyramid_services` service locator |

**Key evidence.** The `src/` layout prevents "accidental usage of the in-development copy of the code"
(https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) [q8a §1.1]. uv workspaces are "*not*
suited for cases in which members have conflicting requirements" (https://docs.astral.sh/uv/concepts/projects/workspaces/)
[q8a §1.2]. Ports and adapters, hexagonal, onion and clean architecture are "pretty much names for the same thing", and
manual DI through a composition root suffices (https://www.cosmicpython.com/book/chapter_02_repository.html,
https://www.cosmicpython.com/book/chapter_13_dependency_injection.html) [q8a §2.1]. Driving vs driven adapters (Cockburn,
https://alistair.cockburn.us/hexagonal-architecture/); functional core, imperative shell (Rhodes,
https://rhodesmill.org/brandon/slides/2014-07-pyohio/clean-architecture/); composition over inheritance (Hynek,
https://hynek.me/articles/python-subclassing-redux/); a Protocol contains only what the consumer calls (Glyph,
https://blog.glyph.im/2020/07/new-duck.html) [q8a §2.1]. Every q8a rule maps to an import-linter contract, and each
caught a seeded violation on a throwaway skeleton [q8b §0, verified locally]. q8c's packaging decisions rest on the
PyPI metadata and wheel contents it read on 2026-10-08: faster-whisper 1.2.1 hard-requires `onnxruntime` and `av>=11`;
sherpa-onnx 1.13.8 requires `sherpa-onnx-core==1.13.8`, whose macOS arm64 wheel bundles its own `libonnxruntime` and
ships no `py.typed`; onnx-asr 0.12.0 puts onnxruntime only in extras and ships `py.typed` [q8c X1, X2, X4]. Its
segment merge follows WhisperX's `merge_chunks` envelope merge, and its CODEOWNERS bypass follows GitHub's ruleset
documentation (roles, teams and Apps are bypass actors; single users are not) [q8c X5].

**Rejected, and why** [q8a §2.2, §9, §12; q8b §0]. A core-library-plus-service split or uv workspace (one published
package). ABCs for ports, a `Stage` class, Repository/Unit of Work, a message bus, a DI container, plugin entry points, a
`Clock` port (ceremony with no second implementation). Model-serving frameworks (LitServe, BentoML, Ray Serve, Triton:
heavy runtimes that would hide the architecture). PyAV for the service (in-process decoding of untrusted media,
unkillable threads). ffmpeg-python (unmaintained). In-process llama-cpp-python (no PyPI wheels). `cu128` (no torch
2.14.1 wheels; would move the default stack to CUDA 12). A second type checker in CI (pyrefly, ty, basedpyright: editor
only). Ruff `preview` rules (nondeterministic gate). A DASH parser in v1 (untrusted XML; D10). Pub/Sub delivery and
in-app OIDC for non-GCP hosting (a reverse proxy instead, D13). A SQLite job store (single-host CAS is enough, D14).
Rejected by q8c [q8c §1–§3, §7.4]: VAD and LID inside each ASR adapter (cue boundaries would depend on the runtime);
one `SpeechFrontEnd` port (the tunable policy would only be testable with models installed); numpy in `app` (breaks
the allow-list); per-segment PCM bytes or WAV paths at the recogniser boundary; faster-whisper's speech concatenation
(every adapter would need an offset map); a separate `asr-whisper` extra (captions would need two extras); onnx-asr
with `onnxruntime-gpu` (two ORT distributions in one environment); PyYAML for taxonomies (a new dependency, loading
split across layers).

Detail: [q8a-architecture-layout.md](../research/q8a-architecture-layout.md),
[q8b-tooling-gates.md](../research/q8b-tooling-gates.md) and
[q8c-reconciliation.md](../research/q8c-reconciliation.md) (its §6 lists every edit to apply when building the
skeleton, file by file).

### Q9. How the harness fits

**To be completed in Part 2**, after the repository exists: which layers and conventions to configure so they match
`ARCHITECTURE.md`, what the Run gates phase runs (the gates in Q8), what the interactive test phase becomes with no
browser UI, and every place the harness assumes a web front end.

---

## 4. User decisions and orchestrator defaults

Full text: [`user-decisions.md`](../research/user-decisions.md). These override the findings files. U13–U15 and
U13a were taken after q8c; U16 and U17 after q10 and q11.

### 4.1 Decided by the user (2026-10-08)

| # | Decision |
|---|---|
| U1 | scenewise stays a **complement** (second opinion) after Video Intelligence shuts down; Expause moves its primary signal elsewhere |
| U2 | Python **3.12** minimum; CI matrix 3.12–3.14 |
| U3 | Operator is **EU-based**: anything with an EU territorial clause (Llama multimodal, Hunyuan/HY-MT) is excluded from every default and recommendation |
| U4 | **Parakeet-TDT-0.6b-v2 (CC-BY-4.0) is the default**, with attribution in NOTICE and README including the ONNX conversion and quantisation note; faster-whisper + large-v3-turbo stays the fallback |
| U5 | Haiku 5.5 through **Vertex AI EU multi-region** for Expause; one Anthropic-SDK adapter supports `Anthropic` and `AnthropicVertex`; provider and region are deployment settings |
| U6 | Latency in **minutes**: synchronous Cloud Run CPU service fed by Cloud Tasks, synchronous Haiku; no batch or hourly modes in v1 |
| U7 | Chapters only for videos **≥ 120 s with ≥ 3 chapters**; summary only above **~40 transcript words**; configurable, re-tuned on samples |
| U8 | Expause's primary after Video Intelligence: **Cloud Vision** (SafeSearch + label detection), confirmed by a shadow run |
| U9 | Keep the **7-day soft delete** on Expause's upload bucket, documented as a recovery window (the transcoder-bucket requirement is unaffected) |
| U10 | **Calibrate before** scenewise labels reach `contentTags`; uncalibrated labels stored for shadow comparison only |
| U11 | Ruff line length **88** |
| U12 | Expause scope: **user posts only**; chat and community later |
| U13 | CODEOWNERS binds through **option A′** (q8c §8, q8b OQ7): a ruleset requires code-owner review on gate files; agent PRs are opened by GitHub Actions, so their author is `github-actions[bot]`, not the maintainer, and the maintainer's approval counts; code-owner review binds on them; only the Repository admin role (the maintainer alone) may bypass, "for pull requests only", visible in the PR and the audit log |
| U13a | PRs from **local** harness runs are opened manually by the maintainer, so they are maintainer-authored: a local-run PR that touches gate files cannot merge with the normal button and needs the logged admin bypass. That is intended: the forced bypass is the signal that an agent changed a gate. PRs from harness runs on GitHub Actions are authored by `github-actions[bot]` and get normal code-owner review |
| U14 | **v1 summaries are speech-only** (transcript ≥ ~40 words); visual-only summaries with a label-based rule come with roadmap item 4 (q8c OQ-B) |
| U15 | The repository lives at **`~/Work/scenewise`** (moved from `~/scenewise`). Before the first push the history is squashed to **one commit** (or "Initial commit: the scenewise" plus one research-docs commit), with **no Co-Authored-By trailer** |
| U16 | **faster-whisper is opt-in.** It (the large-v3-turbo fallback, U4) moves to an `asr-whisper` extra, documented as bringing GPL code through PyAV's bundled x264/x265, and is left out of published images. The language-ID gate uses an in-house onnxruntime Whisper-tiny adapter (q11). The default `asr` extra has no PyAV |
| U17 | **Ubuntu's ffmpeg for development and CI.** Ubuntu build vs an LGPL-only ffmpeg build in published images is decided when the first published Dockerfile is written (q10 §5) |

### 4.2 Orchestrator defaults (the research's recommendation where it gave one, otherwise a technical, reversible choice; the user may override)

D1, D15–D17, D25, D29, D32 and D33 were put to the user and became U11, U6, U5, U7, U10, U8, U12 and U9, so they
are not listed here.

| D | Default |
|---|---|
| D2 | Rename `WriteConflict` → `WriteConflictError` |
| D3 | Pillow is a base dependency |
| D4 | Heavy-adapter coverage omitted from the PR gate, reported in the models job; GCS contract tests on an in-memory fake |
| D5 | CODEOWNERS owner `@firu-daniel` |
| D6 | One `.pre-commit-config.yaml`, runnable with `pre-commit` or `prek` |
| D7 | Add an `input_unavailable` input-error code |
| D8 | Logs never contain transcript text or signed URIs; a test enforces it |
| D9 | `JobRecord` carries `schema_version`, `scenewise_version`, optional `external_ref` |
| D10 | v1: HLS manifests only (no DASH); frame sampling by file list and interval (no `scene`) |
| D11 | Vision in-process; measure GIL contention first |
| D12 | No cu126 image; faster-whisper on CPU |
| D13 | Self-hosted auth outside GCP: a reverse proxy, not in-app auth |
| D14 | Local job store: single-host compare-and-swap; no SQLite mode in v1 |
| D18 | No automatic refusal fallback in v1; log and measure the refusal rate |
| D19 | Partial English captions: an absolute minimum (~2 s of English speech) only |
| D20 | ASR runtime: sherpa-onnx primary, onnx-asr tested second |
| D21 | Windows of unknown language are dropped and flagged |
| D22 | Music handling waits for test T1 (and a licence check on the AudioSet tagger) |
| D23 | No speech → no VTT; the caption stage reports `skipped / no_speech` |
| D24 | Nemotron 3.5 Content Safety dropped as a tier-2 candidate until its licence is clarified |
| D26 | TranslateGemma not adopted |
| D27 | Haiku thinking setting for translation: deferred with roadmap item 5 (a pilot decides) |
| D28 | Translate from the source transcript, no English pivot |
| D30, D31 | Caption serving (VTT encryption, sidecar vs HLS `SUBTITLES`) and backfill of encrypted videos: left to the Expause integration task |

### 4.3 Cross-file inconsistencies, and how this document resolves them

| Topic | Findings say | Resolution here |
|---|---|---|
| Ruff line length | q8b's drafted `pyproject.toml` uses 120 | **88** (U11) |
| Instance memory | q2: 1.33 GB peak for the audio stack, 2 GiB floor; q5 costed 8 GiB; q7: 16 GiB | **Start at 16 GiB; 8 GiB if the benchmark peak with the guard loaded is below about 6 GiB** (q7 §3) |
| Hosted LLM extra | q8a: `llm-anthropic = ["anthropic>=1.12"]`, which does not cover Vertex | **`llm-anthropic = ["anthropic[vertex]>=1.12"]`** (U5; q7 §2.3); adapter config `provider: "anthropic" \| "vertex"`, `project_id`, `region` |
| Gemini Flash-Lite figures | q3 lists Gemini 2.5 Flash-Lite as a price comparison | 2.5 Flash-Lite retires on Vertex AI on 2026-10-20 [q4 S46]; **every Gemini figure here is 3.1 or 3.5 Flash-Lite** (as q4, q5 and q7 already use) |
| ASR runtime | q8a §0, §1.4 and q8b's skeleton use onnx-asr for `adapters/asr/parakeet.py`; q2 (final) chose sherpa-onnx | **sherpa-onnx primary, onnx-asr second** (D20), in `adapters/asr/sherpa_parakeet.py` and `onnx_asr_parakeet.py` (q8c §2) |
| ASR packaging | q8a: `asr = ["onnx-asr[hub]"]`, faster-whisper in a separate `asr-whisper`, `ort-cpu`/`ort-cu130` selectors; q2: the LID gate needs faster-whisper on every captions job | **One CPU-only `asr` extra** with sherpa-onnx, onnx-asr, onnxruntime and numpy; `ort-*` pair removed (q8c §3). faster-whisper is the opt-in `asr-whisper` (fallback only), since LID no longer needs it (q11, U16) |
| GPU ASR | q8a: `ort-cu130` gives ASR a GPU; q2 §6.2: onnx-asr with onnxruntime-gpu; q7 §2.5: onnxruntime-gpu in `-cuda` | **Out of v1**; ASR runs on CPU in both images; the packaging route is researched only if a GPU path is built (q8c §3, §7.8) |
| No-speech captions status | q1 §5.1/§9: `succeeded` with reason `no_speech`; D23: `skipped / no_speech` | **`skipped`, reason `no_speech`, no VTT** (D23 confirmed); a succeeded stage never carries a reason (q8c §5) |
| Summaries without speech | q1 §9 and q3: summary runs on visual input when there is no speech | **Speech-only in v1** (U14): `skipped / below_minimum`; visual-only summaries with roadmap item 4 |
| PyAV | q8a §9.1: "not even a transitive dependency"; q8c §3: transitive through faster-whisper | **Absent from the default install** (U16, q11); only `asr-whisper` brings it, and there it is **never given input** (q8c §3) |
| `SpeechRecognizer` shape | q8a §4: `transcribe(audio, *, language) -> Transcript`; q2 §6: tokens with times and log-probabilities | WAV path + spans in, `list[RecognizedSegment]` out; word building in the domain (q8c §1) |
| Fallback VAD setting | q2 §4.3: `vad_filter=True` | `vad_filter=False`, because the spans are already VAD-cut and merged (q8c §2) |
| Taxonomy format | q5 §6.1: YAML | **TOML** via stdlib `tomllib` (q8c §7.4) |
| Labels wire shape | q1 §5.3 `Label{name, confidence, segments, source}`, `labels_max = 20`; q5 §6.2 sketch | q5's label object; `labels_taxonomy`, `labels_max: int \| None` (q8c §7.5) |
| Text-generation result | q8a: `generate(...) -> str`, no channel for refusals | `Generation(text, model, refused)`; refusal ⇒ `model_refused` (q8c §7.1) |
| Module size limit | q8a: 400 lines | **500 physical lines** (q8b §4.1; recorded as closed in open-decisions §4) |
| Layers contract | q8a: `["service", "adapters", "app", "ports", "domain"]` | **`["service", "adapters \| app", "ports", "domain"]`** (q8b §15.1: the literal list would allow adapters → app) |
| `WriteConflict` name | q8a §4 | `WriteConflictError` (D2) |
| Chapters threshold | q1's `StageOptions.chapters_min_duration_s` defaults to 30 s | **120 s** (U7) |
| Haiku Batch for backfills | q3 recommends Message Batches for backfills and a `sync \| batch` switch | v1 is synchronous only (U6); on Vertex, Message Batches is not supported and Vertex batch prediction needs its own adapter [q7 §2.3], so any batch path is later work |
| Stale speed figures in q8a §6.4 | Parakeet RTFx ≈ 37, SigLIP ≈ 66 ms per frame on CPU | q7's figures govern (RTFx 12.9 on 4 Cloud Run vCPUs; 45.9 ms on the M4 → 115 ms on Cloud Run) |
| q5 local cost | 4 vCPU / 8 GiB, slowdown 2.0 | q7's 16 GiB and 2.5 raise q5's local figures by about 46%; no q5 conclusion changes (q7 open question 14) |
| Chat and community videos, soft delete, label calibration, primary after VI, Haiku endpoint, latency, chapters, CODEOWNERS binding, no-speech summaries | Left as user decisions in q1, q3, q4, q5, q7, q8b, q8c | Settled by U12, U9, U10, U8, U5, U6, U7, U13, U14 |

Conflicts that no decision settles are listed in section 7.5.

---

## 5. Video Intelligence deprecation and its consequences

**Fact.** "Starting on September 14, 2026, Video Intelligence API is officially deprecated and will no longer be
supported. … You can continue using Video Intelligence API until September 14, 2027, when it will be shut down. We
recommend migrating to Gemini family of models." (https://docs.cloud.google.com/video-intelligence/docs/deprecations,
updated 2026-10-07) [q4 S26; q5 S2].

**What it removes from Expause.** One call (`analyzeVideo`, `LABEL_DETECTION` + `EXPLICIT_CONTENT_DETECTION` on a 5 s
synthetic video built from the previews) feeds both Expause's `contentTags` and its `explicit` / `blocked` flags. Both
disappear on 2027-09-14 [q1 §3.3; q5 §1].

**Decisions.**

- **U1: scenewise's role does not change.** It stays a second opinion; only the primary it seconds changes. No part of
  scenewise is designed to become the primary.
- **U8: Expause's new primary is Cloud Vision** (SafeSearch + label detection), confirmed by a shadow run before the
  shutdown.

**Consequences for scenewise.**

| Area | Consequence | Source |
|---|---|---|
| Combination rule | Takes "primary likelihood per category" as input, not `pornographyLikelihood`, so it survives the migration unchanged | [q4 §Video Intelligence deprecation] |
| Categories combined | With Video Intelligence only `sexual` ↔ `pornographyLikelihood` is combined. With SafeSearch: `sexual` ↔ `adult` (and possibly `racy`), `violence_gore` ↔ `violence`. The rest stay new signals | [q4 §Likelihood mapping] |
| Thresholds | SafeSearch `adult` is not defined like VI's `pornography`; thresholds must be re-set, and whether SafeSearch shares a model with VI (correlated errors) is undocumented | [q4 open question 2] |
| scenewise tiers | Cloud Vision is not used as a scenewise tier (a Google signal beside a Google primary). Gemini 3.1/3.5 Flash-Lite remains usable as an optional hosted tier-2 alternative, with its own evaluation | [q4 §Hosted options] |
| Labels | Cloud Vision label detection keeps Google's entity vocabulary at the `description` level, which is all Expause stores today. Whether Vision `mid`s equal VI `entityId`s is unverified and matters only if Expause keys on ids | [q5 §5a, OQ4] |
| Shadow run | Before 2027-09-14, run Cloud Vision (and scenewise) beside Video Intelligence on the same frames, logged against moderator decisions | [q4 §Evaluation plan] |
| Expause's cost (not scenewise's AI cost) | SafeSearch about $0.0015 per frame; Cloud Vision labels about $0.018 per video at 12 thumbnails, against about $0.0167 per video for today's VI call. The pricing page's "Free with Label Detection" for SafeSearch is undefined; confirm on the SKU page | [q4 §Hosted options; q5 §5b] |
| Previews | Expause issue E1 means today's sliced previews are wrong crops for trimmed Flutter uploads, and GVI analyses them. If the new primary reads the same previews, it inherits E1 until E1 is fixed (inference from q1 E1) | [q1 §7.3, §10] |

The deadline for Expause's migration before 2027-09-14 is an Expause fact still needed (section 7).

---

## 6. Expause issues found (candidate later Expause tasks)

Found while reading Expause's Cloud Functions at HEAD `32ed0bf18` (read only). None is fixed by this work; scenewise's
contract is correct regardless. Each row is a candidate Expause task [q1 §10].

| # | Issue | Effect | Suggested fix |
|---|---|---|---|
| E1 | Sprite mis-slicing for trimmed uploads: job start uses the untrimmed ffprobe duration for interval and column count, slicing uses the trimmed `media.duration` | Wrong crops and timestamps off by up to 2× in `previewNNNN.jpeg`; GVI analyses wrong crops | Slice with `payload.config.spriteSheets[0]` values |
| E2 | Second sprite sheet ignored (`findStorageFile` takes the first match) | Last preview lost; orphan sheet encrypted and copied to the CDN | Handle N sheets |
| E3 | `columnCount = 0` when duration < interval | Transcoder reads 0 as "no limit"; slicing divides by 0; no previews | `max(1, …)` |
| E4 | `Math.floor(mediaDuration / 1000) ?? 15` is `NaN`, never 15 | Missing duration → no previews | Test `Number.isFinite` |
| E5 | `previewOutputFiles.length` throws when no sheet was found | Falls into the catch, so encryption is skipped (E6) | Default `[]` |
| E6 | The catch path sets `isProcessing: false` but never starts encryption | Media "published" with no CDN segments; plaintext left in the transcoder bucket | Always reach `triggerVideoEncryption`, or a sweeper |
| E7 | `encrypt_video` is keyed by uid, written with `merge: true` | Two close uploads by one user: orphaned plaintext, two trigger chains racing, second media marked `hasErrors` | Key by `mediaId` |
| E8 | Cloud Tasks HTTP handlers are unauthenticated and tasks set no `oidcToken` (inferred from code; confirm the deployed `run.invoker` binding) | If public, anyone with the URL can trigger subscription auto-renewal, content publishing, boost end, campaign end | OIDC on tasks plus verification in handlers |
| E9 | `hasAudio` is not persisted | Downstream must re-detect it | Persist it with `resolution` |
| E10 | HLS `#EXT-X-KEY` advertises a constant IV that differs from the real per-media IV; init segments are encrypted too | Standard HLS decryptors cannot play or decrypt (the player presumably handles `hlsScheme://`; not verified) | Verify it is intended; backfill must use the Secret Manager IV |
| E11 | Success handler has no retry, a 180 s timeout, and waits synchronously on GVI | A slow GVI call can kill post-processing (E6 outcome), with no redelivery | Move GVI to its own task |
| E12 | ffprobe runs on a client-supplied URL (`dynamicUrl`), unvalidated | Authenticated blind SSRF from the Cloud Function; metadata may not describe the stored object | Probe the `gs://` object via a server-generated signed URL, or use the Transcoder's metadata |
| E13 | Plaintext stays restorable after deletion unless soft delete is off on the transcoder bucket (GCS default: 7 days, https://docs.cloud.google.com/storage/docs/soft-delete) | Deleted plaintext segments, playlists, sprite sheets and raw uploads of paywalled or early-access media restorable for 7 days (accepted for the upload bucket by U9) | **Requirement** for the scenewise integration: transcoder (and staging) bucket soft-delete retention 0. The upload bucket keeps 7 days (U9) |

---

## 7. Open measurements and Expause facts still needed

Grouped by the feature task that should carry each item. Source: [`open-decisions.md`](../research/open-decisions.md)
§2–§3, with the decisions in section 4 applied.

### 7.1 Runtime / deployment task (first engineering task)

- **The one-hour Cloud Run benchmark** on 4 vCPU / 16 GiB, europe-west1, gen2, in this order [q7 open question 1]:
  Freepik and the tier-2 guard per frame; Parakeet int8 RTFx, `tiny` LID, SigLIP 2 B/16, Silero, ffmpeg decode;
  **peak RSS with the guard loaded** (decides 8 vs 16 GiB, or a separate guard service); cold start of the `-cpu` image
  with and without lazy guard loading; audio and frame branches in parallel vs serial. Then set the constants and
  re-run `q7_cost_grid.py`. It also calibrates the push-budget cost factors (q8a Q-11), and it **settles local vs hosted
  Gemini 3.1 / 3.5 Flash-Lite captions**, a close call on CPU speed (Q2; q7 §1), together with whether Gemini 3.x is
  served on the `eu` multi-region endpoint (q7 OQ9).
- Whether Cloud Run health probes take a request slot at `concurrency = max_jobs` (q8a Q-19).
- Real idle retention and cold-start behaviour (q7 OQ8); e2 vs Cloud Run per-vCPU speed (q7 OQ11).
- L4 throughput with the `-cuda` image (TensorRT on driver 580, billed GPU start-up, batched vLLM) (q7 OQ2): only if
  a GPU path is ever considered.
- **Expause facts:** the GCP region of its buckets and Cloud Tasks queues (q7 OQ10); whether its billing account
  already uses the Cloud Run free tier (q7 OQ5); content mix (share with audio, with speech, speech fraction, length
  distribution; the 5-minute average is an assumption) (q7 OQ4, q3 OQ3).

### 7.2 Captions task (roadmap 1)

- **T1** music and no-speech set (instrumental, vocals, music under speech, ambient/silence, real Expause clips with
  permission): Silero ratio, Parakeet with and without VAD, AudioSet tagger plus an RMS gate. Feeds D22 [q2 §7]. Product call alongside it: whether lyric captions or SDH event cues ([music], [laughter]) are
  wanted at all (q2 OQ6).
- **T2** timestamps: sherpa start + duration vs onnx-asr vs NeMo word times; tune the cue end extension, segmentation cap
  and cut window.
- **T3** language ID: `tiny` vs `base` (ONNX, q11) on real Expause clips; the p(en) ≥ 0.5, 1.0 s and ≈ 2 s thresholds,
  reporting p(en) on noise and music beds (q11 OQ2); whether Parakeet
  log-probabilities separate languages; accented English. Feeds D19 and D21.
- **T4** process smoke test in CI: pip onnxruntime, sherpa-onnx and the ORT LID (faster-whisper in a separate
  `asr-whisper` job, q11 §4) in one process, both import orders,
  peak RSS; it runs in the `models` job and fails on a golden-file diff or on peak RSS above the instance budget
  [q8c §6.2 item 11].
- Tune q8c's segmentation starting values with T1–T3: `merge_gap` (2 s) and the LID batch size `lid_chunk` (10)
  [q8c §2].
- Parakeet vs faster-whisper int8 turbo / distil-large-v3.5 on the same CPU; int8 vs fp32 WER (q2 OQ2, OQ3).
- Optional: ARK-ASR-0.6B, Granite-speech, Voxtral (q2 OQ7, OQ8, OQ12). Gemini captions are not optional extras: the
  benchmark in section 7.1 decides local vs Gemini (q7 OQ9). If Gemini wins, its word-timestamp quality is tested here.
- **Legal sign-off:** CC-BY-4.0 NOTICE wording and where Expause shows the credit (q2 OQ11; U4 settles the default);
  the AudioSet tagger: Apache-2.0 per its card, but its AudioSet training-data provenance is a legal call still open
  (D22; q2 OQ16).

### 7.3 Expause adapter / input task (built in Expause)

- Transcoder audio timing on one real job: `elst media_time`, first PTS, `tfdt`; whether fMP4 stitches with `cat`
  (q1 OQ2).
- Second previews sheet and partial-sheet padding, which decides whether `count` is mandatory (q1 OQ3); init and
  playlist object names for the segment path (q1 OQ1).
- p99 duration of `transcodeJobUpdated` (sizes the 120 s skip threshold) (q1 OQ5); server-side copy latency for a
  130 MB object; whether `MuxStream.fileName` may contain `/` (q1 OQ11); billing of the extra audio mux stream on a real
  invoice (q1 OQ10).
- Bucket checks: staging in the transcoder bucket's region, EU, compatible with the `europe-west1` intake; **transcoder
  bucket soft delete set to 0** (q1 OQ12, E13).
- **Expause facts:** the Transcoder sprite and preview job configs (grid, interval, offset, tile size), which Expause
  supplies and scenewise never infers (q1 §4.3); caption serving and VTT encryption (D30) and backfill (D31), decided in
  this task.

### 7.4 Summaries, moderation and labels tasks (roadmap 2–4)

**Summaries (roadmap 2)**
- A 50–100-video eval: Haiku 5.5 vs Qwen3.5-4B / 9B / 35B-A3B, with and without frame labels; refusal rate (q3 OQ1,
  OQ7; D18).
- `llama-bench` on self-host hardware (q3 OQ5); self-hosted GPU prices (q3 OQ6); OpenRouter per-provider structured
  output and thinking-off, smoke-tested with `require_parameters: true` (q3 OQ9).
- Calibrate the 120 s / 40-word thresholds on real samples (U7).

**Moderation (roadmap 3)**
- The **shadow run** in Expause: Video Intelligence vs scenewise vs Cloud Vision, logged against moderator outcomes; it
  also answers SafeSearch-vs-VI equivalence (q4 OQ2).
- Haiku on explicit frames: refuse, or only decline to describe? Does NCMEC hash-matching apply to API traffic? (q4 OQ3)
- CPU latency of Freepik, Marqo, Falconsai, SigLIP 2, Shieldstral GGUF (q4 OQ9).
- That the guard server returns `top_logprobs` for image + text requests, which the `ImageGuard` adapter needs
  (q8c §4.2).
- Licence checks: NudeNet (OQ6), LlavaGuard weights (OQ7), Nemotron (D24), evaluation dataset terms for commercial use
  (OQ12). Unverified: Shieldstral claims, ShieldGemma 2 input resolution, Haiku resolution tier (OQ10, OQ11).
- Gemini terms on Vertex, Vertex prices, whether safety filters can be turned off (q4 OQ5), if Gemini is ever used.
- **Expause facts:** real escalation rate, human-review capacity and target escalation rate (q4 OQ14); the precision
  target at LIKELY+ and the number N of reviewed escalations before `max` mode (release gate); **the legally required
  CSAM detection and reporting process, and whether it must run before frames reach scenewise or any third-party API**
  (q4 OQ4); how many preview thumbnails Expause sends today and whether scenewise scores the same frames (q4 OQ13); the
  deadline for the post-VI migration (q5 OQ1).

**Labels (roadmap 4)**
- An eval set of a few hundred Expause videos: SigLIP 2 B/16 vs B/32-256 vs NaFlex vs PE-Core-B/16; squash vs pad;
  `max` vs `mean` vs top-3; drift with K; default `z_min`; English vs non-English prompts (q5 OQ10). The U10
  calibration run belongs here.
- The **visual-only summary rule** for summaries without speech (U14; q8c §5), with tests.
- Haiku tagging quality and token counts (q5 OQ9); Firestore EU vector rates and flat kNN behaviour (q5 OQ5); Vision
  `mid` vs VI `entityId`, only if Expause keys on ids (q5 OQ4).
- **Expause facts:** whether its recommender consumes dense vectors and where (q5 OQ11); whether video embeddings
  count as personal data under its privacy policy (q5 OQ7).

**Translation (deferred)**
- chrF/COMET head-to-head for Seed-X, MADLAD, Opus-MT, Canary, Haiku 5.5, Qwen3 on Expause languages; Haiku token
  counts per script (q6 OQ4, OQ6); Omnilingual MT weights and licence (q6 OQ2); DeepL/Google context and glossary
  support (q6 OQ9).
- **Expause fact:** target languages (if English↔European only, Canary-1b-v2 becomes an option) (q6 OQ5).

### 7.5 Conflicts: settled by q8c, U13–U17, q10 and q11, and still open

**Settled** (each was an open row here before q8c; the resolutions are in section 4.3 and Q8):

| Item | Resolution |
|---|---|
| Packaging of the ASR runtimes (sherpa-onnx primary vs q8a's onnx-asr `asr` extra; faster-whisper for the LID gate in an optional `asr-whisper`) | **One CPU-only `asr` extra** with sherpa-onnx 1.13.8, onnx-asr 0.12.0, onnxruntime 1.30.0 and numpy 2.5.3, all pinned; `ort-cpu`/`ort-cu130` removed [q8c §3]. Since U16, faster-whisper 1.2.1 is in the opt-in `asr-whisper` (fallback only) and LID is an in-house ORT adapter [q11 §4] |
| GPU path for the primary ASR (onnx-asr + onnxruntime-gpu vs k2-fsa's CUDA wheels) | **Neither in v1: GPU ASR is out of v1**, and ASR runs on CPU in both images. onnx-asr + onnxruntime-gpu is rejected because faster-whisper hard-requires pip `onnxruntime` [q8c §3, X1]. The route is researched only if a GPU deployment or the L4 job mode is built |
| Status of a no-speech captions stage (q1: `succeeded` + `no_speech`; D23: `skipped`) | **`skipped / no_speech`, no VTT** (D23 confirmed); q1's exception is removed [q8c §5] |
| How the tier-2 guard is wired | **Its own `ImageGuard` port** and adapter `adapters/llm/openai_guard.py`, against an out-of-process OpenAI-compatible server [q8c §4.2]. The *model* is still open (below) |
| CODEOWNERS identity model (q8b OQ7) | **U13**: option A′ (agent PRs opened by GitHub Actions as `github-actions[bot]`; code-owner review binds; Repository-admin bypass, pull requests only). **U13a**: local-run PRs are maintainer-authored, so a gate change from them needs the logged admin bypass, on purpose |
| google-auth placement (q8b OQ12) | **Stays in `gcs`**; with `callback_auth = oidc` bootstrap imports `google.oauth2.id_token` and turns an `ImportError` into a `ConfigurationError`. `anthropic[vertex]` brings google-auth too [q8c §8, X4] |
| Online zizmor in the merge gate (q8b OQ13) | **No**: offline in the gate, online in the nightly `supply-chain` job [q8c §8] |
| Summaries for videos without enough speech (q8c OQ-B) | **U14**: speech-only in v1; visual-only summaries with roadmap item 4 |
| Licence of the FFmpeg libraries bundled in PyAV's wheels (q8c §6.3 item 21) | **q10**: effectively GPL-3.0-or-later (x264/x265 linked, `--enable-version3`). **U16**: PyAV only via the opt-in `asr-whisper`, left out of published images; whoever distributes such an image takes on q10 §3. q10 §4's **[lawyer]** questions remain before images are published |

**Still open**

| Item | Side A | Side B | Carried by |
|---|---|---|---|
| **Tier-2 guard model.** q4 names two candidates; q7 open question 6 says the model and quantisation are not fixed, and the guard's RAM drives the 8 vs 16 GiB choice. q8c §4.2 keeps the choice open | Shieldstral-1.0-3B: Apache-2.0, vendor-reported higher scores, free-text policies | ShieldGemma 2 4B: three trained policies with its own published report; Gemma Terms flow-down, gated | Moderation task (roadmap 3), after the benchmark |
| **Guard server returns `top_logprobs`** for image + text chat requests with the candidate's GGUF and vision projector (not checked in q8c §4.2) | — | — | Moderation task (roadmap 3) |
| **Visual-only summary rule** (U14). q8c §5 gives a starting point: at least 3 distinct emitted non-moderation labels, each the top label on at least one frame; plus whether summary runs the labeller itself, and an additive `"labels"` value for `inputs_used` | — | — | Labels task (roadmap 4) |
| **GPU ASR packaging route**, if a GPU path is ever built. Constraint: pip `onnxruntime` is always present, so the route must not install `onnxruntime-gpu` beside it. k2-fsa's CUDA wheel details are unverified pointers [q8c §3] | — | — | Only if a GPU image or the L4 job mode is built |
| **ffmpeg in published images** (U17): GPL either way through the base OS; q10 recommends Ubuntu's unless a consumer needs no GPL ffmpeg [q10 §5] | Ubuntu apt ffmpeg `7:6.1.1-3ubuntu5` (GPL-2.0-or-later; same as dev/CI) | LGPL-only ffmpeg build (no x264/x265; own source bundle) | The first published Dockerfile |
| Tooling follow-ups (q8b OQ3, OQ4, OQ5, OQ8, OQ9) | `uv audit` vs pip-audit; Dependabot and `required-version`; licences of CMU flite voices and `hf-internal-testing/tiny-random-*` models; mutation testing; macOS ffmpeg and libflite | — | Part 2 / tooling |

Starting values that q8c sets but does not treat as decisions: `merge_gap` 2 s, `lid_chunk` 10 windows, and
`summary_min_words` 40; T1–T3 and U7's real-sample tuning adjust them [q8c, round-2 resolution].

---

## 8. Repository setup (Part 2)

Each step is checked off here when done, or explicitly deferred with a reason. The research lives in this folder,
`/Users/daniel/Work/scenewise` (`~/Work/scenewise`, moved from `~/scenewise`; U15).

- [x] **1. Create the public repository `firu-daniel/scenewise`** from this folder, licence Apache-2.0 (set by
  the brief, Repository setup step 1, to match the harness). **Before the
  first push, squash the history** to one commit (or "Initial commit: the scenewise" plus one research-docs commit),
  with **no Co-Authored-By trailer** (U15); then push. Set up the code-owner ruleset (require code-owner review; Repository admin
  bypass, pull requests only) before agents first push gate changes (U13; q8c §8), and confirm there that Actions-authored
  PRs (`github-actions[bot]`) let the maintainer's approval count (U13). Local-run PRs are maintainer-authored, so a
  gate change from them needs the logged admin bypass, as intended (U13a). Add the nightly `codeowners/errors` check
  (q8b OQ7; q8c §8). Confirm the licence works with every model chosen:
  Parakeet v2 CC-BY-4.0 (attribution in NOTICE, U4); Silero v6.2 MIT; Whisper `tiny` / `large-v3-turbo` and their
  CTranslate2 conversions MIT; sherpa-onnx Apache-2.0; onnx-asr MIT; SigLIP 2 Apache-2.0; Freepik MIT; Marqo
  Apache-2.0; Shieldstral Apache-2.0 or ShieldGemma 2 (Gemma Terms flow-down); Qwen3.5-4B Apache-2.0;
  `multilingual-e5-small` MIT; the optional AudioSet tagger Apache-2.0 per its card, provenance check pending (D22;
  q2 OQ16). None is non-commercial. Haiku 5.5 is a
  commercial API, not a distributed model. Also review the licence of the FFmpeg libraries bundled in PyAV's wheels,
  which every `asr` image ships through faster-whisper (q8c §6.3 item 21; not yet checked).

  **Done 2026-10-08:** repository created and pushed, two commits ("Initial commit: the scenewise" and "Add the
  project skeleton"), licence Apache-2.0. The PyAV licence review is now covered by **q10** (GPL-3.0-or-later; with
  U16 PyAV is only in the opt-in `asr-whisper`, outside published images); its open items remain: the **[lawyer]**
  questions of q10 §4, the published-image ffmpeg choice (U17, q10 §5) and the third-party notices and source bundle
  for published images (q10 §3). The code-owner ruleset and the nightly `codeowners/errors` check are not part of this
  tick (see `docs/skeleton-notes.md`, review r1 finding 6).
- [x] **2. Build the skeleton** with q8a's package tree (with the corrections in section 4.3 and every edit in
  [q8c §6.1–§6.3](../research/q8c-reconciliation.md)), the ports as `Protocol`s and the domain types, **one thin stage
  wired end to end** (audio extraction with ffmpeg behind `MediaTool`, with a test), every Q8 gate configured and
  passing (line length 88), and model dependencies pinned in their extras. `pyproject.toml` floors follow q8a's `>=`
  style and equal the versions read on 2026-10-08; `uv.lock` pins exactly, so check after `uv lock` that it resolves
  to them [q8c §3]:

  | Extra | Pins (from the findings) |
  |---|---|
  | base | pydantic 2.13.5 (pydantic-core 2.46.5), pydantic-settings 2.15.0, structlog 26.1.0, httpx 0.28.1, **Pillow 12.3.0** (`pillow>=12.3`, D3) [q8a §6.6, §7, §9.4; q8c §3, X1] |
  | `service` | fastapi 0.142.4, uvicorn 0.54.0 (anyio 4.15.1) [q8a §9.4] |
  | `asr` (CPU only) | sherpa-onnx 1.13.8 (pulls sherpa-onnx-core ==1.13.8; primary, D20); onnx-asr 0.12.0, no `[hub]`, no `[cpu]` (second runtime); onnxruntime 1.30.0 (Silero, Whisper-tiny LID, q11); numpy 2.5.3; no PyAV [q8c §3; q2 §5.2; q11 §4; U16]. Weights for the image layer: Parakeet v2 int8 `csukuangfj/…-int8` @ `1ab9323…` and `istupakov/parakeet-tdt-0.6b-v2-onnx` @ `0bbb45a…` (int8 files only); Silero v6.2 `silero_vad.onnx` sha256 `1a153a22…`, fetched for CI through its byte-identical mirror `istupakov/silero-vad-onnx` @ `b3e3ee3`; Whisper `tiny` LID `onnx-community/whisper-tiny` @ `ff41770…` (fp32 `onnx/encoder_model.onnx`, `onnx/decoder_model.onnx`, `generation_config.json`, `added_tokens.json`; sha256 in q11 §2.3), replacing `Systran/faster-whisper-tiny`; pin huggingface-hub explicitly in the lock [q2 §5.2; q8c §6.2 item 11a, §7.6] |
  | `asr-whisper` (opt-in, U16) | faster-whisper 1.2.1 (fallback recogniser; pulls ctranslate2 4.8.2 and PyAV 19.0.1, whose wheels bundle GPL x264/x265, q10); not in published images. Weights: `dropbox-dash/faster-whisper-large-v3-turbo` @ `0a363e9…` (self-built `asr-whisper` images only, not CI) [q11 §4] |
  | `llm-anthropic` | `anthropic[vertex]>=1.12` (anthropic 1.12.1) (U5) [q7 §2.3; q8a §9.4] |
  | `vision` | open-clip-torch 3.3.0, timm 1.0.30 (floor `>=1.0.17`); Pillow removed (now base, D3) [q5 §3; q8a §9.4; q8c §3] |
  | `gcs` | google-cloud-storage 3.16.0, google-auth (2.61.0 in q8b's lock); google-auth stays here [q8a §9.4; q8c §8] |
  | `torch-cpu` / `torch-cu130` | torch 2.14.1, torchvision 0.29.1, from the PyTorch `cpu` / `cu130` indexes; the only uv `conflicts` pair [q8a §9.4; q8c §6.1 item 3] |
  | removed | `ort-cpu`, `ort-cu130` [q8c §3] (`asr-whisper`, removed by q8c, returned as opt-in with U16) |
  | dev group | uv 0.12.23, ruff 0.16.10, mypy 2.4.0, import-linter 2.15, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.2, pytest-timeout 2.4.0, pytest-randomly 5.0.0, hypothesis 6.168.5, deptry 0.25.1, vulture 2.16, typos 1.51.1, zizmor 1.30.1; hooks: pre-commit 4.6.2 or prek 0.5.5 (D6) [q8b] |

  Images [q8c §3]: `-cpu` = `--extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra
  torch-cpu`; `-cuda` = the same with `--extra torch-cu130`. Neither includes `asr-whisper`; `scripts/check_lock.sh`
  asserts that neither set (nor `asr`) resolves `av`, `ctranslate2` or `faster-whisper` (U16).
  Weights are mirrored into scenewise-controlled storage with full sha256 recorded, and baked into the image [q2 §5.2].
  Commit the q1/q2/q5 local measurement scripts under `bench/` if they still exist; otherwise record that they are lost
  and that the Cloud Run benchmark (section 7.1) replaces their figures [q1 §6.2].

  **Done 2026-10-08:** skeleton built (deviations in `docs/skeleton-notes.md`); every gate green locally and in
  GitHub CI run 37792034530 (`static` and `test` on 3.12, 3.13 and 3.14). U16's extras change landed afterwards.
- [x] **3. Install ffmpeg locally and record the version.** q8b's runs used a static ffmpeg 7.1 (imageio-ffmpeg build,
  no ffprobe); CI installs apt ffmpeg on `ubuntu-24.04`. Whether Homebrew's build has libflite (for generated speech
  fixtures) is open (q8b OQ9). **Done 2026-10-08:** ffmpeg 9.0.2 (with ffprobe) installed via Homebrew; it has **no
  libflite**, so speech fixtures need another source (q8b OQ9). CI keeps Ubuntu's apt ffmpeg 6.1.1 (U17).
- [ ] **4. Adopt the harness:** `npx autonomous-sdlc-harness init`, then `/autonomous-sdlc-harness:harness-analyze`.
  Record the mode it detected (the skeleton should make it `existing`), the preset and layers `init` detected, whether
  the conventions documents match `ARCHITECTURE.md`, and every hand correction as a harness finding. Feeds Q9.
- [ ] **5. Keys, never committed:** `.env.local` (gitignored) and a committed `.env.example`. Expause's Haiku path is
  Vertex AI EU (U5), so the settings are `provider`, Google Cloud `project_id` and `region`; an Anthropic API key is
  needed only for the first-party provider. Default: harness runs and CI reach no paid API.
- [ ] **6. `doctor` passes** on the new repository, or every failing check is explained.

---

## 9. Sources

All external sources were read on **2026-10-08**. Local measurements ([L1] in q1, q2, q5) were run on 2026-10-08 on an
Apple M4 (linux/amd64 in Docker for q2's memory figure); their scripts were in the session scratchpad, not the repo, and are to be committed under `bench/` in Part 2 step 2 if
they still exist. Each
findings file lists further sources; the ones this document relies on are below, grouped by question.

**Decisions and compiled questions**
- `docs/research/user-decisions.md` (U1–U17 and U13a, orchestrator defaults), `docs/research/open-decisions.md`.

**Later findings** (all read 2026-10-08)
- [q10](../research/q10-pyav-ffmpeg-licence.md): the av 19.0.1 manylinux x86_64 wheel's contents; pyav-ffmpeg
  `9.0.2-1`, its `patches/ffmpeg.patch` history and build script; PyAV issue #2270 and PR #967; ffmpeg.org/legal.html
  and FFmpeg `configure` (n8.0); x264/x265 headers; Ubuntu noble ffmpeg `debian/rules` and `debian/copyright`; the GPL
  FAQ, GPLv3 and the ASF's GPL-compatibility page.
- [q11](../research/q11-asr-without-pyav.md): OpenAI Whisper README (MIT); `onnx-community/whisper-tiny` @ `ff41770`;
  sherpa-onnx 1.13.8 and onnx-asr 0.12.0 wheels and sources; faster-whisper 1.2.1 PyPI metadata and wheel; Silero
  and SpeechBrain LID pages; local runs of the scripts in `docs/research/q11/` and a uv 0.12.23 relock.
- The research brief, `research_scenewise_project_task_prompt.md` (outside the repository): sets the Apache-2.0 code
  licence (Repository setup step 1).

**Reconciliation** ([q8c](../research/q8c-reconciliation.md), checks X1–X5, all read 2026-10-08)
- PyPI JSON API, `https://pypi.org/pypi/<name>/<version>/json`: faster-whisper 1.2.1, sherpa-onnx 1.13.8, onnx-asr 0.12.0, onnxruntime 1.30.0, Pillow 12.3.0, numpy 2.5.3, anthropic 1.12.1 (`vertex` extra) [X1, X4]
- Wheel contents of `sherpa_onnx_core-1.13.8` and `sherpa_onnx-1.13.8` (macOS arm64), downloaded from PyPI [X2]
- faster-whisper v1.2.1 `audio.py`: https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/faster_whisper/audio.py ; `transcribe.py` and `vad.py` at v1.2.1 [X3, X5]
- onnx-asr v0.12.0 source tree (`py.typed`, `asr.py` `TimestampedResult.logprobs`) [X4]
- WhisperX `whisperx/vads/vad.py` `merge_chunks`: https://github.com/m-bain/whisperX [X5]
- GitHub docs, "Creating rulesets for a repository" and "Managing rulesets for a repository" (bypass actors, "For pull requests only") [X5]

**Q1** ([q1 §13](../research/q1-input-contract.md))
- Expause Cloud Functions source at HEAD `32ed0bf18` (2026-09-22), read only; `file:line` references in q1 §3 and §10.
- Transcoder `JobConfig`: https://docs.cloud.google.com/transcoder/docs/reference/rest/v1/JobConfig
- Transcoder pricing: https://cloud.google.com/transcoder/pricing
- Cloud Tasks `tasks.create`: https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks/create
- Cloud Tasks `HttpRequest`: https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks
- GCS soft delete: https://docs.cloud.google.com/storage/docs/soft-delete
- OWASP SSRF cheat sheet: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- Firebase Cloud Storage triggers: https://firebase.google.com/docs/functions/gcp-storage-events
- W3C WebVTT: https://www.w3.org/TR/webvtt1/
- openai/whisper `audio.py`: https://raw.githubusercontent.com/openai/whisper/main/whisper/audio.py ; faster-whisper at `9fa78645`: https://github.com/SYSTRAN/faster-whisper

**Q2** ([q2 §11](../research/q2-captions.md))
- Open ASR Leaderboard CSV rev c23ca4f: https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results/resolve/c23ca4f10e5f1a77c9fd3b41e17cd06a04f0f56c/english_short_latest.csv ; Space: https://huggingface.co/spaces/hf-audio/open_asr_leaderboard
- Parakeet v2 card: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- onnx-asr benchmarks: https://istupakov.github.io/onnx-asr/benchmarks/ ; PyPI: https://pypi.org/pypi/onnx-asr/json
- sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx ; PyPI: https://pypi.org/pypi/sherpa-onnx/json ; CUDA wheels: https://k2-fsa.github.io/sherpa/onnx/cuda.html
- Silero VAD: https://github.com/snakers4/silero-vad
- Barański et al., arXiv 2501.11378v1: https://arxiv.org/html/2501.11378v1
- TheStageAI card: https://huggingface.co/TheStageAI/thewhisper-large-v3-turbo ; Qwen3-ASR card: https://huggingface.co/Qwen/Qwen3-ASR-1.7B
- whisper-large-v3-turbo card: https://huggingface.co/openai/whisper-large-v3-turbo ; distil-large-v3.5 card: https://huggingface.co/distil-whisper/distil-large-v3.5

**Q3** ([q3 §Sources](../research/q3-summaries-chapters.md))
- Anthropic pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Haiku 5.5 overview: https://platform.claude.com/docs/en/models/haiku-5-5/overview ; what's new: https://platform.claude.com/docs/en/models/haiku-5-5/whats-new-haiku-5-5
- Structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs ; effort: https://platform.claude.com/docs/en/build-with-claude/effort ; batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing ; refusals: https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
- Chapter-Llama: https://arxiv.org/html/2504.00072v1 ; VidChapters-7M: https://arxiv.org/html/2309.13952 ; YouTube chapters: https://support.google.com/youtube/answer/9884579
- Qwen3.5-4B: https://huggingface.co/Qwen/Qwen3.5-4B ; Gemma 4: https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html ; Gemma Terms: https://ai.google.dev/gemma/terms ; Llama 3.2 AUP: https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/USE_POLICY.md ; Llama 4 AUP: https://github.com/meta-llama/llama-models/blob/main/models/llama4/USE_POLICY.md
- OpenRouter models API: https://openrouter.ai/api/v1/models

**Q4** ([q4 §Sources](../research/q4-moderation.md))
- Video Intelligence deprecations: https://docs.cloud.google.com/video-intelligence/docs/deprecations ; Likelihood: https://docs.cloud.google.com/video-intelligence/docs/reference/rest/v1/Likelihood ; explicit content: https://docs.cloud.google.com/video-intelligence/docs/analyze-safesearch
- Freepik: https://huggingface.co/Freepik/nsfw_image_detector/raw/main/README.md ; Marqo: https://huggingface.co/Marqo/nsfw-image-detection-384/raw/main/README.md
- Shieldstral: https://huggingface.co/mistralai/Shieldstral-1.0-3B ; ShieldGemma 2 report: https://arxiv.org/html/2504.01081 ; Nemotron: https://huggingface.co/nvidia/nemotron-3.5-content-safety ; Llama Guard 4: https://huggingface.co/meta-llama/Llama-Guard-4-12B ; NudeNet: https://pypi.org/project/nudenet/
- Anthropic Usage Policy: https://www.anthropic.com/legal/aup ; content moderation guide: https://platform.claude.com/docs/en/about-claude/use-case-guides/content-moderation ; vision: https://platform.claude.com/docs/en/build-with-claude/vision ; CSAM detection: https://support.claude.com/en/articles/9020328-csam-detection-and-reporting
- Cloud Vision SafeSearch: https://docs.cloud.google.com/vision/docs/detecting-safe-search ; Cloud Vision pricing: https://cloud.google.com/vision/pricing
- Gemini for moderation: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-for-filtering-and-moderation ; Vertex model versions (2.5 Flash-Lite retires 2026-10-20): https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
- UnsafeBench: https://arxiv.org/abs/2405.03486

**Q5** ([q5 §9](../research/q5-labels.md))
- SigLIP 2: https://arxiv.org/html/2502.14786 ; HF API: https://huggingface.co/api/models/google/siglip2-base-patch16-224
- open_clip: https://pypi.org/pypi/open-clip-torch/json ; configs at v3.3.0: https://github.com/mlfoundations/open_clip/tree/v3.3.0/src/open_clip/model_configs
- PE-Core: https://github.com/facebookresearch/perception_models
- Apple model licence: https://raw.githubusercontent.com/apple/ml-mobileclip/main/LICENSE_MODELS ; MetaCLIP 2: https://huggingface.co/facebook/metaclip-2-worldwide-huge-quickgelu ; OpenAI CLIP card: https://huggingface.co/openai/clip-vit-large-patch14
- YouTube recommendations paper: https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/45530.pdf
- Video Intelligence labels: https://docs.cloud.google.com/video-intelligence/docs/analyze-labels ; pricing: https://cloud.google.com/video-intelligence/pricing
- Cloud Vision labels: https://docs.cloud.google.com/vision/docs/labels ; Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Firestore vector search: https://firebase.google.com/docs/firestore/vector-search ; billing: https://firebase.google.com/docs/firestore/pricing

**Q6** ([q6 §Sources](../research/q6-translation.md))
- Whisper paper: https://arxiv.org/html/2212.04356v1 ; README: https://github.com/openai/whisper
- NLLB-200: https://huggingface.co/facebook/nllb-200-distilled-600M ; SeamlessM4T v2: https://huggingface.co/facebook/seamless-m4t-v2-large
- MADLAD-400: https://huggingface.co/google/madlad400-3b-mt ; Opus-MT: https://github.com/Helsinki-NLP/Opus-MT ; Seed-X licence: https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B/raw/main/LICENSE ; Canary-1b-v2: https://huggingface.co/nvidia/canary-1b-v2
- Hunyuan-MT licence: https://huggingface.co/tencent/Hunyuan-MT-7B/raw/main/License.txt ; TranslateGemma: https://huggingface.co/google/translategemma-4b-it
- Google Cloud Translation pricing: https://cloud.google.com/translate/pricing

**Q7** ([q7 §11](../research/q7-runtime-cost.md))
- Cloud Run pricing: https://cloud.google.com/run/pricing ; GPU: https://docs.cloud.google.com/run/docs/configuring/services/gpu ; GPU best practices: https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices ; quotas: https://docs.cloud.google.com/run/quotas ; memory limits: https://docs.cloud.google.com/run/docs/configuring/services/memory-limits ; autoscaling: https://docs.cloud.google.com/run/docs/about-instance-autoscaling ; Delayed Jobs: https://docs.cloud.google.com/run/docs/delayed-jobs
- Compute Engine pricing: https://cloud.google.com/products/compute/pricing/accelerator-optimized , https://cloud.google.com/products/compute/pricing/general-purpose
- Anthropic data residency: https://platform.claude.com/docs/en/build-with-claude/data-residency ; Claude on Vertex AI: https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai ; Vertex Haiku 5.5: https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-5-5 ; Vertex pricing: https://cloud.google.com/vertex-ai/generative-ai/pricing ; Vertex Claude batch: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/claude/batch
- Speech-to-Text pricing: https://cloud.google.com/speech-to-text/pricing ; Gemini audio: https://ai.google.dev/gemini-api/docs/audio
- GitHub terms: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features ; runner pricing: https://docs.github.com/en/billing/reference/actions-runner-pricing ; limits: https://docs.github.com/en/actions/reference/limits

**Q8** ([q8a](../research/q8a-architecture-layout.md), sources inline; [q8b §9](../research/q8b-tooling-gates.md))
- PyPA src layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ ; Hynek, Testing & Packaging: https://hynek.me/articles/testing-packaging/ ; uv workspaces: https://docs.astral.sh/uv/concepts/projects/workspaces/
- Cosmic Python ch. 2: https://www.cosmicpython.com/book/chapter_02_repository.html ; ch. 13: https://www.cosmicpython.com/book/chapter_13_dependency_injection.html ; appendix: https://www.cosmicpython.com/book/appendix_project_structure.html
- Cockburn: https://alistair.cockburn.us/hexagonal-architecture/ ; Rhodes: https://rhodesmill.org/brandon/slides/2014-07-pyohio/clean-architecture/ ; Hynek, Subclassing: https://hynek.me/articles/python-subclassing-redux/ ; Glyph: https://blog.glyph.im/2020/07/new-duck.html ; PEP 544: https://peps.python.org/pep-0544/ ; PEP 725: https://peps.python.org/pep-0725/
- Cloud Run with Cloud Tasks: https://docs.cloud.google.com/run/docs/triggering/using-tasks ; anyio threads: https://anyio.readthedocs.io/en/stable/threads.html ; uv PyTorch guide: https://docs.astral.sh/uv/guides/integration/pytorch/
- Compared projects: https://github.com/SYSTRAN/faster-whisper , https://github.com/m-bain/whisperX , https://github.com/BerriAI/litellm , https://github.com/vllm-project/vllm , https://github.com/pydantic/pydantic-ai , https://github.com/pypi/warehouse
- PyPI JSON API for every version: https://pypi.org/pypi/<name>/json ; mypy changelog: https://mypy.readthedocs.io/en/stable/changelog.html ; ruff rules: https://docs.astral.sh/ruff/rules/ ; ruff formatter: https://docs.astral.sh/ruff/formatter/ ; import-linter: https://import-linter.readthedocs.io/en/stable/contract_types/ ; coverage config: https://coverage.readthedocs.io/en/latest/config.html ; CODEOWNERS: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
