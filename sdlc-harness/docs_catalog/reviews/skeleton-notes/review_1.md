# Review 1: docs/skeleton-notes.md (mode: update, row A6)

verdict: PASS

## Review 0 Must Fix: resolved

- The paths in the A6 "Skeleton does" cell are now repo-relative and resolve from the repo root: `src/scenewise/app/delivery.py` (`artifacts_prefix`, `_shape_refusal`), `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`, `fenced`), `src/scenewise/service/bootstrap.py` (`_stores`). Each symbol greps to a hit in the file it is cited against.

## Verified (accurate)

- Normalisation: `artifacts_prefix` builds the job folder `{uri_prefix}/{job_id}` and compares it with the state prefix. Both go through `_location`, which handles scheme and host case, `localhost` for `file`, percent-escapes, dot segments and repeated slashes. Source: `src/scenewise/app/delivery.py` (`artifacts_prefix`, `_location`).
- Refusal rule: `uri_not_allowed` when the folder lies at or under the state prefix or contains it. The code is `path.is_relative_to(state_path) or state_path.is_relative_to(path)`, and it applies only when the scheme and host match. The row's wording, "lies at or under ... or contains it", already implies the same location, so the scheme-and-host condition is fine to leave out.
- Shape refusals: query, fragment and relative path come from `_shape_refusal`, and they raise `uri_not_allowed` in `artifacts_prefix`. `_shape_refusal` also refuses a URI it cannot parse. The row leaves that out, which is a minor omission and not material.
- Output-store fence: `LocalBlobStore.__init__` takes `fenced`, and `_path` refuses a resolved path that enters a fenced root (`_enters`) unless the request is spelt inside that root (`_spelt`). `_stores` passes `fenced=(state_path,)` to the output store only. The row's claim that "a symlink or another spelling of a parent directory cannot reach it" matches the code and the docstrings.
- The update matches the diff: the old "may not lie under the state prefix" sentence is replaced, and the "nor contain it", query, fragment and relative-path rules are now there. Nothing stale is left in the row.
- Preserved: the rest of row A6 that the diff did not touch is intact (the two stores, `local_roots`, `{uri_prefix}/{job_id}/a{n}/`, and the Why column). So is the finding 1 row that review 0 already checked.
- No line coordinates. Neither detector finds a hit in row A6. The hits elsewhere (dates, tool versions, a timestamp, `U16/U17`) are values in rows this target did not touch.
- `ARCHITECTURE.md` §10, which the row says now holds this rule, states the same normalised at-under-or-containing rule and the fence.

## Must Fix

None.

## Advisory (non-blocking, carried over from review 0)

- The package-relative paths in other rows and columns that this diff did not touch (`domain/jobs.py`, `storage/by_scheme.py`, `service/config.py`, `app/deps.py`, `app/delivery.py` in A9, and so on) still do not resolve from the repo root. Fix them in a pass that covers the whole document.

## missed_docs

none. `docs/concepts/storage-and-uri-policy.md` and the other documents that describe this rule are already in the branch diff. A grep of `docs/` for the old rule's wording finds no stale copy outside the documents the diff already touches.
