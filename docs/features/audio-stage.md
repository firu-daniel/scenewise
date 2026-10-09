# Audio Stage

> Turns one audio or video file into a normalised 16 kHz mono `pcm_s16le` WAV and publishes it as `audio.wav` next to the job's `result.json`.

## Business behaviour
- **The capability.** A request asks for the `audio` stage (wire name `"audio"`). scenewise fetches the input through the input store, probes it with ffprobe, extracts the first audio stream with ffmpeg and publishes the track. The skeleton wires only this stage. The others (captions, summary, chapters, moderation, labels) come with roadmap items 1-4 (`src/scenewise/domain/jobs.py` (`StageName`); `src/scenewise/app/stages.py` module docstring). `docs/skeleton-notes.md` rows A1 and A2 list it as a departure from `ARCHITECTURE.md`. Roadmap item 1 decides whether it stays.
- **Always offered.** `audio` needs only the media tool, so every deployment offers it (`src/scenewise/app/deps.py` (`enabled_stages`)). It is also the default of `ServiceSettings.required_stages`. Because `enabled_stages` always includes `StageName.AUDIO`, the `required_stages` check (`stage_unavailable`) can never fail for `audio` today. The start-up failure that actually applies is a missing or too-old ffmpeg: `find_binaries` runs first and raises `ConfigurationError` with `ffmpeg_unavailable` or `ffmpeg_too_old` (`src/scenewise/service/config.py` (`ServiceSettings`); `src/scenewise/service/bootstrap.py` (`build_dependencies`); `src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`)).
- **Input kinds accepted on the wire:** `{"kind": "file", "uri": ...}` or `{"kind": "none"}`, or no `audio` key at all (`src/scenewise/app/contract/requests.py` (`AudioInputV1`)). Segment lists and HLS playlists exist in the domain but cannot be requested yet (see Technical implementation).
- **Flows and outcomes** (`src/scenewise/app/runner.py` (`_audio_stage`); `src/scenewise/app/audio.py` (`acquire_audio`)):
  - File with an audio stream: the stage is `succeeded`. Over HTTP, `stages.audio.uri` points at `{prefix}/a{attempt}/audio.wav` (`src/scenewise/app/publish.py` (`publish`)). Over the CLI it is the absolute `file://` URI of `DIR/audio.wav` (`src/scenewise/service/cli.py` (`analyse`)). `media` holds the probe result (`duration_s`, `has_audio`, `has_video`).
  - File with no audio stream: the stage is `skipped` with reason `no_audio_stream`. `media` is still reported, and no WAV is written.
  - `kind: "none"` or no `audio` input: the stage is `skipped` with reason `no_audio_stream`, `media` is `null`, and nothing is fetched or probed.
  - A skip is not a failure. The job ends `succeeded`, not `partial` (`src/scenewise/domain/results.py` (`job_state`)).
- **Failure as the caller sees it.** Acquisition runs **before** any stage, outside the per-stage error boundary, so its errors fail the **whole job**, not just the stage. The job record ends `failed` with the error code (`src/scenewise/app/delivery.py` (`_run`)). The CLI exits with `EXIT_FAILED` (`src/scenewise/service/cli.py` (`analyse`)). Codes that can arise:
  - `uri_not_allowed`: not a `file://` URI, or a path outside `inputs.local_roots` or inside the state or artifact roots (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`)).
  - `input_unavailable`: the path is not an existing regular file, which includes a path that is a directory (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore.materialise`)).
  - `corrupt_media`: ffprobe or ffmpeg exits non-zero, the probe JSON is unreadable or has no duration (`src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool._media`, `_media_info`)).
  - `deadline_exceeded`: either the attempt budget ran out (`src/scenewise/app/runner.py` (`remaining`), or the `audio_track` timeout derived from the deadline), or ffprobe ran past the fixed `PROBE_TIMEOUT_S` (60 s), which does not depend on the attempt deadline. A slow probe therefore fails the job with `deadline_exceeded` even when attempt budget remains (`src/scenewise/adapters/media/ffmpeg.py` (`_run`, `PROBE_TIMEOUT_S`, `FfmpegMediaTool.probe`)).
  - `unsupported_media`: segments or a manifest reached the use case (domain-only today).
