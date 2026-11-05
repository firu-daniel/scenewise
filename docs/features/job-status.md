# Job Status (GET /v1/jobs/{job})

> Lets a caller read where a job stands: running, waiting for a retry, or finished with a `result_uri`. The answer comes from the job's durable record.

## Business behaviour
- **One read-only endpoint.** `GET /v1/jobs/{job}` reads the job record at `{state_prefix}/{job}/status.json` and returns it as a `JobStatusV1` document. It never writes. A GET for an unknown job leaves the state directory untouched (`tests/e2e/test_http.py` `test_get_of_an_unknown_job_writes_nothing`).
- **It is the source of truth for reconciliation.** Callbacks are best-effort, and a caller reconciles against this record (`ARCHITECTURE.md` §7, "Callbacks are best-effort"). The documented reconciliation reading is: a terminal status means ingest it, `running` / `retry_wait` means wait, and 404 means scenewise never got the job, so re-enqueue it (`docs/research/q8a-architecture-layout.md` §6.2, "Reconciliation is mandatory").
- **Wire statuses** (`src/scenewise/domain/jobs.py` `wire_status`). The current time is passed in as `now`, a `time.time()` taken by the route:
  - stored `running` with `lease_until > now` → `running` (an attempt holds a live lease);
  - stored `running` with `lease_until <= now` → `retry_wait` (the attempt released its claim or crashed, and nothing runs until the next delivery). `retry_wait` exists only on the wire and is never stored;
  - `succeeded`, `partial`, `failed` → passed through unchanged. `failed` carries `error_code`, for example `attempts_exhausted` (`src/scenewise/app/delivery.py` `_give_up`).
- **Responses as the caller sees them** (`src/scenewise/service/http/routes.py` `get_job`):
  - **200** `application/json`: the `JobStatusV1` body;
  - **404** problem `job_not_found`: the id fails the job-id pattern (for example `a b`, `..`) or no record exists (`tests/e2e/test_http.py` `test_unknown_job_is_404`);
  - **503** problem with `Retry-After: 5`: the store raised a `RetryableError` (for example `storage_unavailable`). This is `RETRY_AFTER_STORAGE_S` = 5.0, rounded up by `problem_response`;
  - **500** problem `invariant_violation`: the record exists but does not parse as `JobRecordV1` (`tests/e2e/test_http.py` `test_unreadable_record`);
  - any other `ScenewiseError`: a problem at the status `http_status` maps it to. An unexpected exception becomes a 500 problem with code `unexpected`, never a bare 500.
- **No admission gate.** `get_job` does not touch `ServiceState.limiter`, so a status read is never refused with 429 while jobs are running.
- The same `JobStatusV1` body is also the 200 answer of `POST /v1/jobs` once the job is terminal (`src/scenewise/app/delivery.py` `_Delivery.answer`; `src/scenewise/app/contract/results.py` `JobStatusV1` docstring). See [[job-submission]].

## Invoked from
- External HTTP callers: the adopter's reconciliation job, or an operator with `curl` (`README.md`, `curl -s localhost:8080/v1/jobs/demo-1`).
- Nothing inside the package calls the route. The CLI (`src/scenewise/service/cli.py`) keeps no job record, so it has no status command.
- Tests: `tests/e2e/test_http.py`, through FastAPI's `TestClient`.

## Technical implementation
### domain
- `src/scenewise/domain/jobs.py` (`job_id`): checks the path segment against `JOB_ID_PATTERN` (`^[A-Za-z0-9._:-]{1,200}$`), rejects `.` and `..`, and raises `ValueError` on failure.
- `src/scenewise/domain/jobs.py` (`JobRecord`, `JobState`): the domain record. Its stored states are `running`, `succeeded`, `partial` and `failed`.
- `src/scenewise/domain/jobs.py` (`wire_status`, `WireStatus`): the pure mapping from stored state to wire status, including the `retry_wait` rule. `now` is passed in as an argument, never read inside the function (`.claude/context/domain.md`).
- `src/scenewise/domain/errors.py` (`JobNotFoundError`, `RetryableError`, `InternalError`): the error classes this feature raises or handles.

