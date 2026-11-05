# Logging

> One-line: how scenewise writes logs. structlog runs over stdlib logging into one stderr handler. Job and request context is bound through `contextvars`. A log or error `detail` must never carry transcript text or signed URIs (D8).

## What it is & why

- One logging set-up serves both entry points, the HTTP service and the `scenewise` CLI. structlog events and stdlib (library) records go through the same `ProcessorFormatter`, so they come out in one format. That format is JSON by default (`src/scenewise/service/logs.py` module docstring; `ARCHITECTURE.md` §10 "**Logging.**").
- Logs go to **stderr**. This keeps stdout free for the CLI's result document ([[cli-analyse]]).
- Context such as `job_id`, `attempt`, `stage` and the Cloud Tasks headers is bound once, at the level that knows it. It is never passed down as a parameter, so a log call deep inside a stage still carries the job it belongs to (`.claude/context/conventions.md` `## Logging`; `.claude/context/app.md` "**Logging context**").
- D8 is a privacy rule. Logs and error `detail`s never contain transcript text or signed URIs (`src/scenewise/service/logs.py` module docstring; `src/scenewise/domain/errors.py` module docstring).

## How it works

### Settings

- `LogSettings` is the `log` group of `Settings`, read from the environment with prefix `SCENEWISE_` and `__` between groups (`src/scenewise/service/config.py` (`LogSettings`, `Settings`)):

```
level:  "DEBUG" | "INFO" | "WARNING" | "ERROR"   default "INFO"     SCENEWISE_LOG__LEVEL
format: "json"  | "console"                        default "json"     SCENEWISE_LOG__FORMAT
```

- Like every settings group, it derives from `_Group` (`extra="forbid"`, `frozen=True`). A value outside the `Literal` fails `Settings()`. In the CLI that is exit code 2 with `scenewise: invalid settings: <field paths>` on stderr, written before logging is configured (`src/scenewise/service/cli.py` (`main`)).

### Set-up: `logs.configure`

`src/scenewise/service/logs.py` (`configure`) is called once per process, right after `Settings` is built:
- in the CLI: `src/scenewise/service/cli.py` (`main`), `logs.configure(settings.log)`;
- in the HTTP service: inside the FastAPI lifespan of `src/scenewise/service/http/app.py` (`create_app`), `logs.configure(resolved.log)`, before `build_dependencies`.

What it builds:
1. A **shared processor chain**: `merge_contextvars` → `add_log_level` → `add_logger_name` → `TimeStamper(fmt="iso", utc=True)`. Every record gets the bound context, `level`, `logger` (the module `__name__`) and a UTC ISO `timestamp`.
2. **structlog** is configured with that chain plus `format_exc_info` and `ProcessorFormatter.wrap_for_formatter`. It uses `stdlib.LoggerFactory`, `stdlib.BoundLogger` and `cache_logger_on_first_use=True`, so every structlog event is handed to stdlib logging.
3. **One stdlib handler**: a `StreamHandler(sys.stderr)` whose `ProcessorFormatter` runs the shared chain as `foreign_pre_chain` on stdlib records that did not come from structlog. It then removes structlog's meta keys and renders with `JSONRenderer()`, or with `ConsoleRenderer(colors=False)` when `format == "console"`.
4. The **root logger**'s handlers are *replaced* (`root.handlers[:] = [handler]`) and its level set to `settings.level`. Calling `configure` twice does not stack handlers.

### Emitting events

- Each module that logs holds a module-level `log = structlog.get_logger(__name__)`. An event is a snake_case string, and its context goes in keyword fields (`.claude/context/conventions.md` `## Logging`). `print` is barred in `src` by ruff `T201`.
- Events emitted today, all carrying a `code` except where noted:

| Event | Level | Where |
|---|---|---|
| `stage_failed` | warning; `exception` for `unexpected` | `src/scenewise/app/runner.py` (`_run_stage`) |
| `job_failed` | warning (with `category`); `exception` for `unexpected` | `src/scenewise/app/delivery.py` (`_run`) |
| `job_finished` | info, with `state` and `error_code` | `src/scenewise/app/delivery.py` (`_finish`) |
| `attempt_released` | warning | `src/scenewise/app/delivery.py` (`_release`) |
| `attempt_superseded` | warning, no fields | `src/scenewise/app/delivery.py` (`_finish`, `_release`) |
| `job_id_conflict` | error, no fields | `src/scenewise/app/delivery.py` (`handle_delivery`) |
| `delivery_rejected` | warning; `exception` for `unexpected` | `src/scenewise/service/http/push.py` (`_admitted`) |
| `status_unreadable` | warning; `exception` for `unexpected` | `src/scenewise/service/http/routes.py` (`get_job`) |

- The convention is to log the error **`code`**, never its `detail`. An unexpected exception is logged with `log.exception(..., code="unexpected")`, which attaches the traceback through `format_exc_info`.

### Binding context

All binding uses `structlog.contextvars.bound_contextvars`, a context manager, so a key is removed when its block exits:

| Key | Bound by | Scope |
|---|---|---|
| `task_name`, `transport_retry`, `trace` | `src/scenewise/service/http/push.py` (`push`, via `_log_context`) | push path, from after envelope parsing through admission and the delivery |
| `job_id` | `src/scenewise/app/delivery.py` (`handle_delivery`) | the whole delivery |
| `attempt` | `src/scenewise/app/delivery.py` (`_attempt`) | from after the claim write succeeds through run and finish |
| `job_id` (again) | `src/scenewise/app/runner.py` (`run_job`) | audio acquisition and every stage; this is the only `job_id` binding on the CLI path (value `cli`) |
| `stage` | `src/scenewise/app/runner.py` (`run_job`) | one stage's `_run_stage` call |

