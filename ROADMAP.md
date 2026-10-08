# Roadmap

scenewise is an open-source, self-hosted Python service that understands video: captions, summaries, chapters, a
moderation second opinion and labels. Adopters run it in their own cloud and pay their own costs. Expause is its first
consumer, through an adapter built on Expause's side.

This roadmap is based on the initial research of 2026-10-08. The decision document
[docs/decisions/initial-research.md](docs/decisions/initial-research.md) summarises it, and the findings it rests on are
in [docs/research/](docs/research/). The current list of open measurements and facts still needed from Expause is
[section 7 of the decision document](docs/decisions/initial-research.md#7-open-measurements-and-expause-facts-still-needed);
[docs/research/open-decisions.md](docs/research/open-decisions.md) is the full record of the questions the research
raised, most of which are now settled.

Codes in brackets point to those files. U-numbers are decisions the maintainer took, and D-numbers are defaults adopted
from the research's recommendation, which the maintainer may still override; both are in
[docs/research/user-decisions.md](docs/research/user-decisions.md). T-numbers are caption tests (decision document
§7.2) and E-numbers are issues found in Expause's current pipeline (decision document §6).

Cost figures are estimates for AI processing only, not measurements. Every local-compute figure, and so every monthly
total, depends on the Cloud Run benchmark described under [Cross-cutting work](#cross-cutting-work).

Status values: **next** (being prepared now), **planned** (designed, scheduled after the items before it),
**deferred** (not scheduled).

## Before item 1

The order of work is: repository skeleton, then the Cloud Run benchmark, then captions (item 1). The skeleton gives the
repository the architecture's shape before any feature: a `src/` layout with the layers
`service > (adapters | app) > ports > domain`, one thin stage wired end to end (audio extraction with ffmpeg behind its
port, with a test), every tooling gate configured and passing, and model dependencies pinned in extras so the base
install has no torch. [ARCHITECTURE.md](ARCHITECTURE.md) describes the layout,
[q8a](docs/research/q8a-architecture-layout.md) and [q8b](docs/research/q8b-tooling-gates.md) give the reasoning, and
[section 8 of the decision document](docs/decisions/initial-research.md#8-repository-setup-part-2) lists the setup steps
and the remaining checks (Dependabot and `required-version`, test-fixture and tiny-model licences, Homebrew ffmpeg and
libflite, and the licence of the FFmpeg libraries bundled in PyAV's wheels). Pull requests from harness runs on GitHub
Actions get normal code-owner review; pull requests from local harness runs that touch gate files need the maintainer's
logged admin bypass (U13, U13a).

## 1. Captions for video on demand, English

**Status: next (after the skeleton and the Cloud Run benchmark).** The model is NVIDIA `parakeet-tdt-0.6b-v2` (int8,
CC-BY-4.0, used with attribution, U4). On the Open ASR Leaderboard it has the best word error rate among openly runnable
models with native word timestamps, and it beats every openly runnable Whisper variant (4.70% average WER vs
5.40–6.36%); in the same runtime it runs about 9× faster than Whisper large-v3-turbo on CPU
([q2](docs/research/q2-captions.md)). It runs on `sherpa-onnx` 1.13.8 behind a `SpeechRecognizer` port (D20), with
`onnx-asr` tested as the second runtime and faster-whisper with large-v3-turbo as the fallback. scenewise owns the
pipeline around the model: a Silero v6.2 voice-activity loop, a language-ID gate (faster-whisper `tiny`), segmentation
and cue building. Captions always run over one continuous audio track, never per 6-second segment, because on one
synthetic clip the per-segment approach made several times more errors ([q1](docs/research/q1-input-contract.md)), so
Expause adds one audio-only MP4 output to its Transcoder job. English is captioned when a video has at least about 2 s
of English speech (D19); windows in an unknown language are dropped and flagged (D21). Below that, no track is emitted
and the stage is skipped with `language_unsupported` or `language_unknown`; videos without speech are skipped with
`no_speech` (D23) and videos without audio with `no_audio_stream`. The main risks are music beds, for which there is no
evidence yet; Parakeet turning non-English speech into invented English when the language gate misses it; and Cloud Run
CPU speed: local captions are estimated at $0.0026 per 5-minute video, and at half the assumed speed that becomes
$0.0051, dearer than gated Gemini 3.x Flash-Lite on Vertex EU ($0.0040–0.0043)
([q7](docs/research/q7-runtime-cost.md)). The tests T1–T4 (music and no-speech set, timestamps, language-ID
thresholds, a one-process smoke test) and a Parakeet vs faster-whisper comparison on the same CPU are listed in
[§7.2](docs/decisions/initial-research.md#72-captions-task-roadmap-1).

## 2. Summaries and chapters

**Status: planned.** The production model is Claude Haiku 5.5, called synchronously with structured output, thinking
disabled and effort set to low, through Vertex AI's EU multi-region endpoint for Expause (U5, U6). Its cost is about
$0.00075 per 5-minute video on Vertex EU including the billed wait, about 17× less than a local Qwen3.5-4B on Cloud Run
CPU ([q3](docs/research/q3-summaries-chapters.md), [q7](docs/research/q7-runtime-cost.md)). Qwen3.5-4B (Apache-2.0)
through Ollama or llama.cpp stays the default for development and for self-hosters without an API key, and any
OpenAI-compatible endpoint can serve as a third back end. All back ends share one prompt, one schema and one Python
validator, which enforces the chapter rules no back end's schema can express. Chapters are emitted only for videos of at
least 120 s with at least 3 chapters, and a summary only from about 40 transcript words; below that, or without speech,
the stage is skipped (`below_minimum`). Both thresholds are configurable (U7). Summaries are speech-only for now;
visual-only summaries come with labels (item 4, U14). The main risks are that no published summarisation or chaptering
benchmark for Haiku 5.5 was found (it was released on 2026-10-07), that Haiku may refuse on moderation-flagged videos
with no automatic fallback in v1 (D18), and that small local models chapter measurably worse. The 50–100-video
evaluation, threshold tuning and back-end smoke tests are listed in
[§7.4](docs/decisions/initial-research.md#74-summaries-moderation-and-labels-tasks-roadmap-24).

## 3. Moderation second opinion, alongside Google's primary signal

**Status: planned.** scenewise can only escalate a video: it never clears one and is never offered as the primary
signal (U1). Tier 1 runs locally on every sampled frame: `Freepik/nsfw_image_detector` (MIT) for explicit content,
because its four graded levels map almost directly onto Google's likelihood buckets, and SigLIP 2 zero-shot prompts for
violence, gore and weapons ([q4](docs/research/q4-moderation.md)). Tier 2 runs only on ambiguous frames, with a
promptable guard model; the model is still open between Mistral Shieldstral-1.0-3B (Apache-2.0) and ShieldGemma 2, and
Nemotron is dropped until its licence is clear (D24). Claude Haiku 5.5 is an optional third opinion, and a refusal from
it counts as a reason to escalate. The combination rule takes the primary likelihood per category as input, so it works
unchanged when Expause's primary moves from Video Intelligence to Cloud Vision SafeSearch (U8). It runs in `advisory`
mode by default; `max` mode is offered only after a shadow run meets Expause's precision target. Content suspected to
involve a minor leaves the scenewise path and goes to Expause's CSAM procedure. The main risks are that the zero-shot
violence prompts have no accuracy evidence yet, that the CPU latencies of Freepik and the guard are guesses that make
up 61% of the estimated local compute per video, that several model and dataset licences are unverified, and that the
repository and CI must never hold explicit material. Still open: the shadow run against moderator decisions, CPU
latency, Haiku's behaviour on explicit frames, whether the guard server returns `top_logprobs` for image and text
requests, and licence checks for Nemotron, NudeNet, LlavaGuard and the evaluation datasets
([§7.4](docs/decisions/initial-research.md#74-summaries-moderation-and-labels-tasks-roadmap-24)).

## 4. Labels for feed recommendations, alongside Google's primary signal

**Status: planned.** The default model is SigLIP 2 ViT-B/16 through `open_clip_torch` 3.3.0, chosen for its Apache-2.0
weights, a multilingual text tower, 78.2% zero-shot accuracy on ImageNet-1k, and a measured median of 37 ms per image
on an Apple M4 CPU ([q5](docs/research/q5-labels.md)). It scores every preview thumbnail against a taxonomy the adopter
supplies as data and returns labels with a `calibrated` flag per label, plus, on request, a pooled video embedding from
the same pass. The estimated cost is about $0.00013 per 60-second video, against about $0.018 for Cloud Vision label
detection. Labels complement Google's signal (U1); uncalibrated labels are stored only for shadow comparison, and one
`scenewise calibrate` run is part of the Expause integration before labels reach Expause's `contentTags` (U10). This
item also defines the label-based rule for visual-only summaries, so that videos without enough speech get a summary
(U14; [q8c](docs/research/q8c-reconciliation.md) §5 gives a starting rule). The main risks are that open_clip squashes
vertical thumbnails to a square (SigLIP 2 NaFlex keeps the aspect ratio and is an evaluation candidate), that nothing
yet shows frame-content embeddings improve Expause's recommender, and that Firestore vector search suits only small or
pre-filtered candidate sets. The evaluation set of a few hundred Expause videos and the other open checks are listed in
[§7.4](docs/decisions/initial-research.md#74-summaries-moderation-and-labels-tasks-roadmap-24).

## 5. Subtitles in other languages

**Status: deferred (research only).** When this item is picked up, the default path is a source-language transcript
with timings, then LLM translation with context that keeps the original cue timings. Claude Haiku 5.5 is the hosted
option, at about $0.015–0.034 per target language per video-hour; Qwen3, Gemma 4 or Seed-X is the local option
([q6](docs/research/q6-translation.md)). Translation goes from the source transcript, not through an English pivot
(D28). Whisper alone cannot do this, because it translates only into English. The best-known dedicated translation
models are ruled out: NLLB, SeamlessM4T, Tower and Aya are non-commercial, and Hunyuan-MT/HY-MT exclude the EU (U3).
TranslateGemma is not adopted (D26). Cost is not the blocker; the blockers are product priority, a list of target
languages, and an evaluation set, because no usable model has quality evidence on short, informal user speech. If the
item is scheduled, it starts with a chrF/COMET comparison on Expause's languages and a pilot of Haiku with thinking off
vs low effort (D27).

## 6. Live input adapters

**Status: deferred, research first.** Live input is out of scope for now because of legal concerns around live
sessions, and because Expause streams through Agora, not LiveKit. The research covered only video on demand. The v1
architecture leaves out live playlists, and captions never run per segment
([q1](docs/research/q1-input-contract.md), [q8a](docs/research/q8a-architecture-layout.md)). Any live adapter needs its
own research before it is designed.

## 7. Hosted, billed service

**Status: deferred.** scenewise is self-hosted and open source first, and adopters pay their own costs. The research
sized only a self-hosted deployment ([q7](docs/research/q7-runtime-cost.md)). A hosted service would need a fresh
licence review: for example, the Gemma Terms of Use, which cover ShieldGemma 2 (a tier-2 candidate in item 3), count
offering a model as a hosted API as distribution ([q3](docs/research/q3-summaries-chapters.md),
[q4](docs/research/q4-moderation.md)).

## Cross-cutting work

- **Google Video Intelligence deprecation.** The API was deprecated on 2026-09-14 and shuts down on 2027-09-14. Expause
  moves its primary moderation and label signal to Cloud Vision (SafeSearch plus label detection), confirmed by a shadow
  run before the shutdown (U8). scenewise stays a complement either way (U1). Its moderation and label outputs are
  designed not to depend on which primary signal they are compared against ([q4](docs/research/q4-moderation.md),
  [q5](docs/research/q5-labels.md)).
- **Cloud Run CPU benchmark (the first engineering task, after the skeleton).** The recommended runtime is one Cloud
  Run CPU service in an EU region (europe-west1 assumed; the region of Expause's buckets decides), with 4 vCPU and
  16 GiB, scaling to 0, fed by Cloud Tasks through a synchronous push handler (U6). The estimated AI cost is $1.89 to
  $218 per month across the grid (1k to 100k monthly active users). If Cloud Run CPUs are between half and twice as
  fast as assumed, that range becomes $1.28 to $421. No source gives Cloud Run CPU speeds for these models, so every
  local-compute figure, every monthly total and every CPU-vs-GPU crossover waits on a one-hour benchmark
  ([q7](docs/research/q7-runtime-cost.md)). It measures, in order:
  - the Freepik detector and the tier-2 guard per frame;
  - Parakeet, the language-ID gate, SigLIP 2, Silero and ffmpeg decode;
  - peak memory with the guard loaded (this decides 8 vs 16 GiB, or a separate guard service);
  - cold start, with and without lazy guard loading;
  - the audio and frame branches in parallel vs in series.

  Whether Cloud Run health probes take a request slot is checked on a deployed revision.
- **Expause integration (built in Expause, not here).** scenewise contains no Expause code. Expause sends a generic
  `JobRequest` through Cloud Tasks and reads the job record and `result.json` from its own buckets
  ([q1](docs/research/q1-input-contract.md)). The Expause-side tasks are:
  - the Transcoder audio-only mux stream and the success-handler hook (copy to a staging bucket, enqueue one task,
    never throw);
  - a daily reconciliation;
  - transcoder bucket soft delete set to 0;
  - one `scenewise calibrate` run for labels (U10);
  - the caption-serving and backfill choices (D30, D31).

  The Expause issues q1 found are Expause-side tasks too, independent of scenewise:
  - E1–E5: sprite-sheet slicing and preview bugs;
  - E6: the encryption skip on the error path;
  - E7: the encryption loop keyed by user, not by media;
  - E8: unauthenticated Cloud Tasks handlers;
  - E9: `hasAudio` is not persisted;
  - E10: a non-standard HLS IV;
  - E11: the post-processing timeout;
  - E12: a blind SSRF through `ffprobe` on a client-supplied URL;
  - E13: soft delete keeps deleted plaintext restorable.

  The facts only Expause can supply, such as its content mix, volumes and region, are listed in
  [section 7 of the decision document](docs/decisions/initial-research.md#7-open-measurements-and-expause-facts-still-needed).
