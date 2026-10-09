# Review 0: docs/features/job-status.md

mode: catalog · iteration: 0 · verdict: PASS

## Must Fix

None.

## What was verified

1. **Anchors resolve.** Every `## Anchor files` path exists, and each named symbol greps inside its file: `get_job`, `RETRY_AFTER_STORAGE_S`, `problem_response`, `http_status`, `_STATUSES`, `create_app`, `ServiceState`, `ServiceSettings`, `_default_state_prefix`, `_stores`, `job_status`, `record_uri`, `job_prefix`, `RECORD_FILE_NAME`, `record_from_json`, `status_json`, `JobRecordV1`, `JobStatusV1`, `StatusV1`, `JSON_MEDIA_TYPE`, `SCHEMA_VERSION_V1`, `job_id`, `JobRecord`, `JobState`, `wire_status`, `WireStatus`, `JobNotFoundError`, `RetryableError`, `InternalError`, `BlobStore`, `Blob`, `LocalBlobStore.read`, and every test function named. The prose paths also resolve from the repo root: `ARCHITECTURE.md` §7, `README.md`, `docs/research/q8a-architecture-layout.md` §6.2, `.claude/context/domain.md`, `tests/fakes.py` `InMemoryBlobStore`. The q8a file shows as `Q8a-…` on this case-insensitive disk, but git tracks it as `q8a-…`, so the citation is correct.
2. **No line numbers.** Detector 1 found one hit, `localhost:8080` in the README curl example. That is a port, so it is a value and stays. Detector 2 found nothing.
3. **Backend surface.** `GET /v1/jobs/{job}` is registered on `router` (`routes.py`), and `create_app` includes it with `include_router`. `tests/e2e/test_http.py` exercises it. `reachable? ✅` is correct. The request, response and side-effect claims match the source: 200 `JSON_MEDIA_TYPE`, 404 from a `None` result, 503 with `Retry-After` set to `ceil(5.0)`, a 500 `invariant_violation`, and a 500 `unexpected` for any other exception.
4. **Data shapes.** The `JobRecordV1` fields, `extra="forbid"`, the `JobStatusV1` fields, the `StatusV1` and `WireStatus` literals, `JOB_ID_PATTERN` with its `.`/`..` rejection, and the record URI `{state_prefix.rstrip('/')}/{job}/status.json` all match the source exactly. `lease_until` and `request_digest` are correctly described as left out of the response.
5. **Gating, sync and clock.** The `wire_status` rule (running only while `lease_until > now`) matches. `now=time.time()` is taken in `get_job`. `get_job` does not touch `ServiceState.limiter`, which is correct. The local store returns `None` on `not path.is_file()` before taking the lock, and raises `OSError` → `RetryableError("storage_unavailable")` inside the lock. `test_storage_down_is_503` asserts a 404 on the GET, as the Gotcha says.
6. **Research depth.** Provenance is traced to the writers: `_attempt` writes the claim, `_release` sets `lease_until=now`, and `_finish`/`_give_up` write the terminal state. All writes go through `_Delivery.write` with `if_generation`. `publish` makes `result_uri` `{prefix}/a{attempt}/result.json`. `record_to_json` is called only from `delivery.py`, and the CLI keeps no record, so "only delivery writes the record" holds.
7. **Parity.** Skipped, because `phases.parity` is `false`.
8. **⚠️ unverified.** The document uses no markers, and every claim checked resolved.
9. **Omissions.** No flow, operation or stored-data set central to the feature is missing.
10. **Merge/supersede.** Not applicable, because no `existing_doc` was passed.

## Observations (non-blocking, no change required)

- The `tests` sub-section says the `test_delivery.py` tests "all run over `InMemoryBlobStore`". `test_record_lives_in_status_json_under_the_job_folder` uses no store; it only calls `record_uri`. This is a minor imprecision.
- The 404 bullet gives `..` as an example of an invalid id, next to a citation of `test_unknown_job_is_404`. That e2e test covers `nope` and `a%20b`. `..` is covered by the unit test `test_job_status_of_no_such_job_is_none`, which the document also cites.
- An edge case the document does not mention: `record_from_json` re-validates `doc.job_id` with `job_id()`, and `JOB_ID_PATTERN` admits `..`. A hand-placed record whose `job_id` is `.`/`..` would raise `ValueError` and come back as a 500 `unexpected` rather than `invariant_violation`. This is not material to the feature.
