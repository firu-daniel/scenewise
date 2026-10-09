# Review: job-results-and-artifacts (catalog, iteration 1)

doc: docs/features/job-results-and-artifacts.md
verdict: PASS

## Prior Must Fix (links_review_0) resolved

1. **`to_domain` attribution.** The `### app` request-side bullet now cites `src/scenewise/app/contract/mapping.py` (`to_domain`) separately from the `requests.py` anchor for `DeliveryV1` / `ArtifactSinkV1`. The `## Anchor files` entry for `mapping.py` now lists `to_domain`. Checked against source: `to_domain` is defined in `mapping.py` and sets `artifacts_prefix=request.delivery.artifacts.uri_prefix` and `external_ref=tuple(sorted(...))`. This matches the document, including the edge-case claim that `external_ref` is re-sorted by key. Resolved.

## Re-checked this round

- **Check 1, anchors.** Every cited path exists. Every named symbol greps inside its cited file. That covers all `## Anchor files` entries, the inline anchors, and the three `tests/unit/test_delivery.py` test names. `JSON_MEDIA_TYPE` is mentioned in prose under the `publish` bullet. It is imported into `publish.py` from `scenewise.app.constants` and used there, so the reference is accurate. The document does not claim `publish.py` defines it.
- **Check 2, line coordinates.** Both detectors return zero hits.
- **Checks 3 to 5, spot-checked against source.** All match the document:
  - `attempt_prefix`, which strips a trailing `/`.
  - `publish`:
    - `audio.wav` is written first, and only when `audio_wav` is set.
    - Neither write passes `if_generation`.
    - It returns the result URI.
  - `job_prefix`, `record_uri`, and `artifacts_prefix`, including the lexical equal-or-under-state check and the job-id suffix.
  - `_run`:
    - The order is parse, then `run_job`, then `publish`, then the terminal record with `result_uri`.
    - A `RetryableError` is re-raised.
    - A `ScenewiseError` ends the job `FAILED`.
  - `_finish`: on `WriteConflictError`, artifacts are left behind with no record pointing at them.
  - `result_json`:
    - Only the `AUDIO` stage is mapped.
    - `timings_ms` uses `round(seconds * MS_PER_SECOND)`.
    - `scenewise_version` is `__version__`.
  - `_stage_fields`: for a failed stage, `reason` holds the error code and `retryable=False`.
  - `ArtifactSinkV1.uri_prefix`: `min_length=1`, default `None`.
- **Related links.** All five slugs resolve to existing documents under `docs/features/` or `docs/concepts/`.
- **Check 10, merge/supersede.** No `existing_doc` was passed as a separate merge target. The uncommitted diff against HEAD changes only the `to_domain` sentence, the `mapping.py` anchor entry and the `## Related` line. No content was dropped.
- **Checks 6, 8 and 9.** The iteration-0 full review found the depth, `audio_wav` provenance, unverified markers and coverage adequate, and nothing in those areas changed. No new issue was found.
- **Check 7.** Skipped because `phases.parity` is `false`.

## Must Fix

None.
