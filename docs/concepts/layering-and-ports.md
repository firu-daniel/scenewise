# Layering, Ports and the Composition Root

> One-line: scenewise is split into four import layers (`domain`, `ports`, `app`/`adapters`, `service`). Every bit of I/O and every model call goes through a `Protocol` port, and exactly one module, `service.bootstrap`, picks the adapters and bundles them into `Dependencies`.

## What it is & why

- **Layers.** A module may import only from the layers below it: `service > (adapters | app) > ports > domain`. `adapters` and `app` sit side by side and never import each other. Because of this rule, the use cases (`app`) can be tested against in-memory fakes, and heavy or optional SDKs stay in `adapters`, where only the composition root reaches them (`ARCHITECTURE.md` §3; `pyproject.toml` contract `name = "Layers: service > (adapters | app) > ports > domain"`).
- **Ports.** All the seams to I/O and to models are listed in one module, `src/scenewise/ports.py`. Each is a structural `typing.Protocol` whose docstring states its behavioural contract. The ports are synchronous on purpose: model work blocks, and each job runs in one worker thread (`src/scenewise/ports.py` module docstring "Ports are synchronous").
- **Composition root.** `src/scenewise/service/bootstrap.py` (`build_dependencies`) is the only factory. It turns `Settings` into concrete adapters, checks the system and the required stages, and returns one frozen `Dependencies` bundle. Every use case receives that bundle as a parameter. There is no DI container, no ABC port and no plugin entry point (`ARCHITECTURE.md` §14).

Layer membership, in the configured layer names:

| Layer | Path | Holds |
|---|---|---|
| `domain` | `src/scenewise/domain` | Values and pure functions. Stdlib only, no I/O. |
| `package` (import layer `ports`) | `src/scenewise/ports.py`, plus `src/scenewise/__init__.py` and `src/scenewise/__main__.py` | Every `Protocol`, plus `Blob`, `WriteConflictError` and the port constants. `__init__` holds `__version__` only. |
| `app` | `src/scenewise/app` | Use cases, the wire contract (`src/scenewise/app/contract/`) and the port bundle (`src/scenewise/app/deps.py`). |
| `adapters` | `src/scenewise/adapters` | Driven implementations of the ports, one subpackage per adapter kind (`src/scenewise/adapters/media/`, `src/scenewise/adapters/storage/`). |
| `service` | `src/scenewise/service` | The driving side (CLI, HTTP, settings, logs) and the composition root. No other layer imports it; only the layers-exempt `__main__` does. |

The harness's `package` layer is the import-linter `ports` layer plus the two top-level modules. `__main__` is exempt from the layers contract (`pyproject.toml` `exhaustive_ignores = ["__main__"]`). It only calls `service.cli.main` (`src/scenewise/__main__.py`).

## How it works

### Enforcement: import-linter contracts in `pyproject.toml` `[tool.importlinter]`
- **"Layers: service > (adapters | app) > ports > domain"** is a `layers` contract with `exhaustive = true`, so every top-level module of `scenewise` must be assigned to a layer.
- **"Adapter kinds are independent of each other"** is an `independence` contract over `scenewise.adapters.*`. A helper shared inside one kind stays inside that kind.
- **"Only the composition root imports adapters"** is a `protected` contract. `scenewise.adapters` may be imported only by `scenewise.service.bootstrap`.
- **"Domain and ports: stdlib only (q8a §1.5 rule 6, as an allow-list)"** and **"Use cases: stdlib, pydantic and structlog only (q8a §1.5 rule 6, as an allow-list)"** are custom `allowed_externals` contracts, implemented in `scripts/import_contracts.py` (`AllowedExternalsContract`). For each source module, the allow-list is the stdlib, the root package and the `allowed` list.
- **"Driving side imports no ML or cloud SDK"** is a `forbidden` contract on `scenewise.service`, with `allow_indirect_imports = true`, because bootstrap reaches those libraries through adapters by design.
- ruff `PLC0415` (function-local imports) is ignored for `src/scenewise/service/bootstrap.py` alone, with the comment "the only lazy imports in src" (`pyproject.toml` `[tool.ruff.lint.per-file-ignores]`).

