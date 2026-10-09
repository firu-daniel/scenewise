# Cross-layer conventions

> **Read this when:** you are implementing, reviewing or planning **any** change to scenewise — these rules hold in every layer, and this file also carries the `general` layer's own rules (the repository root: `pyproject.toml`, `scripts/`, `.github/`, `docs/`). **Skip when:** never; every layer document assumes this one has been read.

**Purpose.** The rules a change satisfies whichever layer it lands in, the vocabulary the harness uses for this project, and the commit-message policy.

## Stack

- Python, floor 3.12; code runs unchanged on 3.12, 3.13 and 3.14, the CI matrix (`pyproject.toml` `requires-python`; `.github/workflows/ci.yml` `test` matrix). Syntax or stdlib names newer than 3.12 are not used — `HTTPStatus.UNPROCESSABLE_CONTENT` is replaced by a literal 422 (`src/scenewise/service/http/problems.py` `UNPROCESSABLE_CONTENT`; `docs/skeleton-notes.md` G18).
- Packaging and environment: uv at the pinned `required-version`, `uv_build`, `src/` layout, one distribution and one import package `scenewise` (`pyproject.toml` `[tool.uv]`, `[build-system]`; `ARCHITECTURE.md` §1).
- Serialization: Pydantic v2 models, `model_validate_json` / `model_dump_json`. `domain` and `ports` never import Pydantic; `app` may (`pyproject.toml` `[tool.importlinter]` allow-list contracts "Domain and ports: stdlib only" and "Use cases: stdlib, pydantic and structlog only"; `src/scenewise/app/contract/mapping.py` `to_domain`).
- Transport: FastAPI in `src/scenewise/service/http/`, served by uvicorn (`service` extra); the HTTP edge is the only async code, everything below it is synchronous (`ARCHITECTURE.md` §8; `src/scenewise/ports.py` module docstring "Ports are synchronous").
- Settings: pydantic-settings, `SCENEWISE_` prefix, `__` nesting (`src/scenewise/service/config.py` `Settings`).
- Logging: structlog over stdlib logging (`src/scenewise/service/logs.py` `configure`).
- Tests: pytest in `strict` mode with hypothesis, pytest-timeout, pytest-randomly, pytest-cov (`pyproject.toml` `[tool.pytest]`, `[dependency-groups]`).
- Gate tooling: ruff (format and `select = ["ALL"]`), mypy `strict`, import-linter, deptry, vulture, typos, zizmor, and the gate scripts under `scripts/` (`pyproject.toml`; `.github/workflows/ci.yml` `static`).

## Layers

Every task is assigned to one of the layers in `harness.config.json`:

| Layer | Path | Responsibility |
|---|---|---|
| `domain` | `src/scenewise/domain` | Values and pure functions; stdlib only, no I/O (`ARCHITECTURE.md` §2–§3). |
| `app` | `src/scenewise/app` | Use cases (stages, runner, delivery, publish) and the versioned wire contract in `src/scenewise/app/contract/`; synchronous (`ARCHITECTURE.md` §2). |
| `adapters` | `src/scenewise/adapters` | Driven implementations of ports, one subpackage per adapter kind; heavy and optional SDK imports live here (`ARCHITECTURE.md` §2). |
| `service` | `src/scenewise/service` | The driving side — CLI, HTTP, settings, logging — and the composition root `src/scenewise/service/bootstrap.py` (`ARCHITECTURE.md` §2). |
| `package` | `src` | The files under `src/scenewise/` outside the four layer directories (`harness.config.json` `detection.review.rationale`). |
| `tests` | `tests` | The unit, contract and e2e tiers, the port fakes and the media fixtures (`ARCHITECTURE.md` §15). |
| `general` | `.` | Everything at the repository root outside `src` and `tests` (`harness.config.json` `layers`). |

## Dependency direction