- The HTTP service has no `file://` input root by default (`inputs.local_roots` is empty), so it accepts file inputs only after `SCENEWISE_INPUTS__LOCAL_ROOTS` is configured. The CLI adds the given file's directory as a root (`src/scenewise/service/config.py` (`InputSettings`, `Settings` with `env_prefix="SCENEWISE_"` and `env_nested_delimiter="__"`); `src/scenewise/service/cli.py` (`_with_local_root`)).

## Invoked from
- **HTTP push:** `POST /v1/jobs` → `src/scenewise/service/http/push.py` → `src/scenewise/app/delivery.py` (`handle_delivery` → `_run` → `run_job` → `publish`).
- **CLI:** `scenewise analyse FILE --out DIR [--stage audio]`. `audio` is the default when no `--stage` is given (`src/scenewise/service/cli.py` (`main`, `analyse`)). The CLI writes `DIR/audio.wav` itself and prints the result document. It keeps no job record and does not call `publish`.

## Technical implementation
### domain
- `src/scenewise/domain/inputs.py` (`AudioSource`): the union `AudioFile | AudioSegments | AudioManifest | NoAudio`.
  - `AudioFile(uri)` is the only shape that is fetched today.
  - `AudioSegments` enforces "exactly one of `segment_uris` and `list_uri`" in `__post_init__`.
  - `AudioManifest(uri, rendition)` is for HLS.
- `src/scenewise/domain/jobs.py` (`StageName.AUDIO`, `SkipReason.NO_AUDIO_STREAM`, `Job.audio`).
- `src/scenewise/domain/plan.py` (`PREREQUISITES`, `ordered`): `AUDIO` needs `Needs.AUDIO`. `_ORDER` is enum order, so `audio` runs first.
- `src/scenewise/domain/media.py` (`MediaInfo`): `duration`, `has_audio`, `has_video`, `width`, `height`.
- `src/scenewise/domain/results.py` (`Analysis.audio_wav`): the WAV bytes held in memory, about 32 kB per second of audio (`docs/skeleton-notes.md` A2). `Skipped`, `Succeeded` and `Failed` are the outcomes.
- The input shapes carry no wire names: `kind`, `mime` and `reason` live only in `src/scenewise/app/contract/requests.py` (`src/scenewise/domain/inputs.py` module docstring). Stage and skip names are different: `StageName` values are the wire names, and `SkipReason` values such as `no_audio_stream` reach the wire unchanged (`src/scenewise/domain/jobs.py` (`StageName`); `src/scenewise/app/contract/mapping.py` (`_stage_fields`)).

### app
- `src/scenewise/app/audio.py` (`acquire_audio`, `AcquiredAudio`): a context manager that matches on the source and always ends in at most one `MediaTool.audio_track` call:
  - `AudioFile`: `store.materialise(uri)` → `media.probe(path)`. If `has_audio` is false, it yields `AcquiredAudio(media=info, track=None)`. Otherwise it yields the track from `media.audio_track([path], deadline=...)`. The track path is valid only inside the context.
  - `AudioSegments | AudioManifest`: raises `UnsupportedMediaError(code="unsupported_media")`.
  - `NoAudio | None`: yields `None`.
- `src/scenewise/app/runner.py` (`run_job`): opens `acquire_audio(job.audio, store=deps.inputs, media=deps.media, deadline=...)` around the stage loop. It calls `remaining(deadline)` before each stage, and keeps the `AUDIO` stage's bytes as `Analysis.audio_wav`.
- `src/scenewise/app/runner.py` (`_dispatch`, `_audio_stage`, `_run_stage`):
  - `_dispatch` routes `StageName.AUDIO` to `_audio_stage`.
  - `_audio_stage` returns `Skipped(NO_AUDIO_STREAM)` when there is no track, and otherwise `Succeeded()` plus `stages.audio(track)`.
  - `_run_stage` turns a non-retryable error inside a stage into `Failed`. A `RetryableError` is re-raised.
