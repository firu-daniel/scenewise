Branch fix_artifacts_prefix_traversal_2, follows review_2.md.

# Review 3: docs/features/job-submission.md

- mode: update
- iteration: 3
- verdict: PASS

## Must Fix

None.

## Verified (no action)

- **Diff reflected (check 11).**
  - The `### app` `artifacts_prefix` bullet now matches `src/scenewise/app/delivery.py`.
  - `_shape_refusal`: it refuses `?` / `#` on the raw string, a `ValueError` from `urlsplit`, and a non-empty relative path.
  - `_location`: it normalises host case (`urlsplit` already lowercases the scheme), maps the `file` host `localhost` to empty, and applies `unquote`, `posixpath.normpath` dot segments and slash collapsing.
  - `artifacts_prefix`: it compares the job folder `job_prefix(uri_prefix, job.id)` with the state prefix when scheme and host match. The folder is refused when it sits at the state prefix, under it, or contains it (the two `is_relative_to` tests), and the caller's spelling is returned. The two consequences the doc states hold: a basename-equal job id is refused, and so is a folder whose `a{attempt}` subfolder would be the state directory. A parent prefix with any other job id is accepted.
  - The `### adapters` fence bullet matches `LocalBlobStore.__init__` (`_fenced` holds pairs of `resolve()` and `_spelt` values), `LocalBlobStore._path`, `_enters` (`is_relative_to` or `samefile` over the parents) and `_spelt` (lexical `normpath`, no symlinks). The `excluded` addition to the first `LocalBlobStore` bullet is true.
  - The `### service` `_stores` bullet matches `src/scenewise/service/bootstrap.py`: `LocalBlobStore(roots=outputs, fenced=(state_path,))`.
- **Tests cited exist.**
  - `tests/e2e/test_isolation.py` has `test_cross_job_overwrite_is_refused` and `test_a_symlink_into_the_state_prefix_is_refused`.
  - `tests/unit/test_delivery.py` has all three named tests.
  - `tests/contract/test_blobstore_local.py` has the fenced-root tests, including `test_a_case_changed_spelling_cannot_enter_a_fenced_root`.
- **Preserved (check 12).** The working-tree diff only adds or extends bullets. Every other section is unchanged, and review_2 verified it against the code.
- **Anchors (check 1).** Every newly cited path exists from the repo root, and every symbol resolves in its cited file: `_shape_refusal`, `_location`, `LocalBlobStore.__init__`, `LocalBlobStore._path`, `_enters`, `_spelt`, `_stores`, and the test names.
- **Line numbers (check 2).** The colon detector found nothing. The shape detector matched only values: the setting defaults 1500, 120 and 1800, and the HTTP statuses 413/422/429/503.
- **Related.** `[[storage-and-uri-policy]]` exists and describes the same rules.
- Check 7 (parity) is skipped because `phases.parity` is false. Check 10 does not apply in update mode.

## Ripple (check 13)

- `docs/features/audio-stage.md` is not in this diff. Its `src/scenewise/app/delivery.py` (`artifacts_prefix`, `job_prefix`) bullet still says only "That prefix may not point into the state prefix (`uri_not_allowed`)". That is not false, but it leaves out three refusals: a job folder that contains the state prefix, a basename-equal job id, and the query / fragment / relative-path refusals. It could point to [[storage-and-uri-policy]] instead.
- These docs already reflect the change in the branch diff, so they need nothing: `docs/concepts/storage-and-uri-policy.md`, `docs/concepts/configuration.md`, `docs/concepts/error-model.md`, `docs/concepts/layering-and-ports.md`, `docs/features/job-results-and-artifacts.md`, `docs/skeleton-notes.md`.
