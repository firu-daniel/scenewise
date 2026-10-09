# Storage and URI Policy

> One-line: every object scenewise reads or writes is a URI handled by a `BlobStore`. Inputs and outputs go through two separate stores, each with its own allow-list of roots. The job record and the artifacts sit at fixed paths under the state prefix or a job-scoped artifact folder, and the only store built today is the single-host `file://` `LocalBlobStore`.

## What it is & why

- **No database.** All durable state is plain objects in a `BlobStore`: the job record `{state_prefix}/{job_id}/status.json` and one artifact folder per attempt, `{prefix}/a{attempt}/` (`ARCHITECTURE.md` §7 "**Storage.**"). Records are written only under compare-and-swap, using the store's per-object `generation` token. That token is what makes the record a safe lock across deliveries (see [[job-lifecycle-and-timing]]).
- **URI-addressed.** Use cases pass URI strings. They never pass paths. The port is meant to cover local files, GCS and read-only https (`src/scenewise/ports.py` (`BlobStore`) docstring "local files | GCS | https read-only"). Only `file://` is implemented. `gs://` and `https://` exist only in the design (`ARCHITECTURE.md` §10 "**URI policy.**"; `docs/skeleton-notes.md` A6).
- **Two stores, so one job cannot touch another job's files.** `Dependencies.store` holds records and artifacts and can write. `Dependencies.inputs` holds request inputs and is never allowed to see the state prefix or an artifact root. With one shared store, a request could name another job's `audio.wav` as its input, or point its artifacts at another job's folder. That was review r1, finding 1, and the split fixed it (`docs/skeleton-notes.md` A6 and the review r1 row "1 (must) `file://` allow-list bypass").

## How it works

### The port: `src/scenewise/ports.py`
- `BlobStore` (`Protocol`) has three methods:
  - `materialise(uri)` is a context manager that yields a local `Path` holding the object's bytes. ffmpeg only ever sees such a path (`src/scenewise/app/audio.py` (`acquire_audio`)).
  - `read(uri)` returns a `Blob`, or `None` when the object is absent.
  - `write(uri, data, *, content_type, if_generation=None)` returns the new generation, which is always > 0.
- `Blob` is a frozen dataclass: `data: bytes` and `generation: int`, "store-assigned compare-and-swap token".
- `ABSENT_GENERATION` (`0`) is the generation of an object that does not exist. With `if_generation=0` the write creates the object only if it is absent. With any other integer the write happens only if that integer is the current generation. Any mismatch raises `WriteConflictError`. With `if_generation=None` the write is unconditional, and the artifacts are written that way (`src/scenewise/app/publish.py` (`publish`)).
- Errors in the contract:

  | Situation | Error |
  |---|---|
  | URI outside the store's allow-list | `InputError(code="uri_not_allowed")` |
  | `materialise` of a missing input | `InputError(code="input_unavailable")` |
  | Failed CAS precondition | `WriteConflictError` (not a `ScenewiseError`) |
  | Transient I/O failure (adapter convention) | `RetryableError(code="storage_unavailable")`, `detail` = the exception's type name only (`.claude/context/adapters.md` "transient storage or network I/O") |

### Path builders (the only code that composes storage URIs)
- `src/scenewise/app/delivery.py` (`job_prefix`) returns `f"{state_prefix.rstrip('/')}/{job}"`, the job's folder.
- `src/scenewise/app/delivery.py` (`record_uri`) returns `{job_prefix}/status.json` (`RECORD_FILE_NAME`). Both `handle_delivery` (through `_Delivery.uri`) and `job_status` use it. `service` never builds this path (`.claude/context/service.md` "`service` never builds the record's path").
- `src/scenewise/app/delivery.py` (`artifacts_prefix`) decides the artifact folder:
  - With no requested prefix, the artifacts share the record's folder: `{state_prefix}/{job_id}`.
  - A requested `delivery.artifacts.uri_prefix` (`src/scenewise/app/contract/requests.py` (`ArtifactSinkV1`), mapped onto `Job.artifacts_prefix` by `src/scenewise/app/contract/mapping.py` (`to_domain`)) is first stripped of a trailing `/`. If it equals the state prefix or starts with `{state_prefix}/`, the call raises `InputError(code="uri_not_allowed")` "artifacts may not be written under the state prefix". Otherwise it becomes `{uri_prefix}/{job_id}`. The job id is always appended, so a caller's prefix is a parent folder, never the job's folder itself.
- `src/scenewise/app/publish.py` (`attempt_prefix`) returns `{prefix}/a{attempt}`. Inside it `publish` writes `audio.wav` (`AUDIO_FILE_NAME`, `audio/wav`) when the analysis produced one, then `result.json` (`RESULT_FILE_NAME`, `JSON_MEDIA_TYPE`), and returns the result URI. That URI goes into the terminal record's `result_uri` (see [[job-results-and-artifacts]]).
- Job ids are safe as a single path segment. `JOB_ID_PATTERN` is `^[A-Za-z0-9._:-]{1,200}$` and `job_id` also rejects `.` and `..` (`src/scenewise/domain/jobs.py` (`job_id`)). `job_status` treats an id that fails this check as "no job" and never builds a URI from it.

