# Q8 part A: architecture, layout, style and design

Status: research finding plus a proposed decision, **final revision after review round 2** (see "Review round 1 — resolution" and "Review round 2 — resolution" at the end). Anything still unsettled is in §13 as a user decision. All sources were read on 2026-10-08 unless a different date is given. Versions are the PyPI "latest" on that date.
Out of scope: tooling and gates (type checking, linting, coverage, tests), which q8b covers. This document states the dependency rule; q8b's import-linter contracts enforce it, and both documents use the same layer names (§1.5). Every change here that q8b must pick up is listed in "Follow-ups for q8b".

Settled inputs (user-decisions.md, 2026-10-08): Python floor 3.12, CI 3.12–3.14 (U2). The operator is EU-based (U3). Moderation and labels are a second opinion beside Google's signal (U1). The ASR default is Parakeet-TDT-0.6b-v2 through onnx-asr, with a faster-whisper fallback (U4, q2).
Scope boundary: the Expause-side adapter (enqueueing Cloud Tasks, receiving results) is **built in Expause later**. scenewise ships only a generic API and contract that Expause calls. scenewise contains no Expause code.

---

## 0. Decision summary

| Topic | Decision |
|---|---|
| Layout | `src/` layout, one distribution and one import package `scenewise`. No uv workspace in v1. |
| Layers (shared with q8b) | `service > adapters > app > ports > domain`. **service** holds the driving side: HTTP routes, CLI, composition root, settings and logging set-up. **adapters** holds driven implementations of ports only. **app** holds the use cases, orchestration **and the versioned wire contract** (`app/contract/`, pydantic). **ports** holds the Protocols. **domain** holds values plus pure functions, stdlib only. |
| Style | Ports and adapters plus "functional core, imperative shell". Ports are `typing.Protocol`s, used only at I/O and model boundaries. Stages are plain functions. Domain values are frozen, slotted dataclasses. One composition root (`service/bootstrap.py`) wires everything. No DI framework and no factory classes. |
| Consumer integration | A generic **push endpoint** `POST /v1/jobs` with Cloud Tasks semantics: idempotent per `job_id`, a durable job record, bounded attempts, and **every request that carries a usable `job_id` ends in a terminal record and a 2xx**. Expause builds its adapter on its own side, against this contract. |
| Execution | A **synchronous push handler**: the request runs the job and returns when the job reaches a terminal state, as Cloud Run's Cloud Tasks guide prescribes. Cloud Run request timeout ≥ Cloud Tasks `dispatchDeadline` (both 30 min), and scenewise's own work budget (default 25 min) sits below both. Media that will not fit the budget is rejected up front. Long media later goes to a Cloud Run job through the jobs `:run` API (deferred). |
| Delivery safety | Static lease = `dispatchDeadline + 120 s` (no heartbeat). The claim's storage generation is a **fencing token**: only the current attempt can write the terminal record. Artifacts are written under an **attempt-scoped prefix** (`…/a{n}/`). A **liveness watchdog** kills an instance whose job thread outlives budget + grace. |
| Callbacks | **Best-effort**, one bounded attempt after the terminal record. The job record (`GET /v1/jobs/{id}`) is the source of truth, and Expause's reconciliation is **mandatory**, not optional. |
| Concurrency | Cloud Run `--concurrency = max_jobs`, so the platform does admission. In-app non-blocking `anyio.CapacityLimiter(max_jobs).acquire_nowait()` stays as a safety net (429 + `Retry-After`). Each admitted job runs in one worker thread. Model adapters hold a `threading.Lock` (shared per GPU) **only around the inference call**. Scaling is by instance. No process pools. |
| Boundary validation | Pydantic v2 (2.13.5) at the edges: wire contract, settings, and LLM JSON, all parsed in `app` (`app/contract/`, `app/llm_output.py`). `domain` stays stdlib-only, with no pydantic. |
| Errors | Four categories: `InputError` (caller), `RetryableError` (transient), `InternalError` (ours, retry will not help) and `ConfigurationError` (start-up). Leaf classes exist only where HTTP mapping differs. Domain constructors raise plain `ValueError`, and boundaries translate it. Stage-level failures mark *that stage* failed and give a `partial` job. They never trigger a whole-job retry. |
| ffmpeg | **subprocess** with an argv list, killable timeouts, and start-up version probe. PyAV is rejected for the service. PEP 725 is Draft, so no `[external]` table. ffmpeg never sees a remote URL. |
| Audio acquisition | `app/audio.py` mirrors `app/frames.py`: file, segment list (inline or by reference) and **HLS** manifest are fetched through `BlobStore`, stitched locally (init + segments byte-concatenated, then one ffmpeg extraction). Playlist parsing is pure (`domain/manifests.py`). DASH is out of v1 (Q-18). |
| Frames across ports | `Frame(timestamp, width, height, rgb: bytes)`: packed RGB24, downscaled at decode to `max_side` (default 448). Stdlib-only, converts zero-copy to numpy or PIL. |
| Heavy deps | The base install has no torch, **and neither does an ASR-only image**. Extras: `service`, `asr`, `asr-whisper`, `llm-anthropic`, `vision`, `gcs`, plus two independent accelerator selector pairs: `ort-cpu`/`ort-cu130` (onnxruntime) and `torch-cpu`/`torch-cu130` (torch + torchvision). cu130 matches the Cloud Run 580 driver, onnxruntime-gpu 1.30 (CUDA 13) and torch's PyPI default. CTranslate2 (CUDA 12) runs on CPU in v1. |
| Local LLM | An OpenAI-compatible HTTP adapter (llama.cpp server, Ollama, vLLM), not in-process llama-cpp-python, which ships no PyPI wheels. |

---

## 1. Project layout

### 1.1 Use the `src/` layout

- The PyPA guide does not mandate a layout. It lists what the `src/` layout prevents: "accidental usage of the in-development copy of the code", and misconfigured packaging that "could result in files not being included in a distribution". https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ (read 2026-10-08; the page shows no date)
- Hynek Schlawack, "Testing & Packaging" (2015-10-19, updated 2021-01-04): with a flat layout "your tests do not run against the package as it will be installed by its users". He calls the trade-off "easy vs correct". https://hynek.me/articles/testing-packaging/
- *Architecture Patterns with Python* puts application code in a pip-installable `src/`, with `tests/` beside it, and exposes config through functions, not import-time constants. https://www.cosmicpython.com/book/appendix_project_structure.html
- `uv run` installs the project first, so the "must install first" cost of `src/` disappears in practice.

**Decision:** `src/scenewise/`, with `tests/` and `docs/` at the root.

### 1.2 One distribution, not a core library plus a service package

uv workspaces share **one lockfile** and **one `requires-python`**, and are "*not* suited for cases in which members have conflicting requirements". https://docs.astral.sh/uv/concepts/projects/workspaces/

The real split in scenewise is light versus heavy dependencies, not core versus service, and extras express that split directly. Layering is enforced by import-linter (q8b). Pydantic AI uses a workspace because it publishes several packages (§11). scenewise publishes one.

**When to revisit:** when a third party wants the library without the service. The layer rule makes that a move of files.

### 1.3 Where adapters live, and no consumer code

Driven adapters live in-tree under `src/scenewise/adapters/<port-kind>/<impl>.py`, one module per implementation, each heavy one behind its own extra.

There is **no `adapters/expause/`**. Expause's needs are expressed through the generic contract instead: a job request with `job_id`, `external_ref`, input URIs and `delivery`, as in q1 §4. Expause maps its media to that contract in its own repo. The "delete Expause" test is then trivially true: scenewise contains nothing to delete. (r1 finding 27. q1 still describes an `adapters/expause/payloads.py` route; see Q-17.)

### 1.4 Package tree

```
scenewise/
├── pyproject.toml                 # one distribution; extras; uv index/sources/conflicts (§9.4)
├── uv.lock
├── Dockerfile                     # apt ffmpeg + `uv sync --extra service --extra asr --extra ort-cu130 [--extra vision --extra torch-cu130]`
├── NOTICE                         # Parakeet CC-BY-4.0 attribution (U4), incl. ONNX conversion note
├── docs/
├── tests/                         # layout owned by q8b
└── src/scenewise/
    ├── __init__.py                # __version__ only; imports nothing heavy
    ├── __main__.py                # `python -m scenewise` → service.cli.main(); in exhaustive_ignores (§1.5)
    ├── py.typed
    │
    ├── domain/                    # LAYER domain: values + pure functions. stdlib only. No I/O.
    │   ├── time.py                #   Seconds, TimeSpan; vtt_timestamp() (rounds to ms in exactly one place)
    │   ├── media.py               #   MediaInfo, Frame, FrameRef, Rect, Tile, SpriteGrid
    │   ├── inputs.py              #   AudioSource and VisualSource unions (mirror q1 §4.2/§4.3)
    │   ├── uris.py                #   resolve(base, ref) for gs:// and https:// (urljoin ignores gs://); template expansion
    │   ├── manifests.py           #   HLS master/media playlist text → SegmentPlan (init, segments); rendition choice
    │   ├── jobs.py                #   JobId, StageName, StageOptions, Callback, JobSpec, Job, JobRecord, Decision; decide_attempt()
    │   ├── results.py             #   Transcript, Cue, Summary, Chapter, moderation/label results, StageOutcome, Analysis
    │   ├── errors.py              #   ScenewiseError categories (§8)
    │   ├── plan.py                #   stages to run for a JobSpec + available inputs; prerequisite table
    │   ├── captions.py            #   Transcript → cues (line breaking, merge/split); render_webvtt()
    │   ├── chapters.py            #   chapter prompt; semantic rules (sorted, within duration, min length)
    │   ├── summary.py             #   summary prompt; transcript chunking for context windows
    │   ├── sampling.py            #   frame timestamps for a duration; sprite grid → tiles (rect + time)
    │   ├── moderation.py          #   per-frame scores → per-category verdicts against thresholds
    │   ├── labels.py              #   prompt set; top-k / threshold selection over scores
    │   └── segments.py            #   segment-list maths (offsets, gaps) → absolute timeline
    │
    ├── ports.py                   # LAYER ports: all Protocols + Blob + WriteConflict (§4); split at ≈200 lines
    │
    ├── app/                       # LAYER app: use cases + wire contract. Orchestrates domain + ports. Sync.
    │   ├── contract/              #   versioned wire contract (q1 §4/§5), pydantic; imported by service/http
    │   │   ├── envelope.py        #     Envelope (schema_version, job_id) + request_digest(raw) — parsed first (§6.2)
    │   │   ├── requests.py        #     JobRequestV1 and its input/delivery/option models
    │   │   ├── results.py         #     JobResultV1, JobStatusV1 (GET body, status.json), problem body
    │   │   └── mapping.py         #     to_domain(), from_domain(), record ↔ JSON; ValueError → InputError
    │   ├── deps.py                #   Dependencies: frozen dataclass of port implementations
    │   ├── frames.py              #   acquire_frames(visual, deps): match on VisualSource → MediaTool / ImageReader
    │   ├── audio.py               #   acquire_audio(audio, deps): match on AudioSource → BlobStore + manifests → MediaTool
    │   ├── llm_output.py          #   TypeAdapter parsing of LLM JSON + bounded retry with a repair prompt
    │   ├── stages.py              #   one function per stage: transcribe, caption, summarise, chapter, moderate, label
    │   ├── runner.py              #   run_job(job, deps, *, deadline) → Analysis; per-stage outcomes, timings, deadline checks
    │   ├── publish.py             #   write ARTIFACTS ONLY (result.json, captions.vtt) under …/a{n}/ via BlobStore → result_uri
    │   └── delivery.py            #   handle_delivery(): decide → claim → parse → run → publish → terminal record → notify (§6.2)
    │
    ├── adapters/                  # LAYER adapters: DRIVEN implementations of ports only. Heavy imports only here.
    │   ├── media/
    │   │   ├── ffmpeg.py          #   MediaTool via subprocess ffmpeg/ffprobe; may split into probe.py + decode.py (size gate)
    │   │   └── images.py          #   ImageReader via Pillow (decode, crop tiles, downscale → Frame)
    │   ├── asr/
    │   │   ├── parakeet.py        #   SpeechRecognizer on onnx-asr (default; extra asr + ort-*)
    │   │   └── faster_whisper.py  #   SpeechRecognizer on CTranslate2 (fallback; extra asr-whisper)
    │   ├── llm/
    │   │   ├── openai_compat.py   #   TextGenerator over HTTP to llama.cpp server / Ollama / vLLM (httpx)
    │   │   ├── anthropic.py       #   TextGenerator on Claude Haiku (extra llm-anthropic)
    │   │   └── fallback.py        #   FallbackTextGenerator(primary, secondary): a TextGenerator wrapping two (ports only)
    │   ├── vision/
    │   │   ├── open_clip.py       #   ZeroShotLabeller on SigLIP 2 via open_clip (extra vision + torch-*)
    │   │   └── nsfw.py            #   ImageModerator on the q4 tier-1 classifier (extra vision + torch-*)
    │   ├── storage/
    │   │   ├── local.py           #   BlobStore on the filesystem (single host; O_EXCL create, lock-guarded CAS)
    │   │   ├── gcs.py             #   BlobStore on GCS (ifGenerationMatch preconditions; extra gcs)
    │   │   ├── https.py           #   read-only BlobStore for https:// and signed URLs (httpx)
    │   │   └── by_scheme.py       #   routes a URI by scheme AND enforces the q1 §4.0 URI allow-list on every access
    │   └── notify/
    │       └── http_callback.py   #   Notifier: POST pre-serialised bytes with a Google ID token or HMAC (q1 §8.6)
    │
    └── service/                   # LAYER service: DRIVING side + composition. Nothing imports service.
        ├── bootstrap.py           #   COMPOSITION ROOT: Settings → system checks → lazy adapter imports → Dependencies
        ├── config.py              #   Settings(BaseSettings) + nested backend settings; timing invariants (§6.3)
        ├── logs.py                #   structlog + stdlib logging config (JSON / console); trace field
        ├── cli.py                 #   `scenewise analyse <path>` (local); `scenewise run-job --job-uri` (Cloud Run job)
        └── http/
            ├── app.py             #   create_app(settings) → FastAPI; lifespan calls bootstrap
            ├── routes.py          #   POST /v1/jobs, GET /v1/jobs/{id}, /readyz
            ├── push.py            #   admission, Envelope parse, Cloud Tasks headers → log context + AttemptInfo, status mapping
            ├── health.py          #   /healthz liveness watchdog over the in-flight job registry (§6.3)
            └── problems.py        #   ScenewiseError → RFC 9457 problem+json
```

