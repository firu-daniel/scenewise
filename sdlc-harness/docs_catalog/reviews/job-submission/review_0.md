# Review 0: docs/features/job-submission.md (mode: catalog)

verdict: FAIL

## Must Fix

1. **Write-conflict answer of `_release` is misdescribed (and `_give_up` does not write under the token).**
   - Claim (`## Technical implementation` > `### app`, the `_finish`, `_release`, `_give_up` bullet): "the terminal write under the token ... A `WriteConflictError` at any of these points means another delivery won, and the answer is `TryLater(job_in_progress, 30 s)` (`RETRY_AFTER_CONFLICT`)."
   - Contradicted by `src/scenewise/app/delivery.py` (`_release`): on `WriteConflictError` it only logs `attempt_superseded` and still returns `TryLater(error=error, retry_after=RETRY_AFTER_CONFLICT)`, where `error` is the original `RetryableError` (for example `storage_unavailable`). So the 503 problem's `code` is that error's code, not `job_in_progress`. `_release` is not a terminal write either: it writes the released `RUNNING` record with `lease_until=now`. Separately, `_give_up` writes with `if_generation=generation` (the generation read in `handle_delivery`, since no claim exists in that path), not with an attempt token. Only `_finish` writes under the claim token.
   - Correction: "`_finish` writes the terminal record under the claim token. `_give_up` writes the terminal `failed` / `attempts_exhausted` record under the generation read from the store. On a `WriteConflictError` either one answers `TryLater(job_in_progress, 30 s)` (`RETRY_AFTER_CONFLICT`). `_release` writes the released record (`lease_until=now`) under the token and answers `TryLater` with the original retryable error and `RETRY_AFTER_CONFLICT`, whether or not that write conflicts."

## Verified (no finding)

- Every cited path exists. Every cited symbol resolves in its cited file. `FIRST_ATTEMPT` is imported into `delivery.py` and defined in `domain/jobs.py`; the doc uses it only inside a code expression, which is acceptable. All five named `tests/e2e/test_http.py` tests exist.
- Line-number detectors: `:NNN` has no hits. The shape detector's hits (`(1500)`, `(120)`, `(1800)`, `(200)`, `413/422/429/503`) are all setting defaults or HTTP statuses, so they are values, not line coordinates.
- Answer table: checked against `push` / `_admitted` / `_rejected` / `read_body` and `problems._STATUSES`, including the 413 content-length and streaming paths, the 422 for an unkeyable envelope, the 429 with `RETRY_AFTER_BUSY_S` 30, the 503 for a live lease with the remaining lease, the 200 `RejectionV1` for a conflict or an unreadable record, and `Retry-After` rounded up with `ceil`. All match.
- `decide_attempt` order, `wire_status` `retry_wait`, the claim fields, `_run` error handling, `artifacts_prefix` `uri_not_allowed`, the `publish` attempt folder, `request_digest` canonicalisation, the `JobRequestV1` / `JobStatusV1` / `RejectionV1` / `ProblemV1` / `JobRecordV1` shapes, the `ServiceSettings` defaults and `_timing`, the `lease_s` property, the `_stores` scheme handling, `LocalBlobStore` sidecar / CAS / errors, and `ABSENT_GENERATION` = 0 all match the code.
- The "not yet built" claims hold: `Dependencies.notifier` defaults to `None` and is never set, `to_domain` does not map `supersedes`, and nothing raises `exceeds_push_budget`.
- `docs/skeleton-notes.md` A9 matches the description. Record provenance holds: written only in `delivery.py`, read by `handle_delivery` and `job_status` / `get_job`. The CLI `analyse` calls `run_job` directly and keeps no record. Reachability ✅ is correct.
- Research depth is adequate: the doc traces the record and artifact provenance, the fencing, and the configuration timing. Parity is skipped because `phases.parity` is `false`.
