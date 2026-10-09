# Review 2: docs/concepts/layering-and-ports.md

verdict: PASS

## Review 1 items

- **Must Fix 1 (the `routes.py` consumer bullet): fixed.** `readyz` now only reports `deps.enabled_stages`. `get_job` passes `store=state.deps.store` and `state_prefix=state.settings.service.state_prefix` to `job_status`, which matches `src/scenewise/service/http/routes.py`. The lead-in now says the `app` use cases never read `Settings` and the `service` routes do. `routes.py` (`get_job`, `readyz`) has been added to `## Anchor files`.
- **Should Fix (the `push.py` consumer): fixed.** `src/scenewise/service/http/push.py` (`push`, `_admitted`) passes `deps=state.deps` and `policy=state.policy` to `handle_delivery` through `anyio.to_thread.run_sync`. It reads `state.settings.service` for `lease_s` and `max_attempts`. The doc says this, and the file is in the anchor list.
- **Should Fix (the field block): fixed.** The block now matches the fields, defaults and inline comments in `src/scenewise/app/deps.py` (`Dependencies`) exactly. The "not offered" meaning is attributed to the class docstring.
- **Should Fix (the shortened contract names): fixed.** Both `allowed_externals` contract names are now quoted in full.

## Re-verified this round

- Both line-number detectors return zero hits.
- Every path and symbol in `## Anchor files` and inline resolves. I checked `pyproject.toml`, `scripts/import_contracts.py`, `ports.py`, `deps.py`, `bootstrap.py`, the three adapters, `http/app.py`, `http/state.py`, `cli.py`, `runner.py`, `delivery.py`, `push.py`, `routes.py`, `__main__.py`, `tests/fakes.py`, the three contract mixins and both tests in `tests/e2e/test_bootstrap.py`.
- `pyproject.toml` has six import-linter contracts. Their types and options match the doc (`exhaustive`, `exhaustive_ignores`, `allowed_importers`, `allow_indirect_imports`). The ruff `PLC0415` exemption for bootstrap only is also there.
- `ports.py` declares ten Protocols, plus `Blob`, `WriteConflictError` and the three constants. It imports only stdlib and `scenewise.domain`.
- The `enabled_stages` logic, the `build_dependencies` steps and the `_stores` `match` (the `file` case, the `excluded=outputs` argument, and `store_unavailable`) match the code. So do the codes `find_binaries` raises (`ffmpeg_unavailable`, `ffmpeg_too_old`).
- No module under `app` or `service` reads `deps.images`, `notifier`, `speech` or `labeller`.
- The claims about `ARCHITECTURE.md` §4 (a required `notifier`, a `guard` field, no `inputs` field) and §14 (no DI container, no ABC ports, no plugin entry points) are accurate. So are `docs/skeleton-notes.md` A6, A8 and A10, and the cited `Order of work in a feature` and `## Not determined` entries in `.claude/context/conventions.md` and `.claude/context/service.md`.
- Every `[[slug]]` in `## Where it's used` and `## Related` exists in `docs/features` or `docs/concepts`.
- The research goes well past the hints: it covers the builders, the consumers, the test fakes, the contract mixins and the departures from the architecture. Parity is off, so it is correctly not covered.

## Must Fix

None.

missed_docs: n/a (catalog mode)
