# CLI analyse Command

> One-line: `scenewise analyse FILE --out DIR` runs the requested stages on one local media file, writes `audio.wav` into `DIR` and prints the v1 result document on stdout. It keeps no job record and publishes nothing to the job store.

## Business behaviour

- **Commands.** `scenewise --version` prints the installed distribution's version and exits 0. `scenewise analyse FILE --out DIR [--stage NAME ...]` is the only subcommand. A subcommand is required (`src/scenewise/service/cli.py` (`_parser`)). The module docstring says `run-job --job-uri` and `calibrate` "come later". Neither exists in the parser.
- **Stage selection.** You can repeat `--stage`, and argparse accepts all six `StageName` values (`audio`, `captions`, `summary`, `chapters`, `moderation`, `labels`). With no `--stage` the command runs `audio` only (`src/scenewise/service/cli.py` (`main`)). Duplicates collapse into a `frozenset`. This deployment offers only `audio` (`src/scenewise/app/deps.py` (`enabled_stages`), called with every back end `None` in `src/scenewise/service/bootstrap.py` (`build_dependencies`)). Any other stage therefore fails the whole run with `stage_unavailable`.
- **Input gating.** The file path is resolved. Its parent directory is added to `inputs.local_roots` for this run only (`src/scenewise/service/cli.py` (`_with_local_root`)). The input store still excludes the state prefix and every `service.artifact_roots` directory. A file under one of those is refused with `uri_not_allowed`. A missing file is `input_unavailable` (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`, `LocalBlobStore.materialise`)).
- **Success.**
  - With an audio stream: ffmpeg extracts a 16 kHz mono `pcm_s16le` WAV. The command creates `DIR` (with parents) if needed, writes `DIR/audio.wav` (overwriting any existing file) and prints the result with `stages.audio.status = "succeeded"` and `stages.audio.uri` set to the absolute `file://` URI of that WAV.
  - With no audio stream: the audio stage is `skipped` with reason `no_audio_stream`. The command creates no `DIR` and writes no file, and still exits 0 (`tests/e2e/test_cli.py` (`test_analyse_video_without_audio`)).
- **Partial.** An error inside a stage fails only that stage. The document then has `status: "partial"` and the stage `failed` with an `error` object, and the exit code is still **0** (`src/scenewise/app/runner.py` (`_run_stage`); `src/scenewise/domain/results.py` (`job_state`)).
- **Failure (exit codes)** (`src/scenewise/service/cli.py` (`EXIT_OK`, `EXIT_FAILED`, `EXIT_CONFIGURATION`)):
  - `0`: a result document was printed (`succeeded` or `partial`).
  - `1`: a `ScenewiseError` that is not a configuration error stopped the job before or between stages. Examples are `corrupt_media` from probe or extraction, `stage_unavailable`, `uri_not_allowed`, `input_unavailable` and `deadline_exceeded`. stderr gets one line, `scenewise: {code}: {detail}`, and stdout gets nothing.
  - `2`: a `ConfigurationError` from bootstrap (`ffmpeg_unavailable`, `ffmpeg_too_old`, `store_unavailable`, `stage_unavailable` for an unsatisfiable `service.required_stages`), or settings that fail validation. For invalid settings the stderr line is `scenewise: invalid settings: <field paths>`. It names the fields and never their values. argparse usage errors also exit 2 (argparse's own `SystemExit`).
  - Not caught: an exception outside `ScenewiseError` raised after `run_job` returns, for example an `OSError` while creating `DIR` or writing `audio.wav`. It escapes `analyse` as a Python traceback (`src/scenewise/service/cli.py` (`analyse`): the write sits after the `try` block).

## Invoked from

- The console script `scenewise`, declared in `pyproject.toml` `[project.scripts]` as `scenewise = "scenewise.service.cli:main"`.
- `python -m scenewise`, through `src/scenewise/__main__.py`, which calls `raise SystemExit(main())`. The e2e tests use this path (`tests/e2e/test_cli.py` (`_cli`)).
- No other caller. Nothing imports `scenewise.service` (`.claude/context/service.md` § Responsibility).

## Technical implementation

### domain
- `src/scenewise/domain/jobs.py` (`Job`, `JobSpec`, `StageName`, `job_id`, `FIRST_ATTEMPT`): the CLI builds `Job(id=job_id("cli"), spec=JobSpec(stages=…), audio=AudioFile(uri=…))`. Every CLI run has the fixed id `cli`, no `external_ref`, no callback and no `artifacts_prefix`.
- `src/scenewise/domain/inputs.py` (`AudioFile`): the only input kind the CLI produces. The URI is `media.resolve().as_uri()`.
- `src/scenewise/domain/plan.py` (`ordered`, `unavailable`): run order, and the check that rejects stages this deployment does not offer.
- `src/scenewise/domain/results.py` (`Analysis`, `StageOutcome`, `Failed`, `Skipped`, `job_state`): what `run_job` returns. `Analysis.audio_wav` holds the WAV bytes the CLI writes out.
- `src/scenewise/domain/errors.py` (`ScenewiseError`, `ConfigurationError`): the split between exit code 1 and exit code 2.

### app
- `src/scenewise/app/runner.py` (`run_job`): the use case the CLI calls. It raises `InputError(code="stage_unavailable")` for a stage that is not offered, opens `acquire_audio` (fed through `deps.inputs`), runs each stage with `remaining(deadline)` between stages, and returns `Analysis`. It never touches the job store.
- `src/scenewise/app/audio.py` (`acquire_audio`): materialises the file through the input store, probes it, and extracts the track once. No audio stream gives `track=None`, which leads to the `no_audio_stream` skip.
- `src/scenewise/app/stages.py` (`audio`): reads the extracted WAV bytes.
- `src/scenewise/app/contract/mapping.py` (`result_json`): serialises the result document. The CLI passes `attempt=FIRST_ATTEMPT` (1), `external_ref=()` and `audio_uri` (the written file's URI, or `None`). The output is `JobResultV1` pretty-printed with `indent=2`. The CLI decodes it and appends a newline.
- `src/scenewise/app/contract/results.py` (`JobResultV1`, `StageResultsV1`, `AudioStageV1`, `ProbedMediaV1`, `ErrorInfoV1`): the document shape (below).
- `src/scenewise/app/publish.py` (`AUDIO_FILE_NAME`): the CLI imports only this constant, `audio.wav`. It does **not** call `publish`, so no `result.json` is written anywhere.

Result document printed on stdout (shape read off `JobResultV1`):

```
{ "schema_version": "1", "scenewise_version": "<installed version>",
  "job_id": "cli", "external_ref": {}, "status": "succeeded" | "partial",
  "media": {"duration_s", "has_audio", "has_video"} | null,
  "stages": {"audio": {"status", "reason", "error", "uri"}},
  "timings_ms": {"audio": <int>}, "attempt": 1 }
```

### adapters
- `src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`): a start-up check. It resolves `ffmpeg` and `ffprobe` with `shutil.which`, requires major version `min_major` (default 6), and otherwise raises `ffmpeg_unavailable` / `ffmpeg_too_old`, which give exit 2.
- `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool.probe`, `FfmpegMediaTool.audio_track`): `ffprobe` JSON probe, then `ffmpeg` extraction to a temporary `track.wav` (`AUDIO_CHANNELS`, `AUDIO_SAMPLE_RATE` from `src/scenewise/ports.py`). A non-zero exit gives `corrupt_media`. A timeout gives `deadline_exceeded`.
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the input store's allow-list and exclusion check. The output store is also built, but the CLI never writes through it.
- `src/scenewise/adapters/media/images.py` (`PillowImageReader`): built into `Dependencies`. No CLI stage uses it.

### service
- `src/scenewise/service/cli.py` (`main`): parses argv (argparse `SystemExit` for `--version` and usage errors), builds `Settings()` (a `ValidationError` gives exit 2), calls `logs.configure(settings.log)`, defaults the stages to `[StageName.AUDIO]`, and calls `analyse`.
- `src/scenewise/service/cli.py` (`_parser`): `--version` (`action="version"`, `__version__`), the `analyse` subparser with positional `file`, required `--out` and repeatable `--stage` (`dest="stages"`, `type=StageName`).
- `src/scenewise/service/cli.py` (`_with_local_root`): `model_copy(update=…)` that appends the media's directory to `inputs.local_roots`. `Settings` itself is never mutated.
- `src/scenewise/service/cli.py` (`analyse`): builds the dependencies, the `Job` and the deadline (`time.monotonic() + settings.service.attempt_budget_s`, default 1500 s), then calls `run_job`. It maps a `ScenewiseError` to the stderr line and exit code, writes `audio.wav` when present, and prints `result_json`.
- `src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`): the composition root. It checks the ffmpeg binaries, derives `enabled_stages` (only `audio`), enforces `service.required_stages`, and builds the two stores. `state_prefix` must be `file://` (default `./.scenewise/state` under the working directory). Any other scheme is `store_unavailable`, even though the CLI writes no record.
- `src/scenewise/service/config.py` (`Settings`, `InputSettings`, `ServiceSettings`, `MediaSettings`, `LogSettings`): environment `SCENEWISE_*` with `__` between groups. The settings the CLI reads are `media.ffmpeg`, `media.ffprobe`, `media.min_major`, `inputs.local_roots`, `service.state_prefix`, `service.artifact_roots`, `service.required_stages`, `service.attempt_budget_s` and `log`. `ServiceSettings._timing` validates the timing invariant (a violation gives exit 2).
- `src/scenewise/service/logs.py` (`configure`): structlog and stdlib logs go to **stderr** (JSON by default), so stdout carries only the result document.

