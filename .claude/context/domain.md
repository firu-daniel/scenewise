# Domain layer

> **Read this when:** the change adds or edits a value type, enum, error category or pure function under `src/scenewise/domain/` — job and attempt rules, media and time values, input and outcome unions, the stage plan. **Skip when:** the change only moves data across a boundary (wire models in `src/scenewise/app/contract/`, ports in `src/scenewise/ports.py`, adapters, the HTTP or CLI surface); read the document for that layer instead. [`conventions.md`](conventions.md) is read first in every case.

**Purpose.** What a domain implementer writes and a domain reviewer checks: stdlib-only values and pure functions that every other layer imports and none of whose rules depend on I/O.

## What the layer is

- `domain` holds values and pure functions: standard library only, no I/O (`src/scenewise/domain/__init__.py` module docstring; `ARCHITECTURE.md` §2). The stdlib-only allow-list, the layer order and `disallow_any_explicit` are owned by `.claude/context/conventions.md` § Dependency direction and § Code shape in every layer; their consequence here: a `domain` module imports only the stdlib and other `scenewise.domain` modules, never `scenewise.ports` or anything above it (`pyproject.toml` contracts "Layers: service > (adapters | app) > ports > domain" and "Domain and ports: stdlib only").
- Interpretation of model output and every speech and language-ID decision (VAD runs, cuts, LID windows, the language rule, segment merging) is pure `domain` code; an adapter only loads, runs and returns raw output (`ARCHITECTURE.md` §4, §13 "Functional core"; `src/scenewise/domain/speech.py` module docstring).
- Current time enters as an argument, never read inside `domain`: `decide_attempt` takes `AttemptInfo.now`, `wire_status` takes `now` (`src/scenewise/domain/jobs.py` `AttemptInfo`, `wire_status`; `ARCHITECTURE.md` §14, no `Clock` port).
- A value type joins `domain` with the stage or port that needs it, not ahead of it (`src/scenewise/domain/results.py` module docstring; `docs/skeleton-notes.md` A5 "Each field arrives with the feature that uses it"). A new module takes the name and responsibility `ARCHITECTURE.md` §2 assigns it in the `domain/` tree.

## Value types

- Every value is `@dataclass(frozen=True, slots=True, kw_only=True)` with tuple (or `frozenset`) collections — owned by `.claude/context/conventions.md` § Code shape in every layer; read off every dataclass in `src/scenewise/domain/`.
- Invariants are checked in `__post_init__` and raise plain `ValueError`, never a `ScenewiseError` (`ARCHITECTURE.md` §5; `src/scenewise/domain/time.py` `TimeSpan.__post_init__`, `src/scenewise/domain/media.py` `Rect.__post_init__`, `src/scenewise/domain/inputs.py` `AudioSegments.__post_init__`). The message is bound to `msg` and then raised (`msg = f"…"; raise ValueError(msg)`, ruff `EM101`/`EM102` under `select = ["ALL"]`). The translation of that `ValueError` belongs to the calling boundary (`.claude/context/conventions.md` § Errors).
- A domain `ValueError` message reaches callers: `mapping.to_domain` puts it in an `InputError` `detail`, and the runner puts it in `Failed.detail` as `invariant_violation` (`src/scenewise/app/contract/mapping.py` `to_domain`; `src/scenewise/app/runner.py` `_run_stage`). So it names the field, and the offending number or id where there is one, and never interpolates transcript text or a URI (`src/scenewise/domain/errors.py` module docstring, D8).
- A shared validation helper is a private module function (`src/scenewise/domain/media.py` `_check_positive`; `src/scenewise/domain/time.py` `_check_time`).
- A validated identifier is a `NewType` over a primitive with a validating constructor function, and the boundary builds it through that function, never by calling the `NewType` directly (`src/scenewise/domain/jobs.py` `JobId`, `job_id`; `src/scenewise/app/contract/mapping.py` `to_domain`; `src/scenewise/app/contract/envelope.py`).

## Closed sets: unions, enums and tables