- A layer imports only the layers below it: `service > (adapters | app) > ports > domain`. `adapters` and `app` never import each other. `__main__` is exempt (`pyproject.toml` contract "Layers: service > (adapters | app) > ports > domain").
- Adapter kinds are independent of each other; a helper shared inside one kind stays in that kind (`pyproject.toml` contract "Adapter kinds are independent of each other"; `ARCHITECTURE.md` §2 "Naming rules").
- Only `scenewise.service.bootstrap` imports `scenewise.adapters`, and it is the only module in `src` with function-local imports (`pyproject.toml` contract "Only the composition root imports adapters"; `pyproject.toml` `PLC0415` per-file ignore "the only lazy imports in src"). A back end behind an optional extra is imported inside the `match` branch that selects it, so a missing extra is a `ConfigurationError`, not an `ImportError` (`src/scenewise/service/bootstrap.py` module docstring). Base-install adapters are observed imported function-locally as well (`src/scenewise/service/bootstrap.py` `build_dependencies`, `_stores`); whether one may be imported at module level is open in `.claude/context/service.md` `## Not determined`.
- Third-party allow-lists: `domain` and `ports` import the stdlib only; `app` adds only `pydantic`, `pydantic_core` and `structlog`; `service` imports no ML or cloud SDK directly (`pyproject.toml` `allowed_externals` and `forbidden` contracts).
- `Settings` is built once at the entry point and handed to `bootstrap`; adapters receive keyword arguments, never `Settings` (`ARCHITECTURE.md` §3, §10; `src/scenewise/service/bootstrap.py` `build_dependencies`).

**How a change flows.** A request enters `service` (HTTP `src/scenewise/service/http/push.py` or `src/scenewise/service/cli.py`), is mapped wire → domain in `src/scenewise/app/contract/mapping.py`, runs as plain use-case functions over the port bundle `Dependencies`, and leaves through the same mapping module; every job request, result and record body is parsed and serialised through `src/scenewise/app/contract/` (`ARCHITECTURE.md` §3 "One wire contract", §7; `src/scenewise/app/deps.py` `Dependencies`). Whether the health-probe bodies fall under this is in `## Not determined`.

**Order of work in a feature.** Build bottom-up along the layer order — domain values and pure rules, then the port in `src/scenewise/ports.py`, then the use case and wire models in `app`, then the adapter, then its `case` in `src/scenewise/service/bootstrap.py` and any `service` surface — so every intermediate tree satisfies the layers contract (read off `pyproject.toml` `[tool.importlinter]`).

**The set that accompanies a new unit** (`ARCHITECTURE.md` §13–§15; `pyproject.toml` comments on `[tool.coverage.report] omit` and `[tool.deptry.per_rule_ignores]`):

- **Port:** a `Protocol` in `src/scenewise/ports.py` whose docstring is its behavioural contract. A port the code uses — implemented by an adapter or read through `Dependencies` — has a contract mixin `tests/contract/<port>_contract.py`, an in-memory fake in `tests/fakes.py`, and a contract-test subclass running the fake through the mixin, in the file `.claude/context/tests.md` `## Naming` assigns it (`tests/fakes.py` module docstring "the ports the skeleton uses"; `ARCHITECTURE.md` §15 "One mixin per port, run against the fake and every light adapter"). When a port declared ahead of its first use gets them is in `## Not determined`.
- **Adapter:** a module under `src/scenewise/adapters/<kind>/`; one `case` in `src/scenewise/service/bootstrap.py`; a contract-suite subclass for it. A heavy-extra adapter also adds its path to coverage `omit`, removes its packages from deptry's `DEP002` list, and is imported inside its test fixture after `pytest.importorskip`.
- **Input kind or outcome variant:** a new dataclass in its union; mypy's exhaustive-`match` check names every place that must handle it.
- **Domain module or use-case function:** unit tests under `tests/unit/` reaching 100% branch coverage of `domain`, `app` and `ports` from the unit tier alone.
- **Wire field:** the Pydantic model in `src/scenewise/app/contract/`, the `to_domain` / `*_json` mapping, and a test in `tests/unit/test_mapping.py`.

## Where a new responsibility goes

Choose the construct by `ARCHITECTURE.md` §14: a `Protocol` only at an I/O or model boundary; a port's implementation is a class satisfying the `Protocol`, with an `__init__` holding state only when it owns a resource with a lifecycle (a model, a client, a lock) — `src/scenewise/adapters/media/images.py` (`PillowImageReader`) has none, `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.__init__`) has one; stateless logic outside a port implementation is a plain function, and a class whose only method is `run()` is a function; frozen dataclasses for values and dependency bundles (`src/scenewise/service/http/state.py` `ServiceState`); inheritance only for the error categories and `BaseSettings` / `BaseModel` (`src/scenewise/service/config.py` `_Group`, `Settings`); one factory, `bootstrap.build_dependencies`, with a `match` per back end. Interpretation of model output is pure `domain` code; an adapter loads, runs and returns raw output (`ARCHITECTURE.md` §13). No `utils.py`; the logging module is `logs.py` (`ARCHITECTURE.md` §2 "Naming rules"). There is no DI container, `Stage` class, `Clock` port, ABC port, repository/unit-of-work, message bus or plugin entry point; adding one is a design decision to state in `ARCHITECTURE.md` first (`ARCHITECTURE.md` §14 "Deliberately left out of v1").

