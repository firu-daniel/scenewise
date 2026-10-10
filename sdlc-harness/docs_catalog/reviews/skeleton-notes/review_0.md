# Review 0: docs/skeleton-notes.md (mode: update, row A6)

verdict: FAIL

## Verified (accurate)

- `artifacts_prefix` normalises the job folder `{uri_prefix}/{job_id}` and the state prefix with `_location`, which handles scheme and host case, `localhost` for `file`, percent-escapes, dot segments and repeated slashes. It refuses the folder with `uri_not_allowed` when, with the same scheme and host, the folder lies at or under the state prefix or contains it (`path.is_relative_to(state_path) or state_path.is_relative_to(path)`). Source: `src/scenewise/app/delivery.py` (`artifacts_prefix`, `_location`).
- Query, fragment and relative-path refusals come from `_shape_refusal`, which also refuses an unparsable URI. Source: `src/scenewise/app/delivery.py` (`_shape_refusal`).
- `LocalBlobStore` `fenced`: `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.__init__`, `LocalBlobStore._path`, `_enters`, `_spelt`). It is set by `src/scenewise/service/bootstrap.py` (`_stores`) as `fenced=(state_path,)` on the output store.
- The "symlink or another spelling of a parent directory" claim matches the code and the docstrings.
- The edit to the review-r1 finding 1 row is also accurate. `{state}/../state/victim` passed the old `startswith(f"{state}/")` check and `{root}/artifacts/../state/victim` did not. `test_cross_job_overwrite_is_refused` and `test_a_symlink_into_the_state_prefix_is_refused` both exist in `tests/e2e/test_isolation.py`.
- No line coordinates: neither detector finds a hit in row A6 or in the finding 1 row.
- The rest of row A6 that the diff did not touch is kept: the two stores, `local_roots`, `{uri_prefix}/{job_id}/a{n}/`, and the Why column.

## Must Fix

1. **Two paths added in the A6 "Skeleton does" cell do not resolve from the repo root.**
   - Claim: "`artifacts_prefix` in `app/delivery.py` …" and "set in `service/bootstrap.py` `_stores`".
   - Contradiction: neither `app/delivery.py` nor `service/bootstrap.py` exists at the repo root. Both resolve only from inside `src/scenewise/`. The docs-writer contract requires every path in a document to be repo-relative, in prose as much as in an anchor.
   - Correction: `src/scenewise/app/delivery.py` (`artifacts_prefix`, `_shape_refusal`) and `src/scenewise/service/bootstrap.py` (`_stores`). Also give the store's path, not just the class and field: `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`, `fenced`).

## Advisory (non-blocking for this target)

- The same rule applies to the existing package-relative paths in the "Where" column and other cells: `domain/jobs.py`, `domain/results.py`, `domain/inputs.py`, `app/contract/requests.py`, `storage/by_scheme.py`, `service/config.py`, `app/deps.py`, `app/delivery.py` (A9), and the A10 tree. This diff did not touch them. Fix them in a later pass that covers the whole document, not as part of this target.

## missed_docs

none. `docs/concepts/storage-and-uri-policy.md`, `docs/features/job-submission.md`, `docs/features/job-results-and-artifacts.md`, `docs/concepts/configuration.md`, `docs/concepts/error-model.md`, `docs/concepts/layering-and-ports.md` and `docs/features/audio-stage.md` are already in the diff. The untouched documents that mention `LocalBlobStore` or `artifacts_prefix` make no claim the change made stale: `docs/concepts/job-lifecycle-and-timing.md`, `docs/features/cli-analyse.md`, `docs/features/job-status.md`, `docs/concepts/wire-contract.md` and `docs/INDEX.md`.
