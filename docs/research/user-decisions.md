# Decisions taken by the user during the research

Recorded by the orchestrator. Research and writing agents treat these as settled.

| # | Date | Question | Decision |
|---|---|---|---|
| U1 | 2026-10-08 | Google Video Intelligence is deprecated (2026-09-14) and shuts down 2027-09-14. Does scenewise's role change? | **Stay a complement.** Expause moves its primary moderation/label signal elsewhere (Gemini or Cloud Vision); scenewise remains a second opinion. No change of role. |
| U2 | 2026-10-08 | Minimum supported Python version | **3.12.** CI matrix 3.12–3.14. |
| U3 | 2026-10-08 | Where is the operator (Expause) based? | **EU.** Exclude anything with an EU territorial clause (Llama multimodal, Hunyuan/HY-MT) from every default and recommendation. |
| U4 | 2026-10-08 | Parakeet-TDT-0.6b-v2 weights are CC-BY-4.0 (attribution required). Acceptable as the default? | **Yes, with attribution** in NOTICE and README (incl. note of ONNX conversion / quantisation); Expause credits it. faster-whisper + large-v3-turbo (MIT) stays the fallback back end. |
| U5 | 2026-10-08 | Haiku 5.5 endpoint (D16) | **Vertex AI EU multi-region for Expause.** Provider and region are deployment settings: one Anthropic-SDK adapter supports `Anthropic` (first-party) and `AnthropicVertex` (any Vertex region), so adopters outside the EU pick their own. Inference location is the adopter's data-protection choice, not a scenewise constraint. |
| U6 | 2026-10-08 | Latency requirement (D15) | **Minutes: synchronous Cloud Run CPU service fed by Cloud Tasks, synchronous Haiku.** Batch/hourly modes are not built in v1. |
| U7 | 2026-10-08 | Chapters in a short-video app (D17) | **Yes, with the proposed limits:** chapters only for videos ≥ 120 s with ≥ 3 chapters; summary only above ~40 transcript words. Thresholds configurable, re-tuned on real samples. |
| U8 | 2026-10-08 | Expause's primary signal after Video Intelligence shuts down (D29) | **Cloud Vision** (SafeSearch + label detection), confirmed by a shadow run. scenewise stays the second opinion (U1). |
| U9 | 2026-10-08 | Soft delete on Expause's default upload bucket (D33) | **Keep the 7-day default**, documented as a recovery window. (The transcoder bucket requirement in q1 is unaffected.) |
| U10 | 2026-10-08 | Uncalibrated labels into Expause `contentTags` (D25) | **No: calibrate first.** Uncalibrated labels are stored for shadow comparison only; one `scenewise calibrate` run is part of the Expause integration. |
| U11 | 2026-10-08 | Ruff line length (D1) | **88.** |
| U12 | 2026-10-08 | Expause videos in scope (D32) | **User posts only** (feed/profile videos through `app_transcoding`). Chat and community later. |

## Orchestrator defaults (the research's recommended option; the user may override)

Taken 2026-10-08 from `open-decisions.md` where the research gave a recommendation or the choice is technical and reversible.

| D | Decision |
|---|---|
| D2 | Rename `WriteConflict` → `WriteConflictError` (ruff N818). |
| D3 | Pillow is a base dependency (the image reader is always needed). |
| D4 | Heavy-adapter coverage: omitted from the PR gate, reported in the models job. GCS contract tests run against an in-memory fake; fake-gcs-server is a later option. |
| D5 | CODEOWNERS owner: `@firu-daniel`. |
| D6 | One `.pre-commit-config.yaml`, runnable with `pre-commit` or `prek`. |
| D7 | Add an `input_unavailable` input-error code. |
| D8 | Logs never contain transcript text or signed URIs; a test enforces it. |
| D9 | JobRecord carries `schema_version`, `scenewise_version` and an optional `external_ref`. |
| D10 | v1: HLS manifests only (no DASH); frame sampling by file list and interval (no `scene`). |
| D11 | Vision runs in-process; measure GIL contention before considering a subprocess. |
| D12 | No cu126 image; faster-whisper runs on CPU. |
| D13 | Self-hosted auth outside GCP: a reverse proxy in front, not in-app auth. |
| D14 | Local job store: single-host compare-and-swap; no SQLite mode in v1. |
| D18 | No automatic refusal fallback in v1; log and measure the refusal rate first. |
| D19 | Partial English captions: an absolute minimum (~2 s English speech) only. |
| D20 | ASR runtime: sherpa-onnx primary, onnx-asr tested second. |
| D21 | Windows of unknown language are dropped and flagged. |
| D22 | Music handling waits for test T1 (and a licence check on the AudioSet tagger). |
| D23 | No speech → no VTT; the caption stage reports `skipped / no_speech`. |
| D24 | Nemotron 3.5 Content Safety is dropped as a tier-2 candidate until its licence is clarified. |
| D26 | TranslateGemma not adopted (roadmap item 5 is deferred anyway). |
| D27 | Deferred with roadmap item 5 (pilot decides). |
| D28 | Translate from the source transcript, no English pivot (deferred item). |
| D30, D31 | Caption serving (VTT encryption, sidecar vs HLS SUBTITLES) and backfill of encrypted videos: left to the Expause integration task. |

## Later user decisions

| # | Date | Question | Decision |
|---|---|---|---|
| U13 | 2026-10-08 | Who can bypass code-owner review of gate config when agents open PRs (q8c OQ-A) | **A′:** a ruleset requires code-owner review on gate files. Agent PRs are opened by GitHub Actions (author `github-actions[bot]`), so no extra bot account is needed and the maintainer's approval counts; code-owner review binds on their PRs; the Repository admin role (the maintainer only) may bypass, "for pull requests only", visible in the PR and audit log. |
| U13a | 2026-10-08 | U13 for local harness runs | PRs from **local** harness runs are opened manually by the maintainer, so they are maintainer-authored: a local-run PR that touches gate files cannot merge with the normal button and needs the logged admin bypass. That is intended: the forced bypass is the signal that an agent changed a gate. PRs from harness runs on GitHub Actions are authored by `github-actions[bot]` and get normal code-owner review. |
| U14 | 2026-10-08 | Silent / music-only videos in v1 summaries (q8c OQ-B) | **Speech-only in v1** (transcript ≥ ~40 words). Visual-only summaries with a label-based rule come with roadmap item 4. |
| U15 | 2026-10-08 | Repository location and history | The repository lives at **`~/Work/scenewise`** (moved from `~/scenewise`). Before the first push the history is squashed to **one commit** (or "Initial commit: the scenewise" plus one research-docs commit), with **no Co-Authored-By trailer**. |
