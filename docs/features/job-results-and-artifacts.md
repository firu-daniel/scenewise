# Job Results and Artifacts

> What a finished job leaves behind: one `result.json` and, when one was produced, the normalised `audio.wav`. Both are written into an attempt-scoped folder, and the job record's `result_uri` points to them.

## Business behaviour
- **What a caller gets.** A job that ends `succeeded` or `partial` leaves an attempt folder `{artifacts_prefix}/a{attempt}/` holding:
  - `result.json`, the `JobResultV1` document;
  - `audio.wav`, the audio stage's 16 kHz mono `pcm_s16le` track, written only when the stage produced one (`src/scenewise/app/publish.py` (`publish`, `AUDIO_FILE_NAME`, `RESULT_FILE_NAME`)).
- **How a caller finds them.** The terminal job record carries `result_uri`, the full URI of that attempt's `result.json`. The caller sees it in the `JobStatusV1` body that `POST /v1/jobs` answers with and that `GET /v1/jobs/{id}` returns (`src/scenewise/app/contract/mapping.py` (`status_json`)). Callers follow `result_uri` and never build the path themselves (`README.md` "follow the record's `result_uri`, never build the path."). Inside `result.json`, `stages.audio.uri` points to the track.
- **Where the folder goes:**
  - No `delivery.artifacts.uri_prefix` in the request → `{state_prefix}/{job_id}`, beside the record's `status.json`.
  - A requested `uri_prefix` → `{uri_prefix}/{job_id}`. The job id is always appended, so one job cannot write into another job's folder (`src/scenewise/app/delivery.py` (`artifacts_prefix`)).
- **Gating:**
  - A `uri_prefix` whose job folder equals the state prefix, or lies under it once both are normalised (dot segments, repeated slashes, percent-escapes, scheme and host case, `localhost`), or one with a query, fragment or relative path, fails the job with `uri_not_allowed` (`src/scenewise/app/delivery.py` (`artifacts_prefix`)).
  - Any other prefix must resolve below the state prefix's directory or one of `service.artifact_roots`. A path that resolves below the state directory must also be spelt below the configured state prefix, so a prefix that reaches it through a symlink or a parent alias is refused too. Otherwise the output store refuses the first write with `uri_not_allowed` (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`); `src/scenewise/service/bootstrap.py` (`_stores`)).
  - Either refusal ends the job `failed` with `error_code: uri_not_allowed`, and nothing is published.
- **Status inside `result.json`.** `status` is only ever `succeeded` or `partial`. It is `partial` when any stage `Failed`; a skip is not a failure (`src/scenewise/domain/results.py` (`job_state`)). A job that fails as a whole publishes nothing, and its record keeps `result_uri: null` (`src/scenewise/app/delivery.py` (`_run`, `_terminal`)).
- **Retries.** Every attempt writes to its own `a{n}/` folder. The terminal record's `result_uri` names the folder of the attempt that won (`ARCHITECTURE.md` §7 "names the winning attempt's files"). Folders from earlier attempts are never cleaned up.

## Invoked from
- **HTTP push:** `POST /v1/jobs` → `src/scenewise/service/http/push.py` (`_admitted`) → `src/scenewise/app/delivery.py` (`handle_delivery` → `_attempt` → `_run` → `publish`).
- **HTTP status read:** `GET /v1/jobs/{job}` → `src/scenewise/service/http/routes.py` (`get_job`) → `src/scenewise/app/delivery.py` (`job_status`). This route only reads `result_uri` back from the record.
- **CLI:** `scenewise analyse FILE --out DIR` → `src/scenewise/service/cli.py` (`analyse`). It does **not** call `publish`. It writes `DIR/audio.wav` itself (no `a{n}/` folder, no blob store) and prints the `result_json` document to stdout instead of storing it. It uses job id `cli`, attempt `FIRST_ATTEMPT` and an empty `external_ref`.

## Technical implementation
### domain
- `src/scenewise/domain/results.py` (`Analysis`): what publishing consumes — `job_id`, `media`, `outcomes`, and `audio_wav` (`None` when no track was produced).
- `src/scenewise/domain/results.py` (`job_state`): decides between `PARTIAL` and `SUCCEEDED`, for both `result.json` `status` and the terminal record state.
- `src/scenewise/domain/jobs.py` (`Job`): carries `artifacts_prefix`, the requested `uri_prefix` or `None`. `JobRecord` carries `result_uri`. `wire_status` maps the record onto the status a caller sees.
- The domain layer does no I/O and no path building.

### app
- `src/scenewise/app/publish.py` (`attempt_prefix`): builds `{prefix}/a{attempt}`, stripping a trailing `/` from `prefix`.
- `src/scenewise/app/publish.py` (`publish`):
  - Writes `audio.wav` first, with `WAV_MEDIA_TYPE` `audio/wav`, and only if `analysis.audio_wav` is set.
  - Then writes `result.json`, with `JSON_MEDIA_TYPE`, and returns its URI.
  - Neither write carries `if_generation`, so each one is an unconditional overwrite.
  - It never touches the job record.
