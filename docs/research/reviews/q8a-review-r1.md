# Review r1: q8a-architecture-layout.md

Reviewer: fresh review agent (did not write the file). Date: 2026-10-08. All sources below were re-opened on 2026-10-08 (PyPI JSON API, GitHub API at the cited commits, and WebFetch of the cited pages).

Severity scale: wrong / unsupported / missing option / design concern / minor.

Verdict: the citations are unusually accurate. Every package version, upload date, commit hash and line count checks out. The real problems are in the design. The Cloud Tasks integration has no idempotency, no handling for exhausted retries and no authentication. The limiter and error semantics contradict themselves. The dependency rule breaks on its own Expause routes. The torch/CUDA extras would produce a broken GPU image.

## Findings

### A. Factual / citation issues

1. **§6.4 and Q-7: "Cloud Tasks `HttpRequest` reference as mirrored at googleapis.dev …; the official page did not state codes".**
   Source: the official REST reference https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks (read 2026-10-08) states all of it. A successful response is 200–299. "If any other HTTP response code is returned or no response is received, the task will be retried". On 429 or 503 Cloud Tasks "will use a higher backoff rate". "The retry specified in the `Retry-After` HTTP response header is considered". `dispatchDeadline` defaults to 10 min and must lie in [15 s, 30 min].
   Severity: **wrong**. The official source exists and confirms the behaviour.
   Correction: cite the official REST reference, drop the mirror, and close Q-7.

2. **§6.3 and Q-6: "That they behave the same for Cloud Run stdout is a lead (Q-6)".**
   Source: https://docs.cloud.google.com/run/docs/logging (updated 2026-10-07) documents this directly for Cloud Run. One line of JSON goes to `jsonPayload`. `severity` is lifted into the entry's severity. `message` is the display text. `logging.googleapis.com/trace` (taken from `X-Cloud-Trace-Context`) nests container logs under the request log. Special fields are stripped from `jsonPayload`.
   Severity: **unsupported**. The claim was left as a lead even though it is resolvable.
   Correction: cite the Cloud Run logging page and close Q-6. Note that the trace value must be `projects/<id>/traces/<trace-id>`, parsed from `X-Cloud-Trace-Context` (or `traceparent`).

3. **§6.1: "`cp314t` wheels exist for … pydantic-core 2.49.0".**
   Source: https://pypi.org/pypi/pydantic/json shows that pydantic 2.13.5 requires `pydantic-core==2.46.5`, not 2.49.0 (2.49.0 is the latest pydantic-core, uploaded 2026-09-09). pydantic-core 2.46.5 also ships 15 cp314t wheels (https://pypi.org/pypi/pydantic-core/2.46.5/json), so the conclusion holds.
   Severity: **wrong** (low impact).
   Correction: write "pydantic-core 2.46.5 (the version pinned by pydantic 2.13.5)".

4. **§6.1 and Q-5: "Unverified lead: inference kernels in torch and CTranslate2 release the GIL".**
   Source: https://opennmt.net/CTranslate2/parallel.html (read 2026-10-08): "Parallelization with multiple Python threads is possible because all computation methods release the Python GIL." Concurrent calls also need `inter_threads` ≥ the number of concurrent callers, otherwise they queue inside CTranslate2. llama-cpp-python calls through `ctypes.CDLL`, which releases the GIL for the duration of each foreign call (Python `ctypes` docs).
   Severity: **unsupported**. It is resolvable for CTranslate2, and the doc leaves it open.
   Correction: mark CTranslate2 as verified and add the `inter_threads` note. Keep torch/open_clip and llama-cpp-python as items still to verify.