## Errors

- Every deliberate error is a `ScenewiseError` subclass — `InputError`, `RetryableError`, `InternalError`, `ConfigurationError` and their leaves — carrying a machine-readable `code` and a human `detail` (`src/scenewise/domain/errors.py`). A new leaf class exists only where the HTTP mapping differs (`src/scenewise/domain/errors.py` module docstring, `JobIdConflictError`); the use case raises or reports the leaf and only `service` turns it into a status (`src/scenewise/app/delivery.py` `Rejected`; `src/scenewise/service/http/problems.py` `http_status`).
- Error codes are a closed vocabulary: one `Literal` alias per class — `InputCode`, `MediaTooLargeCode`, `UnsupportedMediaCode`, `JobIdConflictCode`, `JobNotFoundCode`, `RetryableCode`, `CapacityCode`, `InternalCode`, `ConfigurationCode`, joined as `ErrorCode` — and each class's constructor takes only its own alias, so mypy rejects an unknown code and a code raised through the wrong class. `JobIdConflictError` and `JobNotFoundError` each have one code and take none; the bare `ScenewiseError` takes only `InternalCode`; every constructor funnels into the private `ScenewiseError._init` (`src/scenewise/domain/errors.py`). A new code is added to its class's alias; a code string reaches the wire unchanged, so renaming one is a wire-contract change (`src/scenewise/app/contract/mapping.py` `problem`, `_stage_fields`).
- Construct them with the keyword form `InternalError(code="…", detail=…)`; `ScenewiseError.__init__` and every subclass's `__init__` are keyword-only, and ruff EM101 rejects a positional string literal in `raise` (`docs/skeleton-notes.md` A12; `src/scenewise/domain/errors.py` `ScenewiseError.__init__`; `src/scenewise/app/contract/mapping.py` `to_domain`).
- Domain constructors check invariants in `__post_init__` and raise plain `ValueError`; the calling boundary translates it — `InputError(code="invalid_request")` in `mapping.to_domain`, `InternalError(code="model_output_invalid")` for model output, `InternalError(code="invariant_violation")` elsewhere (`ARCHITECTURE.md` §5, §9; `src/scenewise/domain/time.py`).
- How an exception raised inside a stage or during delivery is mapped and logged is owned by `.claude/context/app.md` `## Use-case rules` (`src/scenewise/app/runner.py` `_run_stage`).
- A `match` over a union ends in `case _: assert_never(x)`; coverage excludes that arm and mypy's `exhaustive-match` keeps it honest (`pyproject.toml` `[tool.coverage.report] exclude_lines`; `src/scenewise/app/contract/mapping.py` `_stage_fields`).

## Logging

- Log through structlog: a module-level `log = structlog.get_logger(__name__)`; an event is a snake_case string with context as keyword fields, e.g. `log.exception("stage_failed", code="unexpected")` (`src/scenewise/app/runner.py`, `src/scenewise/service/http/push.py`). `print` is not used in `src` (ruff `T201` under `select = ["ALL"]`, exempt only in `scripts/**`).
- Request and job context is bound with `structlog.contextvars.bound_contextvars`, not passed down (`src/scenewise/app/runner.py`, `src/scenewise/app/delivery.py`, `bound_contextvars`).
- Logs and error `detail`s never contain transcript text or signed URIs (D8): validation errors are summarised without input values (`src/scenewise/service/logs.py` module docstring; `src/scenewise/domain/errors.py` module docstring; `src/scenewise/app/contract/mapping.py` `_validation_summary`).

## Shared state, storage paths and the wire contract

