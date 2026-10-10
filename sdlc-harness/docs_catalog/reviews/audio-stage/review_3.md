Branch fix_artifacts_prefix_traversal_2, follows review_2.md.

# Review 3: docs/features/audio-stage.md

mode: update · iteration: 3 · verdict: PASS

`phases.parity` is `false`, so check 7 was skipped. Check 10 applies only in catalog mode.

## What the update changed, checked against the diff

1. **`artifacts_prefix` bullet (app): accurate.**
   - Shape refusals: a `?` or `#` anywhere, a relative path, or a `ValueError` from `urlsplit` each raise `InputError(code="uri_not_allowed")`. Source: `src/scenewise/app/delivery.py` (`_shape_refusal`, `artifacts_prefix`).
   - The job folder `job_prefix(uri_prefix.rstrip("/"), job.id)` is compared with the state prefix after `_location` normalises both. The test is `path.is_relative_to(state_path) or state_path.is_relative_to(path)`, applied only when scheme and host match, so the job folder may not equal the state prefix, lie under it, or contain it.
   - The normalisation list is correct: `urlsplit` lowercases the scheme, `_location` lowercases the host, maps `localhost` to empty for `file`, applies `unquote`, and uses `posixpath.normpath` for dot segments and repeated slashes.
   - The parent-plus-basename consequence follows from that comparison.
   - The caller's spelling is returned (`return folder`).
   - "Before `audio.wav` is written" and "fails the whole job" hold. In `src/scenewise/app/delivery.py` (`_run`), `artifacts_prefix` is evaluated as an argument to `publish` before `publish` runs, and an `InputError` is a `ScenewiseError`, which ends the job `FAILED` with its code.
2. **Output-store fence bullet (service): accurate.**
   - `src/scenewise/service/bootstrap.py` (`_stores`) builds `LocalBlobStore(roots=outputs, fenced=(state_path,))`.
   - `src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`, `_enters`, `_spelt`) refuses a resolved path that enters the state directory by name (`is_relative_to`) or by identity (`samefile` on the path or any parent). It allows the path only when the lexically normalised requested spelling sits under the state directory's spelling.
   - That covers symlinks, another spelling of a parent, and a case-changed spelling on a case-insensitive file system, as the document says.
3. **Anchor files:** the additions (`_enters` in `local.py`, `_stores` in `bootstrap.py`) are correct. The file set changed because the fence is new, so revising these entries is justified.

## Re-checked this round

- **Check 1 (anchors):** every newly cited symbol greps in its cited file: `_shape_refusal`, `_location`, `artifacts_prefix` and `job_prefix` in `delivery.py`; `LocalBlobStore._path`, `_enters` and `_spelt` in `local.py`; `_stores` and `fenced=(state_path,)` in `bootstrap.py`.
- **Check 2 (line numbers):** the colon detector has one hit, `-map 0:a:0`. That is an ffmpeg stream specifier, so it is a value and stays. The colon-free detector has no hits.
- **Check 12 (preserved):** every section outside the three edited spots is byte-identical to the committed version. The input-store `uri_not_allowed` bullet ("inside the state or artifact roots") is still true, because the `excluded` handling is unchanged.

## Must Fix

None.

## Non-blocking

- Service bullet, "unless it is written inside it": the code's condition is the requested *spelling* (absolute, lexically normalised, with no symlinks followed) lying inside the state directory's spelling. "Unless it is spelt inside the state directory" would say that without ambiguity.
- `tests/e2e/test_isolation.py` gained `test_a_symlink_into_the_state_prefix_is_refused` in this diff. The tests sub-section still names only the two cross-job tests. It is optional to add it as coverage for the fence.

## Ripple (check 13)

- `docs/skeleton-notes.md` row A6 still states the old rule only: "A requested `artifacts.uri_prefix` may not lie under the state prefix". It says nothing about the job folder (rather than the prefix) being compared, the "nor contain it" rule, or the query, fragment and relative-path refusals. Row "1 (must)" in the same file was updated in this diff, but A6 was not.
