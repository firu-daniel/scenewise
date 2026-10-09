# Job Submission (POST /v1/jobs)

> One-line: a caller (normally a Cloud Tasks queue) pushes one JSON job, and the request runs it to a terminal state and answers with the job's status.

## Business behaviour
- **Synchronous push target.** `POST /v1/jobs` does the work inside the request and answers when the job is terminal. Cloud Tasks is the queue and owns retries and backoff. Any non-2xx answer makes the queue deliver the same body again, so the response codes decide whether a retry happens (`ARCHITECTURE.md` §7; `src/scenewise/service/http/problems.py` module docstring).
- **Idempotent per `job_id`.** One durable record per `job_id`. A re-delivery of the same body after the job is terminal gets the stored status back and does not run again. The same `job_id` with a *different* body is a `job_id_conflict`. A retry of a terminal job has to use a new `job_id` (`src/scenewise/domain/jobs.py` `decide_attempt`; `ARCHITECTURE.md` §7).
- **Bounded attempts.** Each delivery that claims the job is one attempt, numbered from 1. A retryable failure releases the claim so a later delivery can try again. After `service.max_attempts` (default 5) the job ends `failed` / `attempts_exhausted` (`src/scenewise/app/delivery.py` `_attempt`, `_give_up`; `src/scenewise/service/config.py` `ServiceSettings`).
- **Flows and answers.** "Problem" means an RFC 9457 `application/problem+json` body (`src/scenewise/service/http/push.py` `push`, `_admitted`, `_rejected`):

  | Situation | Answer |
  |---|---|
  | Body over `service.max_body_bytes` (default 1 MiB), by `content-length` or while streaming | **413** problem `request_too_large`. No record is written. |
  | Body is not a JSON object, or has no valid `job_id` | **422** problem `invalid_request`. No record can be keyed, so the queue keeps retrying. |
  | Every job slot is busy (`service.max_jobs`, default 1) | **429** problem `capacity_exceeded`, `Retry-After: 30` |
  | Another attempt holds a live lease | **503** problem `job_in_progress`, `Retry-After` = the seconds left on that lease |
  | A lost compare-and-swap race, or a retryable error that released the attempt | **503** problem, `Retry-After: 30` |
  | A `RetryableError` raised out of the delivery, e.g. `storage_unavailable` | **503** problem, `Retry-After: 30` |
  | Job terminal (`succeeded`, `partial` or `failed`), now or from an earlier delivery | **200** + `JobStatusV1` |
  | Same `job_id`, different body | **200** + `RejectionV1` carrying `job_id_conflict` (status 409 inside the body). No record is written. |
  | Any other error once a `job_id` is keyed, e.g. an unreadable record (`invariant_violation`) or an unexpected exception | **200** + `RejectionV1`, so the queue stops redelivering |

- **Request validation runs inside the claim.** A body that keys a record but fails `JobRequestV1` validation (unknown field, bad stage name, missing `delivery`) ends as a terminal `failed` / `invalid_request` record and gets a 200, not a 422 (`src/scenewise/app/delivery.py` `_run`; `src/scenewise/app/contract/mapping.py` `to_domain`).
- **Job outcome.** If no stage failed the record is `succeeded`. If at least one stage failed it is `partial`, and a skipped stage does not count as a failure. An error before the stages, such as a requested stage this deployment does not offer (`stage_unavailable`), makes the record `failed` (`src/scenewise/domain/results.py` `job_state`; `src/scenewise/app/runner.py` `run_job`).
- **Not yet built.** The callback after the terminal record (`notify`) is not implemented, because `Dependencies.notifier` is always `None`. The request field `supersedes` is validated and then ignored, since `to_domain` does not map it. `exceeds_push_budget` exists as an error code but nothing raises it (`src/scenewise/app/deps.py` `Dependencies`; `src/scenewise/app/contract/requests.py` `JobRequestV1`; `src/scenewise/domain/errors.py` `MediaTooLargeCode`).

## Invoked from
- `POST /v1/jobs` on the FastAPI app (`src/scenewise/service/http/routes.py` `post_job`). This is the only production path to `handle_delivery`, through `push._admitted`; `tests/unit/test_delivery.py` also calls it directly. The CLI `analyse` command calls `run_job` directly and keeps no record (`src/scenewise/service/cli.py` `analyse`).
- In production the caller is a Cloud Tasks HTTP task. `README.md` shows a direct `curl` for local use.