- `_log_context` maps headers through the `Final` tuple `_TASK_HEADERS`: `x-cloudtasks-taskname` → `task_name`, `x-cloudtasks-taskretrycount` → `transport_retry`, `x-cloud-trace-context` → `trace`. Only headers that are present are bound, and each value is cut at the first `/` (`request.headers[header].split("/")[0]`). For the trace header that keeps the trace id and drops the span part.
- The delivery runs in a worker thread (`anyio.to_thread.run_sync` in `_admitted`). anyio runs the function in a copy of the caller's context, so the Cloud Tasks keys bound in `push` also appear on `app` log lines.
- Nothing binds context in `src/scenewise/service/http/routes.py` (`get_job`). Its `status_unreadable` events carry no `job_id`.

### Redaction (D8)

- **Validation errors.** `src/scenewise/app/contract/mapping.py` (`_validation_summary`) builds an `invalid_request` `detail` from field paths and messages only, `error.errors(include_input=False, include_url=False)`, joined as `loc: msg` with `<body>` for an empty path. `tests/unit/test_mapping.py` (`test_to_domain_hides_input_values`) checks that the input value is absent.
- **Error details.** The module docstring of `src/scenewise/domain/errors.py` requires that `detail` never contains transcript text or signed URIs. A `detail` reaches the wire: as `ErrorInfoV1.message` of a failed stage (`src/scenewise/app/contract/mapping.py` (`_stage_fields`), from `Failed.detail`) and as the `detail` of the problem body (`src/scenewise/app/contract/mapping.py` (`problem`), `detail=error.detail or error.code`). It also becomes the exception message (`"{code}: {detail}"`), so it shows up in any traceback that `log.exception` renders. The same rule binds a domain `ValueError` message, which becomes a `detail` (`.claude/context/domain.md`).

## Where it's used

- [[job-submission]]: push-path context and `delivery_rejected`; [[job-lifecycle-and-timing]]: `attempt_*` and `job_*` events.
- [[job-status]]: `status_unreadable`.
- [[audio-stage]] and [[stages-and-outcomes]]: `stage` context and `stage_failed`.
- [[cli-analyse]]: stderr logging, so stdout carries only the result.
- [[error-model]]: the codes every event carries.

## Gotchas / constraints

- **Which layers may log.** `domain` and `ports` cannot log, because structlog is outside their stdlib-only import allow-list. `app` may, since its allow-list is stdlib, `pydantic`, `pydantic_core` and `structlog` (`pyproject.toml` `[tool.importlinter]`). No adapter logs today. Whether one may is an open question (`.claude/context/adapters.md` "Whether adapters log").
- **`ARCHITECTURE.md` §10 differs from the code.** It says `runner.py` binds `job_id`, `stage`, `attempt` and `backend`. In the code, `attempt` is bound in `delivery.py` (`_attempt`), and no module binds `backend` (no `backend=` anywhere under `src`).
- **The D8 log test does not exist yet.** §10 says "a test enforces it", but `docs/skeleton-notes.md` A14 records the test as not written. Only the validation-summary unit test exists.
- **Not every stderr line is a log line.** The CLI writes its own `scenewise: <code>: <detail>` lines to stderr with `sys.stderr.write`, not through the logger (`src/scenewise/service/cli.py` (`analyse`, `main`)).
- Before `configure` runs (settings validation, or anything before the FastAPI lifespan), output uses Python's and structlog's defaults.
- **uvicorn's own lines are not scenewise JSON.** The README starts the service with plain `uvicorn --factory ...`, which applies uvicorn's default `log_config`. That config (`.venv/lib/python3.14/site-packages/uvicorn/config.py` (`LOGGING_CONFIG`)) gives the `uvicorn` logger its own `default` handler (`uvicorn.logging.DefaultFormatter`, stderr) and `uvicorn.access` its own `access` handler (`uvicorn.logging.AccessFormatter`, stdout), both with `"propagate": False`; `uvicorn.error` has no handler and propagates to `uvicorn`. `configure` replaces only the root logger's handlers, so uvicorn's server and access lines are written by uvicorn's handlers in uvicorn's text format, and the access lines go to stdout.

## Anchor files

- `src/scenewise/service/logs.py` (`configure`): the whole set-up; module docstring states D8
- `src/scenewise/service/config.py` (`LogSettings`): `level` and `format`
- `src/scenewise/service/cli.py` (`main`): CLI call to `logs.configure`
- `src/scenewise/service/http/app.py` (`create_app`): HTTP lifespan call to `logs.configure`
- `src/scenewise/service/http/push.py` (`_TASK_HEADERS`, `_log_context`, `push`, `_admitted`): Cloud Tasks context; `delivery_rejected`
- `src/scenewise/service/http/routes.py` (`get_job`): `status_unreadable`
- `src/scenewise/app/delivery.py` (`handle_delivery`, `_attempt`, `_run`, `_finish`, `_release`): `job_id` / `attempt` binding; job events
- `src/scenewise/app/runner.py` (`run_job`, `_run_stage`): `job_id` / `stage` binding; `stage_failed`
- `src/scenewise/app/contract/mapping.py` (`_validation_summary`): value-free validation details
- `src/scenewise/domain/errors.py` (module docstring): D8 rule for `detail`
- `tests/unit/test_mapping.py` (`test_to_domain_hides_input_values`): the redaction check
- `ARCHITECTURE.md` §10 "**Logging.**": design statement
- `docs/skeleton-notes.md` (A14): D8 log test deferred

## Related

- [[configuration]] · [[error-model]] · [[job-submission]] · [[job-lifecycle-and-timing]] · [[cli-analyse]] · [[layering-and-ports]]
