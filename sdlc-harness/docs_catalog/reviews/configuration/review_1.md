Branch fix_artifacts_prefix_traversal_2, follows review_0.md.

# Review 1: docs/concepts/configuration.md (mode: update)

verdict: PASS

## Scope checked
- The uncommitted edit to the `artifact_roots` bullet in "Gotchas / constraints", checked against the branch diff (`git diff origin/dev...HEAD`, harness artifacts excluded) and commit 1af4492.
- "case-changed spelling on a case-insensitive file system ... recognises the state directory by identity (`Path.samefile`), not only by its resolved name". This matches `src/scenewise/adapters/storage/local.py`: `_enters` checks `path.is_relative_to(real)` first, then calls `parent.samefile(real)` on the path and each of its parents. `LocalBlobStore._path` refuses when `_enters(...)` is true and the lexical `_spelt(requested)` is not inside the fenced root's spelling. The docstring of `_enters` gives the case-insensitive rationale. Correct.
- "No other spelling reaches the state tree; the full account is in [[storage-and-uri-policy]]". The first bullet of that document's "Gotchas / constraints" now says the same thing: symlink, parent alias and case-changed spelling are all refused by identity, and it names no remaining limit. The stale pointer to "the limit that remains" is gone, and the cross-link resolves.
- The `artifacts_prefix` clause (normalised job folder at, under or containing the state prefix; query, fragment or relative path refused) matches `src/scenewise/app/delivery.py` (`artifacts_prefix`, `_shape_refusal`).
- The output store's roots `[state dir, *artifact_roots]` with `fenced=(state_path,)` match `src/scenewise/service/bootstrap.py` (`_stores`).
- Anchors: `LocalBlobStore._path`, `_enters`, `_spelt` (local.py), `artifacts_prefix` (delivery.py), `_stores` (bootstrap.py) and `test_a_case_changed_spelling_cannot_enter_a_fenced_root` (`tests/contract/test_blobstore_local.py`) were each found by grep in the cited file. All paths resolve from the repo root.
- Preserved: the earlier changes this branch committed to this document (Composition root step 5 `fenced=(state dir,)` and the `LocalBlobStore` anchor role "and the output store's state fence") are intact. Nothing outside the target bullet changed.
- Line-number detectors: both regexes return zero hits.
- Parity check skipped (`phases.parity` is false).

## Ripple
- I checked `docs/features/job-results-and-artifacts.md`, `docs/concepts/error-model.md`, `docs/concepts/layering-and-ports.md`, `docs/skeleton-notes.md` and `ARCHITECTURE.md` for wording about the fence. None of them still states an except-by-case limit or points at a removed limit. `job-results-and-artifacts.md` already names case-changed spellings. No missed document.

## Findings
None.
