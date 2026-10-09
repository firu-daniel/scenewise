# Review 2: docs/features/job-submission.md

- mode: catalog
- iteration: 2
- verdict: PASS

## Must Fix

None.

## Earlier findings, re-checked

- Review 1, Must Fix 1 (validation summary): fixed. The `### app` mapping bullet now says "field paths and validation messages, never input values". That matches `src/scenewise/app/contract/mapping.py` (`_validation_summary`), which joins `loc: msg` from `errors(include_input=False, include_url=False)`.
- Review 1, Should Fix 2 (anchor list): fixed. `src/scenewise/domain/results.py` (`job_state`), `src/scenewise/app/deps.py` (`Dependencies`) and `tests/e2e/test_isolation.py` are now in `## Anchor files`.
- Review 1, Should Fix 3: fixed. `## Invoked from` now says this is the only production path to `handle_delivery`, and that `tests/unit/test_delivery.py` also calls it.
- Review 0, Must Fix 1 (`_finish` / `_release` / `_give_up`): still correct against `src/scenewise/app/delivery.py`.

## Verified (no action)

- Anchors: every cited path exists, and every named symbol resolves in its cited file (checked by script over all `path` (`symbol`) pairs and all bare repo paths).
- Line numbers: the colon detector found nothing. The shape detector matched only values: the setting defaults 1500, 120 and 1800, and the HTTP statuses 413/422/429/503.
- The answer table was checked against `push`, `read_body`, `_admitted`, `_rejected`, `handle_delivery`, `_attempt`, `_release`, `_finish`, `_give_up` and `problems._STATUSES` / `problem_response`. Every row holds, including these:
  - 413 by content-length or while streaming.
  - 422 when `envelope.parse` returns `None`.
  - 429 with `RETRY_AFTER_BUSY_S`.
  - 503 `job_in_progress` with the rest of the lease, rounded up with `ceil`.
  - 503 with 30 s on a conflict or a release.
  - 503 with 30 s on a `RetryableError` raised out of the delivery.
  - 200 `RejectionV1` for a conflict (409 in the body), for `invariant_violation` and for `unexpected`.
- `decide_attempt` order, `wire_status` `retry_wait`, `job_id` path safety and `JOB_ID_PATTERN` match `src/scenewise/domain/jobs.py`.
- The shapes of `JobRequestV1`, `JobRecordV1`, `JobStatusV1`, `RejectionV1` and `ProblemV1` match `requests.py`, `records.py` and `results.py`.
- `ServiceSettings` defaults, `lease_s`, `_timing` and `_default_state_prefix` match `config.py`. The lifespan wiring matches `app.py` and `state.py`. The `Watchdog` limit and the `/healthz` 503 match `health.py` and `routes.py`.
- `_stores` matches `bootstrap.py`: the output store and the input store, with `store_unavailable` for any scheme other than `file://`.
- `LocalBlobStore` keeps a sidecar meta file, raises `WriteConflictError` on a generation mismatch, and maps `storage_unavailable` and `uri_not_allowed`. `ABSENT_GENERATION` is 0.
- `run_job` raises `stage_unavailable` and only `audio` is wired. `job_state` gives partial or succeeded. `publish` writes the `a{attempt}` folder and never touches the record. `artifacts_prefix` raises `uri_not_allowed` for a prefix under the state prefix.
- Provenance: the record is written only in `delivery.py` and read by `handle_delivery` and `job_status` (`routes.get_job`). The CLI `analyse` calls `run_job` and writes no record.
- The not-yet-built claims hold:
  - `notifier` is never set.
  - `to_domain` does not map `supersedes`.
  - `exceeds_push_budget` appears only in the `MediaTooLargeCode` literal.
- The named tests exist in `tests/e2e/test_http.py` (the duplicate-delivery check is inside `test_job_runs_to_a_terminal_record`) and in `tests/unit/test_service.py`. `tests/e2e/test_isolation.py` covers `uri_prefix` and state-prefix isolation.
- `docs/skeleton-notes.md` A9, `ARCHITECTURE.md` §7, the `README.md` curl example and the docstring of `problems.py` say what the document attributes to them.
- `reachable? ✅` for `POST /v1/jobs` is correct.
- Research depth is adequate: the trace reaches record and artifact provenance, fencing, and the timing configuration.
- Check 7 (parity) is skipped because `phases.parity` is false. Check 10 (merge) does not apply because no `existing_doc` was passed.