5. **Q-1: "The costs are a Python ≥3.12 floor (from `av`)".**
   Source: faster-whisper 1.2.1 requires `av>=11` (https://pypi.org/pypi/faster-whisper/json). Only av 19.x needs Python ≥3.12 (`requires_python >=3.12`, abi3 cp312 wheels). On Python < 3.12 the resolver simply picks an older av.
   Severity: **minor**.
   Correction: "a ≥3.12 floor *if we require PyAV 19 (FFmpeg 8)*". Otherwise there is no floor.

6. **Q-2: "is there an accepted standard for declaring an external `ffmpeg` requirement … Not researched".**
   Source: PEP 725, "Specifying external dependencies in pyproject.toml", https://peps.python.org/pep-0725/ (Status: Draft, last modified 2026-04-17). It defines an `[external]` table with DepURLs such as `dep:generic/ffmpeg`. The name registry is deferred to companion PEP 804.
   Severity: **missing option**.
   Correction: name PEP 725/804 as Draft and not accepted. Optionally add an informational `[external]` table, which is harmless to tools that ignore it.

7. **§2.1: cosmicpython "suggest PEP 544 protocols instead".**
   Source: https://www.cosmicpython.com/book/chapter_02_repository.html. The book mentions Protocols as an option ("give you typing without the possibility of inheritance", which suits composition fans). It does not recommend them over ABCs.
   Severity: **minor** (framing).
   Correction: "they mention PEP 544 protocols as an alternative".

8. **§6.1: FastAPI "points to multiprocessing at the deployment level (Uvicorn workers)".**
   Source: https://fastapi.tiangolo.com/async/. The page says parallelism helps "**CPU bound** workloads like those in Machine Learning systems" and links to "Deployment". It does not name Uvicorn workers.
   Severity: **minor**.
   Correction: say "links to its Deployment section". You may add the "Server Workers" page as a separate citation.

9. **§6.1: Cloud Run jobs GPU summary.**
   Source: https://docs.cloud.google.com/run/docs/configuring/jobs/gpu (updated 2026-10-07). The RTX PRO 6000 needs at least 20 CPU and 80 GiB. GPU jobs support only *non-zonal* redundancy and must be deployed with `--no-gpu-zonal-redundancy`. New projects get 3 GPUs per region of quota, and parallelism above quota fails the deployment. The driver is 580.x (CUDA 13.0).
   Severity: **minor** (omissions that matter for planning).
   Correction: add these constraints next to Q-9.

10. **§9 Warehouse: "A production service that does ports and adapters in Python. Take: the explicit `interfaces` module".**
    Source: at warehouse `14b79b44aa`, ports are resolved through `pyramid_services` (`config.register_service_factory(..., IFileStorage)` in `warehouse/packaging/__init__.py`, and `pyramid_services>=2.1` in `requirements/main.in`), looked up with `request.find_service`. That is a service locator. Warehouse also has a package-local `warehouse/logging.py` and `utils/` directories.
    Severity: **minor**, but it undercuts two rules in §1.4 and §2.2.
    Correction: state that the one production exemplar pairs interfaces with a service locator, which is what `svcs` offers. Explain why scenewise still does not need one (a single composition root and few entry points).

### B. Design concerns

11. **§1.5 rule 5 vs the entry-point box: `adapters/expause/routes` is listed as an entry point that "may import bootstrap, config, observability, pipeline". Rule 5 says "`adapters.*` must not import `pipeline`, `service`, `cli` or `bootstrap`".**
    Analysis: the rule contradicts itself. The routes need `run_job`, the problem mapping and the execution helper. The root cause is that the doc does not separate *driving* (primary) adapters from *driven* (secondary) adapters, the core distinction of hexagonal architecture (Cockburn). Expause has both: `routes.py` and `payloads.py` are driving, and `results.py` (ResultSink) is driven.
    Severity: **design concern** (high). An import linter cannot encode the rule as written.
    Correction: move the driving part to `service/expause.py`, or to a top-level `scenewise/expause/` treated as an entry point. Keep only `ExpauseResultSink` under `adapters/`. Rewrite rule 5 accordingly.

12. **§4 ports and `Dependencies`: `FrameSource.frames(plan)` takes no media argument. `Dependencies` has no frame source at all. §1.4 and §3 refer to a `VideoFrameSource` port that §4 does not define.**
    Analysis: as declared, a `FrameSource` must be built per input (video path, image list, sprite sheet plus grid). That is per-job state, so it cannot live in the long-lived `Dependencies` bundle. `label()` and `moderate()` have no way to get frames.
    Severity: **design concern**.
    Correction: either (a) declare `frames(self, source: Path | FramesInput | SpriteSheetInput, plan: Sequence[Seconds]) -> Iterator[Frame]` and add `frames: FrameSource` to `Dependencies`, or (b) make frame acquisition a pipeline function that dispatches on the `Input` kind (with `match`) to the ffmpeg adapter and the image adapter. Option (b) removes one port. Also move `probe()` out of `AudioExtractor` (it is not about audio) into a `MediaProbe` port, or rename the port `MediaTool`. That is the doc's own interface-segregation principle.

13. **§0 says "a per-model `CapacityLimiter`". §6.1 says "a per-device `anyio.CapacityLimiter(1)`" and passes it to `to_thread.run_sync(run_job, …, limiter=model_limiter)`.**
    Analysis: these are three different things. Passing the limiter to `run_sync` around `run_job` holds the token for the *whole job*: ffmpeg extraction, hosted Haiku calls and GCS I/O, while the GPU sits idle. On CPU-only deployments it also serialises everything to one job per process. And an anyio limiter cannot be used from inside the synchronous worker thread without `from_thread`.
    Severity: **design concern**.
    Correction: let each model adapter own a `threading.Lock` or `threading.BoundedSemaphore(n)` around its inference call. That is truly per model, works the same in the CLI and the service, and needs no anyio inside the pipeline. Then use the anyio limiter on `run_sync` only for total job admission (`total_tokens` = Cloud Run concurrency).

14. **§6.4 `CapacityError code="busy" (limiter full / GPU OOM)` → 429 + Retry-After.**
    Analysis: `to_thread.run_sync(..., limiter=…)` *waits* for a token. It never raises when the limiter is full (https://anyio.readthedocs.io/en/stable/threads.html), so nothing produces "limiter full" as designed. GPU OOM for a given input is usually deterministic (a long video, a large batch), so classing it as retryable burns every queue attempt (the sample config shows `maxAttempts: 100`).
    Severity: **design concern**.
    Correction: if 429 is wanted, do an explicit non-blocking admission check (`limiter.acquire_nowait()` → `WouldBlock` → `CapacityError`). Otherwise remove "limiter full". Treat OOM as retryable at most once (for example after shrinking the batch), then as `PermanentError`.

15. **Missing: idempotency and at-least-once delivery.**
    Source: https://docs.cloud.google.com/tasks/docs/dual-overview: Cloud Tasks is "designed to provide 'at least once' delivery … your code must ensure that there are no harmful side-effects of repeated execution … Your handlers should be idempotent." Cloud Run request-timeout docs: for timeouts above 15 min, make requests idempotent or resumable.
    Severity: **missing option** (high).
    Correction: key all outputs by `job_id` (deterministic GCS paths, write-if-absent through `ifGenerationMatch=0`, or a done-marker object). Check for that marker at the start of the handler and acknowledge duplicates. Use the Cloud Tasks task name (`X-CloudTasks-TaskName`) or the Expause job id as the idempotency key.

16. **Missing: the deadline and timeout interplay, and runaway threads.**
    Sources: the HTTP target `dispatchDeadline` defaults to 10 min (max 30 min, see #1). The Cloud Run service request timeout defaults to 5 min (max 60 min; https://cloud.google.com/run/docs/configuring/request-timeout). anyio: on cancellation "the thread will still continue running".
    Analysis: if the job outlives the deadline, Cloud Tasks retries while the first run is still busy in its worker thread. Two copies of the same job then run, queued behind the same limiter on the same instance.
    Severity: **design concern**.
    Correction: require Cloud Run timeout ≥ `dispatchDeadline`, and set `dispatchDeadline` explicitly per task. Estimate the duration from `probe()` and route anything near the deadline to the Cloud Run job path (§6.1 item 4) before starting. Rely on #15 to deduplicate.

17. **Missing: what happens when retries run out.**
    Source: https://docs.cloud.google.com/tasks/docs/configuring-queues (updated 2026-10-07): once the limits are reached "no further attempts are made, and the task is deleted". There is no dead-letter queue.
    Analysis: under §6.4, `RetryableError` and unexpected exceptions never write a failure record, so Expause sees the job silently vanish.
    Severity: **missing option**.
    Correction: read `X-CloudTasks-TaskRetryCount` (and/or `X-CloudTasks-TaskExecutionCount`) and compare it with the queue's `maxAttempts`, passed in through `ExpauseSettings`. On the final attempt, write a failure record and return 2xx. Also set `maxRetryDuration` deliberately.

18. **`ModelOutputError` is `RetryableError` at task level.**
    Analysis: a bad LLM JSON reply makes Cloud Tasks re-run the whole job, including possibly an hour of ASR. Any failed stage restarts from zero.
    Severity: **design concern**.
    Correction: retry the LLM call inside `chapter()`/`summarise()` (bounded, for example 2 attempts, optionally with a repair prompt), then raise `PermanentError`. Also persist intermediate stage outputs (the transcript) under the job's prefix through `BlobStore`, so a retry resumes. This matches Cloud Run's "resume where they stopped" advice and the existing `stage_timings` per-stage structure.

19. **`StageUnavailableError` is an `InputError` (caller's fault, acknowledged with 2xx for Expause).**
    Analysis: a stage that is requested but not configured is a *deployment* fault. For Expause it would quietly acknowledge and drop every job that needs, for example, ASR after a bad deploy.
    Severity: **design concern**.
    Correction: keep 422 for the generic public API, where callers choose stages. For the Expause adapter, check the required stages against `Dependencies` at start-up (`ConfigurationError`), or map the error to `PermanentError` with an alerting log line.

20. **§5 `TimeSpan.__post_init__` raises `InputError`.**
    Analysis: TimeSpans are also built by adapters from model output (ASR segments, parsed chapters). An invalid span from a model bug would be classed as the caller's fault and acknowledged. It also couples the pure domain values to HTTP-flavoured semantics.
    Severity: **design concern**.
    Correction: domain constructors raise plain `ValueError`. Boundaries translate: `schemas.to_domain` → `InputError`, and adapter/core parsing → `ModelOutputError`/`PermanentError`.

21. **Missing: authentication of the Cloud Tasks push.**
    Analysis: the Expause routes accept job payloads over HTTP, and the doc never mentions authenticating them.
    Severity: **missing option**.
    Correction: deploy with IAM-only invocation (`--no-allow-unauthenticated`) and give the Cloud Tasks HTTP task an `oidcToken` for a dedicated service account. If the generic API shares the service, verify the OIDC audience in the Expause router.

22. **§6.4 table "unknown job id → 404" and "/v1/analyses endpoints" vs §2.2 "no Repository … there is no database".**
    Analysis: a GET on a job id implies persisted job state (status, result location). The doc does not say where that lives.
    Severity: **design concern**.
    Correction: either make the generic API synchronous (POST returns the Analysis, with no job resource), or define job status as objects under the job's `BlobStore` prefix (status.json written by the runner). That also serves as the idempotency marker in #15.

23. **§7.2/§7.3 torch extras: `vision = ["torch>=2.14", "open-clip-torch>=3.3", "pillow"]`, with routing only for `torch` through `cpu`/`cu130`.**
    Sources: open-clip-torch 3.3.0 requires `torchvision` and `timm` (https://pypi.org/pypi/open-clip-torch/json). The uv guide says torchvision needs the same index routing as torch (https://docs.astral.sh/uv/guides/integration/pytorch/).
    Analysis: an unrouted torchvision from PyPI next to a CPU or cu130 torch gives mismatched builds. `--extra vision` without `cpu`/`cu130` silently pulls PyPI's default torch build.
    Severity: **design concern**.
    Correction: route `torchvision` in `[tool.uv.sources]` too. Make `vision` require one of `cpu`/`cu130` (documented, and checked in bootstrap via `torch.version.cuda`).

24. **Missing: CUDA major version mismatch between CTranslate2 and torch `cu130`.**
    Source: ctranslate2 4.8.2 on PyPI declares `Environment :: GPU :: NVIDIA CUDA :: 12 :: 12.4`, and its wheels load CUDA 12/cuDNN 9 dynamically and do not bundle them.
    Analysis: a single GPU image with `asr-local` and `vision`+`cu130` needs two CUDA user-space stacks (the cu13 `nvidia-*` wheels for torch, plus CUDA 12 cuBLAS/cuDNN for CTranslate2). The Cloud Run 580 driver supports both, but the image grows and setup gets fragile.
    Severity: **missing option**.
    Correction: offer a `cu128` (or `cu126`) extra, which the uv guide also lists, so torch shares the CUDA 12 runtime with CTranslate2. Alternatively, split the ASR and vision images. Record this in Q-8/Q-10.

25. **Missing options for long and GPU work (§6.1 item 4).**
    Sources: Cloud Run jobs can be executed with per-run overrides (args, env, task count, timeout) through the `:run` REST endpoint (https://docs.cloud.google.com/run/docs/execute/jobs). Cloud Run *worker pools* support L4 and RTX PRO 6000 GPUs (https://docs.cloud.google.com/run/docs/configuring/workerpools/gpu, updated 2026-10-07; launch stage not stated).
    Severity: **missing option**.
    Correction: compare three options. (a) A Cloud Tasks HTTP task that calls the jobs `:run` API directly, with an OAuth token and `--job-file` passed as an override. (b) A GPU worker pool pulling from Pub/Sub, which has no request deadline at all. (c) The current approach, a synchronous push handler. The doc never says who triggers the Cloud Run job.

26. **Missing options: model-serving frameworks.**
    Analysis: there is no mention of LitServe, BentoML, Ray Serve or Triton/Triton-Python, which solve batching, per-model workers and GPU admission. Rejecting them is probably right for a showcase with "no framework ceremony", but the doc should say so.
    Severity: **missing option** (minor).
    Correction: add one line rejecting them, with reasons (dependency weight; they hide the architecture being showcased).

27. **Missing option: generic Cloud Tasks driving adapter plus consumer-side mapping (Q-12).**
    Analysis: Q-12 offers only "in-tree extra" or "workspace member". A third option suits an open-source project better: scenewise ships a *generic* "push-queue" entry point (Cloud Tasks semantics: ack/retry policy, retry-count headers, idempotency, a documented payload schema). Expause maps its own payload to that schema in its own repo, or simply sends the generic schema.
    Severity: **missing option**.
    Correction: add it to Q-12. It makes the deletion test in §1.3 trivially true.

28. **§1.5/§3: `bootstrap` constructs `FasterWhisperRecognizer(settings.asr)`.**
    Analysis: the adapter would then depend on `config.AsrSettings`, which rule 5 does not list as an allowed import. Either the rule silently permits `config`, or the adapter is coupled to pydantic-settings.
    Severity: **design concern** (minor).
    Correction: give adapters plain keyword arguments (`model_path=`, `device=`, `compute_type=`) and have `bootstrap` unpack the settings. State in rule 5 that adapters never import `config`.

29. **§2.3 "Only the runner talks to `ResultSink`" vs §8, where the entry point calls `deps.sink.publish(job, analysis)` after `run_job`.**
    Severity: **minor** (internal inconsistency).
    Correction: pick one. The entry point publishing is cleaner, since the CLI may print instead of publishing. Fix §2.3 accordingly.

30. **§5 "Collections are `tuple[...]` so values are hashable" vs `Analysis.stage_timings: Mapping[...]`.**
    Analysis: a frozen dataclass holding a `MappingProxyType` is not hashable, and nothing in the design needs hashing.
    Severity: **minor**.
    Correction: justify tuples by immutability, not hashability, or use `tuple[tuple[StageName, float], ...]`.

31. **Undefined or misnamed domain names in the port signatures.**
    Analysis: `ModerationScores` (the port) does not match `ModerationScore`/`FrameModeration` (the domain). `MediaInfo`, `TextRequest`, `Frame` and `FrameRef` are used but not sketched in §5.
    Severity: **minor**.
    Correction: align the names and add the four types to the domain sketch.

32. **§6.4 error hierarchy: one subclass per `code`.**
    Analysis: about nine leaf classes, each existing only to carry a string, is mild Java-style ceremony. Callers branch on the category (`InputError`/`RetryableError`/`PermanentError`), not on the leaf. The base declares `code: ClassVar[str]` with no default.
    Severity: **design concern** (minor, about over-engineering).
    Correction: keep the 4 categories. Keep leaf classes only where HTTP mapping or `except` actually differs (`MediaTooLargeError`, `UnsupportedMediaError`, `CapacityError`). Pass `code` as an instance argument for the rest, and give the base a default `code="internal"`.

### C. Assessment of the design questions asked

- **Dependency rule.** It is coherent apart from #11 (driving adapter under `adapters/`) and #28 (config in adapters). Rule 6 (lazy imports in bootstrap) and rule 7 (heavy imports only in adapters) are good and enforceable.
- **Number of ports.** Eight is about right and not ceremonial. Each port covers a slow, nondeterministic or swappable boundary. Fixes needed: `FrameSource` (#12) and `probe()` placement (#12). `ResultSink` could be a plain function over `BlobStore`, but keeping it as a port is defensible because Expause's layout differs. No Stage, Clock or Repository classes, which is correct.
- **Domain model.** Sound and appropriately small. Issues: domain validation raising `InputError` (#20), undefined names (#31), and float `Seconds`. Float seconds are fine, but render WebVTT through millisecond rounding in one place in core.
- **Concurrency model.** The direction is right: a sync pipeline, one worker thread, models loaded once, scale by instance, no `ProcessPoolExecutor`. The limiter placement (#13), admission semantics (#14) and deadline/runaway-thread handling (#16) need fixing. CTranslate2 releasing the GIL (#4) supports the thread approach.
- **Error hierarchy vs Cloud Tasks.** The ack-non-retryable idea is correct and matches the official semantics (#1). The gaps are idempotency (#15), exhausted retries (#17), task-level retry of LLM output and OOM (#14, #18), the classification of stage-unavailable (#19), and authentication (#21).

## Claims verified correct

- PyPI on 2026-10-08:
  - pydantic 2.13.5 (2026-08-28, ≥3.9)
  - pydantic-settings 2.15.0 (2026-08-07, ≥3.10)
  - fastapi 0.142.4 (2026-10-07)
  - structlog 26.1.0 (2026-06-06)
  - av 19.0.1 (2026-10-03, ≥3.12)
  - faster-whisper 1.2.1 (2025-10-31; requires `av>=11` and `ctranslate2<5,>=4.0`)
  - ctranslate2 4.8.2
  - llama-cpp-python 0.3.36 (sdist only, 0 wheels)
  - anthropic 1.12.1, uvicorn 0.54.0, torch 2.14.1, open-clip-torch 3.3.0, transformers 5.19.0, starlette 1.7.0
  - ffmpeg-python 0.2.0 (2019-07-06)
- cp314t wheels exist for torch 2.14.1, ctranslate2 4.8.2, av 19.0.1, numpy 2.5.3 and onnxruntime 1.30.0 (onnxruntime only for manylinux x86_64 and aarch64).
- ffmpeg-python: last commit `df129c7ba3` on 2022-07-11; 479 open issues (excluding PRs); #875 "Incompatible with ffmpeg 7" is open.
- Commits exist with the stated dates: faster-whisper `9fa78645d7` (2026-10-06), WhisperX `771b4a14a9` (2026-09-26), LiteLLM `7a659973e3` (2026-10-08), vLLM `7d47ac2ddb` (2026-10-08), Pydantic AI `f55bb8a6fd` (2026-10-08), Warehouse `14b79b44aa` (2026-10-07).
- File sizes and layouts at those commits:
  - faster-whisper `transcribe.py`: 1,952 lines and 81,135 bytes. Flat layout, `setup.py`, `requirements.txt` and `utils.py`.
  - LiteLLM: `main.py` 9,435 lines, `router.py` 15,234 lines, `utils.py` 449,093 bytes; `proxy/` and `llms/` present.
  - WhisperX: `requires-python >=3.10, <3.14`, `torch~=2.8.0`, `[tool.uv.sources]` with platform markers routing to cu128 and cpu indexes, `uv.lock`, `utils.py`.
  - vLLM: `entrypoints/`, `v1/`, `model_executor/` and `platforms/` present.
  - Pydantic AI: workspace members as listed, `anthropic.py` 235 KB, `openai.py` 320 KB, `Model(AbstractModel)`, and per-provider extras.
  - Warehouse: `accounts`, `packaging` and `oidc` each have `interfaces.py` and `services.py`; `IGenericFileStorage` uses zope.interface.
  - None of faster-whisper, WhisperX, LiteLLM or vLLM uses `src/`.
- uv workspaces page: the definition, the single lockfile, the `requires-python` intersection, and "not suited for … conflicting requirements" are all accurate.
- uv PyTorch guide: `explicit = true`, the cpu/cu130 extras with `conflicts`, CUDA 13.0 as the current example, the index list (cpu, cu118, cu126, cu128, cu130, ROCm 7.2, XPU), the macOS markers, and `--torch-backend=auto` being `uv pip` only are all accurate.
- PyPA src-layout quotes are accurate.
- Hynek "Testing & Packaging" (2015-10-19, updated 2021-01-04): quotes and the Flask/Pyramid/Twisted move are accurate.
- Hynek "Subclassing in Python Redux" (2021-06-22): all quotes accurate, including the attribution of "mostly harmless" to interfaces, and the `TrackingRepository` composition example.
- Glyph "I Want A New Duck" (2020-07-21): quotes and the single-method `Ducky` are accurate.
- Brandon Rhodes: PyOhio 2014-07-27 and the quotes ("small procedure", "tested using only data", the Uncle Bob boundary quote, `big_procedure(...)`, "one or two integration tests", functional core / imperative shell) are accurate.
- cosmicpython:
  - ch. 2 quotes are accurate: "pretty much names for the same thing", the port/adapter definitions, "didactic reasons", "too easy to ignore them", the trade-off question, the DIP wording, CRUD.
  - ch. 13: "Composition Root (a bootstrap script to you and me)", "Explicit is better than implicit", Inject/Punq/Dependencies (dry-python), when frameworks pay off, closures/partial/classes. All accurate.
  - Appendix: `src/` plus `tests/`, and config through functions, are accurate.
- PEP 544: Final, Python 3.8, `@runtime_checkable` required for `isinstance`.
- PEP 779: Final, accepted 2025-06-16; Phase II (supported, optional); no date for Phase III.
- PEP 790: 3.15.0 final expected 2026-10-09 and not yet released.
- Python 3.14.8 docs:
  - free-threading overhead "about 1% on macOS aarch64 to 8% on x86-64 Linux"; extension import can enable the GIL;
  - `ProcessPoolExecutor` default start method changed away from fork; `InterpreterPoolExecutor` added in 3.14 and pickles arguments;
  - dataclasses: `slots`/`kw_only` since 3.10, the `__init_subclass__` caveat, `FrozenInstanceError`.
- Starlette threadpool: "only 40 tokens", tunable via `current_default_thread_limiter().total_tokens`.
- FastAPI: the "external threadpool that is then awaited" quote is accurate.
- vLLM: the API server and engine core are separate processes over ZMQ.
- Cloud Tasks HTTP handler timeout: default 10 min, maximum 30 min (page updated 2026-10-07).
- Cloud Run jobs GPU: L4 24 GB with minimum 4 CPU / 16 GiB, RTX PRO 6000, no launch stage stated (updated 2026-10-07).
- pydantic-settings: `env_prefix`, `env_nested_delimiter` with nested models that must be `BaseModel`, env over dotenv, and the GCP Secret Manager source are all documented.
- structlog 26.1.0 docs: `ProcessorFormatter`, `foreign_pre_chain`, and the chain having to end with `wrap_for_formatter`.
- Pydantic dataclasses quote accurate; stdlib dataclasses inside a `BaseModel` and inside `TypeAdapter` are validated.
- PyAV docs: wheels for Linux, macOS and Windows "with FFmpeg bundled", FFmpeg 8.x for source builds, Python ≥3.12. The repo was last pushed 2026-10-03.
- svcs: "A Flexible Service Locator for Python", last pushed 2026-10-01.
- RFC 9457 obsoletes 7807.
