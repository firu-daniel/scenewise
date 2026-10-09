# Review 0: docs/concepts/job-lifecycle-and-timing.md

verdict: FAIL

The document is accurate and well researched almost everywhere. Things I checked against the source and found correct: the order of checks in `decide_attempt`; the no-record shortcut (A9); the claim, release, finish and give-up CAS writes and the `if_generation` each one uses; `RETRY_AFTER_CONFLICT`; `wire_status`; the `_timing` invariant and its defaults; `lease_s`; the watchdog limit wiring in `create_app`; the deadline paths through `remaining`, `acquire_audio`, `_run_stage` and ffmpeg `_run`; `PROBE_TIMEOUT_S`; the generation-first write and `_HAND_PLACED_GENERATION` in `LocalBlobStore`; the storage-error-on-terminal-write gotcha; and the CLI's `FIRST_ATTEMPT`. Every anchor path exists and every named symbol was found in its file. Neither line-number detector matched anything.

One cited source says something it does not say, and two smaller items need fixing.

## Must Fix

### 1. `ARCHITECTURE.md` step 7 does not say "re-read the record"
- **Claim** (How it works → One delivery, step 6 "Terminal write"): "`ARCHITECTURE.md` step 7 says to re-read the record and answer from it, which the code does not do (A9)."
- **Contradicted by:** `ARCHITECTURE.md` §7, "**One delivery**" step 7 "**Terminal record.**" On a `WriteConflictError` it says only "a later attempt took over after this lease expired: no notify, and these artifacts are never referenced". Neither "re-read" nor "answer as step 2 would" appears anywhere in `ARCHITECTURE.md`. Those words appear only in `docs/skeleton-notes.md`, row A9: "Fenced terminal write: re-read the record and answer as step 2 would".
- **Correction:** credit the re-read design to `docs/skeleton-notes.md` A9, not to `ARCHITECTURE.md` step 7. For example: "`docs/skeleton-notes.md` A9 records the intended behaviour as re-reading the record and answering as step 2 would. The code answers 503 `job_in_progress` instead. `ARCHITECTURE.md` §7 step 7 says only that these artifacts are never referenced." Alternatively, drop the comparison with `ARCHITECTURE.md`.

### 2. Not every `RetryableError` maps to 503
- **Claim** (How it works → One delivery, the HTTP mapping bullet): "`job_in_progress` and every other `RetryableError` code map to 503 (`src/scenewise/service/http/problems.py` `http_status`)."
- **Contradicted by:** `src/scenewise/domain/errors.py` (`CapacityError`) is a subclass of `RetryableError`. In `src/scenewise/service/http/problems.py` (`_STATUSES`), `CapacityError` comes first and maps to `HTTPStatus.TOO_MANY_REQUESTS` (429), ahead of the 503 entry for `RetryableError`.
- **Correction:** "`job_in_progress` and the other `RetryableError` codes map to 503. `CapacityError` (`capacity_exceeded`) is the exception and maps to 429 (`problems.py` `_STATUSES`, first match wins)."

### 3. One `⚠️ unverified` marker hides a fact that a grep settles
- **Claim** (Gotchas → Not built yet): "`exceeds_push_budget` exists as a code ... but nothing raises it. ⚠️ unverified: the upfront cost check in `ARCHITECTURE.md` §7 is a design statement only."
- **Contradicted by:** a grep of `src` for `exceeds_push_budget` finds it only in the `MediaTooLargeCode` literal in `src/scenewise/domain/errors.py`. Nothing constructs a `MediaTooLargeError` with that code. Whether the upfront check exists can therefore be checked, and the doc's own sentence already states the result. The marker is not honest (check 8).
- **Correction:** remove the `⚠️ unverified` marker and state it as fact: "Not built: the upfront cost check that `ARCHITECTURE.md` §7 describes ('rejected up front with `exceeds_push_budget`') does not exist. The code is declared in `MediaTooLargeCode` and nothing raises it."

## Notes (not graded)
- Optional, if the writer is already editing that bullet: the doc says an unreadable record becomes `InternalError(code="invariant_violation")` (`mapping.record_from_json`) but not what the caller gets back. `push._admitted` catches it as a `ScenewiseError` and answers 200 with a rejection body (`_rejected`). That is what an operator will actually see.
