# The Versioned Wire Contract

> One-line: the Pydantic models, the lenient envelope and the mapping functions that turn scenewise's JSON documents (request, job record, status, result, problem, rejection) into domain values and back. All of them live in `src/scenewise/app/contract/`.

## What it is & why

- Every JSON document scenewise reads or writes is defined once, as a Pydantic model in `src/scenewise/app/contract/`. Public models carry their schema version as a `V1` suffix: `JobRequestV1`, `JobRecordV1`, `JobResultV1`, `JobStatusV1`, `ProblemV1` and `RejectionV1`.
- The domain never sees a wire name. Domain types such as `Job`, `JobRecord` and `Analysis` are plain dataclasses, and the conversion in both directions happens only in this package (`src/scenewise/domain/inputs.py` module docstring; `.claude/context/conventions.md` `## Shared state, storage paths and the wire contract`).
- Use-case modules never build a wire document themselves. They call `src/scenewise/app/contract/mapping.py`: `publish`, `_Delivery.write`, `_Delivery.answer` and `job_status` in `src/scenewise/app/`, plus `service` for problems, rejections and the CLI result.
- Why have two models for one request? A request must be **keyed** (by `job_id`) and **fingerprinted** (by `request_digest`) before it is validated. Without that, an invalid body could not end in a terminal job record. So a lenient envelope is parsed first, and strict validation (`to_domain`) runs later, inside the claim.

## How it works

### Version marker
- `src/scenewise/app/constants.py` (`SchemaVersionV1`, `SCHEMA_VERSION_V1`): the alias `Literal["1"]` and the constant `"1"`. A `Literal[...]` cannot name a `Final` (PEP 586), so models type the field with the alias and stamp the constant.
- `src/scenewise/app/constants.py` (`JSON_MEDIA_TYPE`): `"application/json"`. It is the content type of every stored JSON blob (`status.json`, `result.json`) and of the 200 HTTP answers (`src/scenewise/app/delivery.py` `_Delivery.write`; `src/scenewise/app/publish.py` `publish`; `src/scenewise/service/http/push.py` `_rejected`, `_admitted`; `src/scenewise/service/http/routes.py` `get_job`).
- `schema_version` exists only on the wire. Requests and records require it. `JobResultV1` and `JobStatusV1` default it to `SCHEMA_VERSION_V1`. `record_to_json` stamps it and `record_from_json` validates it and then drops it, so the domain `JobRecord` has no such field (`src/scenewise/domain/jobs.py` `JobRecord`).

### Two model bases
- **Inputs:** `_Input` in `src/scenewise/app/contract/requests.py` is `extra="forbid", frozen=True`. A typo or a field from a newer version fails validation loudly.
- **Outputs:** `_Output` in `src/scenewise/app/contract/results.py` is `frozen=True` only. Outputs only grow within `schema_version` "1": later stages add fields and never remove them, and clients ignore unknown fields (module docstring).
- **Record:** `JobRecordV1` in `src/scenewise/app/contract/records.py` is `extra="forbid", frozen=True`. It is both written and read back by scenewise.
- A wire union is a `Literal` `kind` field plus `Field(discriminator="kind")` (`src/scenewise/app/contract/requests.py` `AudioInputV1`). Serialized names are the snake_case attribute names, with no `alias`.

### The documents
```
JobRequestV1   (requests.py; POST /v1/jobs body)
  schema_version: "1"   job_id: str (JOB_ID_PATTERN)   supersedes: str | None
  external_ref: {str: str} = {}   stages: [StageNameV1] (min 1)
  audio: AudioFileV1{kind:"file", uri, mime?} | NoAudioV1{kind:"none", reason} | None
  delivery: DeliveryV1{ notify: NoNotifyV1{kind:"none"}, artifacts: ArtifactSinkV1{uri_prefix?} }
StageNameV1 = "audio" | "captions" | "summary" | "chapters" | "moderation" | "labels"

JobRecordV1    (records.py; {state_prefix}/{job_id}/status.json)
  schema_version, scenewise_version, job_id, state: running|succeeded|partial|failed,
  attempt (>= FIRST_ATTEMPT), lease_until, request_digest, error_code?, result_uri?,
  updated_at, external_ref: {str: str} | None

JobStatusV1    (results.py; answer of POST /v1/jobs and GET /v1/jobs/{job})
  schema_version, scenewise_version, job_id,
  status: running|retry_wait|succeeded|partial|failed, attempt, error_code?, result_uri?,
  updated_at, external_ref?          -- lease_until and request_digest stay internal

JobResultV1    (results.py; {prefix}/a{attempt}/result.json)
  schema_version, scenewise_version, job_id, external_ref, status: succeeded|partial,
  media: ProbedMediaV1{duration_s, has_audio, has_video} | None,
  stages: StageResultsV1{ audio: AudioStageV1{status, reason?, error?: ErrorInfoV1, uri?} | None },
  timings_ms: {stage: int}, attempt

ProblemV1      (results.py; RFC 9457) type="about:blank", title, status, detail, code,
               category: input|retryable|internal|configuration, retryable
RejectionV1    (results.py) job_id, outcome: "rejected", problem: ProblemV1
```