## Technical implementation
### domain
- `src/scenewise/domain/jobs.py` (`job_id`, `JOB_ID_PATTERN`): a job id matches `^[A-Za-z0-9._:-]{1,200}$` and is not `.` or `..`, so it is safe to use as a path segment.
- `src/scenewise/domain/jobs.py` (`decide_attempt`): the pure state machine. With no record → `Start(1)`. Digest differs → `Conflict`. State not `RUNNING` → `AlreadyDone`. Lease still live → `InProgress(retry_after=lease_until-now)`. Attempts left → `Start(n+1)`. Otherwise `GiveUp`.
- `src/scenewise/domain/jobs.py` (`JobRecord`, `JobState`, `AttemptInfo`, `wire_status`): the record, its stored states `running|succeeded|partial|failed`, and the wire mapping. A `running` record whose lease has expired reads as `retry_wait`.
- `src/scenewise/domain/errors.py` (`ScenewiseError` and its leaves): the closed set of error codes and categories. The HTTP status of each answer comes from these classes.
### app
- `src/scenewise/app/delivery.py` (`handle_delivery`): reads the record, matches on `decide_attempt`, and returns `DeliveryOutcome = Finished | Rejected | TryLater`. When no record exists it calls `_attempt(…, FIRST_ATTEMPT, generation=ABSENT_GENERATION)` directly, without `decide_attempt` (`docs/skeleton-notes.md` A9).
- `src/scenewise/app/delivery.py` (`_attempt`): **claim**. Writes `RUNNING{attempt, lease_until=now+lease, request_digest, external_ref}` with `if_generation=<read generation>`. The returned generation is the attempt's fencing token.
- `src/scenewise/app/delivery.py` (`_run`): parse (`mapping.to_domain`) → `run_job` with `deadline = monotonic + attempt_budget` → `publish`. A `RetryableError` propagates. Any other error gives a terminal `FAILED` record with that error's code (`unexpected` for a non-`ScenewiseError`).
- `src/scenewise/app/delivery.py` (`_finish`, `_release`, `_give_up`): the record writes that end a delivery. `_finish` writes the terminal record under the claim token. `_give_up` writes the terminal `failed` / `attempts_exhausted` record under the generation read from the store (no claim exists on that path). On a `WriteConflictError` either one answers `TryLater(job_in_progress, 30 s)` (`RETRY_AFTER_CONFLICT`). `_release` handles a retryable error that still has attempts left: it writes the released `running` record with `lease_until=now` under the token, so the record reads `retry_wait`. It answers `TryLater` with the original retryable error (for example `storage_unavailable`) and `RETRY_AFTER_CONFLICT`, whether or not that write conflicts; a conflict is only logged as `attempt_superseded`.
- `src/scenewise/app/delivery.py` (`artifacts_prefix`, `job_prefix`, `record_uri`): the path rules (see the stored data below). A `uri_prefix` at or under the state prefix is `InputError(code="uri_not_allowed")`, which makes the job `failed`.
- `src/scenewise/app/publish.py` (`publish`, `attempt_prefix`): writes `audio.wav`, if one was produced, and `result.json` under `{prefix}/a{attempt}/`, then returns the `result_uri`. It never touches the record.
- `src/scenewise/app/runner.py` (`run_job`): runs the requested stages. Only `audio` is wired today. See [[audio-stage]].
- `src/scenewise/app/contract/envelope.py` (`parse`, `request_digest`): a lenient pre-parse of `job_id`, `schema_version` and `external_ref`. A non-`str→str` `external_ref` becomes `None` here and is not an error. `request_digest` is the sha256 of `json.dumps(document, sort_keys=True, separators=(",", ":"))`.
- `src/scenewise/app/contract/requests.py` (`JobRequestV1`): the strict body. Every input model is `extra="forbid"`.
  ```
  { schema_version: "1", job_id: str (JOB_ID_PATTERN), supersedes?: str,
    external_ref?: {str: str}, stages: [audio|captions|summary|chapters|moderation|labels] (min 1),
    audio?: {kind:"file", uri, mime?} | {kind:"none", reason?:"source_has_no_audio"},
    delivery: { notify?: {kind:"none"}, artifacts?: {uri_prefix?: str} } }
  ```