- A closed set of shapes is a `type X = A | B | …` alias over frozen dataclasses, one dataclass per variant; a variant with no data is an empty dataclass, not `None` (`src/scenewise/domain/inputs.py` `AudioSource`, `NoAudio`; `src/scenewise/domain/jobs.py` `Decision`; `src/scenewise/domain/results.py` `Outcome`, `Succeeded`). Adding a variant follows `.claude/context/conventions.md` § "The set that accompanies a new unit" (input kind or outcome variant).
- Invalid outcomes are made unrepresentable with `Literal` subsets of an enum: `Skipped.reason` and `LanguageSkipped.reason` take disjoint subsets of `SkipReason`, so only a language skip carries a `LanguageReport` (`ARCHITECTURE.md` §5 "Invalid outcomes are unrepresentable"; `src/scenewise/domain/results.py` `SkipReasonGeneral`, `LanguageSkipped`). A new `SkipReason` member is added to exactly one of those subsets.
- A `match` over an enum or union in `domain` ends in `case _: assert_never(…)` (`.claude/context/conventions.md` § Errors; `src/scenewise/domain/jobs.py` `wire_status`).
- Enumerations are `StrEnum` (every enum under `src/scenewise/domain/`).
- The values of `StageName`, `SkipReason` and `JobState` reach the wire through `.value` in `src/scenewise/app/contract/mapping.py`; `StageName`'s docstring states its values are the wire names (`src/scenewise/domain/jobs.py` `StageName`; `src/scenewise/app/contract/mapping.py` `_stage_fields`, `record_to_json`, `result_json`). Renaming one of their member values is a wire-contract change; an enum whose values never leave `domain` (`src/scenewise/domain/plan.py` `Needs`) is not bound by this. The wire `Literal`s that mirror a domain closed set — `StageNameV1` and `StageName`, `JobRecordV1.state` and `JobState`, `StatusV1` and `WireStatus`, `ProblemV1.category` and `Category` — are pinned equal by unit tests, so a member added on one side fails until the other follows (`tests/unit/test_mapping.py` `test_wire_stage_names_mirror_the_domain`, `test_wire_record_states_mirror_the_domain`, `test_wire_statuses_mirror_the_domain`, `test_wire_error_categories_mirror_the_domain`).
- `WireStatus` is a `Literal`, not an enum, and its strings reach the wire as `wire_status`'s return value in `status_json` (`src/scenewise/domain/jobs.py` `WireStatus`, `wire_status`; `src/scenewise/app/contract/mapping.py` `status_json`). Changing one of its strings is a wire-contract change too. Class and field names carry no wire names (`src/scenewise/domain/inputs.py` module docstring).
- `StageName` declaration order is run order: `plan.ordered` iterates `tuple(StageName)`, producers before consumers. A new stage is declared after every stage it consumes (`src/scenewise/domain/plan.py` `_ORDER`, `ordered`).
- Every `StageName` has a `PREREQUISITES` entry; `tests/unit/test_plan.py` (`test_every_stage_has_a_prerequisite`) enforces it.
- Module-level tables are immutable: `Final` with `MappingProxyType` or a tuple (`src/scenewise/domain/plan.py` `PREREQUISITES`, `_ORDER`), following the no-mutable-module-state rule of `.claude/context/conventions.md` § Code shape in every layer.

## Time

- Positions and spans on the presentation timeline of the output media are `Seconds` (`NewType` over `float`) (`src/scenewise/domain/time.py` module docstring, `Seconds`).
- Presentation-timeline times are rounded to milliseconds in `vtt_timestamp` and nowhere else (`src/scenewise/domain/time.py` `vtt_timestamp` docstring; `ARCHITECTURE.md` §2 "the one millisecond-rounding point"). The rule covers timeline times only: stage processing durations are rounded to whole milliseconds on the wire as `timings_ms` (`src/scenewise/app/contract/mapping.py` `result_json`).
- Wall-clock instants and elapsed processing time are plain `float` — instants marked `# epoch seconds`, stage durations measured with `time.monotonic()` — while leases and waits are `Seconds` (`src/scenewise/domain/jobs.py` `JobRecord.lease_until`, `AttemptInfo.now`, `AttemptInfo.lease`, `InProgress.retry_after`; `src/scenewise/domain/results.py` `StageOutcome.seconds`; `src/scenewise/app/runner.py` `started = time.monotonic()`) — observed; see `## Not determined`.

## Errors

