# Review 1: docs/features/job-submission.md

- mode: catalog
- iteration: 1
- verdict: FAIL (one factual error. Everything else checks out against the source.)

## Must Fix

1. **Validation summary content is misstated.**
   - Claim (`## Technical implementation` → `### app`, the `mapping.py` bullet): "A validation summary carries field paths only and never input values (`_validation_summary`)."
   - Contradicted by: `src/scenewise/app/contract/mapping.py` (`_validation_summary`). It joins `f"{loc}: {e['msg']}"` for each error, so the summary holds the field path **and** pydantic's message. It calls `errors(include_input=False, include_url=False)`, which is why input values never appear. Its own docstring reads "Field paths and messages only".
   - Correction: "A validation summary carries field paths and validation messages, never input values (`_validation_summary`)."

## Should Fix (do not block)

2. **The anchor list leaves out files the prose relies on.** The prose cites `src/scenewise/domain/results.py` (`job_state`), which decides `succeeded` vs `partial`, and `src/scenewise/app/deps.py` (`Dependencies`), which holds the store and the always-`None` notifier. Neither is in `## Anchor files`. Add both. `tests/e2e/test_isolation.py` is also cited as end-to-end coverage but has no anchor entry.
3. **"This is the only caller of `handle_delivery`"** (`## Invoked from`) is true of production code only. `tests/unit/test_delivery.py` also calls it. Say "the only production caller".

## Verified (no action)

- Every anchor path exists, and every named symbol resolves in its cited file: `post_job`, `_state`, `push`, `read_body`, `_admitted`, `_rejected`, `_log_context`, `_TASK_HEADERS`, `_STATUSES`, `http_status`, `problem_title`, `problem_response`, `ServiceState`, `create_app`, `Watchdog`, `ServiceSettings`, `_timing`, `lease_s`, `_default_state_prefix`, `_stores`, `handle_delivery`, `_attempt`, `_run`, `_finish`, `_release`, `_give_up`, `artifacts_prefix`, `job_prefix`, `record_uri`, `RETRY_AFTER_CONFLICT`, `publish`, `attempt_prefix`, `run_job`, `parse`, `request_digest`, `JobRequestV1`, `JobRecordV1`, `JobStatusV1`, `RejectionV1`, `ProblemV1`, `to_domain`, `rejection_json`, `decide_attempt`, `job_id`, `JOB_ID_PATTERN`, `wire_status`, `ScenewiseError`, `MediaTooLargeCode`, `BlobStore`, `ABSENT_GENERATION`, `WriteConflictError`, `LocalBlobStore`, and `analyse` in `src/scenewise/service/cli.py`. Every named test function exists in `tests/e2e/test_http.py`.
- Line-number check: there are no coordinates. The colon detector found nothing. The shape detector matched only values: the setting defaults 1500, 120 and 1800, and the HTTP statuses 413/422/429/503.
- The answer table matches `push`, `_admitted`, `handle_delivery` and `problems._STATUSES`. That covers 413 by content-length or by stream, 422 from `envelope.parse` returning `None`, 429 with `Retry-After: 30` (`RETRY_AFTER_BUSY_S`), 503 `job_in_progress` with the lease remainder (rounded up with `math.ceil`), 503 with 30 s on a conflict or a release, a 200 `RejectionV1` for a conflict (409 in the body), and a 200 `RejectionV1` for `invariant_violation` or `unexpected`.
- Attempt state machine, claim, fencing, release, give-up, terminal write, and `uri_not_allowed` for a state-prefix `uri_prefix`: all match `delivery.py` and `jobs.py`.
- Request, record, status and problem shapes match `requests.py`, `records.py` and `results.py`.
- Settings defaults, the lease formula and the timing invariant match `config.py`. The lifespan wiring matches `app.py`.
- Things described as not yet built are confirmed. `notifier` is never set by `build_dependencies`. `supersedes` is not mapped by `to_domain`. `exceeds_push_budget` appears only in the `MediaTooLargeCode` literal.
- Stored-data provenance is confirmed. Records are written only in `delivery.py` and read only by `handle_delivery` and `job_status`. Artifacts are written only by `publish`. The CLI writes no record.
- `reachable? ✅` for `POST /v1/jobs` is correct. Its caller is the route itself, and the e2e tests exercise it.
- `docs/skeleton-notes.md` A9 and `ARCHITECTURE.md` §7 say what the document attributes to them.
- Research depth is adequate. The trace follows the data from the route through delivery, the stores and publish, and covers record provenance.
- Parity (check 7) is skipped because `phases.parity` is false. No `existing_doc` was passed, so the merge check does not apply.
