# Stages, Planning and Outcomes

> One-line: how a job's requested stages are checked against what the deployment offers, run in producer-before-consumer order, and how each one ends as an `Outcome` that decides whether the job is `succeeded` or `partial`.

## What it is & why

- A **stage** is one unit of analysis a request can ask for. The closed set is `StageName`: `audio`, `captions`, `summary`, `chapters`, `moderation`, `labels`. The enum values are the wire names (`src/scenewise/domain/jobs.py` (`StageName`)). The wire `StageNameV1` literal mirrors it, and a unit test pins the two equal (`src/scenewise/app/contract/requests.py` (`StageNameV1`); `tests/unit/test_mapping.py` (`test_wire_stage_names_mirror_the_domain`)).
- `audio` is the only stage the skeleton wires. It publishes the normalised track. The other five arrive with roadmap items 1–4 (`StageName` docstring; `docs/skeleton-notes.md` A1).
- Per `ARCHITECTURE.md` §6, every stage gets its inputs through ports, transforms them with pure domain functions and returns domain data. Stage functions live in `src/scenewise/app/stages.py`. `src/scenewise/app/runner.py` composes them according to `src/scenewise/domain/plan.py`.
- The point of the design is **per-stage failure isolation**. A stage that fails marks the job `partial` instead of failing it, so the other stages' results still get published.

## How it works

### 1. What a deployment offers: `enabled_stages`
- `enabled_stages(speech, text, moderator, labeller)` works out the offered set from the back ends that are present (`src/scenewise/app/deps.py` (`enabled_stages`)):
  - `audio` is always offered, because it needs only the media tool.
  - `captions` needs `speech` (the `Speech` bundle: VAD, language ID and recogniser).
  - `summary` and `chapters` need `speech` **and** `text`.
  - `labels` needs `labeller`. `moderation` needs `labeller` **and** `moderator`.
- `build_dependencies` currently calls it with every back end `None`, so the offered set is `{audio}`. The result is stored on `Dependencies.enabled_stages` (`src/scenewise/service/bootstrap.py` (`build_dependencies`); `src/scenewise/app/deps.py` (`Dependencies`); `tests/e2e/test_bootstrap.py`).
- **Start-up check.** `ServiceSettings.required_stages` defaults to `frozenset({StageName.AUDIO})` (`src/scenewise/service/config.py` (`ServiceSettings`)). If any required stage is not offered, `build_dependencies` raises `ConfigurationError(code="stage_unavailable")` with the detail `required stages have no back end: …`, and the service refuses to start.
- `GET /readyz` reports the offered set as `{"status": "ready", "stages": [...]}`, sorted (`src/scenewise/service/http/routes.py` (`readyz`)).

### 2. From request to `JobSpec`
- On the wire, `JobRequestV1.stages` is a list of `StageNameV1` with `min_length=1` (`src/scenewise/app/contract/requests.py` (`JobRequestV1`)). `mapping.to_domain` turns it into `JobSpec(stages=frozenset(...))`, so duplicates collapse and the request's order is dropped (`src/scenewise/app/contract/mapping.py` (`to_domain`); `src/scenewise/domain/jobs.py` (`JobSpec`)).
- The CLI builds the same `JobSpec` from repeatable `--stage` flags. With no flag it defaults to `[StageName.AUDIO]` (`src/scenewise/service/cli.py` (`main`, `analyse`)).

### 3. Planning: `domain/plan.py`
- `ordered(stages)` returns the requested stages in **declaration order of `StageName`** (`_ORDER = tuple(StageName)`). Declaration order is therefore run order: producers come before their consumers, so a new stage must be declared after every stage it consumes (`src/scenewise/domain/plan.py` (`ordered`, `_ORDER`); `tests/unit/test_plan.py` (`test_ordered_puts_producers_first`)).
- `unavailable(requested, enabled)` returns the requested stages that are not in `enabled`, in run order (`unavailable`).
- `PREREQUISITES` maps every stage to the one input kind (`Needs`) it cannot run without:

  ```
  audio → AUDIO        captions → AUDIO
  summary → TRANSCRIPT chapters → TRANSCRIPT   (v1: speech-only, U14)
  moderation → VISUAL  labels → VISUAL
  ```

  It is a `MappingProxyType`, and `tests/unit/test_plan.py` (`test_every_stage_has_a_prerequisite`) requires an entry for every `StageName`. **Nothing outside `plan.py` and its test reads it yet.** The runner does not consult it.