### Ports: `src/scenewise/ports.py`
- There are ten `Protocol`s: `BlobStore`, `MediaTool`, `ImageReader`, `VoiceActivityDetector`, `LanguageIdentifier`, `SpeechRecognizer`, `TextGenerator`, `ImageModerator`, `ZeroShotLabeller` and `Notifier`. The same module holds the value `Blob`, the exception `WriteConflictError` and the constants `ABSENT_GENERATION`, `AUDIO_SAMPLE_RATE` and `AUDIO_CHANNELS`.
- Ports import only `domain` types and the stdlib. Their signatures use domain values such as `MediaInfo`, `Frame`, `Tile`, `TimeSpan`, `SpeechProbabilities`, `LabelScores` and `Callback`, never SDK types.
- Adapters satisfy a port **structurally**. `LocalBlobStore`, `FfmpegMediaTool` and `PillowImageReader` are plain classes that do not subclass the `Protocol`. mypy checks the match where `build_dependencies` passes them into `Dependencies`.
- Audio acquisition and publishing are **not** ports. They are plain `app` functions over `MediaTool` and `BlobStore`: `src/scenewise/app/audio.py` (`acquire_audio`) and `src/scenewise/app/publish.py` (`publish`). Frames are planned the same way (a planned `src/scenewise/app/frames.py`, per `ARCHITECTURE.md` §4), but that module is absent from the skeleton (`docs/skeleton-notes.md` A10).

### The bundle: `src/scenewise/app/deps.py`
- `Dependencies` is a frozen, slotted, keyword-only dataclass of long-lived port implementations. Nothing per job is stored in it. Its class docstring says `None` means the deployment does not offer that back end ("``None`` = not offered"). Its fields, with the comments as in the source:
  ```
  store: BlobStore            # job records and artifacts
  inputs: BlobStore           # request inputs only; never sees the state or artifact roots
  media: MediaTool
  images: ImageReader
  speech: Speech | None = None
  text: TextGenerator | None = None
  moderator: ImageModerator | None = None
  labeller: ZeroShotLabeller | None = None
  notifier: Notifier | None = None    # None until HTTP callbacks are built
  enabled_stages: frozenset[StageName]
  ```
- `Speech` groups `vad`, `lid` and `recognizer`, because the captions stage needs all three.
- `enabled_stages(*, speech, text, moderator, labeller)` works out which stages a deployment offers. `AUDIO` is always on, since it needs only the media tool. `CAPTIONS` needs `speech`. `SUMMARY` and `CHAPTERS` need `speech` and `text`. `LABELS` needs `labeller`. `MODERATION` needs `labeller` and `moderator`.

### The composition root: `src/scenewise/service/bootstrap.py`
1. `build_dependencies(settings)` first imports `FfmpegMediaTool`, `find_binaries` and `PillowImageReader` inside the function. It then calls `find_binaries(ffmpeg=…, ffprobe=…, min_major=…)`, which raises `ConfigurationError` `ffmpeg_unavailable` or `ffmpeg_too_old` (`src/scenewise/adapters/media/ffmpeg.py` `find_binaries`).
2. It calls `enabled_stages(speech=None, text=None, moderator=None, labeller=None)`, because no model back end is wired yet. If `settings.service.required_stages` names a stage outside the result, it raises `ConfigurationError(code="stage_unavailable")`, so the process never becomes ready.
3. `_stores(settings)` uses a `match` on the scheme of `settings.service.state_prefix`:
   - `case "file"` imports `LocalBlobStore` lazily and builds two stores. The output store gets `roots=[state path, *service.artifact_roots]`. The input store gets `roots=inputs.local_roots` and `excluded=outputs`, so even when an input root contains the state or artifact directories, inputs can never be read from there (`src/scenewise/adapters/storage/local.py` `LocalBlobStore.__init__`; `docs/skeleton-notes.md` A6).
   - Any other scheme raises `ConfigurationError(code="store_unavailable")`.
