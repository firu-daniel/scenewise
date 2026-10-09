# Review 0: docs/features/health-probes.md (mode: catalog)

verdict: PASS

## Must Fix
None.

## Checks performed
1. Anchors: every path in `## Anchor files` and inline exists, and every named symbol was found in its cited file: `healthz`, `readyz`, `_state`, `router` in routes.py; `Watchdog`, `watch`, `overdue` in health.py; `create_app` in app.py; `ServiceState` in state.py; `_admitted`, `push` in push.py; `ServiceSettings`, `_timing`, `lease_s` in config.py; `build_dependencies` in bootstrap.py; `Dependencies`, `enabled_stages` in deps.py; `run_job` in runner.py; `StageName` in jobs.py; the three named tests. Prose references also resolve: ARCHITECTURE.md §7 "Timing" paragraph and "Crash or watchdog kill" row, §8 "Liveness watchdog", §9 "Stages the deployment cannot run"; q8a §6.3, Q-5 and Q-19; open-decisions.md; skeleton-notes.md A7; conventions.md `## Not determined` (probe bodies); the README `uvicorn --factory` line.
2. Line numbers: the colon detector found none. The shape detector found one line, which holds the config defaults (1500, 120, 10, 3, 1800, 120). These are values, not line coordinates.
3. Backend surface: the 200/503 bodies, the sorted `jobs` list, the `readyz` body with no failure branch, and `reachable? ✅` all match the code. Both routes are on `router`, `create_app` includes it, and `test_probes` calls both.
4. Data shapes: the `enabled_stages` derivation (audio always; captions needs speech; summary and chapters also need text; labels needs labeller; moderation needs labeller and moderator), the `StageName` values and the config defaults all match. The invariant arithmetic (1650 < 1800) and lease 1920 match `_timing` and `lease_s`. The doc correctly avoids calling the timing rejection a ConfigurationError; it is a pydantic ValidationError.
5. Gating: watch is registered only after `acquire_nowait` succeeds and covers the `to_thread.run_sync` delivery. The doc's 413/422/429 claim holds: those errors (MediaTooLargeError, InputError, CapacityError, mapped in problems.py) are all raised before `_admitted`. The watchdog uses `time.monotonic` and keys entries on a counter, so the duplicate-id gotcha is correct. `probe_period_s` and `probe_failure_threshold` are read only in `_timing` (checked with grep).
6. Depth: the doc traces provenance. `build_dependencies` is the only writer of `enabled_stages`, `run_job` enforces the same set, and start-up failure modes (ffmpeg via `find_binaries`, required_stages, the state_prefix scheme) are tied to readiness.
7. Parity: skipped (`phases.parity` is false).
8. Unverified marker: honest. No deployment manifest in the repo declares probes.
9. Omission: none found. Leaving out the Local state section is correct; this feature keeps nothing in local storage.
10. Merge/supersede: not applicable (no existing_doc).

## Notes (not findings)
- `ServiceState` also holds `settings`, `policy` and `limiter`. The doc names only the two fields relevant here, which is accurate.