- `src/scenewise/app/stages.py` (`audio`): `track.read_bytes()`, nothing more.
- `src/scenewise/app/publish.py` (`publish`, `attempt_prefix`, `AUDIO_FILE_NAME`, `WAV_MEDIA_TYPE`): writes `{prefix}/a{attempt}/audio.wav` (`audio/wav`) through `deps.store`, only when `audio_wav` is not `None`, then `result.json`.
- `src/scenewise/app/delivery.py` (`artifacts_prefix`, `job_prefix`): `{prefix}` is `{state_prefix}/{job_id}` by default, or `{delivery.artifacts.uri_prefix}/{job_id}`. That prefix may not point into the state prefix (`uri_not_allowed`).
- `src/scenewise/app/deps.py` (`Dependencies.inputs` vs `Dependencies.store`): inputs are read through `inputs` only. The WAV is written through `store` only.
- **Wire contract:**
  - `src/scenewise/app/contract/requests.py` (`AudioFileV1`, `NoAudioV1`, `AudioInputV1`): a `kind`-discriminated union, `extra="forbid"`.
  - `src/scenewise/app/contract/mapping.py` (`_audio`): maps to the domain. It **drops** `AudioFileV1.mime` and `NoAudioV1.reason`; neither reaches the domain.
  - `src/scenewise/app/contract/results.py` (`AudioStageV1`, `StageResultsV1`, `ProbedMediaV1`): `AudioStageV1` = `status` / `reason` / `error` + `uri`.
  - `src/scenewise/app/contract/mapping.py` (`result_json`, `_stage_fields`): fills `stages.audio` only when `audio` was requested, and adds `timings_ms["audio"]`.
- Result shape (`result.json`, audio part):
  ```
  "media":  {"duration_s": float, "has_audio": bool, "has_video": bool} | null
  "stages": {"audio": {"status": "succeeded"|"skipped"|"failed",
                       "reason": str|null, "error": ErrorInfoV1|null,
                       "uri": "{prefix}/a{attempt}/audio.wav" (HTTP)
                              | "file:///…/DIR/audio.wav" (CLI) | null}}
  "timings_ms": {"audio": int}
  ```

### adapters
- `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool.probe`): `ffprobe -show_format -show_streams` as JSON, parsed by `_media_info`. Timeout is the fixed `PROBE_TIMEOUT_S` (60 s), not the attempt deadline; running past it raises `deadline_exceeded`.
  - `has_audio` is true if any stream has `codec_type == "audio"`.
  - Video streams that are only attached pictures (`attached_pic`) are ignored.
  - A missing `format.duration` is `corrupt_media`.
- `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool.audio_track`): works in a `scenewise-audio-` temp directory.
  - Several parts are concatenated byte-wise into `joined`.
  - Then `-map 0:a:0 -vn -ac AUDIO_CHANNELS -ar AUDIO_SAMPLE_RATE -c:a pcm_s16le -map_metadata -1 -fflags +bitexact -f wav` → `track.wav`.
  - Timeout = `deadline - time.monotonic()`.
- `src/scenewise/adapters/media/ffmpeg.py` (`_PROTOCOLS`, `DEMUXERS`, `_file`): every input is a local `file:` path under `-protocol_whitelist file,pipe` and a demuxer whitelist, so ffmpeg never fetches anything itself or follows an HLS playlist.
- `src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`): resolves ffmpeg and ffprobe at start-up and requires ffmpeg major ≥ `media.min_major` (default 6, `src/scenewise/service/config.py`).
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.materialise`, `LocalBlobStore._path`): the only input store today. It yields the file in place, after the allow-list and exclusion check.

### service
- `src/scenewise/service/bootstrap.py` (`_stores`, `build_dependencies`):
  - Builds the input store as `LocalBlobStore(roots=settings.inputs.local_roots, excluded=outputs)`, kept separate from the output store.
  - Builds `FfmpegMediaTool`.
  - Checks `required_stages` against `enabled_stages`.
  - Only `file://` state prefixes are supported (`store_unavailable` otherwise).
- `src/scenewise/service/cli.py` (`analyse`): builds `Job(audio=AudioFile(uri=media.as_uri()))`, writes `out/AUDIO_FILE_NAME` and calls `mapping.result_json` with `FIRST_ATTEMPT`.

