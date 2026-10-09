# The `service` layer

> **Read this when:** the change lands in `src/scenewise/service` — the command line, the HTTP service, settings, logging set-up or the composition root `src/scenewise/service/bootstrap.py`. **Skip when:** it lands in `domain`, `app`, `adapters`, `src/scenewise/ports.py` or `tests`; each has its own document, and the rules spanning every layer are in `.claude/context/conventions.md`, which this document assumes has been read.

**Purpose.** The rules this layer's implementer and its reviewer both read before they start: what the driving side owns, what it must leave to the layers below, and what a change here is held to.

## Responsibility

- `service` is the driving side and the composition root: it parses a CLI invocation or an HTTP request, builds `Settings` and the `Dependencies` bundle, calls a use case in `app`, and turns the outcome into an exit code or an HTTP response (`src/scenewise/service/__init__.py` module docstring; `ARCHITECTURE.md` §2, §3).
- Nothing imports `service`; `src/scenewise/__main__.py` is the exempt caller, and the console script is `scenewise.service.cli:main` (`src/scenewise/service/__init__.py` "nothing imports it"; `pyproject.toml` `[project.scripts]`).
- Not here: the delivery protocol (decide, claim, run, publish, record), which is `src/scenewise/app/delivery.py`; wire models and serialisation, which are `src/scenewise/app/contract/`; port implementations, which are `adapters`; domain rules. A route or CLI command that decides attempt state, writes a job record, or shapes a wire body itself has drifted into `app` (`ARCHITECTURE.md` §7 "One delivery", §13 "Ownership on the delivery path").
- `service` neither writes nor reads the job record itself: `src/scenewise/app/delivery.py` owns every record write, and `get_job` reads a status through the `app` use case `job_status` (owner: `.claude/context/conventions.md` "Shared state, storage paths and the wire contract"; `src/scenewise/app/delivery.py` `job_status`; `src/scenewise/service/http/routes.py` `get_job`).
- `service` never builds the record's path or parses the record; `get_job` keeps only HTTP concerns — a `JobNotFoundError` problem (404) for `None`, `Retry-After` on a `RetryableError`, problem bodies (`src/scenewise/service/http/routes.py` `get_job`; record path owned by `.claude/context/conventions.md` **Storage paths.**).

## Dependencies

The import direction, the composition-root monopoly and the third-party allow-lists are owned by `.claude/context/conventions.md` "Dependency direction". This layer's consequences:

- Only `src/scenewise/service/bootstrap.py` imports `scenewise.adapters`; every other `service` module reaches an adapter through `Dependencies` (`pyproject.toml` contract "Only the composition root imports adapters").
- `service` imports no ML or cloud SDK directly — the `forbidden_modules` list includes `numpy`, `PIL`, `anthropic` and `google`; reaching them through an adapter is allowed (`pyproject.toml` `[tool.importlinter]` `forbidden` contract, `allow_indirect_imports`).
- `src/scenewise/service/http/` is the only async code in the package, and `anyio` is used only there; `app` is called synchronously, and blocking work leaves the event loop through `anyio.to_thread.run_sync` (`src/scenewise/service/http/__init__.py` module docstring; `src/scenewise/service/http/push.py` `_admitted`; `ARCHITECTURE.md` §8).

## The composition root — `src/scenewise/service/bootstrap.py`

- Order: `Settings` → system checks → adapters → `Dependencies`; one factory, `build_dependencies(settings)` (`src/scenewise/service/bootstrap.py` module docstring, `build_dependencies`; `ARCHITECTURE.md` §14).
- Where an adapter is imported, including a back end behind an optional extra, is owned by `.claude/context/conventions.md` "Dependency direction". Observed here: every adapter import is function-local, and ruff `PLC0415` is ignored for this file alone; why a base-install adapter is imported that way is in `## Not determined` (`src/scenewise/service/bootstrap.py` `build_dependencies`, `_stores`; `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`).
- A new back end is one `case` in the `match` on its setting; an unsupported choice falls to a `case` that raises `ConfigurationError(code=…, detail=…)` (`src/scenewise/service/bootstrap.py` `_stores` `"store_unavailable"`; `ARCHITECTURE.md` §13 "Open/closed").
- Adapters are built once and receive keyword arguments read off `Settings`, never `Settings` itself (`src/scenewise/service/bootstrap.py` `build_dependencies`; owner: `.claude/context/conventions.md` "Dependency direction").
- Start-up failures are `ConfigurationError`: a `required_stages` entry with no back end raises `stage_unavailable`, so the process never becomes ready (`src/scenewise/service/bootstrap.py` `build_dependencies`; `ARCHITECTURE.md` §9).
- Inputs and outputs are separate stores: the output store writes only below the state prefix and `service.artifact_roots`; the input store reads only below `inputs.local_roots` and excludes every output root. A new store back end keeps the same split (`src/scenewise/service/bootstrap.py` `_stores`; `docs/skeleton-notes.md` A6).

