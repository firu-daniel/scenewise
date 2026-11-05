# Health Probes (/healthz, /readyz)

> Lets a platform such as Cloud Run check two things: whether a scenewise instance is still alive (`/healthz`), and whether it finished starting up and which stages it can run (`/readyz`).

## Business behaviour
- **Two unauthenticated GET endpoints with JSON bodies, both registered on `router`** (`src/scenewise/service/http/routes.py` `healthz`, `readyz`). Neither takes a body or a parameter, and neither touches the job store.
- **`GET /healthz`, the liveness probe.** It answers **200** `{"status": "ok"}` while no admitted job has run longer than `attempt_budget_s + watchdog_grace_s`. Once one has, it answers **503** `{"status": "hung", "jobs": [<job_id>, ...]}`. The list holds every overdue job id in sorted order. The design intent is that the Cloud Run liveness probe fails repeatedly, the platform kills the instance and starts a new one, and all of this happens before the job's lease ends. Cloud Tasks then retries, and the next attempt takes over cleanly after the lease (`src/scenewise/service/http/health.py` module docstring; `ARCHITECTURE.md` §7 "Crash or watchdog kill", §8 "Liveness watchdog").
- **Why the watchdog exists.** The attempt deadline is cooperative: `run_job` checks it between stages and frame batches, and Python cannot cancel a thread. A single native call that hangs, such as one long model call, is therefore never interrupted, and the watchdog covers that case. A native call that holds the GIL also stops `/healthz` from answering, so the probe times out, which has the same effect (`docs/research/q8a-architecture-layout.md` §6.3).
- **What a kill costs.** Every other job running on the same instance dies with the hung one. Each is retried after its own lease expires (`docs/research/q8a-architecture-layout.md` §6.3). Correctness still rests on generation fencing, not on the probe. On the CLI, or for a self-hoster with no probe, nothing kills a hung job, and fencing alone handles the zombie case (`ARCHITECTURE.md` §8).
- **`GET /readyz`, the start-up probe.** It always answers **200** `{"status": "ready", "stages": [...]}`. `stages` is the sorted list of `Dependencies.enabled_stages`; today that is `["audio"]` (`tests/e2e/test_http.py` `test_probes`). The route has no failure branch. Readiness comes from the fact that it answers at all: the lifespan builds every dependency before the app serves any request. If that build fails (missing ffmpeg/ffprobe, a `required_stages` entry with no back end, an unsupported `state_prefix` scheme), it raises `ConfigurationError`, the process never serves, and the revision never becomes ready (`src/scenewise/service/bootstrap.py` `build_dependencies`; `ARCHITECTURE.md` §9 "Stages the deployment cannot run").
- **Timing invariant.** Settings are rejected at load time unless `attempt_budget_s + watchdog_grace_s + probe_period_s × probe_failure_threshold < dispatch_deadline_s`. With the defaults this is 1500 + 120 + 10 × 3 = 1650 < 1800, so a hung job is killed about 1650 s after it started, which is before the 1920 s lease (`dispatch_deadline_s + lease_margin_s`) ends (`src/scenewise/service/config.py` `ServiceSettings._timing`, `ServiceSettings.lease_s`).

## Invoked from
- The platform's probes: a Cloud Run HTTP liveness probe on `/healthz` and a start-up probe on `/readyz`, as `ARCHITECTURE.md` §7–§8 and `docs/research/q8a-architecture-layout.md` §6.3 design them (the design values are period 10 s, failure threshold 3, timeout 5 s). ⚠️ unverified: the repository tracks no deployment manifest that declares these probes, so the actual probe configuration belongs to the adopter.
- An operator with `curl` against a server started with `uvicorn --factory scenewise.service.http.app:create_app` (`README.md`).
- Nothing inside the package calls either route. The CLI has no HTTP surface and no watchdog.
- Tests: `tests/e2e/test_http.py` (`test_probes`) through FastAPI's `TestClient`.

## Technical implementation
### domain
- `src/scenewise/domain/jobs.py` (`StageName`): the enum whose values make up the `/readyz` `stages` list and `ServiceSettings.required_stages`.

### app
- `src/scenewise/app/deps.py` (`Dependencies.enabled_stages`): the set `/readyz` reports. It is computed once by `src/scenewise/app/deps.py` (`enabled_stages`). `audio` is always present because it needs only the media tool. `captions` needs `speech`; `summary` and `chapters` also need `text`; `labels` needs `labeller`; `moderation` needs `labeller` and `moderator`.
- **Provenance: who writes what `/readyz` reads.** `src/scenewise/service/bootstrap.py` (`build_dependencies`) is the only writer. Today it calls `enabled_stages(speech=None, text=None, moderator=None, labeller=None)` because no model back end is wired yet, so the answer is `{audio}`. The same set gates jobs: `src/scenewise/app/runner.py` (`run_job`) raises `InputError(code="stage_unavailable")` for a requested stage outside it. `/readyz` therefore shows exactly which stages a job can request from this instance.
- The probe bodies are built inline in the route, not in `src/scenewise/app/contract/`. Whether they belong to the wire contract is an open question (`.claude/context/conventions.md` `## Not determined`).

### adapters
- There are no probe-specific adapters. Building `FfmpegMediaTool`/`PillowImageReader` and the stores in `build_dependencies` is the start-up work whose success `/readyz` signals.

