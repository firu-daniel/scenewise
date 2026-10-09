# Review: docs/concepts/logging.md (catalog, iteration 0)

verdict: FAIL

The document is accurate and well researched almost throughout. I verified the whole of `configure` (processor chain, renderers, handler replacement), `LogSettings` / `_Group` / `Settings` env config, the CLI and lifespan call sites, every event in the table against its emitting function, every `bound_contextvars` site and its scope, `_TASK_HEADERS` / `_log_context`, `_validation_summary` and its test, the `errors.py` docstring and the `"{code}: {detail}"` exception message, the import-linter allow-lists, ruff `T201`, `ARCHITECTURE.md` §10 and `docs/skeleton-notes.md` A14. Both line-number detectors return zero hits, and every `[[slug]]` link resolves to a file under `docs/`. Two items must change.

## Must Fix

1. **Check 8: the `⚠️ unverified` marker is answerable with a grep.** (Gotchas, the uvicorn bullet.)
   - Claim: it is unverified whether uvicorn's `uvicorn` / `uvicorn.access` lines come out in scenewise's format.
   - Evidence: the installed uvicorn's `LOGGING_CONFIG` (`.venv/lib/python3.14/site-packages/uvicorn/config.py`, `LOGGING_CONFIG`) gives `uvicorn` its own `default` handler (`uvicorn.logging.DefaultFormatter`) and gives `uvicorn.access` its own `access` handler (`uvicorn.logging.AccessFormatter`). Both have `"propagate": False`. `uvicorn.error` has no handler and propagates to `uvicorn`.
   - Why it holds: `configure` replaces only the root logger's handlers, so these records never reach the scenewise handler.
   - Correction: drop the marker and state it as fact. When the service is started with the README's plain `uvicorn --factory ...` (default `log_config`), uvicorn's server and access lines are written by uvicorn's own handlers in uvicorn's text format, not as scenewise JSON. Cite uvicorn's `LOGGING_CONFIG`.

2. **Check 1: a symbol that does not exist.** (Redaction (D8), "Error details" bullet: "A `detail` reaches the wire (`ErrorInfo.message`, the problem body)".)
   - The code has no `ErrorInfo`. The wire model is `ErrorInfoV1` in `src/scenewise/app/contract/results.py`, and its `message` field is filled from `Failed.detail` in `src/scenewise/app/contract/mapping.py` (`_stage_fields`).
   - Correction: write `ErrorInfoV1.message`. Optionally anchor the problem body as `src/scenewise/app/contract/mapping.py` (`problem`), where `detail=error.detail or error.code`.

## Advisory (not blocking)

- Binding context table, `attempt` row ("from the claim through run and finish"): `_attempt` binds `attempt` only after the claim write succeeds, so the claim write itself is outside the binding. Something like "from after the claim write through run and finish" would be exact. It has no effect today, because the claim write emits no log line.