- **Source of truth.** The job record `{state_prefix}/{job_id}/status.json` in the `BlobStore` is authoritative; it is written only under compare-and-swap (`if_generation`) preconditions, and `src/scenewise/app/delivery.py` owns every record write (`src/scenewise/app/delivery.py` module docstring; `src/scenewise/ports.py` `BlobStore`). A caller reconciles against the record. Per the v1 target, the notify call belongs to `delivery.py` too, best-effort and after the terminal record is written (`ARCHITECTURE.md` §7, §13); the skeleton departs from it with an optional `Dependencies.notifier`, recorded as `docs/skeleton-notes.md` A8 (`src/scenewise/app/deps.py` `notifier`; `src/scenewise/app/delivery.py` module docstring "Callbacks (step 7's notify) arrive with the HTTP callback adapter").
- **Storage paths.** Artifacts go to `{prefix}/a{attempt}/`, built by `src/scenewise/app/publish.py` (`attempt_prefix`). The record's folder is built by `job_prefix` and its URI by `record_uri`, both in `src/scenewise/app/delivery.py`; every reader or writer of the record takes its URI from `record_uri`, and the status read is the `app` use case `job_status`, which `get_job` calls (`src/scenewise/app/delivery.py` `record_uri`, `job_status`, `_Delivery.uri`; `src/scenewise/service/http/routes.py` `get_job`). A caller follows `result_uri` and never builds a path (`ARCHITECTURE.md` §7; `README.md` "Run the audio stage").
- **Wire models** live in `src/scenewise/app/contract/`. The public request, result and record models are suffixed with their schema version (`JobRequestV1`, `JobResultV1`, `JobRecordV1`) and are `frozen`; request inputs and the record are `extra="forbid"` (`src/scenewise/app/contract/requests.py` `_Input`; `src/scenewise/app/contract/results.py` `_Output`; `src/scenewise/app/contract/records.py` `JobRecordV1`). The envelope's parse models are private, unversioned and neither frozen nor version-suffixed; `_Envelope` is `extra="allow"`, `_ExternalRef` is `strict=True`, and the leniency is in the caller, which turns an invalid `external_ref` into `None` (`src/scenewise/app/contract/envelope.py` `_Envelope`, `_ExternalRef`, `_external_ref`).
- A serialized field name is the model's Python attribute name, snake_case (`schema_version`, `job_id`) (`src/scenewise/app/contract/requests.py`). Domain class and field names carry no wire names (`src/scenewise/domain/inputs.py` module docstring "wire names stay in ``app/contract``"). Which domain values reach the wire, the rule on renaming them, the domain-only enum carve-out (`Needs`) and whether `SkipReason` and `JobState` values are meant to be wire strings are owned by `.claude/context/domain.md` (`## Closed sets: unions, enums and tables` and `## Not determined`).
- The domain ↔ wire conversion happens only in `src/scenewise/app/contract/`: the pre-validation envelope in `envelope.py` (`parse`, which yields the domain `JobId`), everything else in `mapping.py` (`to_domain`, `record_to_json`, `result_json`); the notifier receives pre-serialised bytes (`ARCHITECTURE.md` §3).

## Constants and configuration

- Deployment-tunable values and limits imposed by the platform (`dispatch_deadline_s`, `max_body_bytes`, `max_attempts`) are fields of a settings group in `src/scenewise/service/config.py`, validated at start-up — the timing invariant in `ServiceSettings._timing` included.
- A constant used by more than one module lives in the module that owns its meaning, in the lowest layer that needs it, and is imported from there (`JOB_ID_PATTERN` beside `job_id` in `src/scenewise/domain/jobs.py`). Importing a module for one of its names is fine. The layer rule constrains which layer a module imports from, not how many names it takes (`docs/research/q12a-architecture-review.md`, `q12b`, `q12c`). A shared constant that no single module owns, such as a media type or an object file name used across modules, goes in `src/scenewise/<layer>/constants.py` (`src/scenewise/app/constants.py` `JSON_MEDIA_TYPE`, imported by `app` and `service`; an object file name has an owner, so `AUDIO_FILE_NAME` sits beside `RESULT_FILE_NAME` in `src/scenewise/app/publish.py`, which owns the attempt folder, and `src/scenewise/service/cli.py` imports it from there). The `ports` layer is the single module `src/scenewise/ports.py`, so its contract constants (`ABSENT_GENERATION`) stay there (maintainer decision, 2026-10-09).
- Module-level constants are annotated `Final`. A closed set of values is a `StrEnum` or a `Literal` type alias, never a class that only holds constants.
- A constant used by one module only is an `UPPER_CASE` module-level name in that module (`src/scenewise/adapters/media/ffmpeg.py` `PROBE_TIMEOUT_S`). A literal that carries a meaning (a time, a size, a limit, a count) is a named constant, never inline at its call site (maintainer decision, 2026-10-09).
- Gate thresholds live in `pyproject.toml` `[tool.scenewise.gates]` and are read by the gate scripts (`scripts/check_module_size.py`, `scripts/check_suppressions.py`).

