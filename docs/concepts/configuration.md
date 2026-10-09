# Configuration and Settings

> One-line: every deployment setting is one frozen pydantic-settings `Settings` object, read from `SCENEWISE_*` environment variables once per entry point, then validated, checked against the system and turned into adapters by the composition root.

## What it is & why
- scenewise has a single configuration source: the process environment. `Settings` reads variables with the prefix `SCENEWISE_` and `__` between a group and its field, for example `SCENEWISE_SERVICE__MAX_JOBS=2` (`src/scenewise/service/config.py` (`Settings`, module docstring)).
- No file is loaded. `SettingsConfigDict` sets no `env_file`, and `.env.example` says so: "scenewise reads only SCENEWISE_* variables, from the environment; it loads no file". To use `.env.example`, copy it and export it into the shell yourself.
- Configuration lives in the `service` layer and nowhere else. `Settings` is built once in the entry point and passed to `bootstrap`. Adapters never see it (`ARCHITECTURE.md` §10). Use cases get only the values they need, as plain arguments or small dataclasses (`src/scenewise/app/delivery.py` (`DeliveryPolicy`)). That keeps `domain` and `app` free of environment access.
- Bad configuration fails at start-up. Field types and cross-field invariants are validated when `Settings` is built. Binaries, the store scheme and required stages are checked when `build_dependencies` runs. Either way the process never starts serving with a broken configuration.

