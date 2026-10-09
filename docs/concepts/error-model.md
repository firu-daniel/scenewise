# Error Model and HTTP Mapping

> One-line: the closed set of error categories and codes that scenewise raises, and the single place, the `service` layer, that turns each one into an HTTP status, a problem body, a failed stage, a failed job record or a CLI exit code.

## What it is & why

- Every error scenewise raises on purpose is a `ScenewiseError` with a machine-readable `code` (what a caller acts on) and a human-readable `detail` (`src/scenewise/domain/errors.py` (`ScenewiseError`)). Anything else that escapes is wrapped into `InternalError(code="unexpected")` at the boundary that catches it.
- There are four **categories**: `input`, `retryable`, `internal` and `configuration` (`src/scenewise/domain/errors.py` (`Category`)). `retryable` is derived from the category alone (`ScenewiseError.retryable`).
- Codes are a **closed vocabulary**. Each class has one `Literal` alias, and its constructor accepts only that alias, so mypy rejects a misspelt code or a code raised through the wrong class. The code strings reach the wire unchanged (`ProblemV1.code`, `ErrorInfoV1.code`, the job record's `error_code`), so renaming a code changes the wire contract (`src/scenewise/domain/errors.py` module docstring).
- Leaf classes exist only where the HTTP status differs. A new code that maps to the same status as an existing class goes into that class's alias. It does not get a new class (`.claude/context/domain.md` `## Errors`; `.claude/context/conventions.md` `## Errors`).
- Use cases in `app` only **report** an error. Only `service` picks a status (`ARCHITECTURE.md` §9 "**HTTP.**"; `src/scenewise/app/delivery.py` (`Rejected`)).

## How it works

### The hierarchy and its codes

| Class | Category | Code alias → codes | HTTP status (`http_status`) |
|---|---|---|---|
| `ScenewiseError` (bare) | internal | `InternalCode`, default `internal` | 500 |
| `InputError` | input | `InputCode`: `invalid_request`, `uri_not_allowed`, `input_unavailable`, `corrupt_media`, `invalid_sprite_grid`, `input_encrypted`, `stage_unavailable` | 422 |
| ↳ `MediaTooLargeError` | input | `MediaTooLargeCode`: `media_too_large`, `exceeds_push_budget`, `request_too_large` | 413 |
| ↳ `UnsupportedMediaError` | input | `UnsupportedMediaCode`: `unsupported_media`, `manifest_unsupported` | 415 |
| ↳ `JobIdConflictError` | input | `JobIdConflictCode`: `job_id_conflict` (fixed; takes `detail` only) | 409 |
| ↳ `JobNotFoundError` | input | `JobNotFoundCode`: `job_not_found` (fixed; takes `detail` only) | 404 |
| `RetryableError` | retryable | `RetryableCode`: `backend_unavailable`, `storage_unavailable`, `job_in_progress` | 503 |
| ↳ `CapacityError` | retryable | `CapacityCode`: `capacity_exceeded` | 429 |
| `InternalError` | internal | `InternalCode`: `internal`, `model_output_invalid`, `model_refused`, `resource_exhausted`, `deadline_exceeded`, `invariant_violation`, `attempts_exhausted`, `unexpected` | 500 |
| `ConfigurationError` | configuration | `ConfigurationCode`: `stage_unavailable`, `store_unavailable`, `ffmpeg_unavailable`, `ffmpeg_too_old` | 500 (never reaches HTTP; start-up only) |

- Every constructor is keyword-only and passes its arguments to the private `ScenewiseError._init`, which sets `code`, `detail` and the exception message `"{code}: {detail}"`, or just `code` when there is no detail (`src/scenewise/domain/errors.py` (`ScenewiseError._init`)).
- `stage_unavailable` appears in two aliases. As an `InputError` it means the request asked for a stage this deployment does not offer (`src/scenewise/app/runner.py` (`run_job`)). As a `ConfigurationError` it means a `required_stages` entry has no back end (`src/scenewise/service/bootstrap.py` (`build_dependencies`)).

### Status selection and the problem body

- `http_status` walks `_STATUSES` in order and returns the status of the first class the error is an instance of. Leaves are listed before their parents. When nothing matches, the status is 500 (`src/scenewise/service/http/problems.py` (`http_status`, `_STATUSES`)). The status 422 is the literal `UNPROCESSABLE_CONTENT`, because the `HTTPStatus` member exists only from Python 3.13.
- `problem_title` returns `"Job id already used"` for `JobIdConflictError`. For every other error it returns the reason phrase of the status (`problem_title`).
- `mapping.problem` builds `ProblemV1` (`src/scenewise/app/contract/mapping.py` (`problem`); `src/scenewise/app/contract/results.py` (`ProblemV1`)):

  ```
  { "type": "about:blank", "title", "status", "detail": error.detail or error.code,
    "code", "category", "retryable" }
  ```

- `problem_response` renders that body as `application/problem+json` (`PROBLEM_JSON`) with the chosen status. When a `retry_after` is given, it adds a `Retry-After` header holding the value rounded up to whole seconds (`src/scenewise/service/http/problems.py` (`problem_response`)).
- `mapping.rejection_json` wraps the same problem in `RejectionV1` `{job_id, outcome: "rejected", problem}`, which is sent with HTTP **200** and `JSON_MEDIA_TYPE`, not problem+json (`src/scenewise/app/contract/mapping.py` (`rejection_json`); `src/scenewise/service/http/push.py` (`_rejected`)). The status inside `problem.status` is still what `http_status` chose.

### `POST /v1/jobs` (the push path)

Cloud Tasks retries every non-2xx response. For that reason, every non-retryable failure that can be tied to a job id is answered **200**, and only retryable conditions get a non-2xx status (`src/scenewise/service/http/problems.py` module docstring; `src/scenewise/service/http/push.py` (`push`, `_admitted`)).

| Situation | Error | Answer |
|---|---|---|
| Body over `max_body_bytes` (checked against `content-length` and then while streaming) | `MediaTooLargeError("request_too_large")` | 413 problem (`read_body`, `push`) |
| Body not a JSON object, or no valid `job_id` (`envelope.parse` returns `None`) | `InputError("invalid_request", "no usable job_id")` | 422 problem (`push`) |
| Admission limiter full | `CapacityError("capacity_exceeded")` | 429 problem, `Retry-After: 30` (`RETRY_AFTER_BUSY_S`) |
| Delivery returns `TryLater` (lease held by another delivery, lost compare-and-swap, released attempt) | the `RetryableError` it carries (`job_in_progress`, or the released error) | 503 problem, `Retry-After` = `retry_after` (`_admitted`) |
| `RetryableError` escapes `handle_delivery` (for example `storage_unavailable` while reading or writing the record) | as raised | 503 problem, `Retry-After: 30` (`_admitted`) |
| Delivery returns `Rejected` (same job id, different request digest) | `JobIdConflictError` | 200 `RejectionV1`, inner status 409 (`_admitted`, `_rejected`) |
| Another `ScenewiseError` escapes (for example an unreadable record → `invariant_violation`) | as raised | 200 `RejectionV1`, inner status from `http_status` (`_admitted`) |
| Any other exception escapes | `InternalError("unexpected")` | 200 `RejectionV1`, inner status 500 (`_admitted`) |
| The job reached a terminal state, failures included | none on the wire | 200 `JobStatusV1`, with `status: "failed"` and `error_code` when it failed (`Finished`) |

### Inside the delivery: job failure versus attempt failure

`src/scenewise/app/delivery.py` (`_run`) parses, runs and publishes inside one `try`:

- A `RetryableError` is re-raised. `_attempt` then **releases** the lease (`_release` writes `lease_until=now`, which `GET` reports as `retry_wait`) and answers `TryLater` while `attempt < max_attempts`. On the last attempt the record ends `FAILED` with `attempts_exhausted` (`_attempt`). A delivery that finds a lapsed lease on its final attempt also writes `attempts_exhausted` (`_give_up`).
- Any other `ScenewiseError` ends the job `FAILED` with `error_code=e.code` (`_terminal`). This covers `invalid_request` from `mapping.to_domain`, `stage_unavailable`, `uri_not_allowed` from `artifacts_prefix`, and acquisition errors such as `corrupt_media` or `unsupported_media`.
- Any other exception ends the job `FAILED` with `"unexpected"`, so a deterministic bug does not use up retries.
- A `WriteConflictError` on a record write is never retried in-process. It becomes `TryLater(job_in_progress)` (`_attempt`, `_finish`, `_give_up`). In `_release` it is logged, and the error being released is still carried.

### Inside a stage: stage failure only

`src/scenewise/app/runner.py` (`_run_stage`) contains errors to one stage:

- `RetryableError` → re-raised, so the whole attempt fails as described above.
- Any other `ScenewiseError` → `Failed(error_code=e.code, category=…)`. The category is `"input"` for an `InputError` and `"internal"` for everything else, including a `ConfigurationError`.
- A plain `ValueError` (a domain invariant) → `Failed("invariant_violation", "internal", detail=str(e))`.
- Any other exception → `Failed("unexpected", "internal")`, logged with `log.exception`.
- The deadline is checked between stages. `remaining` raises `InternalError("deadline_exceeded")`, which happens outside `_run_stage` and therefore fails the whole job (`src/scenewise/app/runner.py` (`remaining`, `run_job`)).
- `Failed` reaches `result.json` through `mapping._stage_fields`: stage `status: "failed"`, `reason` = the code, and `error` = `ErrorInfoV1{code, category, retryable: false, message: detail or code, stage}` (`src/scenewise/app/contract/mapping.py` (`_stage_fields`)). Any failed stage makes the job `partial` (`src/scenewise/domain/results.py` (`job_state`)).

### `GET /v1/jobs/{job}`

`src/scenewise/service/http/routes.py` (`get_job`):

- `RetryableError` → 503 problem, `Retry-After: 5` (`RETRY_AFTER_STORAGE_S`).
- Another `ScenewiseError` (an unreadable record) → problem with its mapped status, so 500 for `invariant_violation`. The comment says "never bare 500".
- Any other exception → 500 problem with `unexpected`.
- No record, or a string that is not a valid job id (`job_status` returns `None`) → `JobNotFoundError` → 404 problem.

### Start-up and the CLI

- `ConfigurationError` is raised only while dependencies are being built: `find_binaries` (`ffmpeg_unavailable`, `ffmpeg_too_old`), `_stores` (`store_unavailable` for a non-`file://` state prefix) and `build_dependencies` (`stage_unavailable`) (`src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`); `src/scenewise/service/bootstrap.py` (`_stores`, `build_dependencies`)). In the HTTP service this runs inside the lifespan, so the error propagates out of `create_app`'s lifespan and the app never starts serving (`src/scenewise/service/http/app.py` (`create_app`)).
- CLI `analyse`: a `ScenewiseError` from building dependencies or from `run_job` is printed to stderr as `scenewise: {code}: {detail}`. The exit code is `EXIT_CONFIGURATION` (2) for a `ConfigurationError` and `EXIT_FAILED` (1) for anything else. Settings that fail validation also exit 2 (`src/scenewise/service/cli.py` (`analyse`, `main`)).

