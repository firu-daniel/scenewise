# Review 2: docs/concepts/job-lifecycle-and-timing.md

Mode: catalog. Iteration: 2. No `existing_doc` was passed, so check 10 does not apply. `phases.parity` is `false`, so check 7 does not apply.

**Verdict: PASS.** Review 1's single Must Fix item has been applied correctly. A fresh re-verification of the whole document against the code found no new factual errors.

## Review 1, Must Fix 1: resolved

The Gotchas bullet "A storage error on the terminal write is not a conflict" now says three things. All three were checked against `src/scenewise/app/delivery.py`:

- `_release` catches only `WriteConflictError`. A `RetryableError` raised by its write propagates out of the `except RetryableError` handler in `_attempt`, so the live claim stays in place.
- A storage error on the claim write (`_attempt`) or in `_give_up` escapes as a 503 with `Retry-After: 30` (`push.py` `_admitted`, `RETRY_AFTER_BUSY_S`).
- In those two cases the stored record is already absent or expired. Only `Start` reaches `_attempt`, `GiveUp` requires an expired lease, and the no-record path writes with `ABSENT_GENERATION`.

The terminal-write case is also correct: `_finish` is called after the `try` in `_attempt`, so a storage error there escapes.

## Must Fix

None.

## Minor (non-blocking)

- Timing table, `dispatch_deadline_s` row: "Must match the queue's `dispatchDeadline`". `ARCHITECTURE.md` §7 "Timing" and `docs/research/q8a-architecture-layout.md` state the requirement as `dispatchDeadline` ≤ `dispatch_deadline_s`. "Match" satisfies that bound, so this misleads no one. Writing "must be ≥ the queue's `dispatchDeadline`" would follow the design of record more exactly. No action is required for this review.

## Verified (no finding)

- **Check 1, anchors:** every anchor path exists, and every named symbol was re-grepped in its file. The symbols cover these files:
  - `jobs.py`: `decide_attempt`, `wire_status`, `AttemptInfo`, `FIRST_ATTEMPT`
  - `delivery.py`: `handle_delivery`, `_attempt`, `_release`, `_finish`, `_give_up`, `_run`, `_Delivery.write`, `record_uri`, `job_prefix`, `RECORD_FILE_NAME`, `RETRY_AFTER_CONFLICT`
  - `ports.py`: `BlobStore`, `Blob`, `ABSENT_GENERATION`, `WriteConflictError`
  - `local.py`: `LocalBlobStore`, `_HAND_PLACED_GENERATION`, and the quoted "Generation first" comment
  - `records.py`: `JobRecordV1`
  - `mapping.py`: `record_to_json`, `record_from_json`, `status_json`
  - `config.py`: `ServiceSettings`, `_timing`, `lease_s`
  - `push.py`: `_admitted`, `_rejected`
  - `problems.py`: `_STATUSES`
  - `health.py`: `Watchdog`
  - `app.py`: `create_app`, including `Watchdog(limit_s=attempt_budget_s + watchdog_grace_s)`
  - `ffmpeg.py`: `_run`, `PROBE_TIMEOUT_S`
  - `runner.py`: `remaining`, `_run_stage`
  - `publish.py`: `attempt_prefix`
  - `results.py`: `job_state`
  - `errors.py`: `MediaTooLargeCode`
  - `cli.py`: `analyse`
  - tests: `test_lease_boundary`, `test_timing_invariant`

  The `docs/skeleton-notes.md` references A7, A8, A9 and review r1 finding 14 all resolve.
- **Check 2, line numbers:** both detectors return zero hits.
- **Checks 3 to 5, behaviour:** these claims match the code:
  - the `decide_attempt` order, with strict `>` at the lease boundary;
  - the CAS generations used by claim, release, finish and give-up (`g0`, token, token, `g0`);
  - release sets `lease_until = info.now`;
  - the last attempt ends `attempts_exhausted` through `_finish`;
  - a fenced terminal write answers `job_in_progress` with 30 s;
  - the HTTP mapping: `CapacityError` (a `RetryableError` subclass) is listed first and maps to 429;
  - the record schema (`extra="forbid"`, `attempt >= FIRST_ATTEMPT`);
  - an unreadable record raises `invariant_violation`, which is answered 200 through `_rejected`;
  - the timing defaults and the strict `<` invariant (1650 < 1800);
  - `lease_s` = 1920;
  - a deadline error is job-fatal between stages and during audio acquisition, and stage-local inside `_run_stage`;
  - `probe` uses the fixed 60 s timeout.

  No module other than `delivery.py` writes `status.json`.
- **Check 6, depth:** the document traces admission, the pure decision, the CAS store and its local implementation, run and publish, the HTTP mapping, the watchdog and the CLI's use of the budget. It goes well beyond the hints.
- **Check 8:** there are no `⚠️ unverified` markers. The "no code checks it" claims about queue configuration are accurate.
- **Check 9:** no material omission.
