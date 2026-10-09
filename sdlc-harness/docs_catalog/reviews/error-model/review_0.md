# Review 0: docs/concepts/error-model.md

verdict: FAIL

Mode: catalog. No `existing_doc`. `phases.parity` is false, so check 7 does not apply.

What I checked: the class table against `src/scenewise/domain/errors.py`, which matches every alias and code. `_STATUSES` order and statuses, `problem_title`, `problem_response`, `rejection_json`, `_rejected`. Every row of the push-path table against `push`, `read_body` and `_admitted`. `_run`, `_attempt`, `_release`, `_finish` and `_give_up` in delivery. `_run_stage`, `remaining` and `run_job` in runner. `get_job` and `RETRY_AFTER_STORAGE_S`. `_stores`, `build_dependencies`, `find_binaries`, CLI `analyse`/`main` and `create_app`'s lifespan. `decide_attempt`, `wire_status`, `Failed` and `job_state`. The three test symbols, `ARCHITECTURE.md` §9 "**HTTP.**", `## Errors` in domain.md and conventions.md, and `## Not determined` in adapters.md. All of these are accurate.

The "declared but not raised" list is confirmed: none of the eight codes is raised anywhere under `src` outside `errors.py`.

Line-coordinate detectors: both found nothing. There are no coordinates in the document.

## Must Fix

1. **The `LocalBlobStore` code origins name the wrong methods** ("Where codes originate in adapters").
   - Claim: `uri_not_allowed`, `input_unavailable` and `storage_unavailable` come from (`LocalBlobStore.read`, `LocalBlobStore.write`).
   - Contradicted by `src/scenewise/adapters/storage/local.py`:
     - `input_unavailable` is raised only by `LocalBlobStore.materialise` ("no such file").
     - `LocalBlobStore.read` returns `None` for a missing file. It never raises `input_unavailable`.
     - `uri_not_allowed` is raised by `LocalBlobStore._path`, which all three methods call.
     - `src/scenewise/ports.py` (`BlobStore`) states the same: "a missing input in ``materialise`` is ``InputError(code="input_unavailable")``".
   - Correction: `uri_not_allowed` from `LocalBlobStore._path` (every access), `input_unavailable` from `LocalBlobStore.materialise`, and `storage_unavailable` with `detail=type(e).__name__` from `LocalBlobStore.read` / `LocalBlobStore.write`. Update the anchor to (`LocalBlobStore._path`, `LocalBlobStore.materialise`, `LocalBlobStore.read`, `LocalBlobStore.write`).

2. **The `FfmpegMediaTool` `corrupt_media` origin is credited to the wrong function, and its detail is stated too narrowly.**
   - Claim: "`corrupt_media` (the detail is the stderr tail) and `deadline_exceeded` (`_run`, `FfmpegMediaTool.probe`)".
   - Contradicted by `src/scenewise/adapters/media/ffmpeg.py`:
     - `_run` raises only `InternalError(code="deadline_exceeded")`: with no detail when the timeout is already spent, and with detail = binary name on `subprocess.TimeoutExpired`.
     - The stderr-tail `corrupt_media` is raised by `FfmpegMediaTool._media` on a non-zero exit.
     - Other `corrupt_media` raises carry fixed details: "unreadable probe" (`FfmpegMediaTool.probe`), "no duration" (`_media_info`), and "no video stream" / "no frame at …" in the frame path.
   - Correction: "`corrupt_media`. The detail is the stderr tail on a non-zero exit (`FfmpegMediaTool._media`), or a fixed reason such as `unreadable probe` / `no duration` (`FfmpegMediaTool.probe`, `_media_info`). `deadline_exceeded` comes from `_run`, with the binary name as detail on a timeout."

3. **"An `OSError` from exec ... ends up as `unexpected`" is true only on the push path** (Gotchas, "Adapter translation is incomplete").
   - An `OSError` escaping `_run` does not always end as `unexpected`:
     - At start-up it escapes `find_binaries` → `build_dependencies` untranslated (`src/scenewise/service/bootstrap.py` (`build_dependencies`)).
     - In the CLI it escapes `analyse`, which catches only `ScenewiseError`, and `main`, which catches only `ValidationError`. The result is a traceback, not an exit code of 1 or 2 (`src/scenewise/service/cli.py` (`analyse`, `main`)).
     - On the push path it becomes `Failed("unexpected")` inside a stage (`_run_stage`), or a job `FAILED` with `unexpected` during acquisition (`src/scenewise/app/delivery.py` (`_run`)).
   - Correction: state those three outcomes instead of the single "ends up as `unexpected`".

## Should Fix (does not affect the verdict)

- Gotchas: the claim "stage errors always report `retryable: false`" is cited to `ErrorInfoV1`. That value is set in `src/scenewise/app/contract/mapping.py` (`_stage_fields`), not in the model. `ErrorInfoV1` only declares `retryable: bool`. Cite `_stage_fields` for that half.
- "Keyed input errors are not problem bodies on POST" cites the `RejectionV1` docstring. That docstring names only `job_id_conflict`. The "errors escaping before or around the claim" half is supported by `src/scenewise/service/http/push.py` (`_admitted`), so cite that as well.