## Code shape in every layer

- Dataclasses are `@dataclass(frozen=True, slots=True, kw_only=True)` with tuple collections (`ARCHITECTURE.md` §5; `src/scenewise/app/deps.py`).
- Constructors and option parameters are keyword-only (`*,`); ruff caps positional parameters at 3 in `src` (`ARCHITECTURE.md` §14; `src/scenewise/adapters/storage/local.py` `LocalBlobStore.__init__`; `pyproject.toml` `max-positional-args`).
- Absolute imports only (`ban-relative-imports = "all"`).
- No explicit `Any` in `domain`, `app` or `ports` (`pyproject.toml` mypy override `disallow_any_explicit`).
- No mutable module-level state, which keeps free-threading open (`ARCHITECTURE.md` §8).
- Banned APIs: `pickle`, `torch.load`, `subprocess.call`, `typing.no_type_check`. ffmpeg is called with an argv list and a timeout through the ffmpeg adapter, never handed a URL (`pyproject.toml` `banned-api`; `ARCHITECTURE.md` §11).
- Limits: module ≤ 500 physical lines in `src`, `tests` and `scripts`; cyclomatic complexity ≤ 8, returns ≤ 6, branches ≤ 10, arguments ≤ 5, statements ≤ 40; line length 88 (`pyproject.toml` `[tool.scenewise.gates]`, `[tool.ruff.lint.mccabe]`, `[tool.ruff.lint.pylint]`).
- Suppressions: none at file level and no coverage pragmas anywhere; no line-level `noqa` / `type: ignore` in `domain`, `app` or `ports`; elsewhere each carries `# why: …`, and the total equals `suppression_budget`, so adding one is a reviewed `pyproject.toml` change (`scripts/check_suppressions.py` module docstring).

## Testing bar

A change is done when the CI gates pass (`.github/workflows/ci.yml`; `ARCHITECTURE.md` §15–§16):

- 100% branch coverage of `domain`, `app` and `ports` from `tests/unit` alone; ≥ 90% overall from all tiers.
- Nothing skipped or xfailed in CI (`scripts/check_junit.py`); warnings are errors; 60 s per-test timeout; random order (`pyproject.toml` `[tool.pytest]`).
- The `model` marker appears only under `tests/contract`; no downloads at test time; test media are generated by `tests/fixtures/generate.sh` and tests assert decoded properties, not bytes (`ARCHITECTURE.md` §15; `docs/skeleton-notes.md` G19).
- A used port's test double is its in-memory fake in `tests/fakes.py`, which passes the port's contract suite; use-case tests run over `fake_dependencies` (`tests/fakes.py` module docstring, `fake_dependencies`).
- `unittest.mock` is allowed in tests (maintainer decision, 2026-10-09). It never stands in for a port where that port's fake exists, because only the fake is held to the contract suite.

**One test file on its own:** `bash harness-scripts/test.sh tests/unit/test_jobs.py`, run from the repository root. The full suite is `bash harness-scripts/test.sh` with no argument; type and static gates are `bash harness-scripts/typecheck.sh` (`harness.config.json` `commands`).

## The general layer