- `src/scenewise/app/delivery.py` (`job_prefix`, `record_uri`, `artifacts_prefix`): the path rules. `RECORD_FILE_NAME` is `status.json`.
- `src/scenewise/app/delivery.py` (`_run`): order is parse → `run_job` → `publish` → a terminal record that carries `result_uri`. A `ScenewiseError` raised by `publish` (for example `uri_not_allowed`) ends the job `FAILED`. A `RetryableError` raised by `publish` (for example `storage_unavailable`) propagates and releases the attempt.
- `src/scenewise/app/delivery.py` (`_finish`): writes the terminal record with `if_generation=token`. On `WriteConflictError` this attempt's published artifacts are left behind, and no record refers to them.
- `src/scenewise/app/contract/mapping.py` (`result_json`):
  - Builds `JobResultV1` and serialises it with `model_dump_json(indent=2)`.
  - Only the `audio` stage is mapped into `StageResultsV1`, through `_stage_fields`.
  - `timings_ms` holds one entry per stage, `round(seconds * MS_PER_SECOND)`.
  - `scenewise_version` is the running `__version__`.
- Wire shapes (`src/scenewise/app/contract/results.py`):
  ```
  JobResultV1   { schema_version: "1", scenewise_version, job_id, external_ref: {str: str},
                  status: "succeeded"|"partial", media: ProbedMediaV1|null,
                  stages: StageResultsV1, timings_ms: {stage: int}, attempt: int }
  ProbedMediaV1 { duration_s: float, has_audio: bool, has_video: bool }
  StageResultsV1{ audio: AudioStageV1|null }        # grows a field per new stage
  AudioStageV1  { status: "succeeded"|"skipped"|"failed", reason, error: ErrorInfoV1|null, uri }
  ErrorInfoV1   { code, category: "input"|"retryable"|"internal", retryable, message, stage }
  ```
  Output documents only grow within `schema_version` "1", and clients ignore unknown fields (module docstring). The job-level `media` is `null` when the request had no audio input to probe. The stage-level `audio.uri` is `null` when no track was written. For a failed stage, `reason` holds the error code (`_stage_fields`), and `ErrorInfoV1.retryable` is always `false`.
- Request side (`src/scenewise/app/contract/requests.py`): `DeliveryV1` holds `artifacts: ArtifactSinkV1`, where `uri_prefix: str | None` has `min_length=1`. `src/scenewise/app/contract/mapping.py` (`to_domain`) copies it into `Job.artifacts_prefix`.
- The stored record (`src/scenewise/app/contract/records.py` (`JobRecordV1`)) has the field `result_uri: str | None`.
- Provenance of `audio_wav`: `MediaTool.audio_track` extracts the track inside `src/scenewise/app/audio.py` (`acquire_audio`). `src/scenewise/app/stages.py` (`audio`) reads its bytes. `src/scenewise/app/runner.py` (`run_job`) keeps the bytes from the `AUDIO` stage only and puts them on `Analysis.audio_wav`.
- **Edge cases:**
  - **Artifacts can be orphaned.** `publish` runs before the fenced terminal write. If that write loses (`WriteConflictError` in `_finish`), the files stay on disk and no record refers to them. A released attempt (a `RetryableError` such as `storage_unavailable` on the `result.json` write) can leave a half-written `a{n}/`, for example `audio.wav` without `result.json`.
  - **Other spellings of the state prefix are refused.** `artifacts_prefix` refuses `..` and similar spellings on the normalised URI, and the output store's fence refuses symlinks and parent aliases into the state directory; the remaining case-insensitive-file-system limit is in `docs/concepts/storage-and-uri-policy.md` (Gotchas).
  - `result.json` is pretty-printed (`indent=2`). The record and status documents are compact.
  - `external_ref` in `result.json` is the request's map, re-sorted by key on its way through `to_domain`.

### adapters
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the only `BlobStore` so far, `file://` URIs only.
  - It resolves each path and checks it against its `roots`. A path outside them is `uri_not_allowed`. The output store also fences the state directory: a path resolving into it must be spelt inside it, else `uri_not_allowed`.
  - Each write is atomic, keeps a sidecar `.name.meta.json` with the generation and content type, and takes an `flock` on `.name.lock`.
  - An `OSError` becomes `RetryableError(code="storage_unavailable")`.

### service
- `src/scenewise/service/config.py` (`ServiceSettings`) supplies two settings:
  - `state_prefix` defaults to `./.scenewise/state` as a `file://` URI (`_default_state_prefix`).
  - `artifact_roots` is the allow-list of directories that a `uri_prefix` may point into, and defaults to `()`.
  - Environment variables use the `SCENEWISE_` prefix with `__` between groups.