4. It returns `Dependencies(store=…, inputs=…, media=FfmpegMediaTool(ffmpeg=…, ffprobe=…), images=PillowImageReader(), enabled_stages=…)`. Adapters receive keyword arguments read off `Settings`, never `Settings` itself.

The module docstring gives the plan for extension: back ends behind an optional extra (asr, llm, vision) and the GCS store will each be one `case` that imports its adapter lazily. A missing extra then surfaces as a `ConfigurationError` instead of an `ImportError`.

### Who builds and who consumes the bundle
- **Builders.** Each entry point builds the bundle once:
  - HTTP: `src/scenewise/service/http/app.py` (`create_app`) builds it in the FastAPI lifespan and stores it in `src/scenewise/service/http/state.py` (`ServiceState.deps`).
  - CLI: `src/scenewise/service/cli.py` (`analyse`) builds it per invocation, after `_with_local_root` adds the media file's parent directory to `inputs.local_roots`.
- **Consumers.** The `app` use cases (`run_job`, `handle_delivery`, `job_status`) never read `Settings`. They get ports from the bundle and deployment values as plain arguments, such as `src/scenewise/app/delivery.py` (`DeliveryPolicy`). The `service` routes do read `Settings`, and pass the values on:
  - `src/scenewise/app/runner.py` (`run_job`) checks `plan.unavailable(..., deps.enabled_stages)`. It raises `InputError(code="stage_unavailable")` per job, which is distinct from the start-up `ConfigurationError` with the same code. It then passes `deps.inputs` and `deps.media` to `acquire_audio`.
  - `src/scenewise/app/delivery.py` (`handle_delivery`, `_Delivery`, `_run`) reads and writes the job record through `deps.store`, passes the whole bundle to `run_job`, and hands `deps.store` to `publish`. `job_status` takes a bare `store=` argument, not the bundle.
  - `src/scenewise/service/http/push.py` (`push`, `_admitted`) passes `deps=state.deps` and `policy=state.policy` to `handle_delivery` in a worker thread. This is the production path into delivery. It reads `state.settings.service` for the lease and attempt limits.
  - `src/scenewise/service/http/routes.py` (`get_job`) passes `store=state.deps.store` and `state_prefix=state.settings.service.state_prefix` to `job_status`.
  - `src/scenewise/service/http/routes.py` (`readyz`) reports `deps.enabled_stages`.
- **Tests.** `tests/fakes.py` (`fake_dependencies`) builds the same bundle over in-memory fakes (`InMemoryBlobStore`, `FakeMediaTool`, `FakeImageReader`). By default the inputs store is the same object as the output store.

## Where it's used
- [[job-submission]]: `handle_delivery` runs over `ServiceState.deps`.
- [[job-status]]: `get_job` passes `state.deps.store` to `job_status`.
- [[audio-stage]]: `acquire_audio` gets `deps.inputs` and `deps.media`.
- [[job-results-and-artifacts]]: publishing writes through `deps.store`.
- [[cli-analyse]]: the CLI calls `build_dependencies` and `run_job` directly.
- [[health-probes]]: `/readyz` reports `deps.enabled_stages`.
- [[storage-and-uri-policy]]: `_stores` and the input/output store split.
- [[media-processing]]: the `MediaTool` and `ImageReader` ports and their adapters.

## Gotchas / constraints
- **The order of work follows the layers.** Build in this order: domain values, then the port in `src/scenewise/ports.py`, then the use case and wire model in `app`, then the adapter, then its `case` in `src/scenewise/service/bootstrap.py`. Each intermediate tree then still passes the layers contract (`.claude/context/conventions.md` "Order of work in a feature").
- **A port in use comes with a set of test files.** Each port the code uses has:
  - a contract mixin `tests/contract/<port>_contract.py`,
  - a fake in `tests/fakes.py`,
  - a `test_<port>_<impl>.py` per implementation, covering the fake and every light adapter.

  Today that means `BlobStore`, `MediaTool` and `ImageReader` (`tests/contract/blobstore_contract.py` `BlobStoreContract`, `tests/contract/mediatool_contract.py` `MediaToolContract`, `tests/contract/imagereader_contract.py` `ImageReaderContract`). The other seven ports have no adapter, no fake and no mixin yet. When a port declared ahead of its first use should get them is open (`.claude/context/conventions.md` `## Not determined`).