## Settings — `src/scenewise/service/config.py`

- `Settings` is pydantic-settings, `SCENEWISE_` prefix, `__` between groups, `frozen=True`; each group subclasses `_Group` (`extra="forbid"`, frozen) and becomes one field of `Settings` (`src/scenewise/service/config.py` `Settings`, `_Group`).
- Deployment-tunable values and platform limits are group fields with validated types (`PositiveInt`, `Literal`); cross-field invariants are `model_validator(mode="after")` methods that raise `ValueError` with the numbers in the message; derived values are properties (`src/scenewise/service/config.py` `ServiceSettings._timing`, `ServiceSettings.lease_s`; owner of the constants rule: `.claude/context/conventions.md` "Constants and configuration").
- A settings group or field arrives with the feature that reads it (`src/scenewise/service/config.py` module docstring).
- `Settings` is built once per entry point — `main` in the CLI, the lifespan in HTTP — and never mutated; a per-invocation change is a `model_copy(update=…)` (`src/scenewise/service/cli.py` `main`, `_with_local_root`; `src/scenewise/service/http/app.py` `create_app`).
- Secrets are `SecretStr` fields (attributed: `ARCHITECTURE.md` §10).

## Logging set-up — `src/scenewise/service/logs.py`

- The logger itself, event naming, context binding and what a log never contains (D8) are owned by `.claude/context/conventions.md` "Logging". This layer owns `logs.configure(settings.log)`: structlog and stdlib logging go through one handler on stderr, JSON by default, and each entry point calls it once after `Settings` is built (`src/scenewise/service/logs.py` `configure`; `src/scenewise/service/cli.py` `main`; `src/scenewise/service/http/app.py` `create_app`).
- The push path binds the Cloud Tasks headers with `structlog.contextvars.bound_contextvars` before admission (`src/scenewise/service/http/push.py` `_log_context`); the header table `_TASK_HEADERS` is a `Final` tuple of `(header, key)` pairs, so no module-level state is mutable.

## HTTP — `src/scenewise/service/http/`

