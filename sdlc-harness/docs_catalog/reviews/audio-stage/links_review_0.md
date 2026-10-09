# Review — audio-stage (links_review_0)

doc: docs/features/audio-stage.md · mode: catalog · iteration: 0
verdict: PASS

## What changed (git diff -- docs/features/audio-stage.md)
Only `## Related` changed. Nothing else in the document moved.
- Removed: `[[job-delivery]]`, `[[artifact-publishing]]`, `[[input-blob-store]]`, `[[media-tool-port]]`, `[[captions-stage]]`. None of these exists in the corpus or the catalog checklist.
- Added: `[[job-lifecycle-and-timing]]`, `[[job-results-and-artifacts]]`, `[[storage-and-uri-policy]]`, `[[media-processing]]`, plus one plain-text line about the captions stage.

## Cross-link resolution
- `[[job-lifecycle-and-timing]]` -> docs/concepts/job-lifecycle-and-timing.md. It exists and covers `handle_delivery`, `_run`, attempts and leases, so it replaces `job-delivery`.
- `[[job-results-and-artifacts]]` -> docs/features/job-results-and-artifacts.md. It exists and covers `result.json` / `audio.wav` under `{prefix}/a{attempt}/`, `attempt_prefix` and `artifacts_prefix`, so it replaces `artifact-publishing`.
- `[[storage-and-uri-policy]]` -> docs/concepts/storage-and-uri-policy.md. It exists and covers `LocalBlobStore`, `materialise`, the separate input and output stores and `local_roots`, so it replaces `input-blob-store`.
- `[[media-processing]]` -> docs/concepts/media-processing.md. It exists and covers the `MediaTool` port, `FfmpegMediaTool`, `audio_track` and `PROBE_TIMEOUT_S`, so it replaces `media-tool-port`.

## Replacement plain text (captions)
- "needs this track": verified. `src/scenewise/domain/plan.py` (`PREREQUISITES`) maps `StageName.CAPTIONS: Needs.AUDIO`.
- "has no document yet": verified. The catalog checklist has no captions entry, and no captions doc exists under docs/features or docs/concepts.
- "it is not wired": verified. `src/scenewise/domain/jobs.py` (`StageName`) docstring says AUDIO is "the skeleton's one wired stage". `src/scenewise/app/runner.py` (`_dispatch`) raises `invariant_violation` for any other stage.
- Both anchors resolve: each path exists and each symbol is found by grep in its file.

## Whole-document mechanical checks
- Every `path` (`symbol`) anchor and bare path in the document resolves: each path exists and each named symbol is found by grep in the cited file.
- Line-number detectors: one hit, `-map 0:a:0`. It is an ffmpeg stream specifier, which is a value and not a line coordinate, so it stays. The colon-less detector had no hits.

## Must Fix
None.

## Optional (not blocking)
- docs/concepts/stages-and-outcomes.md exists and owns `PREREQUISITES`, `SkipReason`, `_run_stage` and `job_state`, all of which this document relies on (skip vs failure, `succeeded` vs `partial`). Adding `[[stages-and-outcomes]]` to Related would be a natural link. Leaving it out is not a factual error.
