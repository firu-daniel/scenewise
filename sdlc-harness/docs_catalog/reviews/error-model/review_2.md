# Review 2: docs/concepts/error-model.md

verdict: PASS

Mode: catalog. No `existing_doc` was passed, so check 10 does not apply. `phases.parity` is `false`, so check 7 is skipped.

## Review 1 Must Fix: resolved

- Gotchas, "Adapter translation is incomplete", third sub-bullet. It now says that on the push path an exec `OSError` currently always ends the job `FAILED` with `unexpected`. That matches the source:
  - every `probe` / `audio_track` call is in `src/scenewise/app/audio.py` (`acquire_audio`);
  - `src/scenewise/app/runner.py` (`run_job`) enters `acquire_audio` outside `_run_stage`;
  - `src/scenewise/app/delivery.py` (`_run`) catches `Exception` and records `unexpected`;
  - `src/scenewise/app/stages.py` (`audio`) only calls `track.read_bytes()`;
  - `FfmpegMediaTool.video_frames` has no caller under `src`.
  The stage case is now described as future only, which is correct.

## Re-verified this round (no action)

- Hierarchy table against `src/scenewise/domain/errors.py`: every alias, code, category and keyword-only constructor matches, and so does `_init`. The table's statuses match `src/scenewise/service/http/problems.py` (`_STATUSES`, `http_status`, `UNPROCESSABLE_CONTENT`).
- `problem_title`, `problem_response` (`math.ceil` Retry-After), `mapping.problem` (`detail or code`, `about:blank`), `rejection_json` and `_rejected` (200, `JSON_MEDIA_TYPE`) all match.
- Push-path table: matches `src/scenewise/service/http/push.py` (`read_body`, `push`, `_admitted`, `RETRY_AFTER_BUSY_S`) and `src/scenewise/app/contract/envelope.py` (`parse`).
- Delivery and attempt failure: matches `src/scenewise/app/delivery.py` (`_run`, `_attempt`, `_release`, `_finish`, `_give_up`). Conflict-first matches `src/scenewise/domain/jobs.py` (`decide_attempt`). `retry_wait` matches (`wire_status`).
- Stage containment: matches `_run_stage`, `remaining`, `_stage_fields` (`retryable=False`), `ErrorInfoV1` (no `configuration`), `ProblemV1` and `job_state`.
- GET mapping: matches `src/scenewise/service/http/routes.py` (`get_job`, `RETRY_AFTER_STORAGE_S`).
- Start-up and CLI: matches `_stores`, `build_dependencies`, `find_binaries`, the `create_app` lifespan, and `analyse` / `main` with exit codes 1 and 2.
- Adapter origins: `LocalBlobStore._path`, `materialise`, `read` and `write`; `FfmpegMediaTool._media`, `probe` and `video_frames`; `_media_info`; `_run`; `PillowImageReader.read`. All correct.
- "Declared but not raised yet": none of the eight codes is quoted anywhere under `src` outside `domain/errors.py`.
- Anchors: every cited path exists, and every sampled symbol resolves in its cited file, including all four test functions. The cited headings resolve: `domain.md` / `conventions.md` `## Errors`, `adapters.md` `## Not determined`, and `ARCHITECTURE.md` §9 "**HTTP.**".
- Line-number detectors: both return zero hits.

## Should Fix (does not affect the verdict)

- None.