Resulting layout under a `file://` state prefix (sidecars described below):
```
{state_prefix}/{job_id}/status.json          # job record (CAS-written)
{state_prefix}/{job_id}/a{n}/result.json     # default artifacts, one folder per attempt
{state_prefix}/{job_id}/a{n}/audio.wav
{uri_prefix}/{job_id}/a{n}/...               # when delivery.artifacts.uri_prefix is set
```

### Settings that define the roots: `src/scenewise/service/config.py`
- `ServiceSettings.state_prefix` is a URI string. Its default is `_default_state_prefix`, which gives `<cwd>/.scenewise/state` as a `file://` URI. Env: `SCENEWISE_SERVICE__STATE_PREFIX`.
- `ServiceSettings.artifact_roots: tuple[Path, ...] = ()` lists the directories a requested `uri_prefix` may point into, besides the state prefix's own job folders.
- `InputSettings.local_roots: tuple[Path, ...] = ()` lists the directories that `file://` inputs may come from. It is empty by default, so an HTTP deployment accepts no `file://` input until one is configured. The CLI appends the directory of the file it is given (`src/scenewise/service/cli.py` (`_with_local_root`)).

### Composition: `src/scenewise/service/bootstrap.py` (`_stores`)
- It matches on the scheme of `state_prefix`:
  - `case "file"` builds `outputs = [state path, *artifact_roots]` and returns two stores:
    - `LocalBlobStore(roots=outputs)`, which becomes `Dependencies.store`.
    - `LocalBlobStore(roots=inputs.local_roots, excluded=outputs)`, which becomes `Dependencies.inputs`.
  - Any other scheme raises `ConfigurationError(code="store_unavailable")` "no store for {scheme}:// state_prefix yet; use file://". The process then never starts (`tests/e2e/test_bootstrap.py` uses `gs://bucket/state`).
- The output store has no `excluded` list. Whether a write lands is decided by the store's allow-list together with the lexical state-prefix check in `artifacts_prefix`. See the gotcha about `..` below.
- Readers and writers:
  - `src/scenewise/app/delivery.py` reads and writes the record through `deps.store` and passes `deps.store` to `publish`. This module owns every record write.
  - `src/scenewise/app/runner.py` passes `deps.inputs` to `acquire_audio`, which calls `materialise` on the request's `AudioFile.uri`.
  - `src/scenewise/service/http/routes.py` (`get_job`) passes `state.deps.store` and `settings.service.state_prefix` to `job_status`.
  - `src/scenewise/service/http/app.py` (`create_app`) copies `state_prefix` into `DeliveryPolicy`.

### The local adapter: `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`)
- **URI check** (`_path`): the scheme must be `file` and the host empty or `localhost`, else `uri_not_allowed` "only file:// URIs are local". So `gs://`, `https://`, `file://otherhost/...` and relative strings are all refused (`tests/contract/test_blobstore_local.py` (`test_only_local_file_uris`)). The path is then `resolve()`d, which collapses `..` and follows symlinks. It must lie under some root and under no `excluded` path, else `uri_not_allowed` "path is not allowed". Every method runs this check before it touches the file system.
- **Sidecars** in the object's own directory:
  - `.{name}.meta.json` holds `{"generation": n, "content_type": "..."}` (`_meta`).
  - `.{name}.lock` is the target of an exclusive `fcntl.flock` taken around each read and write (`_locked`). It serialises threads and processes on one host. Lock files are never deleted.
  - `.{name}.<random>` is the temporary file `_replace` writes, fsyncs and renames over the target.
- **Generation** (`_generation`):
  - A missing file is `ABSENT_GENERATION`.
  - A file with no sidecar is `_HAND_PLACED_GENERATION` (1), for example an input copied in by hand.
  - Otherwise the generation is the sidecar's `generation`.
  - `write` checks `if_generation` against this value under the lock and writes `current + 1`.
- **Write order**: the sidecar is replaced first, then the data (comment "Generation first"). After a crash between the two, the generation has advanced while the data is still old, so any token handed out earlier no longer matches.
- **Reads create nothing**: if the file is absent, `read` returns `None` before it takes the lock (comment "reads never create directories or lock files"). `materialise` raises `input_unavailable` when the path is not a regular file, and otherwise yields the file itself without copying.
- **Errors**: an `OSError` in `read` or `write` becomes `RetryableError(code="storage_unavailable", detail=type(e).__name__)`. On HTTP this is answered with a `Retry-After` (`src/scenewise/service/http/routes.py` (`RETRY_AFTER_STORAGE_S`); `src/scenewise/service/http/push.py` (`RETRY_AFTER_BUSY_S`)).