### The envelope (pre-validation)
- `src/scenewise/app/contract/envelope.py` (`parse`) runs `json.loads` on the raw body and validates it against the private `_Envelope` (`extra="allow"`). It then checks `job_id` through the domain `job_id`. It returns `None` only when the body is not a JSON object or has no valid `job_id`. `push` answers that case with an `invalid_request` problem and writes no record (`src/scenewise/service/http/push.py` `push`).
- `Envelope` (frozen dataclass) carries `job_id: JobId`, `schema_version: str | None`, `external_ref` (sorted `(key, value)` tuples, or `None`) and `request_digest`.
- `_external_ref` validates the value against `_ExternalRef` (`strict=True`, `dict[str, str]`). Anything that is not a `str → str` map, including an absent field, becomes `None`. It is never an error at this point.
- `request_digest` is the sha256 of `json.dumps(document, sort_keys=True, separators=(",", ":"))`, with the default ASCII escaping, taken over the **parsed** body. Key order and whitespace therefore do not change it. A property test pins this (`tests/unit/test_envelope.py` `test_digest_ignores_key_order_and_whitespace`; `docs/skeleton-notes.md` G20).
- Consumers: `push` hands the `Envelope` to `handle_delivery` (`src/scenewise/app/delivery.py`). There, `job_id` keys the record URI, `request_digest` feeds `decide_attempt` (a different digest becomes `Conflict`, which becomes `job_id_conflict`), and `external_ref` is copied into the claim record (`_attempt`).

### The mapping (`src/scenewise/app/contract/mapping.py`)
Naming rule: `to_domain()` handles requests, and `*_json()` builds each emitted document, returning `bytes` from `model_dump_json(…).encode()`.
- `to_domain(raw)`: runs `JobRequestV1.model_validate_json` and builds the domain `Job` (stages become a `frozenset[StageName]`, `audio` goes through `_audio`, `external_ref` becomes sorted tuples, and `delivery.artifacts.uri_prefix` becomes `artifacts_prefix`). Every `ValidationError`, and every domain `ValueError`, becomes `InputError(code="invalid_request")`. The detail comes from `_validation_summary`, which keeps field paths and messages only (`include_input=False`) because input values may hold URIs. Its only caller is `_run` in `src/scenewise/app/delivery.py`, inside the claim. The CLI constructs its `Job` directly and does not go through `to_domain` (`src/scenewise/service/cli.py` `analyse`).
- `record_to_json(record)` / `record_from_json(data)`: the `status.json` round trip. A record that `JobRecordV1` cannot read raises `InternalError(code="invariant_violation", detail="unreadable job record")`. Callers: `_Delivery.write`, `handle_delivery` and `job_status`.
- `status_json(record, now)`: builds `JobStatusV1`. The `status` comes from `wire_status` in `src/scenewise/domain/jobs.py`: a `RUNNING` record whose lease has expired reads as `retry_wait`.
- `result_json(analysis, *, attempt, external_ref, audio_uri)`: builds `JobResultV1`, pretty-printed (`indent=2`). `_stage_fields` maps each `StageOutcome`. A failed stage puts its error code in `reason` and gets an `ErrorInfoV1` with `retryable=False`. `_media` maps `MediaInfo`. Callers: `publish` in `src/scenewise/app/publish.py`, and `src/scenewise/service/cli.py`, which passes `FIRST_ATTEMPT` and `external_ref=()`.
- `problem(error, *, status, title)`: returns a `ProblemV1` model rather than bytes. `src/scenewise/service/http/problems.py` (`problem_response`) serialises it as `application/problem+json`. `rejection_json` wraps it in `RejectionV1` for the HTTP 200 answer that `_rejected` in `src/scenewise/service/http/push.py` sends.

## Where it's used
- [[job-submission]]: the envelope, `to_domain`, `status_json` and `rejection_json` on `POST /v1/jobs`.
- [[job-status]]: `record_from_json` and `status_json` on `GET /v1/jobs/{job}`.
- [[job-results-and-artifacts]]: `result_json` and `JobResultV1` in `result.json`.
- [[cli-analyse]]: `result_json` prints the result document to stdout. The CLI builds its `Job` without a request document.
- [[audio-stage]]: `AudioFileV1` / `NoAudioV1` in, `AudioStageV1` out.
- [[error-model]]: `ProblemV1`, `RejectionV1` and `ErrorInfoV1` carry the domain error codes and categories.
- [[job-lifecycle-and-timing]]: `JobRecordV1` is the stored form of the record that every compare-and-swap writes.