- `src/scenewise/app/contract/mapping.py` (`to_domain`, `record_to_json`, `record_from_json`, `status_json`, `rejection_json`, `problem`): converts between the wire models and the domain types. A validation summary carries field paths and validation messages, never input values (`_validation_summary`).
- `src/scenewise/app/contract/results.py` (`JobStatusV1`, `RejectionV1`, `ProblemV1`): the response bodies.
  ```
  JobStatusV1  { schema_version:"1", scenewise_version, job_id, status: running|retry_wait|succeeded|partial|failed,
                 attempt, error_code, result_uri, updated_at, external_ref }
  RejectionV1  { job_id, outcome:"rejected", problem: ProblemV1 }
  ProblemV1    { type:"about:blank", title, status, detail, code, category, retryable }
  ```
### adapters
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the only `BlobStore` so far, and `file://` only. It keeps each object's generation in a sidecar `.name.meta.json`. A `write` with an `if_generation` that does not match raises `WriteConflictError`. An OS failure is `RetryableError(code="storage_unavailable")`. A URI outside its roots is `InputError(code="uri_not_allowed")`.
### service
- `src/scenewise/service/http/routes.py` (`post_job`, `_state`): a thin route that delegates to `push.push` with the `ServiceState`.
- `src/scenewise/service/http/push.py` (`push`): `read_body` with the byte limit, `envelopes.parse`, binding the Cloud Tasks headers to the log context (`_log_context`, `_TASK_HEADERS`), `limiter.acquire_nowait()` (429 on `WouldBlock`), then `_admitted`, and `limiter.release()` in `finally`.
- `src/scenewise/service/http/push.py` (`_admitted`): registers the job with `watchdog.watch(job_id)`, builds `AttemptInfo(now, lease=service.lease_s, max_attempts)`, runs `handle_delivery` through `anyio.to_thread.run_sync`, and maps the outcome. `Finished` → 200 body. `Rejected` → `_rejected`. `TryLater` → `problem_response` with its `retry_after`.
- `src/scenewise/service/http/push.py` (`_rejected`): answers 200 with `mapping.rejection_json`. The status inside the body comes from `problems.http_status`.
- `src/scenewise/service/http/problems.py` (`_STATUSES`, `http_status`, `problem_title`, `problem_response`): maps each error to its status: `CapacityError` 429, `RetryableError` 503, `MediaTooLargeError` 413, `UnsupportedMediaError` 415, `JobIdConflictError` 409, `JobNotFoundError` 404, `InputError` 422, anything else 500. `Retry-After` is rounded up to whole seconds.
- `src/scenewise/service/http/state.py` (`ServiceState`) and `src/scenewise/service/http/app.py` (`create_app`): the lifespan builds `deps`, `DeliveryPolicy(state_prefix, attempt_budget)`, `anyio.CapacityLimiter(max_jobs)` and `Watchdog(limit_s=attempt_budget_s + watchdog_grace_s)` once per process.
- `src/scenewise/service/http/health.py` (`Watchdog`): while a submitted job runs past budget + grace, `/healthz` returns 503 so the platform replaces the instance.
- `src/scenewise/service/config.py` (`ServiceSettings`): `max_jobs`, `max_body_bytes`, `attempt_budget_s` (1500), `watchdog_grace_s` (120), `dispatch_deadline_s` (1800), `lease_margin_s` (120), `max_attempts`, `state_prefix`, `artifact_roots`. The lease is `lease_s = dispatch_deadline_s + lease_margin_s`. `_timing` rejects any configuration where budget + grace + probe window ≥ `dispatch_deadline_s`.
- `src/scenewise/service/bootstrap.py` (`_stores`): builds the output store (records and artifacts) over the state prefix plus `artifact_roots`. The input store is separate and excludes those roots. Any scheme other than `file://` is `ConfigurationError(code="store_unavailable")`.
### package
- `src/scenewise/ports.py` (`BlobStore`, `Blob`, `ABSENT_GENERATION`, `WriteConflictError`): the compare-and-swap contract every record write relies on. `if_generation=0` means "write only if absent".
- **Stored data** (in the output `BlobStore`; `src/scenewise/app/delivery.py` owns every record write):
  - The record `{state_prefix}/{job_id}/status.json`, built by `record_uri` as `JobRecordV1`:
    ```
    { schema_version:"1", scenewise_version, job_id, state: running|succeeded|partial|failed,
      attempt (>=1), lease_until, request_digest, error_code, result_uri, updated_at, external_ref|null }
    ```
  - The artifacts `{artifacts_prefix}/a{attempt}/audio.wav` and `…/result.json` (`JobResultV1`). `artifacts_prefix` is `{state_prefix}/{job_id}`, or `{uri_prefix}/{job_id}` when the request sets one. Attempt-scoped folders mean a fenced-out attempt can never overwrite the files the terminal `result_uri` names.
  - Provenance: the record is written only by `handle_delivery` (claim, release, terminal, give-up). Its readers are this flow and `job_status` (`GET /v1/jobs/{id}`, see [[job-status]]). Artifacts are written only by `publish`.