- `pyproject.toml` holds every gate tool's configuration; a config file elsewhere whose name the `STRAY` pattern lists fails `scripts/check_stray_config.py`, and every gate tool is run with `--config pyproject.toml` / `--config-file pyproject.toml` (`ARCHITECTURE.md` §16; `scripts/check_stray_config.py` `STRAY`; `.github/workflows/ci.yml` `static`).
- `uv.lock` matches `pyproject.toml` (`uv lock --check`, `UV_LOCKED=1`); `scripts/check_lock.sh` asserts the torch selector routing and that `service + asr` and the image extra sets resolve no `av`, `ctranslate2` or `faster-whisper` (`scripts/check_lock.sh`; `ARCHITECTURE.md` §12).
- Dependency floors use `>=` and equal the verified versions; dev tools are pinned `==` (`pyproject.toml` `dependencies`, `[dependency-groups]`). `sherpa-onnx` and `sherpa-onnx-core` stay at the same version (`pyproject.toml` `asr` comment).
- `scripts/` are standalone scripts that may `print` (`pyproject.toml` per-file ignore `"scripts/**"`).
- Every workflow action is pinned by full commit SHA with the version in a comment, and checks out with `persist-credentials: false` (`.github/workflows/ci.yml`); zizmor gates workflow hygiene.
- `vulture_whitelist.py` is generated with `vulture src --min-confidence 60 --make-whitelist` and reviewed by hand; it holds only names for features not wired yet, an entry is removed when its feature reads it, and the file is then regenerated. vulture reads it with `src`, and ruff excludes it (`vulture_whitelist.py` module docstring; `ARCHITECTURE.md` §2 tree "generated by vulture, reviewed by hand"; `pyproject.toml` `[tool.vulture]` `paths`, `extend-exclude`).
- `.pre-commit-config.yaml` holds `repo: local` hooks with `language: system`, run with `pre-commit` or the pinned `prek`; each hook runs its tool through `uv run` against `pyproject.toml`. The hooks are a local convenience and CI is the gate (`.pre-commit-config.yaml` header comment "CI is the gate"; `ARCHITECTURE.md` §2 tree "local hooks (pre-commit or prek); CI is the gate"; `pyproject.toml` `prek` pin).
- `docs/` is the research record, outside ruff and typos (`pyproject.toml` `extend-exclude`, `[tool.typos.files]`). `ARCHITECTURE.md` describes the v1 target; the skeleton's departures from it are recorded in `docs/skeleton-notes.md` (`ARCHITECTURE.md` §2; `README.md`).

## Surfaces this project does not have

scenewise is a headless service (`ARCHITECTURE.md` §1; `docs/decisions/initial-research.md` Q9 "no browser UI"). It has no UI framework, client-side state container, localization accessor, theming or sizing accessor, shared UI components, test attributes for an interactive test, navigation module, or route/screen registries; adding any of them is a design decision to state in `ARCHITECTURE.md` first. Its HTTP routes are registered in `src/scenewise/service/http/routes.py`. `phases.qa` is off (`harness.config.json`).

## Reference implementation

None: scenewise is the single implementation, and `phases.parity` is off (`harness.config.json`).

## Commit-message policy

- **Prefix.** Project commits carry no prefix: a commit fixing existing work and a commit adding new work both use `commit_prefix: none`; there is no prefix vocabulary for project commits (`git log`).
- **Subject.** Imperative mood, first word capitalised, no trailing period — `Remove PyAV from the default install (q10, q11)`. A change implementing a recorded decision or research finding names its IDs in parentheses at the end of the subject (`git log`).
- **Length cap.** None stated; see `## Not determined`.
- **Body.** Optional; wrapped prose saying what changed and why, naming the U-, D- and q-numbers involved (`git log`).
- **Attribution trailer.** Forbidden: no `Co-Authored-By:` or other agent-attribution trailer (`docs/research/user-decisions.md` U15; no commit in `git log` carries one).
- **Fixed-form subjects** — passed byte-for-byte by the commit point that owns them, exempt from the capitalisation rule and from any length cap, with `<branch>`, `<entry-id>` and `K` substituted:
  - `chore: add code review for <branch>`
  - `chore: Mark UI test K passing for <branch>`
  - `chore: Add task plan for <branch>`
  - `chore: Add UI-test plan for <branch>`
  - `chore: Add flow-progress ledger for <branch>`
  - `chore: Flow progress <entry-id> for <branch>`
  - `chore: Add branch statistics for <branch>`
  - `chore: Update branch statistics for <branch>`
  - `chore: Add user-review fix plan for <branch>`
  - `chore: Log improvement observations for <branch>`
  - `chore: Record clarification digest for <branch>`
  - `chore: Log dispatch additions for <branch>`
  - `chore: add user review for <branch>`
  - `chore: add task prompt for <branch>`
  - `chore: add docs checklist for <branch>`

  _Derived by the fixed-subject probe over the harness plugin and `harness-scripts/` (emitters include `harness-scripts/lib/harness-run-lib.sh` `hr_user_review_subject` and `harness-scripts/autonomous-watcher.sh` `docs_subject`). Omitted from the probe's output: `chore: add qa review for <branch>` — the flow text forbids emitting it (it reuses `chore: add code review for <branch>`); `chore: Flow progress A1.5f for <branch>` — a worked example of the `<entry-id>` form above; `chore: Mark UI test N passing for <branch>` (the harness plugin's orchestration-core instructions, "commits only the index") — a prose restatement of the committer's own `chore: Mark UI test K passing for <branch>` (the harness plugin's committer agent, "Fixed-form subjects — yours, not the flow's whole set"), listed above._