### package
- `src/scenewise/ports.py` (`MediaTool`, `BlobStore`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`): the port contract is "ONE 16 kHz mono `pcm_s16le` WAV, valid inside the context".
  - Undecodable input → `corrupt_media`.
  - Out of time → `deadline_exceeded`.
  - Disallowed URI → `uri_not_allowed`.
  - Missing input → `input_unavailable`.

### tests
- `tests/unit/test_audio.py`: `acquire_audio` branches.
- `tests/unit/test_runner.py`: success, `no_audio_stream` skips, and stage availability.
- `tests/unit/test_publish.py`: `a{attempt}/audio.wav` and `audio/wav`.
- `tests/unit/test_mapping.py`: the `stages.audio` document.
- `tests/unit/test_delivery.py`: artifact under `state/j-1/a1/`.
- `tests/fakes.py` (`FakeMediaTool`, `InMemoryBlobStore`, `wav_bytes`).
- `tests/contract/mediatool_contract.py` (`test_audio_track_is_16k_mono_s16`).
- `tests/contract/test_mediatool_ffmpeg.py`: concatenation, a file without audio, and an HLS playlist that is refused.
- `tests/e2e/test_cli.py` (`test_analyse_extracts_the_audio_track`).
- `tests/e2e/test_http.py` (`test_job_runs_to_a_terminal_record`, `test_video_without_audio`, `test_corrupt_media_fails_the_job`): HTTP end-to-end: WAV under `a1/`, no-audio skip, corrupt media fails the job.
- `tests/e2e/test_isolation.py` (`test_cross_job_read_is_refused`, `test_cross_job_overwrite_is_refused`): cross-job read and overwrite are refused (`uri_not_allowed`).
- Fixtures: `tests/fixtures/clip.mp4`, `tests/fixtures/silent.mp4`, `tests/fixtures/tone.m4a`, made by `tests/fixtures/generate.sh`.

### general
- `README.md`: CLI usage, artifacts under `…/{job_id}/a{attempt}/`. Callers follow `result_uri` and never build the path.
- `docs/skeleton-notes.md`: rows A1 and A2 (the stage's existence; `audio_wav` held in memory).

### Backend surface
- **`POST /v1/jobs`** (`src/scenewise/service/http/routes.py`; `src/scenewise/service/http/push.py`): request `JobRequestV1` with `stages` containing `"audio"` and `audio: AudioFileV1 | NoAudioV1 | null` → `JobStatusV1`.
  - Side effects: writes `audio.wav` and `result.json` under `{prefix}/a{attempt}/`, and the job record carries `result_uri`.
  - **reachable? ✅** (Cloud Tasks push; `tests/e2e/test_http.py`).
- **`scenewise analyse`**: local file → `result.json` on stdout plus `DIR/audio.wav`. **reachable? ✅**
- **`AudioSegments` / `AudioManifest` acquisition**: **reachable? ❌**. No wire model produces them (`src/scenewise/app/contract/requests.py` has only `AudioFileV1`, `NoAudioV1`), and `acquire_audio` raises `unsupported_media`. This is a deliberate scope cut until roadmap item 1.

## Anchor files
- `src/scenewise/app/audio.py` (`acquire_audio`): acquisition: materialise, probe, extract
- `src/scenewise/app/runner.py` (`run_job`, `_dispatch`, `_audio_stage`, `_run_stage`): stage loop and outcomes
- `src/scenewise/app/stages.py` (`audio`): the stage body
- `src/scenewise/app/publish.py` (`publish`, `AUDIO_FILE_NAME`): writes `audio.wav`
- `src/scenewise/app/delivery.py` (`_run`, `artifacts_prefix`): the HTTP path's run + publish and the `{prefix}`
- `src/scenewise/app/deps.py` (`Dependencies`, `enabled_stages`): stores and stage availability
- `src/scenewise/app/contract/requests.py` (`AudioFileV1`, `NoAudioV1`): request inputs
- `src/scenewise/app/contract/results.py` (`AudioStageV1`): result entry
- `src/scenewise/app/contract/mapping.py` (`_audio`, `result_json`): wire ↔ domain
- `src/scenewise/domain/inputs.py` (`AudioSource`): input union
- `src/scenewise/domain/jobs.py` (`StageName`, `SkipReason`): names
- `src/scenewise/domain/plan.py` (`PREREQUISITES`): order and needs
- `src/scenewise/domain/results.py` (`Analysis`): `audio_wav`
- `src/scenewise/ports.py` (`MediaTool`, `AUDIO_SAMPLE_RATE`): port contract
- `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool`): ffprobe and ffmpeg
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): input allow-list
- `src/scenewise/service/bootstrap.py` (`build_dependencies`): wiring
- `src/scenewise/service/cli.py` (`analyse`): CLI entry
- `src/scenewise/service/config.py` (`ServiceSettings`, `InputSettings`): `required_stages`, `local_roots`
- `tests/unit/test_audio.py`, `tests/unit/test_runner.py`, `tests/contract/mediatool_contract.py`, `tests/e2e/test_cli.py`: coverage

## Related
- [[job-delivery]] · [[artifact-publishing]] · [[input-blob-store]] · [[media-tool-port]] · [[captions-stage]]
