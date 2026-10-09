# Review: job-submission (links_review_0)

doc: docs/features/job-submission.md
mode: catalog, iteration 0
verdict: PASS

## Must Fix
None.

## Verified
- **Diff.** `git diff -- docs/features/job-submission.md` changes only the `## Related` line. `[[job-record-and-fencing]]` became `[[job-lifecycle-and-timing]]`, and `[[settings]]` became `[[configuration]]`. No other line changed.
- **Cross-links.** All seven `[[slug]]` links resolve to a file in the corpus that covers the linked topic:
  - `[[job-status]]` (in the Related line and in the body of the stored-data section) resolves to `docs/features/job-status.md`, which covers GET /v1/jobs/{job}, the reader of the record.
  - `[[audio-stage]]` (in the Related line and in the body of the `run_job` bullet) resolves to `docs/features/audio-stage.md`, which covers the only wired stage.
  - `[[job-lifecycle-and-timing]]` resolves to `docs/concepts/job-lifecycle-and-timing.md`. It covers the record, CAS generations, the fencing token and the lease, so it replaces the old `job-record-and-fencing`. `docs/INDEX.md` records the same alias.
  - `[[error-model]]` resolves to `docs/concepts/error-model.md`, which covers the error categories and the HTTP mapping.
  - `[[configuration]]` resolves to `docs/concepts/configuration.md`, which covers `ServiceSettings` and the `SCENEWISE_*` environment variables. It replaces the old `settings`, and `docs/INDEX.md` records the same alias.
- **Anchors (check 1).** Every `path` (`symbol`) anchor resolves: each file exists and each symbol greps inside its file. Every bare path also exists.
- **Line numbers (check 2).** The `:[0-9]+` detector found nothing. The no-colon detector found two lines, and both are values, not line numbers:
  - Line 71 lists the `ServiceSettings` defaults 1500/120/1800/120. These match `src/scenewise/service/config.py`.
  - Line 93 lists the HTTP statuses 200/413/422/429/503.
- **Spot checks of the body against the source.** All of the following still match the source:
  - The `_STATUSES` mapping and its 500 fallback.
  - `exceeds_push_budget` appears only in `MediaTooLargeCode`.
  - `Dependencies.notifier` is `None`.
  - The CLI `analyse` calls `run_job`.
  - Row A9 of `docs/skeleton-notes.md`.
  - The delivery helpers `_attempt`, `_run`, `_finish`, `_release` and `_give_up` exist.
  - Checks 3 to 9 were done in full in review_2, and the body has not changed since.
- **Not applicable.** Check 7 (parity) is skipped because `phases.parity` is false. For check 10, `existing_doc` is the document itself, and its substance is intact apart from the Related line.

## Optional (not blocking)
- `docs/features/job-results-and-artifacts.md` and `docs/concepts/wire-contract.md` cover the artifacts and wire shapes this document describes. The Related line could link them, but leaving them out is not a factual error.
