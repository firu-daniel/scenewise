# Review 1: docs/concepts/logging.md (mode: catalog)

verdict: PASS

## Must Fix

None.

## Verified against source

- `src/scenewise/service/logs.py` (`configure`): the shared chain (`merge_contextvars`, `add_log_level`, `add_logger_name`, `TimeStamper(fmt="iso", utc=True)`), the structlog configuration (`format_exc_info`, `wrap_for_formatter`, `LoggerFactory`, `BoundLogger`, `cache_logger_on_first_use=True`), the single `StreamHandler(sys.stderr)` with `foreign_pre_chain=shared`, `remove_processors_meta`, the JSON/console renderer, and `root.handlers[:] = [handler]` plus `root.setLevel`. All match. The D8 line is in the module docstring.
- `src/scenewise/service/config.py` (`LogSettings`, `_Group`, `Settings`): the `Literal` values, the defaults, `extra="forbid"`, `frozen=True`, `env_prefix="SCENEWISE_"`, `env_nested_delimiter="__"` and the `log` field. All match.
- `src/scenewise/service/cli.py` (`main`, `analyse`): the `invalid settings` stderr line is written before `logs.configure`. `EXIT_CONFIGURATION` is 2. `analyse` writes `scenewise: {code}: {detail}` with `sys.stderr.write`. The CLI job id is `job_id("cli")`. All match.
- `src/scenewise/service/http/app.py` (`create_app`): `logs.configure(resolved.log)` is in the lifespan, before `build_dependencies`. Matches.
- `src/scenewise/service/http/push.py` (`_TASK_HEADERS`, `_log_context`, `push`, `_admitted`): the header-to-key mapping, the present-only binding, `.split("/")[0]`, the binding after envelope parsing, and `delivery_rejected` at warning and at exception. All match.
- The doc says anyio runs the worker function in a copy of the caller's context. The installed anyio asyncio backend (`run_sync_in_worker_thread`, `copy_context`, `context.run(func, *args)`) confirms it.
- `src/scenewise/app/delivery.py` and `src/scenewise/app/runner.py`: the event table is complete. A grep of every `log.*(` call under `src` finds exactly the eight events listed, at the stated levels and with the stated fields. The bindings are `job_id` in `handle_delivery`, `attempt` in `_attempt` after the claim write, and `job_id` and `stage` in `run_job`. They match. No `backend=` binding exists anywhere under `src`.
- `src/scenewise/service/http/routes.py` (`get_job`): `status_unreadable` with no binding. Matches.
- `src/scenewise/app/contract/mapping.py` (`_validation_summary`, `_stage_fields`, `problem`): the claims about `include_input=False`, `include_url=False`, the `<body>` fallback, `message=detail or code` and `detail=error.detail or error.code` match.
- `src/scenewise/domain/errors.py`: the module docstring states the D8 rule for `detail`. The exception message is `f"{code}: {detail}" if detail else code`.
- `tests/unit/test_mapping.py` (`test_to_domain_hides_input_values`) exists and asserts that the input value is absent.
- `pyproject.toml` `[tool.importlinter]`: domain/ports are stdlib only, and the app allow-list is `pydantic`, `pydantic_core` and `structlog`. Under `src`, ruff `select = ["ALL"]` exempts `T201` only for `scripts/**`. Matches.
- `ARCHITECTURE.md` §10 "**Logging.**" does claim that `runner.py` binds `job_id`, `stage`, `attempt` and `backend`, and that "a test enforces it". The drift Gotcha is accurate. `docs/skeleton-notes.md` A14 records the D8 test as not written.
- The uvicorn `LOGGING_CONFIG` claims (handlers, formatters, streams, `propagate: False`, `uvicorn.error` with no handler) match the installed `uvicorn/config.py`. The README runs `uvicorn --factory`.
- Line-number detectors: both greps return zero hits. Every `[[slug]]` link resolves to an existing document under `docs/`.

## Advisory (not blocking)

- The Gotcha about uvicorn's own lines cites `.venv/lib/python3.14/site-packages/uvicorn/config.py` (`LOGGING_CONFIG`). The claim is correct and the path resolves in this checkout. But `.venv` is git-ignored and the path is tied to the interpreter version, so a fresh clone or a run worktree will not have it. Consider citing it by module instead, `uvicorn.config` (`LOGGING_CONFIG`), so the anchor survives without a local venv.
