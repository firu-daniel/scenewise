# Job Lifecycle, Leases and Timing Invariants

> One-line: how one durable job record, compare-and-swap writes and a static lease turn repeated Cloud Tasks deliveries of one request into numbered attempts that end in exactly one terminal state, and which time settings keep that safe.

## What it is & why
- scenewise has no database and no background worker. `POST /v1/jobs` is a Cloud Tasks push target that does the work inside the request. The queue owns redelivery and backoff (`ARCHITECTURE.md` §7).
- Every delivery of a request may arrive more than once, overlap with another delivery, or follow a crashed attempt. A per-job **record**, `{state_prefix}/{job_id}/status.json`, makes that safe. It is written only under compare-and-swap (CAS) preconditions on the store's generation. A **lease** says how long a running attempt owns the job. The generation the claim write returns is that attempt's **fencing token** (`src/scenewise/app/delivery.py` module docstring).
- The record's attempt counter decides when the job gives up, not the queue. For that reason the caller's queue is expected to run with `maxAttempts: -1` and a `maxRetryDuration` of about 12 h (`ARCHITECTURE.md` §7 "Timing"; this is caller configuration and no code checks it).

## How it works

### The record
- Domain type `src/scenewise/domain/jobs.py` (`JobRecord`). Stored form `src/scenewise/app/contract/records.py` (`JobRecordV1`, `extra="forbid"`), serialised by `src/scenewise/app/contract/mapping.py` (`record_to_json`, `record_from_json`). A record that does not validate is read as `InternalError(code="invariant_violation")`; `src/scenewise/service/http/push.py` (`_admitted`) catches it as a `ScenewiseError` and answers 200 with a rejection body (`_rejected`).
  ```
  schema_version, scenewise_version, job_id,
  state: "running" | "succeeded" | "partial" | "failed"   # JobState
  attempt: int >= 1                                       # FIRST_ATTEMPT = 1
  lease_until: float   # epoch seconds (time.time())
  request_digest: str  # hash of the canonical request body
  error_code: str | None, result_uri: str | None
  updated_at: float    # epoch seconds
  external_ref: {str: str} | None
  ```
- Its path comes from `src/scenewise/app/delivery.py` (`record_uri`, `job_prefix`, `RECORD_FILE_NAME`). Every write of the record goes through `delivery.py` (`_Delivery.write`), and every one of them passes `if_generation`.

### CAS on the store
- `src/scenewise/ports.py` (`BlobStore`): `read` returns a `Blob(data, generation)` or `None`. `write` returns the new generation, which is always > 0. `if_generation=ABSENT_GENERATION` (0) means create-if-absent, and any other value means "only if this is still the current generation". A failed precondition raises `WriteConflictError`.
- The local implementation is `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`). It keeps the generation in a sidecar `.name.meta.json`, serialises writers with `flock` on `.name.lock`, and replaces files atomically. It writes the generation before the data ("Generation first: a crash in between leaves a stale token unusable."). A file placed by hand with no sidecar reads as generation 1 (`_HAND_PLACED_GENERATION`). It is single-host only (D14).

### The pure decision: `decide_attempt`
`src/scenewise/domain/jobs.py` (`decide_attempt`, `AttemptInfo`, `Decision`) takes the stored record, the delivery's digest and `AttemptInfo(now, lease, max_attempts)`, and checks in this order:
1. No record → `Start(attempt=1)`.
2. Different `request_digest` → `Conflict`.
3. State is not `RUNNING` → `AlreadyDone(record)`.
4. `lease_until > now` → `InProgress(retry_after=lease_until - now)`. A lease that ends exactly at `now` counts as expired (`tests/unit/test_jobs.py` `test_lease_boundary`).
5. `attempt < max_attempts` → `Start(attempt + 1)`.
6. Otherwise → `GiveUp(attempt)`.

### One delivery: `handle_delivery`
`src/scenewise/app/delivery.py` (`handle_delivery`) runs in a worker thread, called from `src/scenewise/service/http/push.py` (`_admitted`). `_admitted` builds `AttemptInfo` once at admission, with `now=time.time()`, `lease=service.lease_s` and `max_attempts=service.max_attempts`.
1. **Read** the record and its generation `g0`. If there is no record, the code calls `_attempt(1, generation=ABSENT_GENERATION)` directly and does not go through `decide_attempt`, although the result is the same (`docs/skeleton-notes.md` A9).
2. **Decide**, then branch:
   - `AlreadyDone` → `Finished`, with the stored status. Nothing is written.
   - `InProgress` → `TryLater(job_in_progress, retry_after=lease remainder)`.
   - `Conflict` → `Rejected(JobIdConflictError)`. Nothing is written, and the event is logged at ERROR.
   - `GiveUp` → `_give_up`.
   - `Start(n)` → `_attempt`.
