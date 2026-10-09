# Review 1: docs/concepts/job-lifecycle-and-timing.md

Mode: catalog. Iteration: 1. No `existing_doc` was passed, so check 10 does not apply. `phases.parity` is `false`, so check 7 does not apply.

**Verdict: FAIL.** There is one Must Fix item: a factual error in one Gotchas bullet. The rest of the document is accurate, and the research goes beyond the hints.

## Must Fix

### 1. Gotchas, "A storage error on the terminal write is not a conflict": the last sentence is wrong, and the case that really stalls is missing

- **Claim:** "The record stays `RUNNING` under its live lease, so later deliveries get `job_in_progress` until the lease (1920 s by default) expires. The claim write and `_give_up` behave the same way."
- **Contradicted by:** `src/scenewise/app/delivery.py` (`_attempt`, `_give_up`, `_release`) and `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.write`, which raises `RetryableError(code="storage_unavailable")` on `OSError`).
  - **Claim write:** a storage error means no new claim was written. The stored record stays as it was: either there is none, or it is a `RUNNING` record whose lease has already expired, because only `Start` reaches `_attempt`. So the next delivery decides again at once. Nothing stalls behind a live lease.
  - **`_give_up`:** it only runs when `decide_attempt` returned `GiveUp`, which means the lease had already expired. A storage error leaves that expired record in place, and the next delivery gives up again at once. Here too nothing stalls behind a live lease.
  - **`_release`:** it also catches only `WriteConflictError`. A storage error on the release write escapes to `push._admitted`, which answers 503 with `Retry-After: 30`. The claim, with `lease_until = now + lease_s`, stays live, so later deliveries get `job_in_progress` until it expires. This is the case that does behave like the terminal write, and the document leaves it out. Step 5 says only that "If the release itself loses a CAS race, the conflict is only logged."
- **Correction:** replace the last sentence with:

  > The release write (`_release`) has the same exposure: it catches only `WriteConflictError`, so a storage error there also leaves the live claim in place. A storage error on the claim write or in `_give_up` escapes the same way, as a 503 with `Retry-After: 30`. But in those two cases the stored record is already absent or expired, so the next delivery decides again at once.

## Verified (no finding)

- **Check 1, anchors:** every cited path exists. Every named symbol resolves in its file: `JobRecord`, `JobState`, `AttemptInfo`, `decide_attempt`, `wire_status`, `FIRST_ATTEMPT`, `handle_delivery`, `_Delivery.write`, `_attempt`, `_release`, `_finish`, `_give_up`, `_run`, `RETRY_AFTER_CONFLICT`, `record_uri`, `job_prefix`, `RECORD_FILE_NAME`, `BlobStore`, `Blob`, `ABSENT_GENERATION`, `WriteConflictError`, `LocalBlobStore`, `_HAND_PLACED_GENERATION`, `JobRecordV1`, `record_to_json`, `record_from_json`, `status_json`, `to_domain`, `ServiceSettings`, `_timing`, `lease_s`, `_admitted`, `_rejected`, `_STATUSES`, `Watchdog`, `create_app`, `DeliveryPolicy`, `ffmpeg.py` `_run`, `PROBE_TIMEOUT_S`, `runner.py` `remaining` and `_run_stage`, `publish.py` `attempt_prefix`, `results.py` `job_state`, `errors.py` `MediaTooLargeCode`, `cli.py` `analyse`, `test_lease_boundary` and `test_timing_invariant`. The quoted comment "Generation first: a crash in between leaves a stale token unusable." resolves in `local.py`. The `docs/skeleton-notes.md` references resolve: A7 (`max_attempts = 5`), A8 (delivery never notifies), A9 (fenced terminal write answers 503, and no record calls `_attempt(1)` directly), and review r1 finding 14 (probe overrun of up to 60 s).
- **Check 2, line numbers:** both detectors return no hits.
- **Checks 3 to 5, behaviour:** these claims match the code:
  - the `decide_attempt` order, and the lease boundary at `lease_until > now`;
  - claim, release, finish and give-up all write under `if_generation`, using `g0` or the token;
  - the 30 s `RETRY_AFTER_CONFLICT`;
  - the HTTP mapping: 429 for `CapacityError` is listed first, ahead of 503 for `RetryableError`;
  - `AttemptInfo` is built once in `_admitted`;
  - the record schema, including `extra="forbid"` and `attempt >= FIRST_ATTEMPT`;
  - `wire_status` is used by `status_json`;
  - the timing defaults (1500, 120, 10 × 3, 1800, 120, 5), the strict `<` invariant, and `lease_s` = 1920;
  - the watchdog limit is budget + grace;
  - a deadline error is job-fatal outside a stage and fails only that stage inside one.

  No other module writes `status.json`.
- **Check 6, depth:** the document traces the full path: push admission, the pure decision, the CAS store, publish, the HTTP mapping and the health watchdog. It goes well beyond the entry hints.
- **Check 8:** no `⚠️ unverified` markers. The "no code checks it" notes about queue configuration are accurate.
- **Check 9:** no material omission apart from the `_release` case in Must Fix 1.