## How it works
1. **Groups.** `Settings(BaseSettings)` has four fields. Each one is a group model that subclasses `_Group` (`ConfigDict(extra="forbid", frozen=True)`), so an unknown field in a group is a validation error and no group can be mutated. `Settings` is `frozen=True` as well (`src/scenewise/service/config.py` (`_Group`, `Settings`)).

   | Group · class | Field = default | Env variable | Read by |
   |---|---|---|---|
   | `media` · `MediaSettings` | `ffmpeg = "ffmpeg"`, `ffprobe = "ffprobe"` (names on `PATH` or absolute paths) | `SCENEWISE_MEDIA__FFMPEG`, `SCENEWISE_MEDIA__FFPROBE` | `build_dependencies` → `find_binaries` |
   | | `min_major = 6` (`PositiveInt`; "Ubuntu 24.04 ships 6.1") | `SCENEWISE_MEDIA__MIN_MAJOR` | `find_binaries` |
   | `inputs` · `InputSettings` | `local_roots: tuple[Path, ...] = ()` | `SCENEWISE_INPUTS__LOCAL_ROOTS='["/srv/media"]'` (JSON array, as in `README.md` "Run the audio stage") | `_stores` (the input store's roots) |
   | `service` · `ServiceSettings` | `max_jobs = 1` | `SCENEWISE_SERVICE__MAX_JOBS` | `create_app` (`anyio.CapacityLimiter`) |
   | | `max_body_bytes = 1_048_576` | `…__MAX_BODY_BYTES` | `push` (`read_body` limit) |
   | | `attempt_budget_s = 1500` | `…__ATTEMPT_BUDGET_S` | `create_app` (`DeliveryPolicy.attempt_budget`, `Watchdog` limit), CLI `analyse` (deadline) |
   | | `watchdog_grace_s = 120` | `…__WATCHDOG_GRACE_S` | `create_app` (`Watchdog` limit = budget + grace) |
   | | `dispatch_deadline_s = 1800`, `lease_margin_s = 120` | `…__DISPATCH_DEADLINE_S`, `…__LEASE_MARGIN_S` | `_timing`. `lease_s` is used by `push._admitted` (`AttemptInfo.lease`) |
   | | `probe_period_s = 10`, `probe_failure_threshold = 3` | `…__PROBE_PERIOD_S`, `…__PROBE_FAILURE_THRESHOLD` | only `_timing` (see Gotchas) |
   | | `max_attempts = 5` | `…__MAX_ATTEMPTS` | `push._admitted` (`AttemptInfo.max_attempts`) |
   | | `state_prefix` = `file://{cwd}/.scenewise/state` (`_default_state_prefix`) | `…__STATE_PREFIX` | `_stores`, `create_app` (`DeliveryPolicy`), `get_job` |
   | | `artifact_roots: tuple[Path, ...] = ()` | `…__ARTIFACT_ROOTS` | `_stores` (the output store's roots) |
   | | `required_stages: frozenset[StageName] = {StageName.AUDIO}` | `…__REQUIRED_STAGES` (⚠️ unverified: assumed to be a JSON array of wire names such as `["audio"]`, by pydantic-settings' handling of complex fields. No test or document sets it from the environment) | `build_dependencies` |
   | `log` · `LogSettings` | `level: Literal["DEBUG","INFO","WARNING","ERROR"] = "INFO"`, `format: Literal["json","console"] = "json"` | `SCENEWISE_LOG__LEVEL`, `SCENEWISE_LOG__FORMAT` | `logs.configure` |

2. **Invariant and derived value.** `ServiceSettings._timing` (`model_validator(mode="after")`) requires `attempt_budget_s + watchdog_grace_s + probe_period_s * probe_failure_threshold < dispatch_deadline_s`. With the defaults that is 1500 + 120 + 30 = 1650 < 1800. If the check fails it raises `ValueError` with the numbers in the message. The property `ServiceSettings.lease_s` = `dispatch_deadline_s + lease_margin_s` (1920 by default; `tests/unit/test_service.py` (`test_timing_invariant`)). [[job-lifecycle-and-timing]] explains why the invariant holds.
3. **Built once per entry point.**
   - CLI: `main` calls `Settings()`. A `pydantic.ValidationError` is written to stderr as one line, `scenewise: invalid settings: <dotted field locations>`, and the process exits with `EXIT_CONFIGURATION` (2). Then `main` calls `logs.configure(settings.log)` and passes `settings` to `analyse` (`src/scenewise/service/cli.py` (`main`); `tests/e2e/test_cli.py` (`test_invalid_settings_are_a_configuration_error`)).
   - HTTP: `create_app(settings: Settings | None = None)`. Inside the lifespan it resolves `settings or Settings()`, calls `logs.configure`, and builds one `ServiceState` (`settings`, `deps`, `policy`, `limiter`, `watchdog`) on `app.state.scenewise` (`src/scenewise/service/http/app.py` (`create_app`); `src/scenewise/service/http/state.py` (`ServiceState`)). Request handlers read settings from there: `state.settings.service.max_body_bytes`, `.lease_s`, `.max_attempts` and `.state_prefix` (`src/scenewise/service/http/push.py` (`push`, `_admitted`); `src/scenewise/service/http/routes.py` (`get_job`)). Because the environment is read in the lifespan and not at import, tests pass a `Settings(...)` built in code (`tests/e2e/test_http.py`; `tests/e2e/test_isolation.py` (`_client`)).
4. **Per-invocation overrides go through `model_copy`, never mutation.** The CLI appends the media file's directory to `inputs.local_roots` with `settings.model_copy(update={"inputs": ...})` (`src/scenewise/service/cli.py` (`_with_local_root`)).
5. **Composition root.** `build_dependencies(settings)` calls `find_binaries(ffmpeg=…, ffprobe=…, min_major=…)` with keyword arguments read off `settings.media`. It computes `enabled_stages`, raises `ConfigurationError(code="stage_unavailable")` if `required_stages - stages` is not empty, and builds the two stores in `_stores`. `_stores` matches on the `state_prefix` scheme. For `file` it creates an output `LocalBlobStore(roots=[state dir, *artifact_roots], fenced=(state dir,))` and an input `LocalBlobStore(roots=local_roots, excluded=outputs)`. Any other scheme raises `ConfigurationError(code="store_unavailable")` (`src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`); `tests/e2e/test_bootstrap.py` (`test_configuration_errors`)).
6. **Start-up failures.** `find_binaries` raises `ConfigurationError` with code `ffmpeg_unavailable` (a binary not found, or its version unreadable) or `ffmpeg_too_old` (`src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`)). In the CLI, `analyse` catches it and exits 2 with `scenewise: <code>: <detail>`. In HTTP, `create_app`'s lifespan has no handler around `Settings()` or `build_dependencies`, so either error propagates out of start-up and the app never serves. `problems.http_status` maps `ConfigurationError` to 500 only if one reaches a response (`tests/unit/test_service.py` (`test_http_status`)).

## Where it's used
- [[cli-analyse]]: `main` builds `Settings`, `_with_local_root` adds the file's directory, and `attempt_budget_s` sets the deadline. Configuration failures exit with code 2.
- [[job-submission]]: `max_body_bytes`, `max_jobs` (limiter), `lease_s`, `max_attempts`, `attempt_budget_s`, `state_prefix`.
- [[job-status]]: `state_prefix` locates `{state_prefix}/{job_id}/status.json`.
- [[job-results-and-artifacts]]: `state_prefix` and `artifact_roots` decide where artifacts may be written.
- [[health-probes]]: the watchdog limit `attempt_budget_s + watchdog_grace_s`, and the probe fields that `_timing` checks.
- [[audio-stage]]: `inputs.local_roots` gates `file://` inputs, and `media.*` selects ffmpeg/ffprobe.
- [[storage-and-uri-policy]], [[media-processing]], [[logging]], [[job-lifecycle-and-timing]], [[stages-and-outcomes]]: the mechanisms each group configures.

## Gotchas / constraints
- **Only four groups exist today:** `media`, `inputs`, `service`, `log`. The other groups in `ARCHITECTURE.md` §10 (asr, captions, llm, vision, labels, storage, delivery) are not built. The module docstring says they "arrive with the features that read them" (`src/scenewise/service/config.py` module docstring; `docs/skeleton-notes.md` A7). If you set a variable for a missing group, such as `SCENEWISE_ASR__BACKEND`, nothing reads it (⚠️ unverified: pydantic-settings' default `extra` handling of unknown prefixed env vars was not tested here).
- **No `SecretStr` field exists yet.** `ARCHITECTURE.md` §10 and `.claude/context/service.md` require secrets to be `SecretStr`. The rule first applies when a group with a credential arrives.
- **`required_stages` must be a subset of the enabled stages.** The skeleton enables only `audio`, so adding any other stage stops start-up with `stage_unavailable`.
- **`state_prefix` must be `file://` for now.** `gs://…` gives `store_unavailable`. The default is computed from the current working directory each time `Settings()` is built (`Field(default_factory=_default_state_prefix)`). A CLI run and a service started from different directories therefore use different state folders unless the variable is set.
- **`inputs.local_roots` is empty by default.** The HTTP service then rejects every `file://` input with `uri_not_allowed` until it is set. The input store also excludes the state directory and every artifact root (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`)).
- **`artifact_roots` is enforced by the store, not the use case.** `artifacts_prefix` refuses, with `InputError(code="uri_not_allowed")`, a `uri_prefix` whose job folder `{uri_prefix}/{job_id}` normalises to the state prefix or under it, and a `uri_prefix` with a query, a fragment or a relative path. The output store's roots refuse any other location outside `[state dir, *artifact_roots]`. Its fence refuses a path that reaches the state directory through a symlink or another spelling of a parent directory. The limit that remains is in [[storage-and-uri-policy]] "Gotchas / constraints" (`src/scenewise/app/delivery.py` (`artifacts_prefix`); `src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`); `src/scenewise/service/bootstrap.py` (`_stores`)).
- **`probe_period_s` and `probe_failure_threshold` do not configure probing.** They describe the platform's probe settings so that `_timing` can check the invariant, and nothing else reads them (`docs/skeleton-notes.md` A7).
- **Some values are deliberately not settings.** The Retry-After values (`RETRY_AFTER_BUSY_S`, `RETRY_AFTER_STORAGE_S`) and ffmpeg's `PROBE_TIMEOUT_S` are module constants. Whether the Retry-After values should become settings is recorded as open in `.claude/context/service.md` "Not determined".
- **Rule for new settings:** a deployment-tunable value or platform limit becomes a validated field (`PositiveInt`, `Literal`) of a group, a cross-field rule becomes a `model_validator(mode="after")`, and a derived value becomes a property. Adapters receive keyword arguments read off `Settings`, never `Settings` itself (`.claude/context/service.md` "Settings"; `.claude/context/conventions.md` "Constants and configuration").

## Anchor files
- `src/scenewise/service/config.py` (`Settings`, `_Group`, `MediaSettings`, `InputSettings`, `ServiceSettings`, `LogSettings`, `_default_state_prefix`): the settings model, defaults, `_timing` and `lease_s`
- `src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`): turns settings into adapters and start-up checks
- `src/scenewise/service/http/app.py` (`create_app`): HTTP entry point that builds `Settings` and `ServiceState` in the lifespan
- `src/scenewise/service/http/state.py` (`ServiceState`): holds `settings` for the life of the process
- `src/scenewise/service/http/push.py` (`push`, `_admitted`): reads `max_body_bytes`, `lease_s`, `max_attempts` per request
- `src/scenewise/service/http/routes.py` (`get_job`): reads `state_prefix`
- `src/scenewise/service/cli.py` (`main`, `_with_local_root`, `analyse`): CLI entry point, invalid-settings handling, exit code 2
- `src/scenewise/service/logs.py` (`configure`): consumes `LogSettings`
- `src/scenewise/app/delivery.py` (`DeliveryPolicy`, `artifacts_prefix`): the narrowed settings the use case receives
- `src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`): `media.*` start-up check
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): enforces `local_roots` / `artifact_roots` / state exclusion, and the output store's state fence
- `.env.example`: commented examples of the skeleton's variables
- `tests/unit/test_service.py` (`test_timing_invariant`, `test_settings_from_the_environment`): invariant and env parsing
- `tests/e2e/test_bootstrap.py` (`test_configuration_errors`): `store_unavailable`, `stage_unavailable`
- `tests/e2e/test_cli.py` (`test_invalid_settings_are_a_configuration_error`): CLI exit 2 on invalid settings

## Related
- [[layering-and-ports]] · [[job-lifecycle-and-timing]] · [[storage-and-uri-policy]] · [[media-processing]] · [[logging]] · [[error-model]] · [[stages-and-outcomes]] · [[cli-analyse]] · [[job-submission]] · [[health-probes]]