- `src/scenewise/domain/errors.py` owns the `ScenewiseError` hierarchy for the whole package; the rules for leaves and construction are in `.claude/context/conventions.md` § Errors. Here: a category is the `ClassVar[Category]` `category`, `retryable` derives from it, and a new error code whose HTTP mapping matches an existing class is a new member of that class's code alias (`InputCode`, `RetryableCode`, `InternalCode`, `ConfigurationCode`, or a leaf's own alias), not a new class; a leaf class exists only where the HTTP mapping differs, and it gets its own code alias and a narrowing `__init__`, its docstring naming its status class (`src/scenewise/domain/errors.py` module docstring "Leaf classes exist only where the HTTP mapping differs", `ScenewiseError`, `MediaTooLargeError`, `UnsupportedMediaError`, `JobIdConflictError`). The code vocabulary rule is owned by `.claude/context/conventions.md` § Errors.

## Constants

- A domain constant shared across modules lives in the module that owns its meaning, annotated `Final`: `JOB_ID_PATTERN` and `FIRST_ATTEMPT` in `src/scenewise/domain/jobs.py`, `MS_PER_SECOND` in `src/scenewise/domain/time.py`, `RGB24_BYTES_PER_PIXEL` in `src/scenewise/domain/media.py`. `domain` has no `constants.py`, since every shared domain constant has an owning module; placement is owned by `.claude/context/conventions.md` `## Constants and configuration`.
- Deployment-tunable values are settings, not `domain` constants; `domain` receives them as arguments (`AttemptInfo.max_attempts`, `AttemptInfo.lease`) (`.claude/context/conventions.md` § Constants and configuration; `src/scenewise/domain/jobs.py` `AttemptInfo`).

## Testing

- The testing bar (100% branch coverage of `domain` from `tests/unit` alone) is owned by `.claude/context/conventions.md` § Testing bar. Here: `domain` tests use no fakes — `domain` takes no ports (`tests/unit/test_time.py`, `tests/unit/test_plan.py`). A `domain` module's unit test file is named as `.claude/context/tests.md` § Naming states.

## Surfaces outside this layer

Wire models and field naming, storage paths, the job-record source of truth, logging and the commit-message policy are owned by `.claude/context/conventions.md`; `domain` has none of them. `domain` does not log (`structlog` is outside its allow-list, `pyproject.toml` "Domain and ports: stdlib only"). The UI-oriented surfaces (localization, theming, navigation, test attributes) do not exist in this project (`.claude/context/conventions.md` § Surfaces this project does not have).

## Example

> `src/scenewise/domain/results.py`: `Skipped.reason` is `SkipReasonGeneral`, a `Literal` subset of `SkipReason`, and `LanguageSkipped.reason` is `Literal[SkipReason.LANGUAGE_UNSUPPORTED, SkipReason.LANGUAGE_UNKNOWN]` with a required `report: LanguageReport`. A language skip without its report, or a generic skip carrying a language reason, fails mypy rather than a test. `src/scenewise/app/contract/mapping.py` (`_stage_fields`) then turns the `Outcome` union into wire fields with an exhaustive `match`.

_Provenance: existing mode. Read every module under `src/scenewise/domain/`; `ARCHITECTURE.md` §2, §4, §5, §8, §13, §14; `docs/skeleton-notes.md` A1–A5, A10; `README.md`; `pyproject.toml` (`[tool.importlinter]`, mypy overrides); the `domain` importers `src/scenewise/app/contract/mapping.py`, `src/scenewise/app/contract/envelope.py`, `src/scenewise/app/contract/records.py`, `src/scenewise/app/runner.py`, `src/scenewise/app/delivery.py`, `src/scenewise/adapters/media/ffmpeg.py`; `tests/unit/test_time.py`, `tests/unit/test_plan.py`, `tests/unit/test_media.py`; `.claude/context/conventions.md` as the vocabulary anchor. Revised on the review fix pass and the corpus fix pass._

## Not determined

- Whether `SkipReason` and `JobState` values are meant to be wire strings: `src/scenewise/app/contract/mapping.py` writes them through `.value`, but only `StageName`'s docstring says its values are the wire names, and `ARCHITECTURE.md` §5 says wire names stay in `app/contract`. A statement in `ARCHITECTURE.md` §5 settles it.
- Whether wall-clock instants and elapsed processing time should have their own type: `JobRecord.lease_until`, `JobRecord.updated_at` and `AttemptInfo.now` are plain `float` with an `# epoch seconds` comment, and `StageOutcome.seconds` (elapsed processing time) is plain `float`, while leases and waits use `Seconds`. Whether that split is intended is not stated anywhere. A maintainer statement or a `NewType` settles it.
