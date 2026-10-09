# Review 0: docs/concepts/storage-and-uri-policy.md

verdict: PASS

## Must Fix

None.

## Verified

- Anchors: every path in `## Anchor files` and inline exists, and every named symbol resolves in its cited file. Checked: `BlobStore`, `Blob`, `WriteConflictError`, `ABSENT_GENERATION` (ports.py); `LocalBlobStore`, `_path`, `_meta`, `_locked`, `_generation`, `_replace`, `_HAND_PLACED_GENERATION` (local.py); `_stores` (bootstrap.py); `ServiceSettings`, `InputSettings`, `_default_state_prefix` (config.py); `job_prefix`, `record_uri`, `artifacts_prefix`, `job_status`, `RECORD_FILE_NAME`, `_Delivery.uri` (delivery.py); `attempt_prefix`, `publish`, `AUDIO_FILE_NAME`, `RESULT_FILE_NAME` (publish.py); `acquire_audio`; `ArtifactSinkV1.uri_prefix`; `to_domain` mapping; `job_id`, `JOB_ID_PATTERN`; `_with_local_root`; `get_job`, `RETRY_AFTER_STORAGE_S`, `RETRY_AFTER_BUSY_S`; `create_app` -> `DeliveryPolicy`; `test_only_local_file_uris`, `test_cross_job_overwrite_is_refused`, `test_cross_job_read_is_refused`; `InMemoryBlobStore` (`mem://`); `BlobStoreContract`; the `gs://bucket/state` case in test_bootstrap.py.
- Quoted strings resolve: "only file:// URIs are local", "path is not allowed", "artifacts may not be written under the state prefix", "no store for {scheme}:// state_prefix yet; use file://", "Generation first", "reads never create directories or lock files", "local files | GCS | https read-only", "store-assigned compare-and-swap token".
- Line numbers: both detectors return zero hits; the section references (§7, §10) are not line coordinates.
- Store split, CAS semantics, sidecar layout, write order, error mapping, the `failed` outcome on `uri_not_allowed` (`_run`), and the `WriteConflictError` -> `job_in_progress` / `TryLater` path all match the source.
- `..` gotcha: reproduced independently. Calling `artifacts_prefix` + `attempt_prefix` + `LocalBlobStore.write` with prefix `{tmp}/artifacts/../state/victim` and job `attacker` writes `state/victim/attacker/a1/result.json`. `test_cross_job_overwrite_is_refused` asserts only that the victim's result is unchanged and checks `victim/a1/attacker`, not `victim/attacker/a1`. The contradiction with docs/skeleton-notes.md review r1 row 1 is stated accurately.
- Parity (check 7): skipped, because `phases.parity` is false.

## Notes (non-blocking)

- The gotcha in `## Gotchas / constraints` describes a real defect in the source: a lexical state-prefix check runs before path resolution. That is a code issue for the project, not a documentation one.
