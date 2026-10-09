# scenewise Docs Index

> One-line: the map of scenewise's feature and concept documents, grouped by area. Every entry links its document and says in one line what you will find there.

## What it is & why

scenewise is a self-hosted video-understanding service. Callers reach it through `POST /v1/jobs` (Cloud Tasks push semantics) or through the `scenewise` command line (`README.md`). This page is where you start: find the area you are working in, open the linked document, and follow that document's own `Anchor files` into the code.

- **Features** (`docs/features/`) describe what a caller can do: the business behaviour, every surface that triggers the feature, and its slice of each layer (`domain`, `app`, `adapters`, `service`, `package`, `tests`, `general`).
- **Concepts** (`docs/concepts/`) describe the cross-cutting mechanisms the features share.

Scope of the code today: `audio` is the only stage that is wired. `StageName` also declares `captions`, `summary`, `chapters`, `moderation` and `labels`, and its docstring says they "arrive with roadmap items 1-4" (`src/scenewise/domain/jobs.py` (`StageName`)). `enabled_stages` adds those stages only when their back ends are present (`src/scenewise/app/deps.py` (`enabled_stages`)). So none of them has a feature document yet.

## How it works: the map

### Features: the HTTP job API

- [Job Submission (POST /v1/jobs)](features/job-submission.md) (`job-submission`). A caller pushes one JSON job, and the request runs it to a terminal state before answering with the job's status. Covers admission, rejection, back-pressure (413/422/429/503) and the delivery use case.
- [Job Status (GET /v1/jobs/{job})](features/job-status.md) (`job-status`). Reads a job's durable record and reports it as running, waiting for a retry, or finished with a `result_uri`.
- [Job Results and Artifacts](features/job-results-and-artifacts.md) (`job-results-and-artifacts`). What a finished job leaves behind: `result.json` and, when one was produced, `audio.wav`, in an attempt-scoped `a{n}/` folder that the record's `result_uri` points to.

### Features: operations

- [Health Probes (/healthz, /readyz)](features/health-probes.md) (`health-probes`). Liveness (including the hung-job watchdog) and readiness, with the list of stages this instance can run.

### Features: the command line

- [CLI analyse Command](features/cli-analyse.md) (`cli-analyse`). `scenewise analyse FILE --out DIR` runs the requested stages in-process on one local file, writes `audio.wav` to `DIR` and prints the v1 result document. It keeps no job record.

### Features: analysis stages

- [Audio Stage](features/audio-stage.md) (`audio-stage`). Turns one audio or video input into a normalised 16 kHz mono `pcm_s16le` WAV and publishes it as `audio.wav`. `AudioSegments` / `AudioManifest` inputs are marked `reachable? ❌` there, as a deliberate scope cut.

### Concepts: architecture and wiring

- [Layering, Ports and the Composition Root](concepts/layering-and-ports.md) (`layering-and-ports`). The import layers that import-linter enforces, the `Protocol` ports in `src/scenewise/ports.py`, the `Dependencies` bundle, and `service.bootstrap` as the one place that picks adapters.
- [Configuration and Settings](concepts/configuration.md) (`configuration`). The frozen pydantic-settings `Settings` object read from `SCENEWISE_*` environment variables, its four groups (`media`, `inputs`, `service`, `log`), and where each entry point consumes it.
- [Logging](concepts/logging.md) (`logging`). structlog over stdlib logging into one stderr handler, context bound through `contextvars` (including the Cloud Tasks headers), and the D8 redaction rule.

### Concepts: jobs and execution

- [Job Lifecycle, Leases and Timing Invariants](concepts/job-lifecycle-and-timing.md) (`job-lifecycle-and-timing`). The durable job record, compare-and-swap writes, the static lease, `decide_attempt` / `handle_delivery`, and the time settings that keep retried deliveries safe.
- [Stages, Planning and Outcomes](concepts/stages-and-outcomes.md) (`stages-and-outcomes`). How requested stages are checked against what the deployment offers, ordered producer-before-consumer, run, and folded into `succeeded` or `partial`.
- [Error Model and HTTP Mapping](concepts/error-model.md) (`error-model`). The closed set of error categories and codes, and how the `service` layer turns each one into an HTTP status, a problem body, a failed stage, a failed record or a CLI exit code.

### Concepts: data, storage and media

- [The Versioned Wire Contract](concepts/wire-contract.md) (`wire-contract`). The Pydantic models in `src/scenewise/app/contract/` (request, record, status, result, problem, rejection), the lenient envelope, and the mapping to domain values.
- [Storage and URI Policy](concepts/storage-and-uri-policy.md) (`storage-and-uri-policy`). The `BlobStore` port, the separate input and output stores with their own root allow-lists, the fixed record and artifact paths, and `LocalBlobStore` (`file://`).
- [Media Processing with ffmpeg](concepts/media-processing.md) (`media-processing`). The `MediaTool` (ffmpeg/ffprobe subprocesses on local files only) and `ImageReader` (Pillow) ports: probe, WAV extraction and frame decoding.

## Where it's used

Use this map to find which documents to read first for a task:

| If you are changing… | Read first |
|---|---|
| The push endpoint, admission or back-pressure | [job-submission](features/job-submission.md), [job-lifecycle-and-timing](concepts/job-lifecycle-and-timing.md), [error-model](concepts/error-model.md) |
| A JSON document shape | [wire-contract](concepts/wire-contract.md), then the feature that emits that document |
| Where something is stored or which URIs are accepted | [storage-and-uri-policy](concepts/storage-and-uri-policy.md), [job-results-and-artifacts](features/job-results-and-artifacts.md) |
| A new stage | [stages-and-outcomes](concepts/stages-and-outcomes.md), [audio-stage](features/audio-stage.md) (the one wired example), [layering-and-ports](concepts/layering-and-ports.md) |
| ffmpeg / ffprobe behaviour | [media-processing](concepts/media-processing.md), [audio-stage](features/audio-stage.md) |
| A setting or an environment variable | [configuration](concepts/configuration.md) |

## Gotchas / constraints

### Link aliases

Some documents were written before the documents they link to existed, so their `Related` lines use slugs that no document has. The table below says which existing document covers each one. It is based on what each target document covers.

| Alias used in a `Related` line | Used by | Read instead |
|---|---|---|
| `[[job-delivery]]`, `[[job-delivery-and-records]]`, `[[job-record-and-fencing]]` | audio-stage, job-results-and-artifacts, job-submission | [job-lifecycle-and-timing](concepts/job-lifecycle-and-timing.md) |
| `[[http-push-jobs]]` | cli-analyse | [job-submission](features/job-submission.md) |
| `[[artifact-publishing]]`, `[[result-document]]` | audio-stage, cli-analyse | [job-results-and-artifacts](features/job-results-and-artifacts.md) |
| `[[input-blob-store]]`, `[[blob-store-input-output-split]]`, `[[blob-storage-and-uri-policy]]` | audio-stage, cli-analyse, job-results-and-artifacts | [storage-and-uri-policy](concepts/storage-and-uri-policy.md) |
| `[[media-tool-port]]` | audio-stage | [media-processing](concepts/media-processing.md) |
| `[[composition-root]]` | cli-analyse | [layering-and-ports](concepts/layering-and-ports.md) |
| `[[settings]]` | cli-analyse, job-submission | [configuration](concepts/configuration.md) |
| `[[error-categories]]` | cli-analyse | [error-model](concepts/error-model.md) |
| `[[wire-contract-v1]]` | job-results-and-artifacts | [wire-contract](concepts/wire-contract.md) |
| `[[captions-stage]]` | audio-stage | No document yet: the captions stage is not wired (`StageName` docstring). |

### Open `⚠️ unverified` items carried by the documents

- [health-probes](features/health-probes.md): the repository tracks no deployment manifest that declares the Cloud Run probes, so the real probe configuration belongs to the adopter. Whether probes take a request slot at `concurrency = max_jobs` (Q-19), and whether torch releases the GIL (Q-5), are open.
- [configuration](concepts/configuration.md): the environment format of `SCENEWISE_SERVICE__REQUIRED_STAGES` is assumed to be a JSON array. How pydantic-settings treats unknown prefixed variables for groups that are not built (for example `SCENEWISE_ASR__BACKEND`) was not tested.

### Flagged for human review

None. Every document in this catalog passed `docs-reviewer` within the fix cap, and no `sdlc-harness/docs_catalog/needs_review.md` was recorded for this run.

## Other documentation (not part of this catalog)

- [`docs/skeleton-notes.md`](skeleton-notes.md): where the repository skeleton departs from `ARCHITECTURE.md`, and gate configurations that did not work as documented.
- [`docs/decisions/initial-research.md`](decisions/initial-research.md): the initial research decisions.
- [`docs/research/`](research/): the research findings `q<N>-<topic>.md`, plus [`open-decisions.md`](research/open-decisions.md) and [`user-decisions.md`](research/user-decisions.md).
- `ARCHITECTURE.md` and `README.md` at the repository root: the design of record and the operator's guide.

## Anchor files

- `docs/features/job-submission.md`, `docs/features/job-status.md`, `docs/features/job-results-and-artifacts.md`, `docs/features/health-probes.md`, `docs/features/cli-analyse.md`, `docs/features/audio-stage.md`: the feature documents.
- `docs/concepts/layering-and-ports.md`, `docs/concepts/configuration.md`, `docs/concepts/logging.md`, `docs/concepts/job-lifecycle-and-timing.md`, `docs/concepts/stages-and-outcomes.md`, `docs/concepts/error-model.md`, `docs/concepts/wire-contract.md`, `docs/concepts/storage-and-uri-policy.md`, `docs/concepts/media-processing.md`: the concept documents.
- `src/scenewise/domain/jobs.py` (`StageName`): the declared stages, of which only `audio` is wired.
- `src/scenewise/app/deps.py` (`enabled_stages`): which stages a deployment offers.

## Related

- [[job-submission]] · [[job-status]] · [[job-results-and-artifacts]] · [[health-probes]] · [[cli-analyse]] · [[audio-stage]] · [[layering-and-ports]] · [[configuration]] · [[logging]] · [[job-lifecycle-and-timing]] · [[stages-and-outcomes]] · [[error-model]] · [[wire-contract]] · [[storage-and-uri-policy]] · [[media-processing]]