- `create_app()` is the factory (`uvicorn --factory scenewise.service.http.app:create_app`); it accepts an optional `Settings` and builds every dependency once, in the lifespan (`src/scenewise/service/http/app.py` module docstring, `create_app`).
- Process-lifetime state is one `ServiceState` frozen dataclass on `app.state.scenewise`, read through `routes._state`; state lives on the app instance, never at module level (`src/scenewise/service/http/state.py` `ServiceState`; `src/scenewise/service/http/health.py` module docstring "The registry lives on the app instance, not the module").
- Routes are registered on `router` in `src/scenewise/service/http/routes.py`, which `create_app` includes; a route handler stays thin and delegates (`src/scenewise/service/http/routes.py` `post_job` → `push.push`).
- Handlers that call a synchronous use case are sync `def`; `async def` is used where the body is streamed or work is handed to a worker thread (`src/scenewise/service/http/routes.py` `get_job`, `post_job`).
- Job and record bodies come pre-serialised from `src/scenewise/app/contract/mapping.py` and are returned as `Response(content=…, media_type=JSON_MEDIA_TYPE)`, the media type imported from `src/scenewise/app/constants.py`; no response model is declared on a route (`src/scenewise/service/http/routes.py` `get_job`; `src/scenewise/service/http/push.py` `_admitted`, `_rejected`).
- **Errors.** Outside the push path's keyed rejections (below), every error is answered as RFC 9457 `application/problem+json` through `problems.problem_response`, never a bare 500; an unexpected exception is logged with `log.exception(…, code="unexpected")` and answered as `InternalError(code="unexpected")` (`src/scenewise/service/http/problems.py` `problem_response`; `src/scenewise/service/http/routes.py` `get_job` "problem+json, never bare 500").
- The status of a problem comes from `problems.http_status`, which reads the `_STATUSES` table, first match wins; a new `ScenewiseError` leaf with its own status gets an entry there, placed before its parent class's entry (`src/scenewise/service/http/problems.py` `_STATUSES`, `http_status`; `JobIdConflictError` → 409, `JobNotFoundError` → 404; owner of the leaf-class rule: `.claude/context/conventions.md` "Errors"). The problem `title` is the status phrase unless `problems.problem_title` gives the error its own (`JobIdConflictError`: "Job id already used").
- **Push path** (`POST /v1/jobs`): read the body with the byte limit before parsing (413), parse the envelope (422 without a usable `job_id`), bind log context, `limiter.acquire_nowait()` (429 with `Retry-After` when full, released in `finally`), register with the watchdog, then run `app.delivery.handle_delivery` in a worker thread (`src/scenewise/service/http/push.py` `read_body`, `push`, `_admitted`; `ARCHITECTURE.md` §7).
- On the push path a `RetryableError` is answered through `problem_response` with `Retry-After`, at the status `problems.http_status` gives it (503; 429 for `CapacityError`); any other error once a `job_id` is keyed — a `ScenewiseError` or an unexpected exception — goes through `_rejected`, which answers **200** with a `mapping.rejection_json` body and never calls `problem_response`, because Cloud Tasks retries every non-2xx; a `Rejected` delivery outcome (a reused job id) is answered the same way. The `match` over `DeliveryOutcome` ends in `case _: assert_never(outcome)` (`src/scenewise/service/http/push.py` `_rejected`, `_admitted`; `src/scenewise/app/delivery.py` `Rejected`; `src/scenewise/service/http/problems.py` `http_status`, module docstring; `src/scenewise/domain/errors.py` `CapacityError`).
- `/healthz` fails (503) while a job has outlived `attempt_budget_s + watchdog_grace_s`; the `Watchdog` holds its registry under a lock (`src/scenewise/service/http/health.py` `Watchdog`; `src/scenewise/service/http/app.py` `create_app`).

## CLI — `src/scenewise/service/cli.py`

- argparse, one subparser per command; `main(argv)` returns the exit code (`src/scenewise/service/cli.py` `_parser`, `main`).
- Exit codes are module constants: `EXIT_OK` success, `EXIT_FAILED` for a `ScenewiseError`, `EXIT_CONFIGURATION` for a `ConfigurationError` or invalid settings (`src/scenewise/service/cli.py` `EXIT_OK`, `EXIT_FAILED`, `EXIT_CONFIGURATION`).
- The result document goes to stdout; an error is one stderr line `scenewise: {code}: {detail}`; invalid settings name the failing fields, never their values (`src/scenewise/service/cli.py` `analyse`, `main`; `docs/skeleton-notes.md` review r1 finding 16).
- `analyse` calls `run_job` and writes artifacts to `--out`; it keeps no job record and does not publish (`src/scenewise/service/cli.py` module docstring; `ARCHITECTURE.md` §13).

## Naming and layout

- One module per concern under `src/scenewise/service/` and `src/scenewise/service/http/`; the logging module is `logs.py` (owner: `.claude/context/conventions.md` "Where a new responsibility goes"; `ARCHITECTURE.md` §2).
- The choice of construct — class with `__init__`, function, frozen dataclass — is owned by `.claude/context/conventions.md` "Where a new responsibility goes". In this layer: `Watchdog` holds a lock and has an `__init__`, `ServiceState` is a frozen dataclass, and settings groups are `_Group` models (`src/scenewise/service/http/health.py` `Watchdog`; `src/scenewise/service/http/state.py` `ServiceState`; `src/scenewise/service/config.py` `_Group`).
- Module-level constant naming is owned by `.claude/context/conventions.md` "Constants and configuration"; in this layer, for example, `src/scenewise/service/http/push.py` `RETRY_AFTER_BUSY_S` and `src/scenewise/service/http/problems.py` `PROBLEM_JSON`, `UNPROCESSABLE_CONTENT`.