## Example

> Domain constructors raise plain `ValueError`; the layer that receives untrusted data translates it. `src/scenewise/app/contract/mapping.py` (`to_domain`) turns a `ValueError` from `domain.jobs.job_id` into `InputError(code="invalid_request", detail=str(e))`, so the caller gets an actionable code and `domain` stays free of HTTP and wire concerns.

_Provenance: existing mode. Read `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/skeleton-notes.md`, `docs/decisions/initial-research.md` (§Q9, §8), `docs/research/user-decisions.md`, `pyproject.toml`, `harness.config.json`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `scripts/check_suppressions.py`, `scripts/check_module_size.py`, key modules in every `src/scenewise/` layer, `tests/fakes.py`, `tests/contract/`, and `git log`. Corpus fix pass: re-read `src/scenewise/domain/jobs.py`, `src/scenewise/domain/inputs.py`, `src/scenewise/app/contract/envelope.py`, `src/scenewise/app/contract/mapping.py`, `src/scenewise/app/runner.py`, `src/scenewise/app/delivery.py`, `src/scenewise/app/deps.py`, `src/scenewise/ports.py`, `src/scenewise/adapters/`, `src/scenewise/service/bootstrap.py`, `src/scenewise/service/http/routes.py`, `src/scenewise/service/config.py`, `tests/fakes.py`, `tests/contract/`, `ARCHITECTURE.md` §3, §14, §15, and re-ran the fixed-subject probe. Second corpus fix pass: re-read `.claude/context/domain.md`, `app.md`, `service.md`, `tests.md`, `src/scenewise/domain/plan.py`, `src/scenewise/domain/jobs.py`, `src/scenewise/app/runner.py`, `src/scenewise/service/bootstrap.py`, `vulture_whitelist.py`, `.pre-commit-config.yaml`, `scripts/check_stray_config.py`, `pyproject.toml`, `ARCHITECTURE.md` §2, and re-ran the fixed-subject probe. Third corpus fix pass: re-read `.claude/context/domain.md` `## Closed sets: unions, enums and tables`, `src/scenewise/domain/jobs.py` (`WireStatus`, `wire_status`) and `src/scenewise/app/contract/mapping.py` (`status_json`)._

## Not determined

- Commit-message policy beyond what history shows: no project document states one. The prefix-less, capitalised subject form is read off `git log` alone; U15 states the no-trailer rule for the squashed initial history, extended here because no later commit carries one; no source states a subject-length cap. A maintainer-stated commit policy settles all three.
- Where departures from `ARCHITECTURE.md` made after the skeleton are recorded — appended to `docs/skeleton-notes.md` or applied to `ARCHITECTURE.md` itself: `README.md` describes `docs/skeleton-notes.md` as the skeleton's departures only. A maintainer statement settles it.
- When a port declared in `src/scenewise/ports.py` ahead of its first use gets its contract mixin and fake — at declaration, or with its first adapter or use-case reader: no source states the trigger. The evidence points to first use. The `tests/fakes.py` docstring covers "the ports the skeleton uses", the ports with no adapter and no reader have neither a fake nor a mixin, and `docs/skeleton-notes.md` A10 says model adapters are "left out rather than stubbed". No tool forces either option: vulture scans only `src`, and coverage excludes Protocol bodies. A testing rule in `ARCHITECTURE.md` §15 settles it.
- Whether the health-probe bodies (`/healthz`, `/readyz`) are part of the wire contract: `ARCHITECTURE.md` §3 says HTTP serialises through `app/contract/`, while `src/scenewise/service/http/routes.py` (`healthz`, `readyz`) builds them inline. A maintainer statement, or moving them into `app/contract/`, settles it.