3. **Claim** (`_attempt`): write `RUNNING{attempt=n, lease_until=now+lease, error_code=None, result_uri=None}` with `if_generation=g0`. The returned generation is the **token**. A `WriteConflictError` means another delivery won the claim, and the answer is `TryLater(job_in_progress, 30 s)` (`RETRY_AFTER_CONFLICT`).
4. **Run** (`_run`): parse the full request (`mapping.to_domain`). Set `deadline = time.monotonic() + attempt_budget`. Call `run_job`, then `publish` under the attempt folder `{artifacts_prefix}/a{n}/` (`src/scenewise/app/publish.py` `attempt_prefix`).
   - A `RetryableError` propagates out of `_run`.
   - Any other `ScenewiseError` becomes a terminal `FAILED` with its code. Any other exception becomes `FAILED` / `unexpected`.
   - Success gives `SUCCEEDED` or `PARTIAL` (`src/scenewise/domain/results.py` `job_state`), with `result_uri` set.
5. **Retryable failure**:
   - If `n < max_attempts`, `_release` rewrites the claim with `lease_until = AttemptInfo.now` and `if_generation=token`, so the record reads `retry_wait` from then on. It answers `TryLater(error, 30 s)`. If the release itself loses a CAS race, the conflict is only logged. A storage error on the release is not caught (see Gotchas).
   - On the last attempt, the job ends `FAILED` / `attempts_exhausted` straight away.
6. **Terminal write** (`_finish`): write the final record with `if_generation=token`. On success → `Finished`. On a `WriteConflictError`, a later attempt took over after this attempt's lease expired. The answer is then `TryLater(job_in_progress, 30 s)`, and this attempt's `a{n}/` artifacts are never referenced. `docs/skeleton-notes.md` A9 records the intended behaviour as re-reading the record and answering as step 2 would; the code answers 503 `job_in_progress` instead. `ARCHITECTURE.md` §7 step 7 says only that these artifacts are never referenced.
7. **Give up** (`_give_up`): write `FAILED` / `attempts_exhausted` with `if_generation=g0`. A conflict → `TryLater(job_in_progress, 30 s)`, and the next delivery decides again.
- `push.py` (`_admitted`) maps the outcomes to HTTP: `Finished` → 200, `Rejected` → 200 + rejection body, and `TryLater` → problem with `Retry-After`. `job_in_progress` and the other `RetryableError` codes map to 503. `CapacityError` (`capacity_exceeded`) is the exception and maps to 429 (`src/scenewise/service/http/problems.py` `_STATUSES`, first match wins). [[job-submission]] has the full table.

### What callers see: `wire_status`
`src/scenewise/domain/jobs.py` (`wire_status`): a `RUNNING` record whose lease is still live is `running`. If the lease has expired the record shows as `retry_wait`, until the next delivery claims it again or gives up. Terminal states map one-to-one. `GET /v1/jobs/{job}` exposes this through `mapping.status_json` ([[job-status]]).

### Timing invariants
`src/scenewise/service/config.py` (`ServiceSettings`) sets the defaults and enforces the invariant at settings construction (`_timing`):

| Setting | Default | Role |
|---|---|---|
| `attempt_budget_s` | 1500 | Monotonic deadline given to `run_job` (`DeliveryPolicy.attempt_budget`) |
| `watchdog_grace_s` | 120 | `/healthz` fails once a job thread passes budget + grace (`Watchdog(limit_s=…)` in `src/scenewise/service/http/app.py` `create_app`) |
| `probe_period_s` × `probe_failure_threshold` | 10 × 3 | The probe window before the platform kills a hung instance |
| `dispatch_deadline_s` | 1800 | Must match the queue's `dispatchDeadline` (no check in code) |
| `lease_margin_s` | 120 | Added on top of the dispatch deadline |
| `max_attempts` | 5 | Attempt counter ceiling (`docs/skeleton-notes.md` A7) |

- **Invariant:** `attempt_budget_s + watchdog_grace_s + probe_period_s * probe_failure_threshold < dispatch_deadline_s`. With the defaults that is 1650 < 1800. A violation is a `ValueError` naming `dispatch_deadline_s` (`tests/unit/test_service.py` `test_timing_invariant`).
- **Lease:** `lease_s = dispatch_deadline_s + lease_margin_s`, which is 1920 by default. It is static, with no heartbeat.
- **Order of events:** the budget is hit (1500 s). Then the watchdog reports the job thread (1620 s) and the probe kills the instance (about 1650 s). Then Cloud Tasks gives up on the request (1800 s). Only after that does the lease expire (1920 s). So a hung attempt is gone before another attempt can take over. Where there is no probe, the fencing token still prevents a stale terminal write (`ARCHITECTURE.md` §8).
- **Deadline checks:**
  - `src/scenewise/app/runner.py` (`remaining`) raises `InternalError(code="deadline_exceeded")` between stages in `run_job`. That error escapes `run_job` and ends the job `FAILED`.
  - ffmpeg calls get `timeout = deadline - now`, and any timeout raises `deadline_exceeded` (`src/scenewise/adapters/media/ffmpeg.py` `_run`). That error fails the job when it comes from audio acquisition, which runs before the stages. It fails only that stage when it is raised inside a stage (`runner.py` `_run_stage`).

