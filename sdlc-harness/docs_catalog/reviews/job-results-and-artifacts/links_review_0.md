# Review — job-results-and-artifacts (catalog, iteration 0)

doc: docs/features/job-results-and-artifacts.md
existing_doc: the same file (an in-place revision)
verdict: FAIL

## Scope checked

- Uncommitted diff (`git diff -- docs/features/job-results-and-artifacts.md`): only the `## Related` line changed. No other line was touched, so the merge/supersede check (check 10) passes trivially: no earlier content was dropped.
- `## Related` cross-links. All five resolve to an existing document that covers the linked topic:
  - `[[job-lifecycle-and-timing]]` -> `docs/concepts/job-lifecycle-and-timing.md` (job record, `handle_delivery`, `_finish`, fencing). This is the correct target for the old `[[job-delivery-and-records]]`, as the `docs/INDEX.md` alias table also says.
  - `[[audio-stage]]` -> `docs/features/audio-stage.md`
  - `[[storage-and-uri-policy]]` -> `docs/concepts/storage-and-uri-policy.md` (replaces `[[blob-storage-and-uri-policy]]`)
  - `[[cli-analyse]]` -> `docs/features/cli-analyse.md`
  - `[[wire-contract]]` -> `docs/concepts/wire-contract.md` (replaces `[[wire-contract-v1]]`)
- Full factual review of the rest of the document (checks 1-9). Every anchor path exists. Every named symbol was grepped in its cited file, and all resolve except the one below. Both line-number detectors return zero hits. Spot-checked against source and found accurate:
  - `publish`, `attempt_prefix`, `artifacts_prefix`, `_run` and `_finish`
  - `result_json` and `_stage_fields`, including the claim that `retryable=False` and that `reason` holds the error code
  - the `JobResultV1`, `AudioStageV1`, `ErrorInfoV1`, `ProbedMediaV1` and `ArtifactSinkV1` shapes
  - `job_state`
  - the `_stores` output/input split and `store_unavailable`
  - the `ServiceSettings` defaults and env prefix
  - the `LocalBlobStore` sidecar, lock and `uri_not_allowed` behaviour
  - the CLI path (`FIRST_ATTEMPT`, `external_ref=()`, no `publish`)
  - the `..`-spelling edge case, which matches `tests/e2e/test_isolation.py` (`test_cross_job_overwrite_is_refused`): that test only asserts that nothing is overwritten
  - the `README.md` and `ARCHITECTURE.md` quotes

## Must Fix

1. **`to_domain` is attributed to the wrong file (check 1, symbol half).**
   - Claim: `### app` -> "Request side (`src/scenewise/app/contract/requests.py`): `DeliveryV1` holds ... `to_domain` copies it into `Job.artifacts_prefix`." The parenthetical sends the reader to `requests.py` for `to_domain`.
   - Contradicted by: `to_domain` is not defined in `src/scenewise/app/contract/requests.py`. Its definition is in `src/scenewise/app/contract/mapping.py` (`to_domain`), which sets `artifacts_prefix=request.delivery.artifacts.uri_prefix` and `external_ref=tuple(sorted(...))`.
   - Correction: keep `requests.py` as the anchor for `DeliveryV1` / `ArtifactSinkV1`, and give `to_domain` its own anchor. For example: "... `min_length=1`. `src/scenewise/app/contract/mapping.py` (`to_domain`) copies it into `Job.artifacts_prefix`." Then add `to_domain` to the `src/scenewise/app/contract/mapping.py` entry in `## Anchor files`.

## Notes (not findings)

- `docs/INDEX.md` still lists the old slugs `[[job-delivery-and-records]]` and `[[blob-storage-and-uri-policy]]` in its alias table, mapped to the right targets. That is the INDEX's alias record, not this document's concern.