### app
- `src/scenewise/app/delivery.py` (`job_status`): the use case. An invalid id returns `None`. Otherwise it calls `store.read(record_uri(...))`; an absent blob returns `None`, and a present one returns `mapping.status_json(mapping.record_from_json(blob.data), now)`. A store failure propagates unchanged.
- `src/scenewise/app/delivery.py` (`record_uri`, `job_prefix`, `RECORD_FILE_NAME`): the record's URI, `{state_prefix without its trailing "/"}/{job}/status.json`. The delivery writer uses the same helper (`_Delivery.uri`), so readers and writers always agree on the path.
- `src/scenewise/app/contract/mapping.py` (`record_from_json`): validates `status.json` against `JobRecordV1`. A `ValidationError` becomes `InternalError(code="invariant_violation", detail="unreadable job record")`.
- `src/scenewise/app/contract/mapping.py` (`status_json`): builds `JobStatusV1` from the record and `wire_status(record, now)`, and returns bytes.
- Stored record shape, `status.json` (`src/scenewise/app/contract/records.py` `JobRecordV1`, `extra="forbid"`):
  ```
  schema_version: "1"   scenewise_version: str   job_id: str (JOB_ID_PATTERN)
  state: running|succeeded|partial|failed   attempt: int >= 1   lease_until: float (epoch s)
  request_digest: str   error_code: str|null   result_uri: str|null
  updated_at: float (epoch s)   external_ref: {str: str}|null
  ```
- Response shape (`src/scenewise/app/contract/results.py` `JobStatusV1`, `StatusV1`):
  ```
  schema_version: "1"   scenewise_version   job_id
  status: running|retry_wait|succeeded|partial|failed
  attempt   error_code|null   result_uri|null   updated_at   external_ref|null
  ```
  `lease_until` and `request_digest` stay internal and are not sent. Clients must ignore unknown fields, because later stages add fields within `schema_version` "1" (`src/scenewise/app/contract/results.py` module docstring).
- **Provenance: who writes what this reads.** `src/scenewise/app/delivery.py` makes every write of the record, always under `if_generation` compare-and-swap:
  - `_attempt` writes the `running` claim, with `lease_until = now + lease`;
  - `_release` sets `lease_until = now`, which is what makes the GET return `retry_wait`;
  - `_finish` and `_give_up` write the terminal record. On success `result_uri` names the winning attempt's `result.json`, written earlier by `src/scenewise/app/publish.py` (`publish`).

  This feature only reads the record, and the writers are described in [[job-submission]] and [[job-lifecycle-and-timing]].

### adapters
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.read`): the only store wired today, and only for `file://` state prefixes. It returns `None` when the path is not a regular file, without creating directories or lock files. Otherwise it reads under an exclusive `flock`. An `OSError` becomes `RetryableError(code="storage_unavailable")`, and a URI outside the allow-list is `InputError(code="uri_not_allowed")`.
- Any other state-prefix scheme fails at start-up with `store_unavailable` (`src/scenewise/service/bootstrap.py` `_stores`). The GCS store is not built yet.

### service
- `src/scenewise/service/http/routes.py` (`get_job`): a sync handler on `router`. It reads `ServiceState` through `_state`, calls `job_status` with `state.deps.store` and `state.settings.service.state_prefix`, and maps the outcome to HTTP. A `RetryableError` goes to `problem_response(e, retry_after=RETRY_AFTER_STORAGE_S)`. Any other `ScenewiseError` is logged as `status_unreadable` at warning and rendered as a problem. Any other exception is logged with `log.exception` and returned as `InternalError(code="unexpected")`. A `None` result becomes `JobNotFoundError(detail="no such job")`.
- `src/scenewise/service/http/problems.py` (`problem_response`, `http_status`, `_STATUSES`): renders RFC 9457 `application/problem+json` with `code`, `category` and `retryable`. The status mapping is `JobNotFoundError` → 404, `RetryableError` → 503, and a fallback of 500 for internal errors.
- `src/scenewise/service/http/app.py` (`create_app`): includes `router` and builds `ServiceState` in the lifespan. `src/scenewise/service/config.py` (`ServiceSettings.state_prefix`, `_default_state_prefix`) defaults the state prefix to `file://{cwd}/.scenewise/state`, and `SCENEWISE_SERVICE__STATE_PREFIX` overrides it.

### package
- `src/scenewise/ports.py` (`BlobStore.read`, `Blob`): by contract, reading an absent object returns `None`. A `Blob` carries `data` and `generation`; the status read ignores `generation`.