### package
- `src/scenewise/__main__.py`: the `python -m scenewise` entry. It is exempt from the layer check.
- `src/scenewise/__init__.py` (`__version__`): `importlib.metadata.version("scenewise")`, which `--version` prints.
- `src/scenewise/ports.py` (`AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`, `MediaTool`, `BlobStore`): the WAV format constants and the ports the run goes through.

### tests
- `tests/e2e/test_cli.py`: runs the CLI as a subprocess (`_cli`). It covers audio extraction and the WAV format (`test_analyse_extracts_the_audio_track`), the no-audio skip with no `--out` directory (`test_analyse_video_without_audio`), exit 1 for `corrupt_media` and `stage_unavailable` (`test_analyse_failures`), exit 2 for a missing ffmpeg and for invalid settings (`test_missing_ffmpeg_is_a_configuration_error`, `test_invalid_settings_are_a_configuration_error`), and `--version` (`test_version`).
- `tests/e2e/conftest.py` (`inputs`): copies `clip.mp4`, `silent.mp4` and `tone.m4a` from `tests/fixtures/` (made by `tests/fixtures/generate.sh`) and writes a `broken.mp4`.
- No unit test covers `src/scenewise/service/cli.py`. `service` is outside the 100% unit-tier core (`.claude/context/service.md` § Done).