### Where codes originate in adapters

- `LocalBlobStore` (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`, `LocalBlobStore.materialise`, `LocalBlobStore.read`, `LocalBlobStore.write`)):
  - `uri_not_allowed` comes from `LocalBlobStore._path`, which every access calls. It is raised for a non-`file://` URI and for a path outside the allowed roots or inside an excluded one.
  - `input_unavailable` ("no such file") comes only from `LocalBlobStore.materialise`. `LocalBlobStore.read` returns `None` for a missing file and does not raise.
  - `storage_unavailable` with `detail=type(e).__name__` comes from `LocalBlobStore.read` and `LocalBlobStore.write`.
- `FfmpegMediaTool` (`src/scenewise/adapters/media/ffmpeg.py` (`_run`, `FfmpegMediaTool._media`, `FfmpegMediaTool.probe`, `_media_info`, `FfmpegMediaTool.video_frames`)):
  - `corrupt_media` carries the stderr tail as its detail on a non-zero exit (`FfmpegMediaTool._media`). Otherwise it carries a fixed reason: `unreadable probe` (`FfmpegMediaTool.probe`), `no duration` (`_media_info`), and `no video stream` or `no frame at …` (`FfmpegMediaTool.video_frames`).
  - `deadline_exceeded` comes from `_run`. It has no detail when the timeout is already spent, and the binary name as its detail on `subprocess.TimeoutExpired`.
- `PillowImageReader`: `corrupt_media` and `invalid_sprite_grid` (`src/scenewise/adapters/media/images.py` (`PillowImageReader.read`)).
- `acquire_audio`: `unsupported_media` for segment lists and manifests (`src/scenewise/app/audio.py` (`acquire_audio`)).

## Where it's used

- [[job-submission]]: the push path and its 200-versus-retry rule.
- [[job-status]]: the GET problem mapping and the 404.
- [[stages-and-outcomes]]: `Failed` outcomes and `partial` jobs.
- [[job-lifecycle-and-timing]]: release, `retry_wait` and `attempts_exhausted`.
- [[job-results-and-artifacts]]: `ErrorInfoV1` in `result.json`.
- [[cli-analyse]]: exit codes.
- [[configuration]] and [[media-processing]]: start-up `ConfigurationError`s.
- [[storage-and-uri-policy]]: `uri_not_allowed`, `input_unavailable` and `storage_unavailable`.

## Gotchas / constraints

- **`detail` must stay free of secrets.** It must never contain transcript text or signed URIs. Validation errors are summarised as field paths and messages only (`include_input=False, include_url=False`), and storage errors carry only the exception type name (`src/scenewise/domain/errors.py` module docstring; `src/scenewise/app/contract/mapping.py` (`_validation_summary`)). See [[logging]].
- **Pre-envelope errors on the push path are non-2xx.** A 413 for an oversized body and a 422 for an unkeyable body cannot be tied to a record, so they are answered with a non-2xx status even though they are not retryable. Cloud Tasks will redeliver them (`src/scenewise/service/http/push.py` (`push`)).
- **Keyed input errors are not problem bodies on POST.** After the claim, `invalid_request` and similar errors become a `FAILED` record, and the response is a 200 `JobStatusV1` with `error_code`. Only `job_id_conflict` and errors escaping before or around the claim produce `RejectionV1` (`src/scenewise/app/contract/results.py` (`RejectionV1`); `src/scenewise/service/http/push.py` (`_admitted`)).
- **Conflict is checked first.** `decide_attempt` compares the request digest before it looks at the record state. A reused job id is rejected even when the earlier job has already finished (`src/scenewise/domain/jobs.py` (`decide_attempt`)).
- **A storage failure on the final record write leaves the job `RUNNING`.** `_finish` catches only `WriteConflictError`, so a `RetryableError` raised by that write is answered 503. The record keeps the claim's lease until it expires, and then `decide_attempt` starts the next attempt or gives up (`src/scenewise/app/delivery.py` (`_finish`)).
- **`ErrorInfoV1.category` excludes `configuration`** (`src/scenewise/app/contract/results.py` (`ErrorInfoV1`)), and stage errors always report `retryable: false` (`src/scenewise/app/contract/mapping.py` (`_stage_fields`)). `ProblemV1.category` includes all four, and a unit test keeps it equal to the domain `Category` (`tests/unit/test_mapping.py` (`test_wire_error_categories_mirror_the_domain`)).
- **Adapter translation is incomplete.** `ffmpeg._run` catches only `subprocess.TimeoutExpired`, so an `OSError` from exec escapes untranslated (`.claude/context/adapters.md` `## Not determined`). Where it lands depends on the caller:
  - At start-up it escapes `find_binaries` and `build_dependencies` untranslated (`src/scenewise/service/bootstrap.py` (`build_dependencies`)).
  - In the CLI it is not caught: `analyse` catches only `ScenewiseError` and `main` catches only `ValidationError`, so the result is a traceback rather than exit code 1 or 2 (`src/scenewise/service/cli.py` (`analyse`, `main`)).
  - On the push path it currently always ends the job `FAILED` with `unexpected` (`src/scenewise/app/delivery.py` (`_run`)). Every ffmpeg and ffprobe call (`probe`, `audio_track`) happens during acquisition, in `src/scenewise/app/audio.py` (`acquire_audio`), which `run_job` enters outside `_run_stage` (`src/scenewise/app/runner.py` (`run_job`)). No stage calls the media tool today, and `FfmpegMediaTool.video_frames` has no caller under `src`. A future stage that calls the media tool would contain the error as `Failed("unexpected")` through `_run_stage`.
- **Declared but not raised yet.** No module under `src` raises `backend_unavailable`, `model_output_invalid`, `model_refused`, `resource_exhausted`, `media_too_large`, `exceeds_push_budget`, `manifest_unsupported` or `input_encrypted`. They are reserved for model back ends and input kinds on the roadmap (`ARCHITECTURE.md` §9 names `model_output_invalid` for LLM and model parsing).

## Anchor files

- `src/scenewise/domain/errors.py` (`ScenewiseError`): the hierarchy, categories and code aliases.
- `src/scenewise/service/http/problems.py` (`http_status`, `problem_title`, `problem_response`): error → status, title and problem+json response.
- `src/scenewise/service/http/push.py` (`push`, `_admitted`, `_rejected`, `read_body`): push-path mapping and the 200 rejection.
- `src/scenewise/service/http/routes.py` (`get_job`): GET mapping and the 404.
- `src/scenewise/app/contract/mapping.py` (`problem`, `rejection_json`, `_stage_fields`, `to_domain`, `record_from_json`): wire bodies and boundary translation.
- `src/scenewise/app/contract/results.py` (`ProblemV1`, `RejectionV1`, `ErrorInfoV1`): wire shapes.
- `src/scenewise/app/delivery.py` (`_run`, `_attempt`, `_release`, `_finish`, `_give_up`, `Rejected`, `TryLater`): job-level and attempt-level failure.
- `src/scenewise/app/runner.py` (`_run_stage`, `remaining`, `run_job`): stage-level containment.
- `src/scenewise/domain/results.py` (`Failed`): the stage failure value.
- `src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`): start-up `ConfigurationError`s.
- `src/scenewise/service/cli.py` (`analyse`, `main`, `EXIT_CONFIGURATION`): CLI exit codes.
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`), `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool`, `_run`, `find_binaries`): adapter-side code origins.
- `ARCHITECTURE.md`: §9, the design statement.
- `tests/unit/test_errors.py` (`test_categories`), `tests/unit/test_service.py` (`test_http_status`), `tests/unit/test_mapping.py` (`test_problem_and_rejection`): pinned behaviour.

## Related

- [[wire-contract]] · [[job-lifecycle-and-timing]] · [[stages-and-outcomes]] · [[job-submission]] · [[job-status]] · [[logging]] · [[layering-and-ports]]