### tests
- `tests/unit/test_jobs.py` (`test_wire_status`): the `running` / `retry_wait` split and the terminal pass-through.
- `tests/unit/test_delivery.py`: `test_job_status_reads_the_record`, `test_job_status_of_no_such_job_is_none` (covers `j-2`, `..` and `not a job id`), `test_unreadable_record_is_an_invariant_violation`, and `test_record_lives_in_status_json_under_the_job_folder`. All run over `InMemoryBlobStore` from `tests/fakes.py`.
- `tests/unit/test_mapping.py`: `test_status_json`, and `test_wire_statuses_mirror_the_domain`, which keeps `StatusV1` equal to `WireStatus`.
- `tests/e2e/test_http.py`: covers 404, writes-nothing, the unreadable record (500 problem), a live lease reading `running` (`test_live_lease_is_503`), and the storage-down setup (`test_storage_down_is_503`).
- `tests/contract/blobstore_contract.py`: the `BlobStore` contract, including reading an absent object.

### general
- `ARCHITECTURE.md` §7 is the design statement of the endpoint and the record layout. `README.md` gives the `curl` example and the record path.

### Backend surface
- **`GET /v1/jobs/{job}`**. Request: the path segment `job`, with no body. Response: `JobStatusV1` JSON, or a problem (404 / 503 + `Retry-After` / 500). Side effects: none, because it only reads. **reachable? ✅** It is registered on `router`, which `create_app` includes, and is exercised by `tests/e2e/test_http.py`.

## Gotchas
- **On the local store, "storage down" usually returns 404, not 503.** `LocalBlobStore.read` checks `is_file()` before it takes the lock. A state prefix that cannot be reached, for example one under a regular file, reads as absent. `test_storage_down_is_503` shows this: the POST is 503, and the GET for the same job is 404. A 503 needs an `OSError` while the store reads a file that exists.
- **`retry_wait` depends on the clock.** The same record reads `running` or `retry_wait` depending on the server's `time.time()` against `lease_until`.
- **Do not build artifact paths from the record.** Follow `result_uri`, because artifacts are scoped by attempt (`README.md`).
- **There is no list, retry or delete endpoint.** A retry of a terminal job is a new `job_id` (`ARCHITECTURE.md` §7).

## Anchor files
- `src/scenewise/service/http/routes.py` (`get_job`, `RETRY_AFTER_STORAGE_S`): the HTTP route and its error mapping
- `src/scenewise/service/http/problems.py` (`problem_response`, `http_status`): problem+json rendering and status mapping
- `src/scenewise/service/http/app.py` (`create_app`): registers the router and builds `ServiceState`
- `src/scenewise/service/http/state.py` (`ServiceState`): holds `deps.store` and `settings`
- `src/scenewise/service/config.py` (`ServiceSettings`): `state_prefix` and its default
- `src/scenewise/service/bootstrap.py` (`_stores`): picks the store for the state-prefix scheme
- `src/scenewise/app/delivery.py` (`job_status`, `record_uri`, `job_prefix`): the use case and the record path; also writes the record
- `src/scenewise/app/contract/mapping.py` (`record_from_json`, `status_json`): parses the record and builds the status document
- `src/scenewise/app/contract/records.py` (`JobRecordV1`): the stored `status.json` schema
- `src/scenewise/app/contract/results.py` (`JobStatusV1`, `StatusV1`): the response schema
- `src/scenewise/app/constants.py` (`JSON_MEDIA_TYPE`, `SCHEMA_VERSION_V1`): media type and schema version
- `src/scenewise/domain/jobs.py` (`job_id`, `JobRecord`, `JobState`, `wire_status`): id validation, the record and the wire-status rule
- `src/scenewise/domain/errors.py` (`JobNotFoundError`): the 404 error class
- `src/scenewise/ports.py` (`BlobStore`): the read contract
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the `file://` store
- `tests/e2e/test_http.py` (`test_unknown_job_is_404`, `test_unreadable_record`): end-to-end behaviour
- `tests/unit/test_delivery.py` (`test_job_status_reads_the_record`): use-case tests
- `tests/unit/test_jobs.py` (`test_wire_status`): wire-status tests

## Related
- [[job-submission]] · [[job-results-and-artifacts]] · [[job-lifecycle-and-timing]] · [[wire-contract]] · [[error-model]] · [[storage-and-uri-policy]] · [[configuration]]