## Where it's used
- [[job-submission]]: claims the record and writes the terminal record through `deps.store`. A `uri_not_allowed` from either store ends the job as `failed`.
- [[job-status]]: `job_status` reads `record_uri` through the output store.
- [[job-results-and-artifacts]]: `publish` writes the attempt folder.
- [[audio-stage]]: `acquire_audio` materialises the input through `deps.inputs`.
- [[cli-analyse]]: adds the media file's parent to `local_roots`. It writes `audio.wav` straight to `--out` with `Path.write_bytes`, not through a store, and writes no record.
- [[job-lifecycle-and-timing]]: the generation token is the attempt's fencing token.

## Gotchas / constraints
- **A `uri_prefix` with `..` can land artifacts inside the state tree.** The state-prefix check in `artifacts_prefix` compares strings only. `LocalBlobStore._path` resolves `..` later, and the output store's roots include the state path. A prefix such as `{artifact_root_parent}/artifacts/../state/victim` passes the check, and the attempt folder resolves to `{state}/victim/{job_id}/a1/`. I confirmed this by calling `artifacts_prefix`, `attempt_prefix` and `LocalBlobStore.write` directly with an attacker job id: the write succeeded at `state/victim/attacker/a1/result.json`. It cannot overwrite another job's `status.json` or `result.json`: the job id is appended and is one safe segment, and reusing the victim's id hits the victim's record (a digest `Conflict` → rejected). It does write into another job's folder, though. `tests/e2e/test_isolation.py` (`test_cross_job_overwrite_is_refused`) asserts only that nothing was overwritten. It does not assert `uri_not_allowed` for this spelling, although `docs/skeleton-notes.md` (review r1 row 1) says both `..` spellings "now end `failed` / `uri_not_allowed`". The spelling `{state}/../state/victim` is refused, because it starts with `{state}/`.
- **The local store is single-host only** (D14, `docs/decisions/initial-research.md`). `flock` does not work across network file systems, so they are unsupported. The directory is not fsynced after the rename (`docs/skeleton-notes.md` review r1 row 17).
- **`file://` inputs over HTTP are off by default.** `local_roots` is `()`. The input store also refuses the state prefix and artifact roots even when a configured input root contains them (`tests/e2e/test_isolation.py` (`test_cross_job_read_is_refused`)).
- **`WriteConflictError` is not a `ScenewiseError`.** Use cases must catch it explicitly. `delivery.py` turns it into `job_in_progress` / `TryLater`.
- **Artifact writes are unconditional.** A superseded attempt can still write its own `a{n}/` folder. Only the record is fenced, and the record's `result_uri` names the winning attempt.
- **A new store keeps the input/output split.** A planned GCS store or a `by_scheme.py` router must apply the same allow-list and the same exclusion of output roots from input reads, including for URIs inside segment lists and playlists (`ARCHITECTURE.md` §10 "**URI policy.**"; `.claude/context/adapters.md` `## Storage`). `by_scheme.py` does not exist yet.
- The in-memory fake `tests/fakes.py` (`InMemoryBlobStore`) allows only URIs that start with its `prefix` (default `mem://`). It passes the same contract suite, `tests/contract/blobstore_contract.py` (`BlobStoreContract`).

## Anchor files
- `src/scenewise/ports.py` (`BlobStore`): port contract; also `Blob`, `WriteConflictError`, `ABSENT_GENERATION`
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the only store; allow-list, sidecars, flock, CAS
- `src/scenewise/service/bootstrap.py` (`_stores`): builds the input and output stores from settings
- `src/scenewise/service/config.py` (`ServiceSettings`): `state_prefix`, `artifact_roots`; also `InputSettings` (`local_roots`)
- `src/scenewise/app/delivery.py` (`record_uri`): record path; also `job_prefix`, `artifacts_prefix`, `job_status`
- `src/scenewise/app/publish.py` (`attempt_prefix`): attempt folder and the `publish` file names
- `src/scenewise/app/audio.py` (`acquire_audio`): materialises inputs through the input store
- `src/scenewise/app/contract/requests.py` (`ArtifactSinkV1`): wire `uri_prefix`
- `src/scenewise/domain/jobs.py` (`job_id`): job ids are one safe path segment
- `src/scenewise/service/cli.py` (`_with_local_root`): CLI widens the input roots
- `tests/contract/blobstore_contract.py` (`BlobStoreContract`): shared port contract suite
- `tests/contract/test_blobstore_local.py`: local-store specifics (schemes, `..`, exclusion, concurrency)
- `tests/e2e/test_isolation.py`: cross-job read and overwrite probes
- `tests/fakes.py` (`InMemoryBlobStore`): in-memory store for unit tests
- `docs/skeleton-notes.md`: A6 (two stores) and the review r1 rows

## Related
- [[layering-and-ports]] · [[job-lifecycle-and-timing]] · [[job-results-and-artifacts]] · [[job-status]] · [[job-submission]] · [[audio-stage]] · [[cli-analyse]] · [[configuration]] · [[error-model]] · [[media-processing]]