- `ServiceSettings.state_prefix` defaults to `./.scenewise/state` as a `file://` URI (`src/scenewise/service/config.py` `_default_state_prefix`).
### tests
- `tests/e2e/test_http.py`: the full push path, through `TestClient` over generated media. It covers duplicate delivery, `test_unreadable_record` (a 200 rejection), `test_streamed_body_over_the_limit_is_413`, `test_full_admission_is_429`, `test_live_lease_is_503` and `test_storage_down_is_503`.
- `tests/e2e/test_isolation.py`: `uri_prefix` isolation between jobs and the state prefix.
- `tests/unit/test_delivery.py`, `tests/unit/test_jobs.py`, `tests/unit/test_envelope.py`, `tests/unit/test_mapping.py`, `tests/unit/test_publish.py`: the delivery protocol, `decide_attempt`, envelope parsing and digest, the wire mapping, and attempt paths.
- `tests/unit/test_service.py`: the watchdog and the settings timing.
### general
- `ARCHITECTURE.md` §7 is the design of record for the lifecycle and the answer table. `docs/skeleton-notes.md` A9 records the departure where a delivery with no record skips `decide_attempt`, and where a lost terminal write answers 503 rather than re-reading the record.

### Backend surface
- **`POST /v1/jobs`**: `JobRequestV1` JSON → `JobStatusV1` (200), `RejectionV1` (200), or a `ProblemV1` (413/422/429/503). Side effects: writes the record and the attempt artifacts. **reachable? ✅**. It is the service's own public entry point, and it is exercised end to end in `tests/e2e/test_http.py` and `tests/e2e/test_isolation.py`.

## Anchor files
- `src/scenewise/service/http/routes.py` (`post_job`): the route
- `src/scenewise/service/http/push.py` (`push`): body limit, envelope, admission, threading and outcome mapping
- `src/scenewise/service/http/problems.py` (`http_status`): status mapping and problem rendering
- `src/scenewise/service/http/state.py` (`ServiceState`): limiter, watchdog, policy, deps
- `src/scenewise/service/http/app.py` (`create_app`): the lifespan that builds the state
- `src/scenewise/service/http/health.py` (`Watchdog`): hung-job liveness
- `src/scenewise/service/config.py` (`ServiceSettings`): limits, lease and timing
- `src/scenewise/service/bootstrap.py` (`_stores`): the output and input stores
- `src/scenewise/app/delivery.py` (`handle_delivery`): the delivery protocol and every record write
- `src/scenewise/app/publish.py` (`publish`): attempt artifacts
- `src/scenewise/app/runner.py` (`run_job`): runs the stages
- `src/scenewise/app/contract/envelope.py` (`parse`): lenient envelope and request digest
- `src/scenewise/app/contract/requests.py` (`JobRequestV1`): request body
- `src/scenewise/app/contract/records.py` (`JobRecordV1`): stored record
- `src/scenewise/app/contract/results.py` (`JobStatusV1`): response bodies
- `src/scenewise/app/contract/mapping.py` (`rejection_json`): wire ↔ domain
- `src/scenewise/domain/jobs.py` (`decide_attempt`): attempt state machine, job id, record
- `src/scenewise/domain/errors.py` (`ScenewiseError`): error codes and categories
- `src/scenewise/domain/results.py` (`job_state`): `succeeded` vs `partial` from the stage outcomes
- `src/scenewise/app/deps.py` (`Dependencies`): the store and the always-`None` notifier
- `src/scenewise/ports.py` (`BlobStore`): compare-and-swap storage contract
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the `file://` store
- `tests/e2e/test_http.py`: end-to-end push-path tests
- `tests/e2e/test_isolation.py`: `uri_prefix` and state-prefix isolation tests
- `tests/unit/test_delivery.py`: delivery protocol unit tests

## Related
- [[job-status]] · [[audio-stage]] · [[job-lifecycle-and-timing]] · [[error-model]] · [[configuration]]
