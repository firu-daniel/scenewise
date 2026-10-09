# Review 0: docs/features/job-results-and-artifacts.md

verdict: PASS

## Must Fix
None.

## Checks performed
1. Anchors: all cited paths exist from the repo root, and every symbol anchor resolves in its file. Checked: `publish`, `attempt_prefix`, `AUDIO_FILE_NAME`, `RESULT_FILE_NAME`, `WAV_MEDIA_TYPE`, `artifacts_prefix`, `job_prefix`, `record_uri`, `RECORD_FILE_NAME`, `_run`, `_finish`, `_terminal`, `job_status`, `result_json`, `_stage_fields`, `_media`, `status_json`, `to_domain`, the results/requests/records models, `Analysis`, `job_state`, `Job`, `JobRecord`, `wire_status`, `BlobStore`, `LocalBlobStore._path`, `_stores`, `ServiceSettings`, `_default_state_prefix`, `create_app`/`DeliveryPolicy`, `analyse`, `get_job`, `post_job`, `_admitted`, `run_job`, `stages.audio`, `acquire_audio`, and the three named tests in `tests/unit/test_delivery.py`. The quoted strings in `README.md` ("never build the path") and `ARCHITECTURE.md` §7 ("names the winning attempt's files") both grep-resolve.
2. Line numbers: both detectors return zero hits. The document has no coordinates.
3. Backend surface: the `POST /v1/jobs` and `GET /v1/jobs/{job}` payloads and responses match `routes.py`, `push.py` and `JobStatusV1`. Both are correctly marked reachable. The claim that no endpoint serves artifact bytes is correct.
4. Data shapes: the `JobResultV1`, `ProbedMediaV1`, `StageResultsV1`, `AudioStageV1`, `ErrorInfoV1`, `ArtifactSinkV1`/`DeliveryV1` and `JobRecordV1.result_uri` shapes match the source. So do `reason`=error code on a failure, `retryable=False`, `indent=2`, the re-sorted `external_ref`, and `media` being null only when there was no audio input (`acquire_audio` yields None).
5. Gating: the lexical state-prefix refusal (`artifacts_prefix`) and the store allow-list (`_stores` roots = state dir plus `artifact_roots`; input store `excluded`) are accurate. I reproduced the `..` bypass edge case by calling `artifacts_prefix` and `LocalBlobStore._path` directly. `{root}/artifacts/../state/victim` passes the lexical check and resolves to `state/victim/attacker/a1/result.json`, inside the state root, so the store accepts it. `tests/e2e/test_isolation.py` only checks that the victim's `a1/result.json` is unchanged and that no `victim/a1/attacker` exists, so it does not catch this. The document's claim is correct.
6. Depth: the provenance of `Analysis.audio_wav` is traced through `acquire_audio` → `stages.audio` → `run_job`. Orphaned artifacts under `WriteConflictError` and the CLI's separate artifact path are both covered.
7. Parity: skipped (`phases.parity` is false).
8. No `⚠️ unverified` markers.
9. No material omission found.
10. Merge/supersede: not applicable (no `existing_doc`).

## Should Fix (non-blocking)
- **The retryable-publish claim is incomplete.** The `### app` bullet on `_run` says a `RetryableError` raised by `publish` "propagates and releases the attempt". That holds only while `attempt < info.max_attempts`. On the last attempt, `_attempt` (in `src/scenewise/app/delivery.py`) instead writes a terminal `FAILED` record with `error_code: attempts_exhausted` and `result_uri: null`. Correction: append "(on the last attempt the job ends `failed` / `attempts_exhausted` instead)".
- **The description of `tests/unit/test_mapping.py` is narrow.** The `### tests` bullet describes it only as `result_uri` round-tripping. The file also pins `result_json` directly (`test_result_succeeded`, `test_result_skipped_and_failed`, `test_result_ignores_other_stages`, `test_result_without_media_or_stages`), and those tests are central to this feature. Correction: mention them.

## Observation outside this document
- `docs/skeleton-notes.md` (review-r1 fix row 1) says the "two `..` spellings" of a cross-job overwrite "now end `failed` / `uri_not_allowed`". The code does not support that for `{root}/artifacts/../state/victim`: it is accepted and writes under `state/victim/attacker/`. This document describes the code correctly. The skeleton note, and possibly the security property it claims, needs attention elsewhere.
