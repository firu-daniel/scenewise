# Fix artifacts prefix traversal

# Fix: artifact `uri_prefix` with `..` escapes into the state prefix

## Problem

A job's `delivery.artifacts.uri_prefix` must never point into the state prefix. `artifacts_prefix` in
`src/scenewise/app/delivery.py` enforces this. It strips trailing slashes, then refuses the prefix if it equals the
state prefix or starts with `{state}/`. That comparison is on the **unresolved URI string**. The `..` segments are only
resolved later, when `LocalBlobStore._path` (`src/scenewise/adapters/storage/local.py`) calls `Path(...).resolve()`.
The output store is built in `_stores` (`src/scenewise/service/bootstrap.py`) with the state path among its allowed
roots. So a prefix that is spelt to start outside the state prefix and then walks back into it gets past the check, and
the store then accepts the write.

Three agents reproduced this independently during the `docs_catalog_initial` docs run, by calling
`artifacts_prefix` → `attempt_prefix` → `LocalBlobStore.write` directly:

- **`{artifact_root}/../state/victim`, job id `attacker`:** accepted. The write lands at
  `state/victim/attacker/a1/result.json`.
- **`{state}/../state/victim`:** refused (`uri_not_allowed`), because the string already starts with the state prefix.

What the attacker can and cannot do:

- They can create files inside another job's state folder.
- They cannot overwrite another job's `status.json` or `result.json`. The appended job id is one safe path segment,
  and reusing the victim's id hits the victim's record and gets a digest conflict.

## Why the existing safeguards miss it

- **The notes are wrong.** `docs/skeleton-notes.md`, review-r1 fix row 1, says the cross-job overwrite with "two `..`
  spellings now end `failed` / `uri_not_allowed`". For `{root}/artifacts/../state/victim` that is not true.
- **The test passes anyway.** `tests/e2e/test_isolation.py`, `test_cross_job_overwrite_is_refused`, includes that
  spelling in its parameters. It still passes because it only asserts that the victim's own `a1/result.json` is
  unchanged and that `victim/a1/attacker` does not exist. It never asserts the request was refused, and never looks at
  `victim/attacker/`.
- **The docs record it as current behaviour.** `docs/concepts/storage-and-uri-policy.md` and
  `docs/features/job-results-and-artifacts.md` both describe it as a gotcha.

## What done looks like

- Any artifact `uri_prefix` that **resolves** to the state prefix or anywhere under it ends the job `failed` /
  `uri_not_allowed`, however it is spelt (`..`, `.`, repeated slashes, and so on). No file is written anywhere under
  the state prefix for that job.
- `test_cross_job_overwrite_is_refused` asserts the refusal itself (status and `error_code`) for every spelling, and
  asserts that nothing was created under the state prefix for the attacker. The test must fail against the current code.
- The review-r1 row in `docs/skeleton-notes.md`, the gotchas in the two docs above, and `ARCHITECTURE.md` §7 (which
  says a prefix under the state prefix is refused) are updated to match.
- The layering in `.claude/context/conventions.md` § Dependency direction still holds.

## Likely fix (a hint for planning to verify, not a decision)

Resolve the requested prefix **before** comparing it with the state prefix. That means normalising both the requested
`uri_prefix` and `state_prefix` to the same form, with `..` and `.` collapsed, then doing the containment check on the
results.

Planning should check, against the code:

- **Where the resolution belongs.** `artifacts_prefix` in `app` is scheme-agnostic and must not do filesystem path
  resolution, because `app` must not depend on adapter concerns. One alternative is for the output store to refuse
  artifact writes under the state root, for example a write-scoped exclusion like the input store's `excluded`. Another
  is a pure, URI-level normalisation in `app` that works for any scheme. Decide which, or both.
- **Whether URI-level normalisation without the filesystem is enough.** `posixpath.normpath` on the URI path collapses
  `..` but not symlinks. Planning should decide whether symlinked roots matter here.
- **The other callers.** Anything else that builds paths from caller-supplied URIs, for example `job_prefix` and
  `record_uri` with a hostile `job_id`, may have the same string-versus-resolved gap. Check them too.

---

Started from https://github.com/firu-daniel/scenewise/issues/8 by @firu-daniel, who applied the label `sdlc-harness` at 2026-10-09T20:19:18Z. This is the issue's text at that moment; later edits to the issue do not reach this run.