- `src/scenewise/service/bootstrap.py` (`_stores`) builds two stores:
  - the output store (`deps.store`) over the state directory plus `artifact_roots`, with the state directory fenced (`fenced=(state path,)`);
  - the input store (`deps.inputs`), which excludes both, so one job cannot read another job's `audio.wav` as its input.
  - A state prefix that is not `file://` is `ConfigurationError(code="store_unavailable")`.
- `src/scenewise/service/http/app.py` (`create_app`) passes `state_prefix` into `DeliveryPolicy`.

### package
- `src/scenewise/ports.py` (`BlobStore`): its `write(uri, data, *, content_type, if_generation=None)` contract is the seam `publish` writes through. Its documented failure for a URI outside the allow-list is `uri_not_allowed`.

### tests
- `tests/unit/test_publish.py`: the attempt prefix, publishing both files, and publishing without a track (only `result.json`).
- `tests/unit/test_delivery.py` (`test_first_delivery_runs_to_a_terminal_record`, `test_artifacts_go_to_the_requested_prefix`, `test_artifacts_never_go_under_the_state_prefix`): the path rules and `result_uri` in the record.
- `tests/unit/test_mapping.py`: `result_uri` round-tripping through the record and the status document.
- `tests/e2e/test_http.py`: the real `file://` layout under `{state}/{job_id}/a1/`.
- `tests/e2e/test_isolation.py`: cross-job reads and overwrites refused, job-scoped artifact roots, and a prefix outside every root refused.
- `tests/e2e/test_cli.py`: the CLI's `audio.wav` and the `stages.audio.uri` it prints.

### general
- `README.md` documents the layout. `ARCHITECTURE.md` §7 (steps 6–7) and §10 are the design. `docs/skeleton-notes.md` A6 records the input/output store split and the job-id suffix on `uri_prefix`.

### Backend surface
- **`POST /v1/jobs`**: `JobRequestV1` (optionally `delivery.artifacts.uri_prefix`) → `JobStatusV1` with `result_uri`. Side effects: `audio.wav` and `result.json` under `a{n}/`, plus the record. **reachable? ✅** (`src/scenewise/service/http/routes.py` (`post_job`)).
- **`GET /v1/jobs/{job}`**: no body → `JobStatusV1`, which repeats the stored `result_uri`. No side effects. **reachable? ✅** (`get_job`).
- There is no endpoint that serves artifact bytes. Callers read `result_uri` directly from the shared store.

## Anchor files
- `src/scenewise/app/publish.py` (`publish`, `attempt_prefix`): writes the attempt folder.
- `src/scenewise/app/delivery.py` (`artifacts_prefix`, `job_prefix`, `record_uri`, `_run`, `_finish`, `job_status`): path rules, orchestration, `result_uri`.
- `src/scenewise/app/contract/mapping.py` (`to_domain`, `result_json`, `_stage_fields`, `_media`, `status_json`): copies the request's prefix into the job and builds the documents.
- `src/scenewise/app/contract/results.py` (`JobResultV1`, `StageResultsV1`, `AudioStageV1`, `ProbedMediaV1`, `ErrorInfoV1`, `JobStatusV1`): output wire models.
- `src/scenewise/app/contract/requests.py` (`DeliveryV1`, `ArtifactSinkV1`): the request's artifact sink.
- `src/scenewise/app/contract/records.py` (`JobRecordV1`): the stored `result_uri`.
- `src/scenewise/app/runner.py` (`run_job`): builds `Analysis.audio_wav`.
- `src/scenewise/app/stages.py` (`audio`): the track's bytes.
- `src/scenewise/domain/results.py` (`Analysis`, `job_state`): the input to publishing and the partial/succeeded rule.
- `src/scenewise/domain/jobs.py` (`Job`, `JobRecord`, `wire_status`): `artifacts_prefix` and `result_uri` in the domain.
- `src/scenewise/ports.py` (`BlobStore`): the write seam.
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the allow-list and atomic writes.
- `src/scenewise/service/bootstrap.py` (`_stores`): the output/input store split.
- `src/scenewise/service/config.py` (`ServiceSettings`): `state_prefix`, `artifact_roots`.
- `src/scenewise/service/cli.py` (`analyse`): the CLI's separate artifact path.
- `src/scenewise/service/http/routes.py` (`get_job`): reads `result_uri` back.
- `tests/unit/test_publish.py`, `tests/unit/test_delivery.py`, `tests/e2e/test_isolation.py`, `tests/e2e/test_http.py`, `tests/e2e/test_cli.py`: behaviour pins.

## Related
- [[job-lifecycle-and-timing]] · [[audio-stage]] · [[storage-and-uri-policy]] · [[cli-analyse]] · [[wire-contract]]