### 4. Running: `run_job` and `_run_stage`
`run_job(job, deps, *, deadline)` in `src/scenewise/app/runner.py` (`run_job`):
1. **Gate.** If `plan.unavailable(job.spec.stages, deps.enabled_stages)` is non-empty, it raises `InputError(code="stage_unavailable", detail="not offered here: …")` before any input is touched. That error **fails the whole job** (`tests/unit/test_runner.py` (`test_stage_not_offered_fails_the_job`)).
2. **Acquire inputs.** `acquire_audio(job.audio, store=deps.inputs, media=deps.media, deadline=deadline)` is a context manager that yields `None` when the request has no audio input (`src/scenewise/app/audio.py` (`acquire_audio`)). Errors raised here are outside every stage, so they fail the job (`test_errors_before_the_stages_fail_the_job`).
3. **Loop** over `plan.ordered(job.spec.stages)`:
   - `remaining(deadline)` runs **before** each stage. Once the deadline has passed it raises `InternalError(code="deadline_exceeded")`. The call sits outside `_run_stage`, so a missed deadline fails the job and not just the stage (`remaining`; `test_deadline`).
   - `_run_stage(stage, acquired)` runs while `stage` is bound in the structlog context. The elapsed `time.monotonic()` seconds are recorded in `StageOutcome(stage, outcome, seconds)`.
   - Only the `audio` stage's bytes are kept, as `wav`.
4. The function returns `Analysis(job_id, media, outcomes, audio_wav)`. `media` is `None` when there was no audio input to probe (`src/scenewise/domain/results.py` (`Analysis`)).

`_run_stage` is the failure boundary for one stage (`src/scenewise/app/runner.py` (`_run_stage`); `ARCHITECTURE.md` §9):

| Raised inside the stage | Result |
|---|---|
| `RetryableError` | re-raised, so the **attempt** fails and the job is retried (`test_retryable_error_in_a_stage_fails_the_attempt`) |
| `InputError` (any `ScenewiseError` that is an input error) | `Failed(error_code=e.code, category="input", detail=e.detail)` |
| any other `ScenewiseError` | `Failed(..., category="internal")` |
| `ValueError` (a broken domain invariant) | `Failed(error_code="invariant_violation", category="internal", detail=str(e))` |
| any other `Exception` | `Failed(error_code="unexpected", category="internal")`, logged with a traceback |

- `_dispatch` matches on the stage name. `AUDIO` goes to `_audio_stage`. Any other stage that is enabled but not wired raises `InternalError(code="invariant_violation")`, which fails **that stage only** (`_dispatch`; `test_enabled_but_unwired_stage_fails_that_stage_only`).
- `_audio_stage` returns `Skipped(reason=SkipReason.NO_AUDIO_STREAM)` when there is no acquired audio or no track. Otherwise it returns `Succeeded()` plus the WAV bytes from `stages.audio` (`_audio_stage`; `src/scenewise/app/stages.py` (`audio`)). See [[audio-stage]].

### 5. Outcomes: `domain/results.py`
`type Outcome = Succeeded | Skipped | LanguageSkipped | Failed` (`src/scenewise/domain/results.py` (`Outcome`)):
- `Succeeded()` carries no data. The stage's result lives on `Analysis`.
- `Skipped(reason: SkipReasonGeneral)` means the stage had nothing to work on. `SkipReasonGeneral` is the `Literal` subset `not_requested`, `no_audio_stream`, `no_speech`, `dependency_failed`, `below_minimum`.
- `LanguageSkipped(reason, report: LanguageReport)` is for captions only. Its reason is `language_unsupported` or `language_unknown`, and it carries what the language gate saw (`src/scenewise/domain/speech.py` (`LanguageReport`)). Because the two reason subsets are disjoint, a language skip without its report fails mypy.
- `Failed(error_code, category: "input" | "internal", detail)` never has the category `retryable`, because a retryable error fails the attempt rather than the stage.
- `SkipReason` (`src/scenewise/domain/jobs.py` (`SkipReason`)) is the full enum. A new member goes into exactly one of the two `Literal` subsets (`.claude/context/domain.md` "Closed sets").

### 6. From outcomes to job state and wire
- `job_state(outcomes)` returns `PARTIAL` if any outcome is `Failed`, otherwise `SUCCEEDED`. **A skip is not a failure**, and an empty list counts as `SUCCEEDED` (`src/scenewise/domain/results.py` (`job_state`); `tests/unit/test_results.py`).
- `delivery._run` writes that state to the terminal job record. A `ScenewiseError` raised by `run_job` itself (the gate, input acquisition, the deadline) makes the record `FAILED` with the error's `error_code` (`src/scenewise/app/delivery.py` (`_run`)). See [[job-lifecycle-and-timing]].
- `mapping._stage_fields` maps each outcome to the wire `StageStatusV1` fields `(status, reason, error)` (`src/scenewise/app/contract/mapping.py` (`_stage_fields`); `src/scenewise/app/contract/results.py` (`StageStatusV1`)):
  - `Succeeded` → `("succeeded", None, None)`
  - `Skipped` / `LanguageSkipped` → `("skipped", reason.value, None)`. The `LanguageReport` is **not** put on the wire.
  - `Failed` → `("failed", code, ErrorInfoV1(code, category, retryable=False, message=detail or code, stage=<name>))`