### general
- `pyproject.toml` `[project.scripts]`: the `scenewise` console script.
- `README.md` "Run the audio stage": the documented invocation `uv run scenewise analyse path/to/video.mp4 --out out`.
- `ARCHITECTURE.md` §13 "Ownership on the delivery path": "the CLI's `analyse` mode calls `run_job` and prints, without publishing."

### Backend surface
- There is no HTTP or remote operation. The CLI runs in-process. Its only external calls are the `ffprobe` and `ffmpeg` subprocesses (`src/scenewise/adapters/media/ffmpeg.py` (`_run`)), each with an argv list and a timeout, and restricted to `file,pipe` protocols and the `DEMUXERS` list. **reachable? ✅** through `run_job` → `acquire_audio`.
- The job store's delivery protocol (`src/scenewise/app/delivery.py` (`handle_delivery`), `publish`) is **not** reached from the CLI by design.

## Anchor files
- `src/scenewise/service/cli.py` (`main`, `analyse`, `_parser`, `_with_local_root`): the command
- `src/scenewise/__main__.py`: `python -m scenewise` entry
- `src/scenewise/__init__.py` (`__version__`): version printed by `--version`
- `pyproject.toml` (`[project.scripts]`): console-script entry
- `src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`): composition root and start-up checks
- `src/scenewise/service/config.py` (`Settings`): environment settings
- `src/scenewise/service/logs.py` (`configure`): stderr logging
- `src/scenewise/app/runner.py` (`run_job`, `_run_stage`, `remaining`): the use case
- `src/scenewise/app/audio.py` (`acquire_audio`): input materialise, probe and extract
- `src/scenewise/app/stages.py` (`audio`): the audio stage
- `src/scenewise/app/deps.py` (`Dependencies`, `enabled_stages`): port bundle and offered stages
- `src/scenewise/app/publish.py` (`AUDIO_FILE_NAME`): output file name
- `src/scenewise/app/contract/mapping.py` (`result_json`): result serialisation
- `src/scenewise/app/contract/results.py` (`JobResultV1`): result document model
- `src/scenewise/domain/jobs.py` (`Job`, `StageName`, `job_id`, `FIRST_ATTEMPT`): job values
- `src/scenewise/domain/plan.py` (`ordered`, `unavailable`): stage order and availability
- `src/scenewise/domain/results.py` (`Analysis`, `job_state`): run outcome
- `src/scenewise/domain/errors.py` (`ConfigurationError`, `InputError`): error categories behind the exit codes
- `src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`, `FfmpegMediaTool`): ffmpeg / ffprobe
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): input allow-list
- `tests/e2e/test_cli.py` (`_cli`): end-to-end tests
- `tests/e2e/conftest.py` (`inputs`): fixture media directory

## Related
- [[http-push-jobs]] · [[audio-stage]] · [[composition-root]] · [[settings]] · [[blob-store-input-output-split]] · [[result-document]] · [[error-categories]]