## Where it's used
- [[job-submission]]: the only writer of the record, through `handle_delivery`.
- [[job-status]]: reads the record and renders `wire_status`.
- [[job-results-and-artifacts]]: `a{attempt}/` folders and the terminal record's `result_uri` name the winning attempt.
- [[health-probes]]: the watchdog that enforces the budget + grace bound.
- [[cli-analyse]]: uses `attempt_budget_s` as its deadline but writes no record, holds no lease and always reports attempt 1 (`src/scenewise/service/cli.py` `analyse`).

## Gotchas / constraints
- **Two clocks.** Leases and `updated_at` use the wall clock (`time.time()`). The attempt deadline and the watchdog use `time.monotonic()`. On a shared store, clock skew between instances shifts lease expiry.
- **`now` is fixed at admission.** The claim's `lease_until` and the released `lease_until` both come from `AttemptInfo.now`, not from the time of the write. A released record is therefore already expired, and the next delivery can claim it immediately.
- **A storage error on the terminal write is not a conflict.** `_finish` catches only `WriteConflictError`. A `RetryableError` such as `storage_unavailable` escapes to `push._admitted`, which answers 503 with `Retry-After: 30`. The record stays `RUNNING` under its live lease, so later deliveries get `job_in_progress` until the lease (1920 s by default) expires. The release write (`_release`) has the same exposure: it catches only `WriteConflictError`, so a storage error there also leaves the live claim in place. A storage error on the claim write or in `_give_up` escapes the same way, as a 503 with `Retry-After: 30`. But in those two cases the stored record is already absent or expired, so the next delivery decides again at once.
- **Retry-After values.** `InProgress` returns the lease remainder, which can be up to `lease_s`. Lost races and released attempts use a fixed 30 s.
- **A retry of a terminal job needs a new `job_id`.** Re-delivering the same body returns the stored status, and a changed body is `job_id_conflict`.
- **Not built yet:**
  - The best-effort notify after the terminal write is not built. `delivery.py` never calls a notifier (A8).
  - The upfront cost check that `ARCHITECTURE.md` §7 describes (rejected up front with `exceeds_push_budget`) does not exist. The code is declared in `src/scenewise/domain/errors.py` (`MediaTooLargeCode`) and nothing raises it.
  - Deadline checks between frame batches and speech-model calls arrive with those stages.
- **`MediaTool.probe` ignores the deadline.** It runs under `PROBE_TIMEOUT_S` (60 s) in `ffmpeg.py`, which can overrun the budget by up to 60 s. That still fits inside the 120 s watchdog grace (`docs/skeleton-notes.md` review r1 finding 14).

## Anchor files
- `src/scenewise/domain/jobs.py` (`decide_attempt`): `JobRecord`, `JobState`, `AttemptInfo`, the `Decision` variants, `wire_status`
- `src/scenewise/app/delivery.py` (`handle_delivery`): claim, release, finish and give-up, all of them CAS writes; `RETRY_AFTER_CONFLICT`, `record_uri`
- `src/scenewise/app/runner.py` (`remaining`): the between-stages deadline check
- `src/scenewise/ports.py` (`BlobStore`): the CAS contract, `ABSENT_GENERATION`, `WriteConflictError`, `Blob`
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the single-host generation and lock implementation
- `src/scenewise/app/contract/records.py` (`JobRecordV1`): the stored record schema
- `src/scenewise/app/contract/mapping.py` (`record_to_json`): record (de)serialisation and `status_json`
- `src/scenewise/service/config.py` (`ServiceSettings`): timing defaults, `_timing`, `lease_s`
- `src/scenewise/service/http/push.py` (`_admitted`): builds `AttemptInfo`, runs the delivery in a thread, maps outcomes to HTTP
- `src/scenewise/service/http/health.py` (`Watchdog`): the budget + grace liveness bound
- `src/scenewise/service/http/app.py` (`create_app`): wires `DeliveryPolicy` and the watchdog limit
- `src/scenewise/adapters/media/ffmpeg.py` (`_run`): the subprocess timeout taken from the deadline
- `tests/unit/test_jobs.py`, `tests/unit/test_delivery.py`, `tests/unit/test_service.py` (`test_timing_invariant`): tests that pin this behaviour
- `ARCHITECTURE.md` §7–§8 and `docs/skeleton-notes.md` A7–A9: the design of record and where the code departs from it

## Related
- [[job-submission]] · [[job-status]] · [[job-results-and-artifacts]] · [[health-probes]] · [[cli-analyse]] · [[storage-and-uri-policy]] · [[error-model]] · [[configuration]] · [[wire-contract]]