- **Some bundle members exist but nothing reads them yet.** No `app` module reads `deps.images`. `PillowImageReader` is built because Pillow is a base dependency and the field is required (`docs/skeleton-notes.md` A10). `notifier` is always `None`, and delivery never notifies (`docs/skeleton-notes.md` A8). `speech`, `text`, `moderator` and `labeller` are always `None` in the bootstrap.
- **`ARCHITECTURE.md` §4 differs from the code.** It shows `Dependencies` with a required `notifier`, a `guard` field and no `inputs` field. The code, recorded as departures in `docs/skeleton-notes.md` A6 and A8, has `inputs` and an optional `notifier`, and has no `guard`. Trust `src/scenewise/app/deps.py`.
- **Base-install adapters are imported lazily too.** `FfmpegMediaTool` and `PillowImageReader` are imported inside `build_dependencies`, even though they need no extra. Whether a base-install adapter may be imported at module top of `src/scenewise/service/bootstrap.py` is open (`.claude/context/service.md` `## Not determined`).
- **Adapters raise domain errors.** They import `scenewise.domain.errors` and `scenewise.ports` (for example `LocalBlobStore` raises `InputError(code="uri_not_allowed")` and `WriteConflictError`). They never import `app` or `service.config`.
- **Naming.** Adapters live at `src/scenewise/adapters/<kind>/<technology>.py` with class name `<Technology><Port>` (`.claude/context/adapters.md`).

## Anchor files
- `pyproject.toml` (`[tool.importlinter]`): the six import contracts; `[tool.ruff.lint.per-file-ignores]` has the `PLC0415` exemption for bootstrap.
- `scripts/import_contracts.py` (`AllowedExternalsContract`): the custom third-party allow-list contract.
- `src/scenewise/ports.py` (`BlobStore`, `MediaTool`, `ImageReader`, `Notifier`, `Blob`, `WriteConflictError`, `ABSENT_GENERATION`): every port and its contract.
- `src/scenewise/app/deps.py` (`Dependencies`, `Speech`, `enabled_stages`): the port bundle and how enabled stages are worked out.
- `src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`): the composition root.
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`): the `file://` `BlobStore` with root and excluded allow-lists.
- `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool`, `find_binaries`): the `MediaTool` adapter and the start-up binary check.
- `src/scenewise/adapters/media/images.py` (`PillowImageReader`): the `ImageReader` adapter.
- `src/scenewise/service/http/app.py` (`create_app`): builds the bundle in the HTTP lifespan.
- `src/scenewise/service/http/state.py` (`ServiceState`): holds the bundle for the process.
- `src/scenewise/service/cli.py` (`analyse`, `_with_local_root`): builds the bundle for the CLI.
- `src/scenewise/app/runner.py` (`run_job`): consumes `enabled_stages`, `inputs` and `media`.
- `src/scenewise/app/delivery.py` (`handle_delivery`, `_run`, `job_status`, `DeliveryPolicy`): consumes `store` and passes the bundle on to `run_job`.
- `src/scenewise/service/http/push.py` (`push`, `_admitted`): hands `state.deps` to `handle_delivery`.
- `src/scenewise/service/http/routes.py` (`get_job`, `readyz`): passes `state.deps.store` and the state prefix to `job_status`, and reports `deps.enabled_stages`.
- `src/scenewise/__main__.py`: the entry module exempt from the layers contract.
- `tests/fakes.py` (`fake_dependencies`): the bundle over in-memory fakes.
- `tests/e2e/test_bootstrap.py` (`test_builds_the_skeleton_dependencies`, `test_configuration_errors`): end-to-end tests of the composition root.
- `ARCHITECTURE.md` §2–§4, §14 and `docs/skeleton-notes.md` A6, A8, A10: the design target and the departures from it.

## Related
- [[storage-and-uri-policy]] · [[media-processing]] · [[configuration]] · [[stages-and-outcomes]] · [[error-model]] · [[wire-contract]]