Naming notes:
- No `utils.py`. Every helper is named after what it is about.
- `service/logs.py`, not `logging.py`, so it does not shadow the stdlib module.
- One `ports.py`, so a reviewer sees every seam on one screen. Split it at about 200 lines into a `ports/` package (one module per port kind).
- `service` holds the CLI as well as HTTP. Both are driving entry points, and the CLI's `run-job` mode is the same service run as a Cloud Run job.
- Size (q8b `MAX_LINES = 400`): the wire contract is a package from the start (`app/contract/`), because request models, result models and both mapping directions together are plausibly 450–600 lines. `adapters/media/ffmpeg.py` may split into `probe.py` (ffprobe JSON → `MediaInfo`) and `decode.py` (concat, audio extraction, rawvideo frames, kill-on-timeout, stderr mapping) inside `adapters/media/`; the `MediaTool` class then composes the two.

### 1.5 The dependency rule (one rule, shared with q8b)

**Layer names, top to bottom: `service`, `adapters`, `app`, `ports`, `domain`.** A layer may import only layers below it. q8b's contract `layers = ["service", "adapters", "app", "ports", "domain"]` with `exhaustive = true` encodes this, **plus `exhaustive_ignores = ["__main__"]`**. import-linter's exhaustive mode checks "that the contract declares every possible layer", and modules that should not fail go in `exhaustive_ignores` ("A list of layers to ignore in exhaustiveness checks"; https://import-linter.readthedocs.io/en/stable/contract_types/layers/). The page does not exempt `__main__`, and `scenewise.__main__` is a top-level child, so it must be listed. Alternative rejected: moving the entry point to `scenewise.service.__main__` would make `python -m scenewise` stop working for a cosmetic gain.

```
service   (http/*, cli, bootstrap, config, logs)  ──► adapters (bootstrap only, lazily), app, ports, domain
adapters  (driven: media, asr, llm, vision, storage, notify) ──► ports, domain     [never app, never service]
app       (use cases + app/contract wire models)   ──► ports, domain              [never adapters, never service]
ports     (Protocols)                              ──► domain
domain    (values + pure functions)                ──► stdlib only
```

Rules for the import linter (q8b §3):
1. **Layers** `service > adapters > app > ports > domain`, exhaustive, `exhaustive_ignores = ["__main__"]`.
2. **Driven adapters never import `app` or `service`.** The layers contract already forbids that. Consequences: adapters never import `service.config` (they take plain keyword arguments; `bootstrap` unpacks settings, r1 finding 28), and **adapters never import `app.contract`**. The notifier therefore takes pre-serialised bytes (§4), and stays contract-agnostic.
3. **Adapters are independent of each other** (`independence` over `scenewise.adapters.*`, at the port-kind level). Composition inside one kind (`storage/by_scheme.py` importing `storage/gcs.py`, `llm/fallback.py` wrapping any `TextGenerator`) is allowed.
4. Within `service`, only `bootstrap` imports `scenewise.adapters`. It imports them lazily inside the `match` branch that selects them, so a missing extra raises `ConfigurationError("install scenewise[asr]")`. q8b adds a `forbidden` contract from `scenewise.service.http`/`scenewise.service.cli` to `scenewise.adapters`.
5. **One wire contract.** `service/http`, `app/publish.py` and `app/delivery.py` all serialise through `app/contract/`. `service/http` imports it from there; nothing re-implements the JSON shapes. (r2 finding 7.)
6. **Third-party bans.** `domain` gets the q8b deny-list, which already includes pydantic, numpy and PIL. `ports` and `app` may not import torch, torchvision, ctranslate2, onnxruntime, onnx_asr, faster_whisper, open_clip, PIL, numpy, fastapi or httpx. `app` *may* import pydantic (`TypeAdapter`, `app/contract/`) and structlog (to bind context).

This is the Dependency Inversion Principle as *Architecture Patterns with Python* states it: "high-level modules (the domain) should not depend on low-level ones (the infrastructure)". https://www.cosmicpython.com/book/chapter_02_repository.html

---

## 2. Architecture style: ports and adapters, the idiomatic Python way

### 2.1 What the sources say

- **Percival & Gregory (cosmicpython ch. 2):** ports-and-adapters, hexagonal, onion and clean architecture are "pretty much names for the same thing". The port is "the *interface* between our application and whatever it is we wish to abstract away", and the adapter is "the implementation behind that interface". They use ABCs "for didactic reasons", note that Python makes it "too easy to ignore them", and **mention** PEP 544 protocols as an alternative that gives "typing without the possibility of inheritance". Each pattern must answer "What do we get for this? And what does it cost us?" https://www.cosmicpython.com/book/chapter_02_repository.html
- **Cosmicpython ch. 13:** manual DI through a bootstrap script ("Composition Root (a bootstrap script to you and me)"). DI frameworks pay off only when dependencies chain or are needed in many places. https://www.cosmicpython.com/book/chapter_13_dependency_injection.html
- **Driving and driven sides.** Hexagonal architecture distinguishes the side that *drives* the application (HTTP, CLI, test harness) from the side the application *drives* (storage, models). scenewise maps the driving side to `service/` and the driven side to `adapters/`. Cockburn, "Hexagonal architecture" (2005-09-04): "A primary actor is an actor that drives the application"; "A secondary actor is one that the application drives"; "They could be also called driving adapters and driven adapters." https://alistair.cockburn.us/hexagonal-architecture/
- **Brandon Rhodes, "The Clean Architecture in Python"** (PyOhio, 2014-07-27): isolate I/O "to a small procedure". "By definition, pure functions can be tested using only data." Functional core, imperative shell. https://rhodesmill.org/brandon/slides/2014-07-pyohio/clean-architecture/
- **Hynek Schlawack, "Subclassing in Python Redux"** (2021-06-22): composition over inheritance; often "a function is all you need". https://hynek.me/articles/python-subclassing-redux/
- **Glyph, "I Want A New Duck"** (2020-07-21): a `Protocol` contains only what the consumer calls. https://blog.glyph.im/2020/07/new-duck.html
- **PEP 544** (Final, 3.8): structural subtyping. `isinstance` works only with `@runtime_checkable`. https://peps.python.org/pep-0544/

### 2.2 Where the line is: Protocol, class or function

| Construct | Use it when | Do NOT use it for |
|---|---|---|
| `Protocol` (port) | An I/O or model boundary with (a) ≥2 real implementations, or (b) a need for a fake in tests because the real thing is slow, nondeterministic or costly. | Pure functions, values, config, the use cases themselves. |
| Class with `__init__` | It owns a resource with a lifecycle: a loaded model, a client, a lock. | Stateless logic. A class whose only method is `run()` should be a function. |
| Plain function | Every stage, every domain transformation, the runner, the delivery protocol. | — |
| `@dataclass(frozen=True, slots=True, kw_only=True)` | Values and the `Dependencies` bundle. | Validating untrusted input (pydantic at the boundary). |
| Inheritance | Only the four error categories plus three leaf errors, and `BaseSettings`/`BaseModel`. | Sharing code between back ends. |
| Factory | One function, `bootstrap.build_dependencies(settings)`, with a `match` per back end. | Registries, plugin entry points. |
| DI container / service locator | Never in v1. | — |

On service locators: the one production Python exemplar of ports and adapters in §11, Warehouse, pairs zope `interfaces.py` with a **service locator**: `pyramid_services>=2.1` (`requirements/main.in`), `config.register_service_factory(..., IFileStorage)` in `warehouse/packaging/__init__.py`, looked up with `request.find_service`. Warehouse needs this because hundreds of views across many features look services up per request. scenewise has two entry points (HTTP and CLI) and one composition root, so a plain `Dependencies` dataclass is enough. Hynek's `svcs` (https://github.com/hynek/svcs, last push 2026-10-01) is the upgrade path if that changes. (Verified at warehouse `14b79b44aa`.)

Model-serving frameworks are rejected for v1: LitServe, BentoML, Ray Serve and Triton (with its Python backend). They solve batching, per-model workers and GPU admission, but they add a heavy runtime and would hide the very architecture scenewise exists to show. At scenewise's scale (one GPU, a handful of jobs in flight), a lock per device covers the need (§6.3).

Also rejected: Repository/Unit of Work, message bus, domain events, a `Clock` port (time is passed in as data), ABCs for ports, and a `Stage` class.

### 2.3 Functional core and imperative shell, concretely

Every stage has the same shape: **fetch through a port, transform with pure domain functions, return domain data.**

Ownership on the delivery path (r2 finding 10, one statement used everywhere in this document):
- `app/publish.py` writes **artifacts only** (`result.json`, `captions.vtt`) under the attempt-scoped prefix and returns the `result_uri`. It never touches the job record and never notifies.
- `app/delivery.py` owns **every job-record write** (claim, release, terminal) **and the notify call**.
- The CLI's local `analyse` mode calls `run_job` and prints, without publishing.

---

## 3. Design principles with scenewise examples

| Principle | Pipeline stage | Model back end | Input source |
|---|---|---|---|
| **Single responsibility** | `domain/captions.py` only turns a `Transcript` into cues and WebVTT. `app/stages.py::caption()` is a few lines. | `adapters/asr/parakeet.py` only maps `SpeechRecognizer` onto onnx-asr. (Contrast: faster-whisper's `transcribe.py` is 1,952 lines, §11.) | `adapters/media/images.py` only decodes and crops pixels. Grid maths lives in `domain/sampling.py`; playlist parsing in `domain/manifests.py`. |
| **Open/closed** | A new stage (OCR) is a new function, a new `StageName` and a plan rule. | A new back end is a new module plus one `case` in `bootstrap`. | A new visual or audio kind is a new dataclass in the union. The type checker's `match` exhaustiveness check shows every place that must handle it. |
| **Liskov** | n/a | Every `SpeechRecognizer` returns segments with absolute seconds, non-decreasing. This is stated in the docstring and checked by one shared contract test per port (q8b). | `app/frames.py` yields frames in time order, whatever the source kind. `app/audio.py` always yields one continuous track on the q1 §4.0 timeline. |
| **Interface segregation** | `label()` takes a `ZeroShotLabeller` and frames, not the model zoo. | `TextGenerator` has one method. | `ImageReader` is separate from `MediaTool`, so sprite-sheet inputs need no ffmpeg. |
| **Dependency inversion** | `app` depends on `ports.SpeechRecognizer`, never on `onnx_asr`. | `bootstrap` constructs `ParakeetRecognizer(model=..., device=..., lock=gpu_lock)`. | `app` asks `BlobStore.materialise(uri)` for a local path and never knows the scheme. |
| **Composition over inheritance** | `run_job` composes stage functions according to `plan.stages_for(spec, inputs)`. | Fallback is `adapters/llm/fallback.py::FallbackTextGenerator(primary, secondary)`, a wrapper. | A segment list holds URIs. Offsets come from `domain/segments.py`. |
| **Functional core / imperative shell** | `chapter()` = generate → `llm_output.parse` → `domain.chapters.normalise`. | The adapter loads, runs and returns raw output. | `domain.manifests.parse_media_playlist(text, base_uri)` is pure; `app/audio.py` does the reads. |

### 3.1 Sketch of one stage (style reference)

```python
# app/stages.py
def chapter(transcript: Transcript, *, generator: TextGenerator, duration: Seconds) -> tuple[Chapter, ...]:
    request = chapters.build_request(transcript)                       # pure (domain)
    items = llm_output.generate_valid(generator, request, CHAPTERS_SCHEMA, attempts=2)
    # ^ generate → TypeAdapter.validate_json; on ValidationError re-ask once with the errors (repair prompt);
    #   still invalid → InternalError(code="model_output_invalid") → this stage fails, the job continues (partial)
    try:
        return chapters.normalise(items, duration=duration)             # pure; ValueError on semantic violations
    except ValueError as e:
        raise InternalError("model_output_invalid", detail=str(e)) from e
```

### 3.2 Pydantic `TypeAdapter`: in `app`, not in the domain

**Decision.** `domain` stays stdlib-only, enforced by q8b's forbidden contract. Structural parsing of LLM output (JSON shape and types) uses `pydantic.TypeAdapter` in `app/llm_output.py`, which then hands plain values to the pure `domain/chapters.normalise()` and `domain/summary` functions. Those apply the cross-field rules q3 says every back end needs: first chapter at 0, ascending, minimum spacing, within duration. https://pydantic.dev/docs/validation/latest/concepts/dataclasses/

Why this split:
- Pydantic is already a base dependency, and it produces error lists that can feed a repair prompt.
- Constrained decoding cannot express cross-field rules (q3), so those must live in pure, fully tested domain code anyway.
- Hand-written structural validation in the domain was the alternative. It was rejected as more code for a worse result.

The same reasoning puts the wire contract in `app/contract/`: pydantic is allowed in `app`, and every writer of the contract (HTTP, publish, delivery) can reach it there.

---

## 4. Ports (all in `scenewise/ports.py`)

```python
class WriteConflict(Exception): ...   # a precondition (create-if-absent / generation match) failed

@dataclass(frozen=True, slots=True, kw_only=True)
class Blob:
    data: bytes
    generation: int                            # store-assigned; the CAS token (GCS object generation, local counter)

class BlobStore(Protocol):                     # local FS | GCS | https (read-only), routed by scheme + URI allow-list
    def materialise(self, uri: str) -> AbstractContextManager[Path]: ...       # local file; cleans temp copies
    def read(self, uri: str) -> Blob | None: ...                               # None = absent
    def write(self, uri: str, data: bytes, *, content_type: str,
              if_generation: int | None = None) -> int: ...                    # 0 = create only if absent; returns new generation
                                                                               # raises WriteConflict on precondition failure

class MediaTool(Protocol):                     # ffmpeg / ffprobe (subprocess)
    def probe(self, path: Path) -> MediaInfo: ...
    def audio_track(self, parts: Sequence[Path], *, deadline: float) -> AbstractContextManager[Path]: ...
        # 16 kHz mono WAV. >1 part = init + media segments (fMP4) or TS segments, byte-concatenated
        # in order into one local file, then ONE ffmpeg extraction (q1 §6.3). Never given a URL.
    def video_frames(self, path: Path, times: Sequence[Seconds], *, max_side: int,
                     deadline: float) -> Iterator[Frame]: ...                  # rawvideo rgb24 from stdout

class ImageReader(Protocol):                   # Pillow
    def read(self, path: Path, tiles: Sequence[Tile], *, max_side: int) -> list[Frame]: ...
        # Tile(timestamp, rect | None); decodes the file once, crops each tile (sprite sheets) or uses the whole image

class SpeechRecognizer(Protocol):              # Parakeet via onnx-asr | faster-whisper
    def transcribe(self, audio: Path, *, language: str | None) -> Transcript: ...

class TextGenerator(Protocol):                 # OpenAI-compatible local server | Claude Haiku | FallbackTextGenerator
    def generate(self, request: TextRequest) -> str: ...

class ImageModerator(Protocol):                # q4 tier-1 classifier
    def score(self, frames: Sequence[Frame]) -> list[FrameModeration]: ...

class ZeroShotLabeller(Protocol):              # SigLIP 2 via open_clip
    def scores(self, frames: Sequence[Frame], labels: Sequence[str]) -> list[list[float]]: ...   # [frame][label], 0..1

class Notifier(Protocol):                      # HTTP callback (OIDC | HMAC) | none
    def notify(self, body: bytes, *, callback: Callback, idempotency_key: str) -> None: ...
        # body = JobResultV1 JSON, serialised by app/contract; idempotency_key = job_id (Standard Webhooks `webhook-id`)
        # raises RetryableError after its own bounded retries; delivery logs and swallows it (§6.2)
```

**Frames** (r1 finding 12, option b): there is no `FrameSource` port. `app/frames.py::acquire_frames(visual, deps, *, max_side, deadline)` does a `match` on the `VisualSource`:
- `VideoFrames`: materialise, then `domain.sampling.interval_times(duration, interval)`, then `deps.media.video_frames(...)`.
- `TimedFrames` / `IntervalFrames`: one `deps.images.read(path, [Tile(t, None)])` per image (`IntervalFrames` URIs come from `domain.uris.expand_template`).
- `SpriteSheets`: `domain.sampling.sprite_tiles(grid, interval, start_offset, count)`, then one `deps.images.read(sheet, tiles)` per sheet.

Frames are yielded in batches (default 32), so memory stays bounded.

**Audio** (r2 finding 6): `app/audio.py::acquire_audio(audio, deps, *, deadline) -> AbstractContextManager[Path | None]` does a `match` on the `AudioSource` and always ends in exactly one `deps.media.audio_track(parts, deadline=...)` call:
- `NoAudio` → yields `None` (captions `skipped`, `no_audio_stream`, q1 §9).
- `AudioFile` → `store.materialise(uri)` → `audio_track([path])`. A file without an audio stream (from `probe`) is treated as `NoAudio`.
- `AudioSegments` → segment URIs come either inline or from `segments_list_uri`: `store.read(list_uri)` → `contract.requests.SEGMENT_LIST.validate_json(...)` (a `TypeAdapter[list[SegmentRef]]`) → relative URIs resolved against the list's location with `domain.uris.resolve`. Then init + segments are materialised into one `ExitStack`, fetched with a bounded `concurrent.futures.ThreadPoolExecutor` (default 8 workers; a 90-min Expause job is about 901 segments, q1 §3.1), then `audio_track([init, *segments])`.
- `AudioManifest` (HLS) → `store.read(uri)` → `domain.manifests.parse(text, base_uri=uri)`. A master playlist yields its `#EXT-X-MEDIA:TYPE=AUDIO` renditions; `domain.manifests.choose_rendition(renditions, wanted)` picks `rendition` or the lowest-bandwidth one; its media playlist is read and parsed into a `SegmentPlan(init_uri from #EXT-X-MAP, segment_uris, container)`. From there it is the `AudioSegments` path.
- **Rules applied in the pure parser** (q1 §4.2): any `#EXT-X-KEY` other than `METHOD=NONE` → `InputError("input_encrypted")`; `#EXT-X-BYTERANGE`, a live playlist (no `#EXT-X-ENDLIST`) and `format: "dash"` → `UnsupportedMediaError("manifest_unsupported")` in v1 (Q-18).
- **Limits:** `Settings.inputs.max_segments` (default 2000) and a total-bytes cap, checked before and during fetching, so a hostile playlist cannot exhaust disk.
- **URI policy:** every URI, including those found inside a list or playlist, goes through `BlobStore` → `by_scheme.py`, which enforces the q1 §4.0 allow-list. ffmpeg never sees a remote URL, so its own protocol handlers (HLS demuxer, `concat:`) never fetch anything. This is why scenewise does not hand ffmpeg the playlist, even though `ffmpeg -i audio.m3u8` works locally (q1 §6.3): it would bypass `BlobStore` and cannot read `gs://` anyway.
- **Timeline:** byte-concatenated fMP4 with its init segment starts at 0 because ffmpeg applies the init's edit list (q1 §5.4, measured). For MPEG-TS the adapter normalises the first PTS to 0. Only fMP4 stitching of Google Transcoder output is unverified (q1 open question 2).

Ports are synchronous on purpose. The model work blocks, and the service runs each job in one worker thread (§6.3). Count: 8 ports (`BlobStore`, `MediaTool`, `ImageReader`, `SpeechRecognizer`, `TextGenerator`, `ImageModerator`, `ZeroShotLabeller`, `Notifier`). Publishing is a plain `app` function over `BlobStore`.

`app/deps.py`:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Dependencies:
    store: BlobStore
    media: MediaTool
    images: ImageReader
    asr: SpeechRecognizer | None          # None ⇒ stage not offered by this deployment (§8, r1 finding 19)
    text: TextGenerator | None
    moderator: ImageModerator | None
    labeller: ZeroShotLabeller | None
    notifier: Notifier
    enabled_stages: frozenset[StageName]  # derived by bootstrap from the above
```

Both `Dependencies` members and adapters are long-lived; nothing per-job is stored in them.

---

## 5. Domain model sketch (`scenewise/domain/`)

All classes are `@dataclass(frozen=True, slots=True, kw_only=True)` (https://docs.python.org/3/library/dataclasses.html, 3.14.8). Collections are `tuple[...]` **for immutability**. Nothing relies on hashing (r1 finding 30). Constructors validate invariants in `__post_init__` and raise plain **`ValueError`**. Boundaries translate it: `app/contract/mapping.to_domain` → `InputError("invalid_request")`; LLM and model parsing in `app` → `InternalError("model_output_invalid")`; anything else reaching the runner → `InternalError("invariant_violation")` (r1 finding 20).

```python
# domain/time.py
Seconds = NewType("Seconds", float)
class TimeSpan:   start: Seconds; end: Seconds                  # 0 <= start <= end, else ValueError
def vtt_timestamp(t: Seconds) -> str: ...                      # the single ms-rounding point

# domain/media.py
class MediaInfo:  duration: Seconds; has_audio: bool; has_video: bool; width: int | None; height: int | None
class Rect:       x: int; y: int; width: int; height: int
class Tile:       timestamp: Seconds; rect: Rect | None
class Frame:      timestamp: Seconds; width: int; height: int; rgb: bytes   # packed RGB24, len == w*h*3
class FrameRef:   uri: str; timestamp: Seconds
class SpriteGrid: columns: int; rows: int; tile_width: int; tile_height: int

# domain/inputs.py   (mirrors q1 §4.2/§4.3; wire names stay in app/contract/requests.py)
class AudioFile:     uri: str
class AudioSegments: container: Literal["fmp4", "mpegts"]; init_uri: str | None
                     segment_uris: tuple[str, ...] | None; list_uri: str | None     # exactly one of the two
class AudioManifest: uri: str; format: Literal["hls", "dash"]; rendition: str | None   # "dash" rejected in v1
class NoAudio:       pass
type AudioSource = AudioFile | AudioSegments | AudioManifest | NoAudio            # PEP 695 (3.12+)
class VideoFrames:    uri: str; interval: Seconds
class TimedFrames:    frames: tuple[FrameRef, ...]
class IntervalFrames: uri_template: str; count: int; interval: Seconds; start_offset: Seconds
class SpriteSheets:   sheets: tuple[str, ...]; grid: SpriteGrid; interval: Seconds; start_offset: Seconds; count: int | None
type VisualSource = VideoFrames | TimedFrames | IntervalFrames | SpriteSheets

# domain/manifests.py   (pure; stdlib only)
class SegmentPlan:    container: Literal["fmp4", "mpegts"]; init_uri: str | None; segment_uris: tuple[str, ...]
class AudioRendition: name: str; group_id: str; bandwidth: int | None; playlist_uri: str
def parse(text: str, *, base_uri: str) -> SegmentPlan | tuple[AudioRendition, ...]: ...   # media vs master playlist
def choose_rendition(renditions: Sequence[AudioRendition], wanted: str | None) -> AudioRendition: ...

# domain/jobs.py
JobId = NewType("JobId", str)       # q1 pattern ^[A-Za-z0-9._:-]{1,200}$, and not "." or ".." (safe as one path segment)
class StageName(StrEnum):  CAPTIONS, SUMMARY, CHAPTERS, MODERATION, LABELS   # wire names from q1
class StageOptions: language_hint: str | None; labels_max: int; summary_max_chars: int
                    chapters_min_duration: Seconds; include_words: bool          # q1 §4.1 defaults live in app/contract
class Callback:     url: str; auth: Literal["hmac", "oidc"]; key_id: str | None; audience: str | None
                    # q1 HttpCallback; url already checked against Settings.delivery.allowed_callback_urls
class TextContext:  title: str | None; description: str | None; tags: tuple[str, ...]
class JobSpec:      stages: frozenset[StageName]; options: StageOptions
class Job:          id: JobId; spec: JobSpec; audio: AudioSource | None; visual: VisualSource | None
                    context: TextContext | None; external_ref: tuple[tuple[str, str], ...]
                    callback: Callback | None; artifacts_prefix: str | None
class JobState(StrEnum):  RUNNING, SUCCEEDED, PARTIAL, FAILED
class JobRecord:    job_id: JobId; state: JobState; attempt: int; lease_until: float   # epoch seconds
                    request_digest: str            # sha256 of the canonical request body; detects job_id reuse
                    error_code: str | None; result_uri: str | None; updated_at: float
class AttemptInfo:  now: float; lease: Seconds; max_attempts: int

# decision returned by the pure state machine (§6.2):
class Start:       attempt: int
class AlreadyDone: record: JobRecord
class InProgress:  retry_after: Seconds
class GiveUp:      attempt: int
class Conflict:    existing_digest: str
type Decision = Start | AlreadyDone | InProgress | GiveUp | Conflict
def decide_attempt(record: JobRecord | None, request_digest: str, info: AttemptInfo) -> Decision: ...
def wire_status(record: JobRecord, now: float) -> Literal["running", "retry_wait", "succeeded", "partial", "failed"]: ...
    # RUNNING with lease_until <= now ⇒ "retry_wait" (released or crashed; nothing runs). r2 finding 16.

# domain/results.py
class TranscriptSegment: span: TimeSpan; text: str; confidence: float | None
class Transcript:        language: str; segments: tuple[TranscriptSegment, ...]
class Cue:               span: TimeSpan; text: str
class Summary:           text: str; model: str
class Chapter:           start: Seconds; title: str
class ModerationScore:   category: str; score: float                 # 0..1
class FrameModeration:   timestamp: Seconds; scores: tuple[ModerationScore, ...]
class ModerationReport:  frames: tuple[FrameModeration, ...]; flagged: tuple[str, ...]
class Label:             name: str; score: float
class TextRequest:       system: str; prompt: str; json_schema: str | None; max_tokens: int  # JSON Schema as text: stdlib-only, immutable
class StageOutcome:      stage: StageName; status: Literal["succeeded", "skipped", "failed"]; reason: str | None; seconds: float
class Analysis:          job_id: JobId; media: MediaInfo; outcomes: tuple[StageOutcome, ...]
                         transcript: Transcript | None; cues: tuple[Cue, ...]; summary: Summary | None
                         chapters: tuple[Chapter, ...]; moderation: ModerationReport | None; labels: tuple[Label, ...]
```

`Analysis.state` is derived: `PARTIAL` if any requested stage `failed`, else `SUCCEEDED`. A `skipped` stage (for example `no_audio_stream`, q1 §9) does not make the job partial.

`decide_attempt` takes the request digest, not a `Job`: it runs **before** the full request is validated (§6.2), so a request that fails domain validation still gets a terminal record. `AttemptInfo` has no transport-retry field: `X-CloudTasks-TaskRetryCount` is bound to the log context in `service/http/push.py` and never reaches the domain (r2 finding 11).

There is deliberately no `Stage` class. `domain/plan.py` holds the prerequisite table: `CAPTIONS` needs audio; `SUMMARY` and `CHAPTERS` need a transcript or visual input; `MODERATION` and `LABELS` need visual input. A stage whose prerequisite failed is `skipped` with `reason="dependency_failed"`.

### 5.1 Pydantic at the boundary, dataclasses inside

- Pydantic **2.13.5** (2026-08-28, pins `pydantic-core==2.46.5`). https://pypi.org/project/pydantic/
- `app/contract/` holds the versioned wire contract from q1 §4/§5 (`schema_version: "1"`, discriminated unions on `kind`, inputs `extra="forbid"`) and explicit `to_domain()`/`from_domain()` functions, so the wire format, which is the one Expause codes against, can evolve independently of the domain. It is split in four modules (§1.4) to stay under q8b's 400-line gate.
- `Envelope` is a deliberately lenient model (`extra="allow"`) with only `schema_version` and `job_id`. It is parsed first so that a record can be keyed even when the rest of the body is invalid. `request_digest(raw)` hashes the canonical JSON (`json.loads` then `json.dumps(sort_keys=True, separators=(",", ":"))`) of the raw body.

---

## 6. Execution on Cloud Run with Cloud Tasks

### 6.1 Facts the design rests on

- **Cloud Tasks HTTP targets** (official REST reference, https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks, updated 2026-09-30):
  - 200–299 is success. Any other code, "or no response", is retried. **This includes 409 and 422.**
  - On 429 or 503, Cloud Tasks "will use a higher backoff rate", and "The retry specified in the `Retry-After` HTTP response header is considered".
  - `dispatchDeadline` defaults to 10 min and must lie in [15 s, 30 min]. When it passes, the "request is cancelled and the attempt is marked as a `DEADLINE_EXCEEDED` failure", but "whether the worker stops processing depends on the worker". So the retry of a deadline-exceeded attempt cannot arrive before `dispatchDeadline` + backoff.
- **Delivery is at least once:** "In some rare circumstances, multiple task execution is possible … Your handlers should be idempotent." https://docs.cloud.google.com/tasks/docs/dual-overview (updated 2026-10-07)
- **Exhausted retries:** "no further attempts are made, and the task is deleted". There is no dead-letter queue. `maxAttempts: -1` means unlimited, and `maxRetryDuration: 0s` means no time limit. https://docs.cloud.google.com/tasks/docs/configuring-queues (updated 2026-10-07)
- **Headers:** `X-CloudTasks-TaskName`, `-TaskRetryCount` (0 on the first attempt), `-TaskExecutionCount` (excludes 5XX failures), `-TaskETA` and `-TaskPreviousResponse`. "These headers provide information only. They should not be used as sources of identity." https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks (updated 2026-10-07)
- **Cloud Run request timeout:** default 5 min, maximum 60 min. On timeout the client gets 504, but the instance is not terminated and may keep running the abandoned request. For timeouts over 15 min, make requests idempotent or resumable. https://docs.cloud.google.com/run/docs/configuring/request-timeout (updated 2026-10-07)
- **Cloud Run's Cloud Tasks guide:** "The Cloud Run service must return an HTTP 200 code to confirm success after processing of the task is complete." For work beyond the Cloud Tasks maximum, use Cloud Run jobs. https://docs.cloud.google.com/run/docs/triggering/using-tasks (updated 2026-10-07)
- **Background work after the response:** under request-based billing, "CPU is only allocated during request processing". https://docs.cloud.google.com/run/docs/configuring/billing-settings (updated 2026-10-07). GPU services require instance-based billing. https://docs.cloud.google.com/run/docs/configuring/services/gpu (updated 2026-10-07)
- **GCS preconditions:** `ifGenerationMatch=0` writes only if no live object exists, else `412 Precondition Failed`. Read-then-write with the read generation as a precondition gives compare-and-swap. https://docs.cloud.google.com/storage/docs/request-preconditions (updated 2026-10-07)
- **Cloud Run liveness probes:** they are "intended to restart individual instances that can't be recovered in any other way". When the probe fails `failureThreshold` times (default 3, every `periodSeconds`, default 10, range 1–3600), "the container is shut down using a `SIGKILL` signal", in-flight requests end with 503, and "Cloud Run autoscaling starts up a new container instance". `timeoutSeconds` cannot exceed `periodSeconds`. https://docs.cloud.google.com/run/docs/configuring/healthchecks (read 2026-10-08). The page does not say whether probes count toward request concurrency (Q-19).

**Decision: synchronous push handler.** The request does the work and answers when the job is terminal (or hands it back for retry). The queue is Cloud Tasks itself: retries, backoff and `maxConcurrentDispatches` come for free, and no background work runs outside a request. This **diverges from q1 §8.1/§8.5**, which proposed `202 queued` with a scenewise-owned durable queue. A 202 would need instance-based billing for background CPU and a second queue, and it would discard Cloud Tasks' at-least-once retry for the actual work. (Q-12.)

### 6.2 The delivery protocol: idempotency, a durable job record, and fencing

**Storage layout.** No database (r1 finding 22).
- Job record: `{state_prefix}/{job_id}/status.json` (a `JobRecord`), written **only** with preconditions.
- Artifacts: `{artifacts_prefix}/a{attempt}/result.json` and `…/a{attempt}/captions.vtt`, where `artifacts_prefix` is `delivery.artifacts.uri_prefix` or `{state_prefix}/{job_id}`. The terminal record's `result_uri` names the winning attempt's `result.json`. Orphaned `a{n}/` prefixes of losing attempts are harmless and are removed by the bucket's lifecycle rule (results retention, q1 §8.7).

**Entry** (`service/http/push.py`, then `app/delivery.handle_delivery(envelope, raw, deps, info)`):

0. **Envelope first** (r2 finding 4). `push.py` parses `Envelope` (`job_id`, `schema_version`) from the raw body and computes `request_digest`. Only if that fails (not JSON, no `job_id`, or a `job_id` outside the pattern) is the answer **422**: there is no key under which a record could be written. Everything after this point ends in a terminal record or a retryable 429/503.
1. `read(status.json)` returns the record and its generation `g0`, or nothing.
2. `domain.jobs.decide_attempt(record, digest, info)` is pure and exhaustively unit-tested:
   - no record → `Start(1)`;
   - `request_digest` differs → `Conflict`;
   - terminal state → `AlreadyDone(record)`. **Duplicates and late retries are absorbed here.**
   - `RUNNING` and `lease_until > now` → `InProgress(lease_until − now)`;
   - `RUNNING`, lease expired, `attempt < max_attempts` → `Start(attempt + 1)` (crash or release recovery);
   - `RUNNING`, lease expired, `attempt ≥ max_attempts` → `GiveUp(attempt)`.
3. **Claim** (`Start(n)`): write `RUNNING{attempt=n, lease_until=now + lease}` with `if_generation=g0` (0 if absent). The returned generation `gc` is the attempt's **fencing token**. `WriteConflict` → another delivery won the race → `InProgress` (503, `Retry-After` 30 s).
4. **Parse** inside the claim: `contract.mapping.to_domain(raw)`. A `ValidationError` or domain `ValueError` becomes `InputError("invalid_request")` (or `uri_not_allowed`), so a body with a good `job_id` but a bad sprite grid, `start > end` or a forbidden URI ends as a terminal `FAILED` record and a 200 — never a retried 422.
5. **Run and publish:** `run_job(job, deps, deadline=monotonic() + budget)`, then `publish(analysis, prefix=…/a{n}/) → result_uri`.
6. **Finish** = write the terminal record (`SUCCEEDED`/`PARTIAL`/`FAILED`, `error_code`, `result_uri`) with `if_generation=gc`.
   - Success → **notify** (best-effort, below) → **200** + record.
   - `WriteConflict` → this attempt was **fenced**: a later attempt claimed the record after this one's lease expired. Do not notify. Log `attempt_superseded` at WARNING. Re-read the record and answer as step 2 would (normally `AlreadyDone` 200 or `InProgress` 503); in practice this request was already cancelled by Cloud Tasks, so the answer goes nowhere. Its `a{n}/` artifacts are orphaned, never referenced.
7. **Exceptions** inside the claim:
   - `InputError` / `InternalError` → finish as `FAILED` with `error_code` → notify → **200**. Retrying cannot help, and the record is durable.
   - `RetryableError` → if `n ≥ max_attempts`, finish as `FAILED("attempts_exhausted")`; otherwise **release**: write `RUNNING{attempt=n, lease_until=now}` with `if_generation=gc` and return **503 + Retry-After**. A `WriteConflict` on release is the fenced case of step 6.
   - Any other exception becomes `InternalError("unexpected")`, so a deterministic bug does not burn GPU time on retries.
8. **`Conflict`** (r2 finding 2) → **200**, body `{"job_id": …, "outcome": "rejected", "problem": {RFC 9457, code "job_id_conflict"}}`. No record is written (the record belongs to the original request), and the event is logged at ERROR. A non-2xx would be retried by Cloud Tasks until `maxRetryDuration` (about 12 h), with every retry conflicting again.
9. **`GiveUp`** → write `FAILED("attempts_exhausted")` with `if_generation=g0` → notify → 200. On `WriteConflict`, return 503 with a short `Retry-After` and let the next delivery decide again.
10. **`AlreadyDone`** → 200 + the existing record. No re-notify.

**Why this lease and fencing, and nothing more** (r2 finding 1). The goal is: at most one attempt's result becomes visible, and a hung attempt cannot block the job for ever.
- **Lease = `dispatch_deadline_s + lease_margin_s`** (defaults 1800 + 120 = 1920 s). A retry of a deadline-exceeded attempt arrives no earlier than 1800 s + backoff, so a lease of only budget + 60 s (1560 s, round 1) had always expired by then and would start a second copy beside a still-running one. With 1920 s, an early duplicate or a deadline retry sees `InProgress` while the first attempt can still be alive.
- **No heartbeat renewal.** Renewal would need a CAS between stages and a new failure mode (renewal fails mid-job → abort). All it buys is faster crash recovery. With the static lease, a crashed attempt is retried at most about 32 min later, well inside the queue's 12 h window. Not worth the code.
- **Fencing by generation** is free: the terminal write is a CAS anyway, and using the claim's generation as the precondition means any later claim invalidates it. **Attempt-scoped artifact paths** stop a zombie from overwriting the winner's `result.json`/`captions.vtt` before its fenced CAS fails. Together they make the result correct even when a zombie outlives the lease.
- **Watchdog** (§6.3) makes the zombie case rare: an instance whose job thread outlives budget + grace is killed before the lease expires, freeing the GPU lock and the admission token. Fencing is still needed because the watchdog exists only on Cloud Run services, not on the Cloud Run job path or for self-hosters without probes, and because probe timing is not a correctness guarantee.

**Callbacks: best-effort, and why** (r2 finding 3). Two correct designs were compared:
- (A) **Best-effort.** After the terminal record, `notify` once (with the adapter's own bounded retries within about 30 s). A failure is logged and swallowed and never touches the record. The record (`GET /v1/jobs/{id}`) is the source of truth; Expause's reconciliation (below) picks up any lost callback.
- (B) `notified: bool` in `JobRecord`, re-notify on `AlreadyDone`. But after a 200, Cloud Tasks never redelivers, so (B) only works if scenewise answers 503 when the callback fails. That turns an outage of the Expause endpoint into hours of Cloud Tasks retries of finished jobs, and needs extra rules for permanent 4xx from the receiver.

**Decision: (A).** It is simpler and still correct, because reconciliation is required anyway for the storage-down case, and one mechanism then covers both. The cost is latency: a lost callback is noticed at Expause's next reconciliation run, not within minutes. (B) is the upgrade path if that latency matters. q1 §8.6 specifies at-least-once callbacks with a 24 h retry schedule, so the two documents disagree; see Q-16.

**Contract statements for callers** (documented for Expause):
- **scenewise's own counter is authoritative.** Set the queue to `maxAttempts: -1` and `maxRetryDuration` comfortably above `max_attempts × (lease + maxBackoff)`, for example 12 h. The queue's limits then never delete a task before scenewise has written a terminal record. `X-CloudTasks-TaskRetryCount` is only logged, because the docs say the headers are information only and 503 "in progress" replies would inflate it anyway.
- **Every task's `dispatchDeadline` must be ≤ the deployment's `dispatch_deadline_s`** (default 1800 s). scenewise cannot read the deadline from the request, so the lease relies on this.
- Idempotency key: the request's `job_id` (Expause: `expause:user_media:{mediaId}:r{rev}`, q1 §4.1). Expause may also name the task after it, to deduplicate enqueueing.
- **A retry is a new `job_id`** (r2 finding 16). A terminal job, including `FAILED("attempts_exhausted")` after a long backend outage, answers every re-delivery of the same `job_id` with `AlreadyDone`. Expause's `rev` already gives a new `job_id` for deliberate re-runs (q1 §8.3 item 6). An explicit `POST /v1/jobs/{id}/retry` is not in v1 (Q-17).
- **Reconciliation is mandatory.** A job with no callback after N hours triggers `GET /v1/jobs/{id}`: a terminal record → ingest it (this covers lost callbacks); `running`/`retry_wait` → wait; 404 → never received (or storage was down on every attempt until the task was deleted), so re-enqueue. The storage-down case is the only one scenewise cannot cover on its own.

### 6.3 Deadlines, liveness and concurrency (one design)

**Deadlines and timing invariants** (r1 finding 16, r2 finding 1). Settings under `service.*`, checked at start-up by `service/config.py` (a violation is a `ConfigurationError`):

| Setting | Default | Invariant |
|---|---|---|
| `attempt_budget_s` | 1500 | `budget + watchdog_grace_s + probe window (period × threshold) < dispatch_deadline_s` |
| `watchdog_grace_s` | 120 | — |
| `dispatch_deadline_s` | 1800 | = the tasks' `dispatchDeadline`; ≤ Cloud Run `--timeout` (deploy-time check, documented) |
| `lease_margin_s` | 120 | lease = `dispatch_deadline_s + lease_margin_s` = 1920 s |

- **Pre-flight:** after `probe()`, estimate the cost as `duration × Σ stage cost factors` (settings, calibrated per deployment from q2/q5 numbers). If the estimate exceeds the budget, raise `MediaTooLargeError(code="exceeds_push_budget")`: a terminal record, acknowledged, never retried. That media belongs on the Cloud Run job path (§6.4).
- **Cooperative deadline:** `run_job` checks the deadline between stages and between frame batches, and ffmpeg subprocesses get `timeout = remaining`. Hitting it raises `InternalError("deadline_exceeded")` (terminal). The anyio docs note that "there is no mechanism in Python to cancel code running in a thread" (https://anyio.readthedocs.io/en/stable/threads.html), so the work must stop itself. It cannot interrupt one long native call (the whole-file `transcribe()` is one call); that is what the watchdog is for.
- **Liveness watchdog:** `push.py` registers each admitted job in an in-process registry `{job_id: started_monotonic}` and removes it in `finally`. `/healthz` (`service/http/health.py`) returns 503 when any entry is older than `budget + watchdog_grace_s`. The Cloud Run service declares an HTTP liveness probe on `/healthz` (period 10 s, failure threshold 3, timeout 5 s). A hung native call is then killed by `SIGKILL` about 1650 s after it started, before the 1920 s lease ends: the instance is replaced, the GPU lock and admission token are freed, and the job's retry gets a clean `Start(n+1)` after the lease. A native call that holds the GIL also blocks `/healthz`, which fails the probe too: same outcome. The cost: another job in flight on that instance is killed with it and retried after its lease. `/readyz` (start-up probe) is separate and reports model loading.

**Concurrency** (r1 findings 13, 14; r2 finding 5):
- **Platform settings:** Cloud Run `--concurrency = max_jobs`. Cloud Run's own routing and scaling then do admission, so a burst after a cold start queues at the platform or scales out instead of collecting 429s. The queue's `maxConcurrentDispatches` is ≤ `max_instances × max_jobs`. Accepted cost: a rare `GET /v1/jobs/{id}` (reconciliation only) may wait behind jobs. Defaults: `max_jobs = 2` on GPU (one job in model calls while the other does I/O) and `1` on small CPU instances.
- **Admission safety net** (`service/http/push.py`): `limiter = anyio.CapacityLimiter(max_jobs)`, then `limiter.acquire_nowait()`. On `WouldBlock`, raise `CapacityError` → **429 + Retry-After**, and Cloud Tasks backs off. `acquire_nowait` "Acquire[s] a token for the current task without waiting … Raises WouldBlock" (anyio 4.15.1 API reference, https://anyio.readthedocs.io/en/stable/api.html). With `concurrency = max_jobs` this fires only for self-hosted deployments or if Cloud Run over-routes. The job runs in `await anyio.to_thread.run_sync(handle_delivery, ...)`, which uses the default 40-thread limiter, ≥ `max_jobs`, and the token is released in `finally`. Nothing in `app` touches anyio.
- **Model locks:** each local model adapter is constructed with a `threading.Lock` and holds it **only around the inference call**, never around ffmpeg, storage, hosted API calls or the whole job. `bootstrap` passes **one shared lock per GPU** to every model on that device (default when `device=cuda`), and a separate lock per model on CPU. Hosted adapters (Haiku, the OpenAI-compatible server) take no lock, because they are rate-limited by their own back end.
- **GPU OOM** (r1 finding 14): the adapter catches `torch.cuda.OutOfMemoryError` (documented for torch 2.14: https://docs.pytorch.org/docs/2.14/generated/torch.cuda.OutOfMemoryError.html) or onnxruntime's allocation failure, retries **once** with half the batch, then raises `InternalError("resource_exhausted")`. Only that stage fails (partial result). A whole-job retry would hit the same OOM.
- **GIL** (r1 finding 4):
  - **CTranslate2** releases it: "all computation methods release the Python GIL" (https://opennmt.net/CTranslate2/parallel.html). Concurrent calls also need `inter_threads` ≥ the number of concurrent callers.
  - **onnxruntime** `InferenceSession.run` releases it: `py::gil_scoped_release` with the comment "release GIL to allow multiple python threads to invoke Run() in parallel", in `onnxruntime/python/onnxruntime_pybind_state.cc` at commit `b131c79b6f` (read 2026-10-08).
  - **llama-cpp-python** is a `ctypes` binding (its README), and `ctypes.CDLL` releases the GIL around each foreign call (https://docs.python.org/3/library/ctypes.html). This no longer matters for v1, which talks to an HTTP server.
  - **torch/open_clip** is still unverified (Q-5).
  - Even without GIL release, the event loop stays responsive while a job runs: one job thread plus short I/O endpoints. If a native call holds the GIL for longer than the probe window, the watchdog treats it as hung, which is the intended behaviour only beyond the budget; Q-5 must confirm it does not happen within it.

### 6.4 Long media and other triggers (r1 finding 25)

| Option | How it works | Verdict |
|---|---|---|
| **(c) Synchronous push handler** (Cloud Tasks → Cloud Run service) | §6.1–6.3. Bounded by the 30-min `dispatchDeadline`. | **Default.** Short-form UGC fits easily. Parakeet CPU RTFx ≈ 37 (q2), and SigLIP 2 B/16 ≈ 66 ms per frame on CPU (q5). |
| (a) Cloud Tasks → Cloud Run **jobs `:run`** API | Expause enqueues an HTTP task to the Admin API's `jobs.run` with an OAuth token. `overrides` (args, env, task count, timeout) pass `--job-uri gs://…/request.json` (https://docs.cloud.google.com/run/docs/execute/jobs, updated 2026-10-07; overrides need `roles/run.developer`). The job runs `scenewise run-job`, the same `handle_delivery` with a larger budget and lease, and the same job record makes job-level retries idempotent. No liveness probe there, so fencing (§6.2) carries the zombie case alone. | **The long-media path, deferred.** Needs no scenewise code beyond the CLI command. GPU jobs need `--no-gpu-zonal-redundancy`, the L4 needs ≥4 CPU/16 GiB, the RTX PRO 6000 needs ≥20 CPU/80 GiB, new projects get 3 GPUs of regional quota and parallelism above it fails the deployment, and the driver is 580.x (CUDA 13.0). https://docs.cloud.google.com/run/docs/configuring/jobs/gpu (updated 2026-10-07; no launch stage stated). |
| (b) GPU **worker pool** pulling from Pub/Sub | No request deadline. L4 and RTX PRO 6000 are supported. "GPU worker pools cannot be autoscaled", although "worker pools that are set to instance-based billing can still scale to zero" (https://docs.cloud.google.com/run/docs/configuring/workerpools/gpu, updated 2026-10-07; no launch stage stated). It would also need a pull-loop entry point. | Rejected for v1: **no built-in autoscaling**, so zero-to-N would need an external scaler that sets the instance count. Revisit if volume becomes steady. |

### 6.5 Authentication of the push (r1 finding 21, r2 finding 14)

- Deploy the service with `--no-allow-unauthenticated`. Expause's tasks carry `oidcToken {serviceAccountEmail, audience}`. That service account "must have the Cloud Run Invoker IAM role to allow the task queue to push tasks to the Cloud Run service" (https://docs.cloud.google.com/run/docs/triggering/using-tasks, updated 2026-10-07).
- **Two more IAM facts** from the OidcToken reference: "The service account must be within the same project as the queue", and "The caller must have iam.serviceAccounts.actAs permission for the service account" (https://docs.cloud.google.com/tasks/docs/reference/rest/v2/OidcToken). So the identity that *creates* tasks (Expause's Cloud Functions service account) needs `iam.serviceAccounts.actAs` on the invoker service account, for example through `roles/iam.serviceAccountUser` granted on that one service account, not project-wide.
- **Set `oidcToken.audience` explicitly to the service root URL.** If omitted, "the URI specified in target will be used" (OidcToken reference), which is the full `/v1/jobs` URL. Cloud Run expects "the URL of the receiving service or a configured custom audience", and custom domains are not supported as `aud` (https://docs.cloud.google.com/run/docs/authenticating/service-to-service, updated 2026-10-07).
- Token verification is the platform's job, so scenewise has no token code on the push path. In-app verification for self-hosting outside GCP is deliberately left out of v1 (Q-13).
- Outbound callbacks to Expause carry a Google ID token (`google-auth`) or an HMAC signature (q1 §8.6).

### 6.6 Free-threading

- Free-threading is supported but not the default in 3.14 (PEP 779, Final, accepted 2025-06-16, https://peps.python.org/pep-0779/). The overhead is "about 1% on macOS aarch64 to 8% on x86-64 Linux", and importing an extension not marked free-threading-safe re-enables the GIL. https://docs.python.org/3/howto/free-threading-python.html (3.14.8)
- `cp314t` wheels on PyPI (2026-10-08): torch 2.14.1, ctranslate2 4.8.2, av 19.0.1, numpy 2.5.3, onnxruntime 1.30.0 (manylinux x86_64/aarch64 only), and pydantic-core **2.46.5** (the version pinned by pydantic 2.13.5; 15 cp314t files). https://pypi.org/pypi/pydantic-core/2.46.5/json
- Decision: target the GIL build in v1. Keep the door open: no mutable module-level state (the watchdog registry lives on the app instance, guarded by a lock), models owned by adapter instances, and all concurrency through explicit locks.
- Python 3.15.0 final is scheduled for 2026-10-09 (PEP 790). The CI matrix (3.12–3.14, U2) is q8b's.

---

## 7. Configuration and logging

### 7.1 Configuration

- pydantic-settings **2.15.0** (2026-08-07): `env_prefix="SCENEWISE_"`, `env_nested_delimiter="__"` (nested models must be `BaseModel`), and `SecretStr` for secrets. https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
- Shape: `asr` (discriminated on `backend: "parakeet" | "faster-whisper" | "none"`), `llm` (`"anthropic" | "openai-compat" | "none"`), `vision`, `storage`, `inputs` (allow-lists, `allow_local_paths`, `max_segments`, `max_input_bytes`), `delivery` (allowed callback URLs, HMAC keys), `service` (`max_jobs`, `attempt_budget_s`, `watchdog_grace_s`, `dispatch_deadline_s`, `lease_margin_s`, `max_attempts`, `state_prefix`, `required_stages`), `log`.
- `Settings()` is built **once** in the entry point and passed to `bootstrap`. Adapters never see it (r1 finding 28). A model validator enforces the §6.3 timing invariants.

### 7.2 Structured logging

- structlog **26.1.0** (2026-06-06) with stdlib `ProcessorFormatter` and a `foreign_pre_chain`, so uvicorn, httpx and torch logs are JSON too. The chain must end with `ProcessorFormatter.wrap_for_formatter`. https://www.structlog.org/en/stable/standard-library.html
- `contextvars` binding of `job_id`, `stage`, `attempt` and `backend` in `app/runner.py`; `task_name` and `transport_retry` (from `X-CloudTasks-TaskName`/`-TaskRetryCount`) in `service/http/push.py`. JSON in production, console in development.
- **Cloud Run** (r1 finding 2): one JSON line per entry goes to `jsonPayload`. `severity` is lifted into the entry's severity, `message` is the display text, and `logging.googleapis.com/trace` = `projects/<PROJECT>/traces/<TRACE_ID>`, with the trace id being the first segment of `X-Cloud-Trace-Context` split on `/`. That nests container logs under the request log. https://docs.cloud.google.com/run/docs/logging (updated 2026-10-07). `service/http` binds the trace value per request.

---

## 8. Error hierarchy and mapping (r1 findings 14, 18, 19, 20, 32; r2 findings 2, 4)

```python
class ScenewiseError(Exception):
    category: ClassVar[Literal["input", "retryable", "internal", "configuration"]]
    def __init__(self, code: str = "internal", detail: str = "") -> None: ...

class InputError(ScenewiseError)          # caller must change the request; never retried
    # codes: invalid_request, uri_not_allowed, corrupt_media, invalid_sprite_grid, input_encrypted,
    #        stage_unavailable, job_id_conflict
    class MediaTooLargeError(InputError)    # 413 class; codes: media_too_large, exceeds_push_budget
    class UnsupportedMediaError(InputError) # 415 class; codes: unsupported_media, manifest_unsupported
class RetryableError(ScenewiseError)      # transient; codes: backend_unavailable, storage_unavailable, job_in_progress
    class CapacityError(RetryableError)     # 429 + Retry-After; only from the non-blocking admission check
class InternalError(ScenewiseError)       # our side; retrying will not help
    # codes: model_output_invalid, resource_exhausted, deadline_exceeded, invariant_violation, attempts_exhausted, unexpected
class ConfigurationError(ScenewiseError)  # start-up only; process exits non-zero
```

Where errors land:
- **Inside a stage:** `InputError`/`InternalError` mark that stage `failed` (reason = code), and dependent stages are `skipped`. The job ends `PARTIAL`. **`RetryableError`** propagates and fails the attempt (§6.2 step 7).
  - Bad LLM JSON is retried **inside the stage** (2 attempts, the second with a repair prompt), then becomes `InternalError("model_output_invalid")`. It is never a whole-job retry.
  - Hosted APIs retry transient errors in their own client first: the Anthropic SDK retries by default, and the httpx adapter gets a bounded retry.
- **Before stages** (parse, fetch, probe, frame/audio acquisition): any error fails the whole job.
- **Stage not offered** (r1 finding 19): `service.required_stages` is checked at start-up. If a required stage has no back end, `ConfigurationError` stops the revision from becoming ready, so a bad deploy cannot silently swallow jobs. A request for a stage outside `enabled_stages` is an `InputError("stage_unavailable")`: a terminal record, visible to the caller.
- **Callback failure:** logged, never an error of the job (§6.2).
- No stage checkpointing in v1: a retried attempt starts over. This is deliberately left out (§12).

HTTP mapping (`service/http/problems.py`, RFC 9457 `application/problem+json` with extension members `code`, `category`, `retryable`; https://www.rfc-editor.org/rfc/rfc9457.html). The leaf classes' 413/415 apply only to a non-push caller; **on the push path every error with a keyed record answers 200**, because Cloud Tasks retries every non-2xx:

| Situation | `POST /v1/jobs` status |
|---|---|
| Job finished: succeeded, partial, or failed with a terminal record (any `InputError` incl. invalid body with a readable `job_id`, `InternalError`, `GiveUp`) | **200** + job status (a failure is in the body, not the status, so Cloud Tasks stops) |
| `job_id` reused with a different request | **200** + `{outcome: "rejected", problem: job_id_conflict}`; no record written; ERROR log |
| No usable `job_id` (not JSON, missing, or outside the pattern) | 422 (no record can be keyed; Cloud Tasks retries until `maxRetryDuration`, the signal for a broken producer) |
| `CapacityError` | 429 + `Retry-After` |
| `job_in_progress`, other `RetryableError` | 503 + `Retry-After` |
| Crash / no response / watchdog kill | Cloud Tasks retries; lease expiry recovers (§6.2) |

`GET /v1/jobs/{id}`: 200 + job status (`wire_status`, `result_uri` when terminal), or 404.

---

## 9. ffmpeg, frames and heavy dependencies

### 9.1 ffmpeg: subprocess (decided)

| Option | Status (read 2026-10-08) | Verdict |
|---|---|---|
| `subprocess` + system `ffmpeg`/`ffprobe` | — | **Chosen.** A decoder crash on hostile UGC kills a child process, not the service with its loaded models and other in-flight job. Timeouts are enforced by killing the child, which a thread cannot do (§6.3). Segment concat and fps filters are one argv each, reproducible by hand. Output frames arrive as `-f rawvideo -pix_fmt rgb24` on stdout, which is exactly the `Frame` format (§9.3), so there is no image encode/decode round-trip. Input is always a local file (§4), and `-protocol_whitelist file,pipe` keeps ffmpeg from fetching anything itself. |
| PyAV (`av`) | 19.0.1 (2026-10-03), Python ≥3.12, wheels "with FFmpeg bundled". https://pyav.basswood.io/docs/stable/overview/installation.html | **Rejected for the service.** The 3.12 floor is no longer a cost (U2), but in-process decoding of untrusted media and unkillable threads are. With Parakeet/onnx-asr as the ASR default, PyAV is not even a transitive dependency. faster-whisper's `av>=11` applies only to the `asr-whisper` extra, and any av version resolves there, since only av 19 needs ≥3.12. |
| ffmpeg-python | Last release 0.2.0, 2019-07-06; last commit `df129c7ba3`, 2022-07-11; #875 "Incompatible with ffmpeg 7" open. https://github.com/kkroening/ffmpeg-python | Rejected: unmaintained. |

Start-up check in `bootstrap`: `shutil.which` for both binaries, then `ffmpeg -hide_banner -version` compared against a minimum major version. Failure raises `ConfigurationError` with an install hint. Paths can be overridden by `SCENEWISE_MEDIA__FFMPEG`. The adapter always passes an argv list (never `shell=True`) and a timeout, and maps exit codes plus the stderr tail to `InputError("corrupt_media")` or `InternalError`.

### 9.2 Declaring ffmpeg: PEP 725 (r1 finding 6)

- **PEP 725** "Specifying external dependencies in pyproject.toml": **Draft**, Standards Track, created 2023-08-17, last modified 2026-04-17. It defines an `[external]` table (`build-requires`, `host-requires`, `dependencies`, optional variants, dependency groups) with DepURLs such as `dep:generic/ffmpeg`. Naming and the central registry are deferred to **PEP 804**. https://peps.python.org/pep-0725/
- The pyproject spec says top-level tables other than `[build-system]`, `[project]` and `[tool]` "are reserved for future use". https://packaging.python.org/en/latest/specifications/pyproject-toml/
- **Decision:** do not add `[external]` while PEP 725 is a Draft, because the table is reserved and tool behaviour is unspecified. Declare ffmpeg in the README, the Dockerfile and the start-up check. Adopt `[external] dependencies = ["dep:generic/ffmpeg"]` (runtime-only, so `dependencies`, not `host-requires`) once the PEP is accepted.

### 9.3 How frames cross ports (decided)

`Frame(timestamp, width, height, rgb: bytes)` holds packed RGB24, row-major, downscaled at decode so the longer side is ≤ `max_side` (default 448, the q4 classifier's input size; SigLIP B/16 uses 224–256).

| Option | Verdict |
|---|---|
| **Raw RGB bytes + dims** | **Chosen.** Stdlib-only, so `domain` stays clean. ffmpeg emits it directly, and Pillow produces it with `tobytes()`. Adapters convert zero-copy (`numpy.frombuffer`, `PIL.Image.frombuffer`). Lossless. Fakes are trivial. Memory: 448×448×3 ≈ 0.6 MB per frame, so a 32-frame batch is ≈ 19 MB. |
| Encoded JPEG/PNG bytes | Smaller, but every model adapter decodes again, and video frames would be re-encoded lossily. |
| File path | Adds temp-file management and disk I/O per frame, and sprite tiles would have to be written out. |
| numpy array / PIL image | Puts a third-party type in `domain` and the ports, which breaks the layer rule. |

### 9.4 Extras (r2 finding 9: torch only where vision needs it)

Round 1 had one `cpu`/`cu130` selector that routed torch, torchvision **and** onnxruntime, so every ASR image pulled the torch CUDA 13 stack (torch 2.14.1 requires `cuda-toolkit==13.0.3`, `nvidia-cudnn-cu13`, NCCL and more; PyPI `requires_dist`) that onnxruntime-gpu does not need. The selectors are now split by runtime:

```toml
[project]
requires-python = ">=3.12"
dependencies = ["pydantic>=2.13", "pydantic-settings>=2.15", "structlog>=26.1", "httpx>=0.28"]
[project.optional-dependencies]
service       = ["fastapi>=0.142", "uvicorn>=0.54"]
asr           = ["onnx-asr[hub]>=0.12"]                    # runtime comes from ort-cpu / ort-cu130
asr-whisper   = ["faster-whisper>=1.2.1"]                 # CTranslate2 (CUDA 12) — CPU in v1 images, §9.5
llm-anthropic = ["anthropic>=1.12"]
vision        = ["open-clip-torch>=3.3", "timm>=1.0.17", "pillow"]   # torch comes from torch-cpu / torch-cu130
gcs           = ["google-cloud-storage>=3.16", "google-auth"]
ort-cpu       = ["onnxruntime>=1.30"]
ort-cu130     = ["onnxruntime-gpu[cuda,cudnn]>=1.30"]
torch-cpu     = ["torch>=2.14", "torchvision>=0.29"]
torch-cu130   = ["torch>=2.14", "torchvision>=0.29"]

[tool.uv]
conflicts = [
  [{ extra = "ort-cpu" },   { extra = "ort-cu130" }],
  [{ extra = "torch-cpu" }, { extra = "torch-cu130" }],
]

[tool.uv.sources]
torch       = [{ index = "pytorch-cpu", extra = "torch-cpu", marker = "sys_platform == 'linux'" },
               { index = "pytorch-cu130", extra = "torch-cu130" }]
torchvision = [{ index = "pytorch-cpu", extra = "torch-cpu", marker = "sys_platform == 'linux'" },
               { index = "pytorch-cu130", extra = "torch-cu130" }]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true
```

- **Why torch is listed in the selector extras, not only reached transitively through `vision`:** uv's docs say "Sources can also be declared as applying only to a specific optional dependency", and the example lists `torch` inside each extra its source names (https://docs.astral.sh/uv/concepts/projects/dependencies/). The page does not say that a source applies to a package reached only transitively, so torch and torchvision are listed directly in `torch-cpu`/`torch-cu130`. A lock-time check (q8b follow-up) asserts that `uv.lock` resolves torch from the PyTorch index under each selector.
- **The pairs are independent.** `ort-cu130` with `torch-cu130` is the normal GPU image. Mixing CPU and GPU across the pairs resolves but is caught at start-up: with `device=cuda`, `bootstrap` requires `onnxruntime.get_available_providers()` to contain `CUDAExecutionProvider` and, when vision is enabled, `torch.version.cuda` to start with "13". Otherwise `ConfigurationError`.
- **Images:** ASR-only GPU = `--extra service --extra asr --extra ort-cu130` (no torch); full GPU adds `--extra vision --extra torch-cu130`; CPU images use `ort-cpu`/`torch-cpu`.
- **torchvision is routed with torch** (r1 finding 23). open-clip-torch 3.3.0 requires `torchvision` and `timm>=1.0.17` (https://pypi.org/pypi/open-clip-torch/json), and the uv guide routes torchvision through the same index (https://docs.astral.sh/uv/guides/integration/pytorch/). torchvision 0.29.1 requires `torch>=2.14.0`, and both `+cpu` and `+cu130` cp312 wheels exist on the PyTorch indexes (checked 2026-10-08).
- onnx-asr 0.12.0 has no hard onnxruntime dependency (`cpu`/`gpu`/`hub` extras), so `onnx-asr[hub]` plus one `ort-*` selector does not double-install onnxruntime.
- macOS: the `torch-cpu` routing marker is Linux-only, so macOS gets PyPI's torch (no CUDA builds exist there).
- No `llm-local` extra. The OpenAI-compatible adapter uses httpx only. llama-cpp-python 0.3.36 ships **no PyPI wheels** (sdist only), and an out-of-process server also isolates crashes and memory.
- Versions read from PyPI on 2026-10-08: fastapi 0.142.4, uvicorn 0.54.0, onnx-asr 0.12.0, onnxruntime-gpu 1.30.0, faster-whisper 1.2.1, ctranslate2 4.8.2, anthropic 1.12.1, torch 2.14.1, torchvision 0.29.1, open-clip-torch 3.3.0, timm 1.0.30, google-cloud-storage 3.16.0, httpx 0.28.1, anyio 4.15.1. Lower bounds are placeholders for the dependency-policy item.
- pip users: `tool.uv.*` does not reach wheel metadata, so `pip install scenewise[vision,torch-cpu]` gets PyPI's default torch build. That build is **CUDA 13** on Linux: torch 2.14.1 on PyPI requires `cuda-toolkit[...]==13.0.3` and `nvidia-cudnn-cu13`. The README tells pip users to pass `--index-url https://download.pytorch.org/whl/cpu` for CPU.

### 9.5 CUDA versions across runtimes (r1 finding 24)

| Runtime | CUDA it needs (checked 2026-10-08) |
|---|---|
| torch 2.14.1 (PyPI default and `+cu130`) | 13.0 (`cuda-toolkit==13.0.3`, `nvidia-cudnn-cu13`) |
| onnxruntime-gpu 1.30.0 (Parakeet default ASR) | 13 (`nvidia-cuda-runtime~=13.0`, `nvidia-cudnn-cu13` via extras) |
| ctranslate2 4.8.2 (faster-whisper fallback) | 12 (classifier `NVIDIA CUDA :: 12 :: 12.4`; loads CUDA 12/cuDNN 9 at run time) |
| Cloud Run GPU driver | 580.x = CUDA 13.0 |

**Decision:** `cu130` is the GPU target. It is the one CUDA major shared by the default ASR, vision and the Cloud Run driver.

The reviewer's `cu128` proposal (round 1) is rejected on two counts:
- The cu128 index stops at **torch 2.11.0**, with no 2.14.1 wheels (checked 2026-10-08).
- It would move the *default* stack to CUDA 12 just to serve the fallback.

The CTranslate2 fallback therefore runs on **CPU** in v1 GPU images. If a GPU whisper image is ever needed, build it separately with torch `+cu126` (2.14.1 wheels exist on the cu126 index) and leave out onnxruntime-gpu (Q-8).

---

## 10. Entry-point flow

```
service/http/app.py lifespan            service/cli.py
   settings = Settings()                   settings = Settings()          # timing invariants validated
   logs.configure(settings.log)            logs.configure(settings.log)
   deps = bootstrap.build_dependencies(settings)   # ffmpeg probe, required_stages check, models loaded once, lazy imports

POST /v1/jobs (OIDC-checked by Cloud Run IAM)
   push: contract.envelope.parse(raw) → Envelope, digest          → 422 only if no usable job_id
   push: bind task headers to log context; admit()                → 429 if full; register in watchdog
   await to_thread.run_sync(app.delivery.handle_delivery, envelope, raw, deps, info)
        read record → decide → claim (CAS, fencing token) → contract.to_domain(raw)
        → app.runner.run_job(deadline) → app.publish (artifacts under a{n}/)
        → terminal record (CAS on token) → notify (best-effort)
   → 200 status | 200 rejected (job_id_conflict) | 429/503 + Retry-After

GET /healthz → 503 if a job thread is older than budget + grace (liveness probe)
scenewise analyse <file>     → app.runner.run_job → print/write locally (no record, no notify)
scenewise run-job --job-uri  → app.delivery.handle_delivery with a large budget and lease (Cloud Run job path, §6.4)
```

---

## 11. Comparison with real projects

Layouts and commits were checked through the GitHub API on 2026-10-08.

| Project | Commit / date | Layout | What scenewise takes / avoids |
|---|---|---|---|
| **faster-whisper** https://github.com/SYSTRAN/faster-whisper | `9fa78645d7`, 2026-10-06 | Flat, `setup.py`. `transcribe.py` 1,952 lines. `utils.py`. Depends on `av>=11`, `ctranslate2>=4,<5`. | Avoid the huge module and `utils.py`. Take the narrow API, easy to wrap. |
| **WhisperX** https://github.com/m-bain/whisperX | `771b4a14a9`, 2026-09-26 | Flat, `uv.lock`, `requires-python >=3.10,<3.14`, `torch~=2.8.0`, `[tool.uv.sources]` with platform markers to cu128/cpu indexes. | Take the uv index routing. Avoid torch in base deps and the Python upper bound. |
| **LiteLLM** https://github.com/BerriAI/litellm | `7a659973e3`, 2026-10-08 | Flat. `main.py` 9,435 lines, `router.py` 15,234 lines, `utils.py` 449 KB. | Counter-example. Take one module per provider. |
| **vLLM** https://github.com/vllm-project/vllm | `7d47ac2ddb`, 2026-10-08 | `entrypoints/` separate from the engine. API server and engine core are separate processes over ZMQ. https://docs.vllm.ai/en/latest/design/arch_overview.html | Take entry points separated from the engine. The `openai_compat` adapter can target a vLLM server. |
| **Pydantic AI** https://github.com/pydantic/pydantic-ai | `f55bb8a6fd`, 2026-10-08 | uv workspace of several published packages. One module per provider behind `Model(AbstractModel)`. | Take one adapter module and one extra per back end. A workspace is justified only by several published packages. |
| **Warehouse (PyPI)** https://github.com/pypi/warehouse | `14b79b44aa`, 2026-10-07 | Split by feature. `interfaces.py` (zope.interface) + `services.py`, resolved through the **`pyramid_services` service locator**. Also has a package-local `warehouse/logging.py` and `utils/` directories. | Take explicit interface modules and storage behind an interface. Do not take the locator (§2.2) or the naming. |

FastAPI on CPU-bound work: the async page says parallelism helps "**CPU bound** workloads like those in Machine Learning systems" and links to its Deployment section (https://fastapi.tiangolo.com/async/). Its "Server Workers" page covers multi-process serving (https://fastapi.tiangolo.com/deployment/server-workers/). scenewise runs one process per Cloud Run instance and scales by instance.

None of the four ML projects uses `src/`. scenewise follows PyPA, Hynek and cosmicpython because it is a showcase.

---

## 12. Deliberately left out of v1

- Stage checkpointing and resume. ASR of short-form media costs seconds, so a retried attempt simply restarts. Add it if the Cloud Run job path for long media lands.
- Lease renewal (heartbeat). The static lease plus fencing is correct; renewal would only speed up crash recovery (§6.2).
- At-least-once callbacks (`notified` flag, re-notify, redeliver endpoint). Best-effort plus mandatory reconciliation is correct and simpler (§6.2, Q-16).
- A `202 Accepted` + background execution mode. Background CPU needs instance-based billing, and it discards Cloud Tasks' retry for the actual work (§6.1).
- DASH manifests, HLS byte ranges and live playlists (Q-18).
- A database, a Repository, Unit of Work, a message bus, a DI container, plugin entry points, a `Stage` class, a `Clock` port.
- Model-serving frameworks (LitServe, BentoML, Ray Serve, Triton).
- In-process llama-cpp-python, PyAV, the `[external]` table, `cu128`, a GPU faster-whisper image.
- Pub/Sub delivery (q1 lists it as an alternative). It would be a second `Notifier` when needed.
- In-app OIDC verification for non-GCP hosting.
- Any Expause-specific code.

---

## 13. Open questions

Each is phrased as a decision for the user, with both sides. This was the last review round; nothing here blocks starting v1 with the default stated.

- **Q-5 (torch GIL):** does open_clip/torch inference release the GIL? *If it does not*, a long vision call can starve `/healthz`; the probe timeout (5 s × 3) bounds the risk. Decide: (a) accept and measure in the model test tier (default), or (b) run vision in a subprocess, which costs a second model copy and IPC.
- **Q-8 (GPU whisper):** is a CUDA 12 image (torch `+cu126`, ctranslate2, no onnxruntime-gpu) ever needed for the faster-whisper fallback? (a) CPU is enough (default; no second image). (b) Build a cu126 image, if q2's language-ID gate runs Whisper on every job and CPU is too slow.
- **Q-11 (cost factors):** calibrate the per-stage cost factors for the push-budget pre-flight on the target Cloud Run shape (CPU vs L4). A measurement, not a design choice.
- **Q-12 (q1 alignment: 200-on-completion vs 202-queued):** (a) this document: synchronous push handler, Cloud Tasks is the queue, `dispatchDeadline` 1800 s; (b) q1 §8.3/§8.5: 202 admission within a 30 s `dispatchDeadline`, a scenewise-owned bounded durable queue, workers with leases. (a) needs no second queue or always-on CPU; (b) decouples admission from execution and supports media longer than 30 min without the jobs path. Recommendation: (a). q1 must then change its queue settings (`dispatchDeadline` 30 s → 1800 s; `maxAttempts` 50/24 h → `-1`/12 h).
- **Q-13 (self-hosted auth):** outside GCP, (a) a reverse proxy does auth (default, no code), or (b) in-app bearer/OIDC verification (q1 §8.6 sketches it), which adds google-auth on the push path.
- **Q-14 (local FS store):** `storage/local.py` CAS is single-host only (lock plus `O_EXCL`). (a) Enough for docker-compose self-hosting (default). (b) A SQLite-backed record store, as a second `BlobStore` mode, not a new port.
- **Q-16 (callback semantics, q1 vs q8a):** (a) best-effort callback + record as source of truth + mandatory Expause reconciliation (this document; one mechanism, no retry scheduler in scenewise); (b) q1 §8.6: at-least-once with a Standard Webhooks schedule up to 24 h, `delivery_failed` state and `POST …/redeliver`, which needs a durable retry scheduler that the synchronous design does not have (or the `notified` flag plus 503s, §6.2). Choose (a) unless Expause needs results within minutes even when its endpoint flaps.
- **Q-17 (other q1 mismatches; q1 is being revised in parallel, read 2026-10-08):** each needs one side to change.
  - `job_id` pattern: q8a adopts q1's `^[A-Za-z0-9._:-]{1,200}$` (round 1 had `[A-Za-z0-9_-]{1,128}`, which rejects Expause's `expause:user_media:…:r1`), plus "not `.` or `..`". Settled here; q1 should state the path-segment rule.
  - `POST /v1/adapters/expause/tasks` and `adapters/expause/payloads.py` (q1 §8.4–8.5) vs no Expause code in scenewise (§1.3). (a) Expause sends the generic `JobRequest` (this document); (b) scenewise hosts an Expause-shaped route. Recommendation: (a).
  - Endpoints in q1 but not in v1 here: `POST …/retry`, `POST …/redeliver`, `DELETE /v1/jobs/{id}`, `POST /v1/purge`, and `input_retention: "delete_on_terminal"`. The last three need a `BlobStore.delete` method and an `external_ref` index. Decide whether purge and input deletion are v1 (they matter for the plaintext-lifecycle argument in q1 §8.7); if yes, add `delete(uri)` and `list(prefix)` to `BlobStore`.
  - `SpriteSheets.sheets_prefix` (q1 §4.3) needs a prefix listing, which `BlobStore` lacks; q8a's domain takes an explicit `sheets` tuple. (a) add `BlobStore.list(prefix)` (gcs and local only), or (b) Expause sends the explicit list (at most a few sheets).
  - `VideoForFrames.format: "hls" | "dash"` and `sampling: "scene"` (q1 §4.3) have no counterpart in `VideoFrames`. Default: `format: "file"` and `sampling: "interval"` only in v1.
  - Artifacts are attempt-scoped (`…/a{n}/`), so q1's `vtt_uri` and `uri_prefix` examples gain an `a{n}/` segment; callers must read `result_uri`/`vtt_uri`, never build paths.
  - q1 §8.5 says a `segments`/`manifest` request is stitched by scenewise; this document implements HLS only (Q-18).
- **Q-18 (DASH in v1):** (a) HLS only; `format: "dash"` → `manifest_unsupported` (default: Expause's default path is a single file, and its backfill submits HLS); (b) add DASH `SegmentTemplate`/`SegmentList` parsing, which needs untrusted-XML parsing (Python's docs warn that Expat below 2.7.2 "may be vulnerable to the 'billion laughs', 'quadratic blowup' and 'large tokens' vulnerabilities", https://docs.python.org/3/library/xml.html) and its own tests.
- **Q-19 (probes and concurrency):** the Cloud Run health-check page does not say whether probes take a request slot. If they do, a liveness probe at `concurrency = max_jobs` could queue behind two long jobs and kill a healthy instance. Decide: (a) verify on a deployed revision before production (default), and if probes do take slots, (b) set `--concurrency = max_jobs + 1` and accept occasional 429s from the in-app limiter.
- Closed in round 1: Q-1 (subprocess), Q-2 (PEP 725 Draft), Q-3 (TypeAdapter in `app`), Q-4 (raw RGB frames), Q-6 (Cloud Run log fields), Q-7 (Cloud Tasks codes), Q-9 (jobs GPU constraints), Q-10 (floor 3.12, U2), Q-12-old (Expause boundary). Q-11-old (hosted ASR) dropped.
- Closed in round 2: Q-15 (q8b contract updates) moves to "Follow-ups for q8b" below.

---

## Follow-ups for q8b

Every change in this document that affects `q8b-tooling-gates.md` (not edited here):

1. **Layers contract:** add `exhaustive_ignores = ["__main__"]` to the `layers` contract (q8b §3, around its `exhaustive = true` line); add a `__main__.py` to its seeded test so the exhaustive check is exercised.
2. **Forbidden contract "ports and use cases":** add `onnxruntime`, `onnx_asr`, `torchvision`, `PIL` and `numpy` to `forbidden_modules`. pydantic stays **allowed** in `app` (it now hosts `app/contract/`).
3. **New forbidden contract:** `scenewise.service.http` and `scenewise.service.cli` → `scenewise.adapters` (only `bootstrap` may import adapters).
4. **Adapters must not import `scenewise.app`** (incl. `app.contract`): already enforced by the layers contract; add a seeded test (`adapters/notify` importing `app.contract`) so the rule is visibly covered.
5. **Coverage include paths:** `src/scenewise/app/*` now includes `app/contract/*` and `app/audio.py`; `domain/*` includes `domain/manifests.py` and `domain/uris.py`. The 100% domain+app gate applies to all of them. `service/http/health.py` (watchdog) needs a unit test.
6. **Module size gate (`MAX_LINES = 400`):** `app/contract/` is a package from the start; `adapters/media/ffmpeg.py` may split into `probe.py`/`decode.py`; `ports.py` splits at ≈200 lines into `ports/`. No exemptions are requested.
7. **Extras renamed:** CI's `uv sync --group dev --extra asr --extra vision` must add selectors: `--extra ort-cpu --extra torch-cpu` (q8b's model-tier job). Replace the placeholder note "The extra names (`asr`, `vision`) are placeholders".
8. **Lock checks:** a gate that `uv lock --check` passes with both conflict pairs, and a small script asserting that `uv.lock` resolves torch/torchvision from the PyTorch index under `torch-cpu`/`torch-cu130` and that an `--extra asr --extra ort-cu130` resolution contains no `torch` (r2 finding 9).
9. **Contract tests per port:** `Notifier` now takes `bytes`; `BlobStore` contract tests must cover `WriteConflict` on create-if-absent and on a stale generation (the fencing case), for both `local` and `gcs` (emulator or fake).
10. **Pure-function tests with hypothesis:** `domain.jobs.decide_attempt` (all decision branches, lease boundary), `domain.manifests.parse` (encrypted, byte-range, live, master vs media, relative URIs), `domain.uris.resolve` for `gs://`.
11. **e2e media generation:** add an HLS fMP4 audio fixture generated with ffmpeg (`-f hls -hls_segment_type fmp4`) from the existing lavfi/flite sources, to test the stitch path.
12. **deptry:** `onnxruntime`/`onnxruntime-gpu` and `torch` are now reached only through selector extras; deptry config must map `onnxruntime-gpu` to the `onnxruntime` import name.

---

## Review round 1 — resolution

Each finding was re-checked against the source on 2026-10-08.

| # | Finding | Resolution |
|---|---|---|
| 1 | Cloud Tasks codes cited from a mirror | **Fixed.** The official REST reference (updated 2026-09-30) confirms 2xx, retry on other/no response, 429/503 higher backoff, `Retry-After`, deadline [15 s, 30 min], and the cancel-on-deadline wording. §6.1. Q-7 closed. |
| 2 | Cloud Run log fields left as a lead | **Fixed.** Cited https://docs.cloud.google.com/run/docs/logging, with the trace format `projects/<P>/traces/<id>`. §7.2. Q-6 closed. |
| 3 | pydantic-core version | **Fixed.** pydantic 2.13.5 pins `pydantic-core==2.46.5`, which has 15 cp314t files (PyPI JSON). §6.6. |
| 4 | GIL release left unverified | **Fixed.** CTranslate2 (docs, plus the `inter_threads` note), onnxruntime (source line at `b131c79b6f`) and ctypes (docs) are verified. torch remains open (Q-5). §6.3. |
| 5 | PyAV 3.12 floor | **Fixed** (moot): the floor is 3.12 anyway (U2), and only av 19 needs it. §9.1. |
| 6 | PEP 725 not researched | **Fixed.** Draft, last modified 2026-04-17, PEP 804 for the registry. The reviewer's "optionally add `[external]`" part is **rejected**: the spec reserves other top-level tables "for future use". §9.2. |
| 7 | cosmicpython "suggest" Protocols | **Fixed** to "mention … as an alternative". §2.1. |
| 8 | FastAPI "Uvicorn workers" | **Fixed:** "links to its Deployment section", plus the Server Workers page cited separately. §11. |
| 9 | Jobs GPU constraints omitted | **Fixed:** RTX PRO 6000 ≥20 CPU/80 GiB, `--no-gpu-zonal-redundancy`, 3-GPU quota, driver 580/CUDA 13. §6.4. |
| 10 | Warehouse uses a service locator | **Fixed** (verified `pyramid_services>=2.1` and `register_service_factory` at `14b79b44aa`). Explained why scenewise does not need one. §2.2, §11. |
| 11 | Driving adapter under `adapters/` breaks rule 5 | **Fixed.** Driving code (HTTP, CLI, bootstrap) lives in `service/`, and `adapters/` is driven only. The Expause package is removed entirely (Expause builds its own adapter). §1.3–1.5. |
| 12 | `FrameSource` unwired; `probe()` misplaced | **Fixed** with option (b): `app/frames.py` dispatches on `VisualSource` to the `MediaTool` and `ImageReader` ports. Round 2 added the audio counterpart `app/audio.py`. §4. |
| 13 | Limiter held for the whole job | **Fixed.** Admission limiter for jobs. `threading.Lock` per GPU (or per model on CPU) held only around inference. No anyio in `app`. §6.3. |
| 14 | "Limiter full" never raised; OOM retried | **Fixed.** `acquire_nowait()` → `WouldBlock` → 429 (anyio API verified). OOM: retry once at half batch inside the adapter, then `InternalError`, failing that stage only. §6.3, §8. |
| 15 | No idempotency | **Fixed.** `job_id`-keyed record with `ifGenerationMatch` CAS, digest check, and duplicates acknowledged. §6.2. |
| 16 | Deadline interplay, runaway threads | **Fixed in round 2** (round 1's lease was too short): lease ≥ `dispatchDeadline` + margin, generation fencing, attempt-scoped artifacts, liveness watchdog. §6.2, §6.3. |
| 17 | Retries running out | **Fixed differently.** scenewise's own attempt counter is authoritative and writes a terminal record; queue `maxAttempts: -1` plus a long `maxRetryDuration`. §6.2. |
| 18 | Bad LLM JSON retries the whole job | **Fixed** (in-stage retry with a repair prompt, then the stage fails and the job is partial). The checkpointing half is **rejected for v1** (§12). |
| 19 | `StageUnavailable` silently acknowledged | **Fixed.** `required_stages` is checked at start-up. A request for an unoffered stage stays a visible `InputError`. §8. |
| 20 | `TimeSpan` raises `InputError` | **Fixed.** Domain raises `ValueError`, and boundaries translate it. §5. |
| 21 | No push authentication | **Fixed.** IAM-only service, `roles/run.invoker`, `oidcToken`, audience set explicitly; round 2 added `actAs`. §6.5. |
| 22 | 404 implies state with no store | **Fixed.** `status.json` job record under the state prefix. §6.2. |
| 23 | torchvision not routed | **Fixed.** torchvision is routed with torch, `timm` is added; round 2 split the selectors. §9.4. |
| 24 | CTranslate2 CUDA 12 vs cu130 | **Fixed differently.** `cu128` **rejected** (index stops at torch 2.11.0; onnxruntime-gpu 1.30 is CUDA 13). CTranslate2 on CPU; cu126 image optional (Q-8). §9.5. |
| 25 | Options for long/GPU work | **Fixed.** Jobs `:run` (deferred) vs worker pool (rejected for v1) vs sync push (default). §6.4. |
| 26 | No mention of serving frameworks | **Fixed:** one paragraph rejecting LitServe/BentoML/Ray Serve/Triton. §2.2. |
| 27 | Generic push adapter option | **Adopted** as the design. §1.3. |
| 28 | Adapters coupled to `config` | **Fixed.** Plain kwargs, `bootstrap` unpacks. §1.5 rule 2. |
| 29 | Who publishes | **Fixed**; round 2 made the ownership statement consistent everywhere (§2.3). |
| 30 | Tuples "hashable" vs Mapping | **Fixed.** Justified by immutability. `outcomes: tuple[StageOutcome, ...]`. §5. |
| 31 | Undefined names in ports | **Fixed**; round 2 sketched the remaining names (`Blob`, `Callback`, `StageOptions`, the five decisions, `FallbackTextGenerator`). §4–5. |
| 32 | One subclass per code | **Fixed.** Four categories plus three leaves. `code` is an instance argument with default `"internal"`. §8. |

Rejected outright: none. Partly rejected: #6 (adding `[external]` now), #17 (header-vs-maxAttempts mechanism), #18 (checkpointing), #24 (`cu128`). Round 2's reviewer judged all four partial rejections sound.

---

## Review round 2 — resolution

Each finding was re-checked on 2026-10-08 (WebFetch of the import-linter layers page, the Cloud Run health-check, Cloud Tasks-trigger and GPU worker-pool pages, the OidcToken reference, the anyio threads page, uv's dependency-sources page and the Python XML-security page). All 17 findings held up; none is rejected. Two are resolved by a choice the reviewer offered as an alternative (#3, #9's approach).

| # | Sev. | Finding | Resolution |
|---|---|---|---|
| 1 | wrong | Lease (budget + 60 s) shorter than the Cloud Tasks deadline; zombie unfenced; `WriteConflict` unhandled | **Fixed.** Lease = `dispatch_deadline_s + 120 s` (1920 s), static, no heartbeat (reason in §6.2). Claim generation is the fencing token for the terminal and release CAS; artifacts under `a{n}/`; `WriteConflict` on claim → 503, on finish/release → "superseded", no notify, re-decide. Liveness watchdog on `/healthz` kills the instance at budget + grace (verified: liveness failure → `SIGKILL`, new instance). Start-up invariants. §6.2, §6.3. |
| 2 | wrong | 409 for `job_id_conflict` is retried for 12 h | **Fixed.** 200 with `{outcome: "rejected", problem}`, no record write, ERROR log. 409 removed. §6.2 step 8, §8. |
| 3 | design | Callback is at-most-once and can be lost | **Fixed by choosing the reviewer's alternative:** best-effort callbacks, record is the source of truth, Expause reconciliation made mandatory. Rejected the `notified` flag because after a 200 Cloud Tasks never redelivers, so it would require 503s on callback failure. Notify failure never touches the record. Disagreement with q1 §8.6 → Q-16. |
| 4 | design | Domain-invalid bodies with a readable `job_id` never reach a terminal record | **Fixed.** `Envelope` parsed first in `push.py`; `decide_attempt` takes the digest; full `to_domain` runs inside the claim, so `InputError` → terminal `FAILED` + 200. 422 only without a usable `job_id`. §5.1, §6.2. |
| 5 | design | `--concurrency = max_jobs + 2` makes 429s the burst path | **Fixed.** `--concurrency = max_jobs`; the limiter is a safety net; a rare GET may wait. Whether probes take a slot is not documented → Q-19. §6.3. |
| 6 | design | No audio acquisition; `AudioManifest` unimplementable | **Fixed.** `app/audio.py::acquire_audio`, `domain/manifests.py` (pure HLS parsing), `domain/uris.py`; lists by reference parsed via `app/contract`; all fetches through `BlobStore` with the URI allow-list; local byte-concat then one ffmpeg extraction; segment and byte limits. DASH deferred (Q-18). q1 mismatches → Q-17. §4. |
| 7 | design | Wire contract in `service/` unreachable from `app/publish.py` and the notifier | **Fixed.** Moved to `app/contract/` (envelope, requests, results, mapping); `service/http` imports it; `Notifier.notify(body: bytes, *, callback, idempotency_key)`. §1.4, §1.5 rule 5, §4. |
| 8 | unsupported | `exhaustive = true` needs `__main__` excluded | **Fixed** (verified `exhaustive_ignores` on the import-linter page): `exhaustive_ignores = ["__main__"]`; q8b follow-up 1. §1.5. |
| 9 | design | Accelerator selectors pull torch into ASR-only images | **Fixed** with split selectors `ort-cpu`/`ort-cu130` and `torch-cpu`/`torch-cu130`, two conflict pairs, torch listed directly in the selector extras because uv's docs only show extra-scoped sources for packages listed in that extra; lock-check follow-up. §9.4. |
| 10 | minor | Who writes the record and notifies: three inconsistent statements | **Fixed.** `publish` = artifacts only; `delivery` = every record write + notify. §1.4, §2.3, §6.2, §10. |
| 11 | minor | `AttemptInfo.transport_retry` is unused ceremony | **Fixed.** Removed; bound to the log context in `push.py`. §5, §7.2. |
| 12 | design | `schemas.py` likely > 400 lines; `ffmpeg.py` borderline | **Fixed.** `app/contract/` package of four modules; `ffmpeg.py` may split into `probe.py`/`decode.py`; `ports.py` split rule kept. §1.4. |
| 13 | minor | Two paraphrases in quotation marks | **Fixed** with verbatim text: "The Cloud Run service must return an HTTP 200 code to confirm success after processing of the task is complete." and "there is no mechanism in Python to cancel code running in a thread" (both re-read). §6.1, §6.3. |
| 14 | missing option | `iam.serviceAccounts.actAs` and same-project rule for `oidcToken` | **Fixed** (quoted from the OidcToken reference); suggests `roles/iam.serviceAccountUser` on the one SA. §6.5. |
| 15 | minor | Unsketched names | **Fixed.** `Blob` (ports), `Callback` (q1's `HttpCallback`), `StageOptions`, `Start`/`AlreadyDone`/`InProgress`/`GiveUp`/`Conflict` (domain), `FallbackTextGenerator` → `adapters/llm/fallback.py`. §1.4, §4, §5. |
| 16 | minor | Retry of a failed job; "running" shown while nothing runs | **Fixed.** Contract statement "a retry is a new `job_id`"; `wire_status` derives `retry_wait` from an expired lease, no new state. §5, §6.2. |
| 17 | minor | Worker pools are not inherently "always-on" | **Fixed:** "no built-in autoscaling; zero-to-N would need an external scaler", with both verbatim quotes. §6.4. |

Additional changes made while resolving the findings: `job_id` pattern aligned with q1 (round 1's pattern rejected Expause's own ids); `by_scheme.py` enforces the URI allow-list; ffmpeg gets `-protocol_whitelist file,pipe`; "Follow-ups for q8b" replaces Q-15.