- `result_json` currently fills only `StageResultsV1.audio`, the one field `StageResultsV1` has. `timings_ms` lists every outcome, keyed by stage value and rounded to whole milliseconds. `status` is `"partial"` or `"succeeded"` from `job_state` (`result_json`). See [[job-results-and-artifacts]].

## Where it's used
- [[job-submission]]: `POST /v1/jobs` runs `run_job` through `handle_delivery`, and `stage_unavailable` lands in the job record.
- [[cli-analyse]]: `--stage` builds the `JobSpec`, and the CLI calls `run_job` directly.
- [[audio-stage]]: the one wired stage and the only producer of `Skipped(no_audio_stream)`.
- [[job-results-and-artifacts]]: per-stage status, `timings_ms` and the `succeeded`/`partial` result.
- [[health-probes]]: `/readyz` reports `enabled_stages`.
- [[error-model]]: the stage-vs-job failure boundary and the two meanings of `stage_unavailable`.

## Gotchas / constraints
- **Dependent-stage skipping is not built.** `ARCHITECTURE.md` §6 says "a failed stage marks the job `partial`, and dependent stages are `skipped`". The runner neither reads `PREREQUISITES` nor emits `SkipReason.DEPENDENCY_FAILED`. Only the first half (failed → `partial`) is implemented.
- **Most skip reasons are unproduced.** No code under `src` outside `domain` constructs `not_requested`, `no_speech`, `dependency_failed`, `below_minimum`, `language_unsupported` or `language_unknown`. `no_audio_stream` is the only one that is emitted. These reasons are reserved for the stages on the roadmap.
- **Reordering `StageName` members changes run order.** It also changes the wire values if a member's value is edited, and renaming a value is a wire-contract change.
- **Request order is ignored.** Stages run in `StageName` order, whatever the order of `stages[]` in the request.
- **Offered vs. wired.** `enabled_stages` decides what a request may ask for, and `_dispatch` decides what actually runs. A stage that is enabled but has no `_dispatch` arm fails at run time with `invariant_violation` (an internal error, and the job becomes `partial`) instead of being rejected up front. Enable a back end only together with its `_dispatch` arm.
- **Two different `stage_unavailable` errors.** At start-up it is a `ConfigurationError` (`required_stages` not offered, so the process does not start). Per request it is an `InputError` (the request asked for a stage that is not offered, so the job is `failed`).
- The deadline is checked only between stages. A long stage can overrun it, and the watchdog grace covers that (see [[job-lifecycle-and-timing]]).
- The audio WAV is held in memory on `Analysis.audio_wav` (`docs/skeleton-notes.md` A2).

## Anchor files
- `src/scenewise/domain/jobs.py` (`StageName`, `SkipReason`, `JobSpec`): the stage vocabulary and the requested set
- `src/scenewise/domain/plan.py` (`ordered`, `unavailable`, `PREREQUISITES`, `Needs`): run order, the offered-set check and the prerequisite table
- `src/scenewise/domain/results.py` (`Outcome`, `StageOutcome`, `Analysis`, `job_state`): outcome variants and the succeeded/partial rule
- `src/scenewise/domain/speech.py` (`LanguageReport`): the payload of a language skip
- `src/scenewise/app/runner.py` (`run_job`, `_run_stage`, `_dispatch`, `_audio_stage`, `remaining`): composition and the per-stage failure boundary
- `src/scenewise/app/stages.py` (`audio`): the stage functions
- `src/scenewise/app/deps.py` (`enabled_stages`, `Dependencies`): the offered set derived from back ends
- `src/scenewise/service/bootstrap.py` (`build_dependencies`): the `required_stages` start-up check
- `src/scenewise/service/config.py` (`ServiceSettings`): `required_stages`
- `src/scenewise/app/contract/requests.py` (`StageNameV1`, `JobRequestV1`): wire stage names
- `src/scenewise/app/contract/mapping.py` (`to_domain`, `_stage_fields`, `result_json`): request → `JobSpec`, outcome → wire
- `src/scenewise/app/contract/results.py` (`StageStatusV1`, `StageResultsV1`): wire stage status
- `src/scenewise/app/delivery.py` (`_run`): job record state from `job_state`, or `FAILED`
- `src/scenewise/service/http/routes.py` (`readyz`): exposes the offered stages
- `tests/unit/test_plan.py`, `tests/unit/test_runner.py`, `tests/unit/test_results.py`, `tests/unit/test_deps.py`, `tests/e2e/test_bootstrap.py`: tests that pin this behaviour
- `ARCHITECTURE.md` §6 and `docs/skeleton-notes.md` A1–A3: the design of record and the skeleton's departures from it

## Related
- [[audio-stage]] · [[job-submission]] · [[cli-analyse]] · [[job-results-and-artifacts]] · [[health-probes]] · [[error-model]] · [[job-lifecycle-and-timing]] · [[wire-contract]] · [[layering-and-ports]] · [[configuration]]