## Gotchas / constraints
- **A wrong `schema_version` is a failed job, not a rejection.** The envelope accepts any `schema_version`, and `Envelope.schema_version` is read by nothing outside `envelope.py` and its tests. Strict validation happens in `to_domain`, inside the claim, so `"schema_version": "2"` ends as a terminal `failed` record with `error_code` `invalid_request` (`tests/unit/test_mapping.py` `test_to_domain_rejects`). The same applies to any other validation failure.
- **The digest covers the whole parsed body.** Re-sending the same `job_id` with any changed value (including `external_ref` or the stage order) produces `Conflict`, which is answered as a `job_id_conflict` rejection (`src/scenewise/domain/jobs.py` `decide_attempt`).
- **`external_ref` differs between documents when it is absent.** The envelope turns an absent or non-`str → str` value into `None`, so the record and the status carry `null`. `JobRequestV1` defaults it to `{}`, so `result.json` carries `{}`.
- **`JobRecordV1` is `extra="forbid"`.** A record written by a build that has added a field cannot be read by an older build: `record_from_json` raises `invariant_violation`. Unlike the output documents, the record cannot simply grow.
- **Error code strings are wire values.** They reach `ErrorInfoV1.code`, the problem `code` and the record's `error_code` unchanged, so renaming one is a wire-contract change (`src/scenewise/domain/errors.py` module docstring).
- **Wire literals mirror domain enums, and tests enforce it.** Five tests in `tests/unit/test_mapping.py` pin them: `test_wire_stage_names_mirror_the_domain`, `test_wire_record_states_mirror_the_domain`, `test_wire_statuses_mirror_the_domain`, `test_wire_error_categories_mirror_the_domain` and `test_wire_result_statuses_are_job_states`. Changing a `StageName`, `JobState`, `WireStatus` or `Category` value breaks them until the matching `Literal` changes too.
- **Fields arrive with the feature that reads them.** The request is deliberately a subset of the q1 contract: audio `file` / `none` only and notify `none` only. `JobResultV1` has no `failed` status, because a job that fails before its stages writes no `result.json` (`docs/skeleton-notes.md` A5). `supersedes` is validated but `to_domain` does not map it.
- **Not every document carries `schema_version`.** `ProblemV1`, `RejectionV1` and the nested models have none, and which documents must carry it is recorded as open (`.claude/context/app.md` `## Not determined`).
- **Adding a stage touches this package in four places:** `StageNameV1`, a field on `StageResultsV1` with its own `*StageV1` model, and a branch in `result_json` (`.claude/context/app.md` `## The set that accompanies a new unit here`).

## Anchor files
- `src/scenewise/app/constants.py` (`SCHEMA_VERSION_V1`) — the version alias and constant, and `JSON_MEDIA_TYPE`
- `src/scenewise/app/contract/requests.py` (`JobRequestV1`) — request models, `_Input`, `AudioInputV1`, `StageNameV1`
- `src/scenewise/app/contract/results.py` (`JobResultV1`) — output models: `JobStatusV1`, `ProblemV1`, `RejectionV1`, `ErrorInfoV1`, `StageResultsV1`
- `src/scenewise/app/contract/records.py` (`JobRecordV1`) — the stored form of `status.json`
- `src/scenewise/app/contract/envelope.py` (`parse`) — the lenient envelope, `request_digest`, `_external_ref`
- `src/scenewise/app/contract/mapping.py` (`to_domain`) — the wire ↔ domain conversion: `record_to_json`, `record_from_json`, `status_json`, `result_json`, `problem`, `rejection_json`
- `src/scenewise/domain/jobs.py` (`wire_status`) — the derived status, plus `JOB_ID_PATTERN` and `job_id`
- `src/scenewise/app/delivery.py` (`handle_delivery`) — consumes the envelope and writes the record through the mapping
- `src/scenewise/service/http/push.py` (`push`) — calls `parse` and renders rejections
- `src/scenewise/service/http/problems.py` (`problem_response`) — renders `ProblemV1` as `application/problem+json`
- `tests/unit/test_envelope.py` (`test_digest_ignores_key_order_and_whitespace`) — envelope leniency and the digest property
- `tests/unit/test_mapping.py` (`test_wire_statuses_mirror_the_domain`) — mapping behaviour and the wire/domain mirror tests

## Related
- [[job-submission]] · [[job-status]] · [[job-results-and-artifacts]] · [[cli-analyse]] · [[audio-stage]] · [[error-model]] · [[job-lifecycle-and-timing]] · [[stages-and-outcomes]] · [[layering-and-ports]] · [[logging]]