### service
- `src/scenewise/service/http/health.py` (`Watchdog`): the registry of in-flight jobs. `__init__(limit_s=...)` sets the limit. `watch(job_id)` is a context manager: it records `(job_id, time.monotonic())` under a private counter key while holding a `threading.Lock`, and removes the entry in `finally`. `overdue(now)` copies the entries under the lock and returns the sorted ids whose age exceeds `limit_s`.
- `src/scenewise/service/http/app.py` (`create_app`): the lifespan builds `Settings`, configures logging, calls `build_dependencies`, and stores one `ServiceState` on `app.state.scenewise`, with `watchdog=Watchdog(limit_s=service.attempt_budget_s + service.watchdog_grace_s)`. The registry lives on the app instance, never at module level.
- `src/scenewise/service/http/state.py` (`ServiceState`): the frozen dataclass that holds `watchdog` and `deps`.
- `src/scenewise/service/http/push.py` (`_admitted`): the only caller of `watch`. The job is registered after the `limiter.acquire_nowait()` admission in `push` succeeds, and it stays registered while `handle_delivery` runs in the worker thread (`anyio.to_thread.run_sync`). A request answered 413, 422 or 429 is never registered.
- `src/scenewise/service/http/routes.py` (`healthz`, `readyz`, `_state`): sync handlers. `healthz` calls `watchdog.overdue(time.monotonic())`. `readyz` sorts `deps.enabled_stages`. Neither reads `ServiceState.limiter`, so the in-app admission limit never answers either probe with 429.
- `src/scenewise/service/config.py` (`ServiceSettings`): `attempt_budget_s` (1500), `watchdog_grace_s` (120), `probe_period_s` (10), `probe_failure_threshold` (3), `dispatch_deadline_s` (1800) and `lease_margin_s` (120), set through `SCENEWISE_SERVICE__<FIELD>`. `probe_period_s` and `probe_failure_threshold` are read only by the `_timing` validator. They describe the platform's probe configuration so the invariant can be checked, but they do not configure it (`docs/skeleton-notes.md` A7).

### package
- No contribution. `src/scenewise/ports.py` has no probe-related port.

### tests
- `tests/unit/test_service.py` (`test_watchdog_reports_only_overdue_jobs`): overdue only past the limit, and empty again once the `watch` blocks exit.
- `tests/unit/test_service.py` (`test_timing_invariant`): `lease_s == 1920`, and `attempt_budget_s=1700` is rejected with a message that names `dispatch_deadline_s`.
- `tests/e2e/test_http.py` (`test_probes`): the healthy `/healthz` body and the `/readyz` body `["audio"]`. No end-to-end test covers the 503 `hung` path.
- `tests/unit/test_deps.py` and `tests/e2e/test_bootstrap.py`: the `enabled_stages` derivation and the bootstrap result `{audio}`.

### general
- `ARCHITECTURE.md` §7 (Timing), §8 (Liveness watchdog) and §9 hold the design statement. `docs/research/q8a-architecture-layout.md` §6.3 has the full rationale and the Cloud Run probe semantics.

### Backend surface
- **`GET /healthz`**. Request: none. Response: 200 `{"status":"ok"}`, or 503 `{"status":"hung","jobs":[str,...]}`. Side effects: none. **reachable? ✅** It is on `router`, which `create_app` includes, and is exercised by `test_probes`.
- **`GET /readyz`**. Request: none. Response: 200 `{"status":"ready","stages":[str,...]}`. Side effects: none. **reachable? ✅** It is on `router` and exercised by `test_probes`.

## Gotchas
- **`/readyz` does not report model loading yet.** `ARCHITECTURE.md` §7 describes it as reporting model loading, but no model back end exists. Today it only shows that the lifespan finished and lists the stages that are on.
- **Duplicate ids in `jobs`.** `watch` keys entries by a counter, not by job id. Two concurrent deliveries of the same `job_id` both count as overdue, and that id then appears twice in the 503 body.
- **Probe starvation and concurrency are open questions.** Whether torch releases the GIL (Q-5) and whether Cloud Run probes take a request slot at `concurrency = max_jobs` (Q-19) are both unverified. If probes do take a slot, a liveness probe could queue behind long jobs and kill a healthy instance (`docs/research/open-decisions.md`; `docs/research/q8a-architecture-layout.md` Q-19).
- **The watchdog uses the monotonic clock, and the record uses wall time.** `overdue` takes `time.monotonic()`, while lease checks use `time.time()`. Never pass a wall-clock `now` to `overdue`.

## Anchor files
- `src/scenewise/service/http/routes.py` (`healthz`, `readyz`, `_state`): the two probe routes
- `src/scenewise/service/http/health.py` (`Watchdog`): the in-flight job registry behind `/healthz`
- `src/scenewise/service/http/app.py` (`create_app`): the lifespan that builds `Watchdog` and `Dependencies`
- `src/scenewise/service/http/state.py` (`ServiceState`): holds `watchdog` and `deps`
- `src/scenewise/service/http/push.py` (`_admitted`): registers each admitted job with the watchdog
- `src/scenewise/service/config.py` (`ServiceSettings`): budget, grace and probe settings, and the `_timing` invariant
- `src/scenewise/service/bootstrap.py` (`build_dependencies`): start-up checks and the `enabled_stages` value
- `src/scenewise/app/deps.py` (`Dependencies`, `enabled_stages`): the stage set `/readyz` reports
- `src/scenewise/app/runner.py` (`run_job`): enforces the same stage set on jobs
- `src/scenewise/domain/jobs.py` (`StageName`): stage names
- `tests/unit/test_service.py` (`test_watchdog_reports_only_overdue_jobs`, `test_timing_invariant`): unit coverage
- `tests/e2e/test_http.py` (`test_probes`): end-to-end probe bodies

## Related
- [[job-submission]] · [[job-lifecycle-and-timing]] · [[configuration]] · [[stages-and-outcomes]] · [[wire-contract]] · [[layering-and-ports]]
