# Review 1: docs/concepts/error-model.md

verdict: FAIL

Mode: catalog. No `existing_doc` was passed, so check 10 does not apply. `phases.parity` is `false`, so check 7 is skipped.

## Must Fix

1. **Gotchas, "Adapter translation is incomplete", third sub-bullet ("On the push path it becomes `Failed("unexpected")` inside a stage ...").**
   - Claim: an `OSError` from executing ffmpeg can land inside a stage and become `Failed("unexpected")` through `_run_stage`.
   - Contradicted by: no stage calls the `MediaTool` today. `src/scenewise/app/runner.py` (`_dispatch`) routes only `StageName.AUDIO` to `_audio_stage`, and `src/scenewise/app/stages.py` (`audio`) only does `track.read_bytes()` on a track that already exists. Every ffmpeg/ffprobe call (`probe`, `audio_track`) runs in `src/scenewise/app/audio.py` (`acquire_audio`). `run_job` enters that context manager outside `_run_stage`, so an exec `OSError` there escapes `run_job`. `_run` then ends the job `FAILED` with `unexpected` (`src/scenewise/app/delivery.py` (`_run`)). `FfmpegMediaTool.video_frames` is not called from any module under `src`.
   - Correction: say that on the push path an exec `OSError` currently always ends the job `FAILED` with `unexpected`, because every ffmpeg call happens during acquisition (`acquire_audio`, inside `run_job` and outside `_run_stage`). If you want to keep the stage case, mark it as future: a stage that calls the media tool would contain the error as `Failed("unexpected")`. Do not describe it as a path that exists now.

## Verified (no action)

- Hierarchy table: every class, category, code alias and code matches `src/scenewise/domain/errors.py`, and every status matches `src/scenewise/service/http/problems.py` (`_STATUSES`, `http_status`). The 422 literal and its 3.13 comment are correct.
- `problem_title`, `problem_response` (`Retry-After` uses `math.ceil`), `mapping.problem` body shape, and `rejection_json` with `_rejected` (200, `JSON_MEDIA_TYPE`) are all correct.
- Push-path table: every row matches `src/scenewise/service/http/push.py` (`read_body`, `push`, `_admitted`) and `src/scenewise/app/contract/envelope.py` (`parse`).
- Delivery: release, `attempts_exhausted`, `_give_up`, `WriteConflictError` to `TryLater(job_in_progress)` and the `_release` logging all match `src/scenewise/app/delivery.py` and `src/scenewise/domain/jobs.py` (`decide_attempt`). The "final write leaves RUNNING" gotcha is correct: `WriteConflictError` is not an `OSError`, and `_finish` catches only that error.
- Stage containment, `remaining` / `deadline_exceeded`, `_stage_fields` / `ErrorInfoV1` and `job_state` partial: all correct.
- GET mapping (`RETRY_AFTER_STORAGE_S` = 5, 404 on `None`): correct.
- Start-up `ConfigurationError` sources (`find_binaries`, `_stores`, `build_dependencies`), lifespan propagation, and CLI exit codes 1/2 including settings validation: correct.
- Adapter code origins (`LocalBlobStore`, `FfmpegMediaTool`, `_run`, `_media_info`, `PillowImageReader`, `acquire_audio`): correct.
- "Declared but not raised yet": a grep under `src`, excluding `domain/errors.py`, finds no raise of any of the eight listed codes. Confirmed.
- Every cited path exists. The test anchors (`test_categories`, `test_http_status`, `test_problem_and_rejection`, `test_wire_error_categories_mirror_the_domain`) and the convention headings (`domain.md` `## Errors`, `conventions.md` `## Errors`, `adapters.md` `## Not determined`, `ARCHITECTURE.md` §9 "**HTTP.**") resolve.
- Both line-number detectors return zero hits.