## Surfaces this layer does not have

No UI, localization, theming, navigation module or screen registry; the HTTP route registry is `router` in `src/scenewise/service/http/routes.py` (owner: `.claude/context/conventions.md` "Surfaces this project does not have").

## Done

- The testing bar, coverage thresholds, suppression budget and the single-file test command are owned by `.claude/context/conventions.md` "Testing bar" and "Code shape in every layer". `service` is outside the 100% unit-tier core (`domain`, `app`, `ports`) and counts toward the ≥ 90% overall figure.
- A CLI or HTTP behaviour is tested in `tests/e2e` through FastAPI's `TestClient` against the real app, lifespan and adapters, over generated media; the watchdog has a unit test (`ARCHITECTURE.md` §15; `docs/skeleton-notes.md` "Gate results (local)").
- The set that accompanies a new unit here: a new back end — its adapter (owner: `.claude/context/conventions.md` "The set that accompanies a new unit"), its settings fields, and its `case` in `bootstrap._stores` (or the selector `build_dependencies` calls) (`src/scenewise/service/bootstrap.py` `_stores`, `build_dependencies`; `src/scenewise/service/config.py` `InputSettings`); a new route — the handler on `router` and an e2e test (`src/scenewise/service/http/routes.py` `router`; `ARCHITECTURE.md` §15 "CLI and HTTP over media that ffmpeg generates"); a new settings group — a `_Group` subclass and its field on `Settings` (`src/scenewise/service/config.py` `_Group`, `Settings`); a new error leaf with its own status — its entry in `problems._STATUSES`, before its parent's (`src/scenewise/service/http/problems.py` `_STATUSES`).
- Commit messages follow `.claude/context/conventions.md` "Commit-message policy".

## Example

> A failure on the push path must not start a Cloud Tasks retry loop unless a retry can help. `src/scenewise/service/http/push.py` (`_admitted`) answers a `RetryableError` with `problem_response(e, retry_after=RETRY_AFTER_BUSY_S)` (503, or 429 for a `CapacityError`), but any other `ScenewiseError` — and any unexpected exception, after `log.exception("delivery_rejected", code="unexpected")` — goes through `_rejected`, which answers **200** with `mapping.rejection_json(…)`, so the queue stops redelivering a request that will fail the same way.

_Provenance: existing mode. Read every module under `src/scenewise/service/` (`bootstrap.py`, `cli.py`, `config.py`, `logs.py`, `http/app.py`, `http/health.py`, `http/problems.py`, `http/push.py`, `http/routes.py`, `http/state.py`, `__init__.py` and `http/__init__.py`), `ARCHITECTURE.md` §2, §3, §7–§11, §13–§16, `docs/skeleton-notes.md`, `pyproject.toml` (`[tool.importlinter]`, `[tool.ruff.lint.per-file-ignores]`, `[project.scripts]`), and `.claude/context/conventions.md` as the vocabulary anchor. Fix pass: applied four review findings, re-reading `src/scenewise/service/http/push.py`, `src/scenewise/service/http/problems.py`, `src/scenewise/domain/errors.py`, `src/scenewise/service/config.py`, `src/scenewise/service/bootstrap.py` and `ARCHITECTURE.md` §14, §15. Corpus fix pass: applied four corpus findings, reading `.claude/context/conventions.md`, `.claude/context/app.md`, `src/scenewise/service/http/routes.py` and `pyproject.toml`. Second corpus fix pass: applied one corpus finding, reading `.claude/context/conventions.md` "Logging"._

## Not determined

- Whether the `/healthz` and `/readyz` probe bodies are part of the wire contract is owned by `.claude/context/conventions.md` `## Not determined`, which owns the wire contract.
- Retry-After values: whether they stay module constants or become deployment settings is unstated. They are module constants now (`src/scenewise/service/http/push.py` `RETRY_AFTER_BUSY_S`, `src/scenewise/service/http/routes.py` `RETRY_AFTER_STORAGE_S`). A maintainer statement settles whether they should become settings.
- Why base-install adapters (`FfmpegMediaTool`, `PillowImageReader`) are imported function-locally in `build_dependencies` rather than at module top: the code shows the pattern, no source states the intent. A maintainer statement settles whether a base-install adapter may be imported at module level in `bootstrap.py`.
