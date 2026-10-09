# Q12 part C: independent architecture review

Status: independent review, 2026-10-09. Sources read that day: S1 https://github.com/pcah/python-clean-architecture/blob/master/docs/PRINCIPLES.md (read through its raw copy, https://raw.githubusercontent.com/pcah/python-clean-architecture/master/docs/PRINCIPLES.md); S2 https://google.github.io/styleguide/pyguide.html (read in two parts, the whole page); S3 https://deepengineering.net/p/clean-architecture-essentials-transforming.
Scope: the architecture and the structural Python idioms of `src/scenewise/` as of the working tree on `dev` (including today's uncommitted constants change), checked against `ARCHITECTURE.md` §1–§5, §13, §14, §16, `docs/research/q8a-architecture-layout.md`, `docs/research/q8b-tooling-gates.md` and `.claude/context/conventions.md`. Formatting is out of scope (ruff, `line-length = 88`). Every claim below names a file and a symbol; the code claims were confirmed with grep and with `uv run --frozen lint-imports` (6 contracts kept, 0 broken).

---

## 1. Summary verdict

**Yes: this is solid clean architecture, written in idiomatic modern Python.** The dependency rule is not just written down, it is machine-checked on every change, and the code obeys it. The domain is plain standard-library data and pure functions; the use cases depend on `typing.Protocol` ports, not on ffmpeg, Pillow or the file system; there is one composition root; and the project consistently refuses the Java-style ceremony (DI containers, abstract base classes for every interface, repository/unit-of-work, a class per use case) that the three sources partly recommend and that Python does not need.

For a Python newcomer, the two specific worries have short answers:

- **Constants placement does not break any principle.** Clean architecture only cares that a constant lives in a layer at or below every module that uses it, and that holds for every shared constant (§5). The per-layer `constants.py` is a legitimate, deliberate choice; it is not what Python's own standard library usually does (it keeps a constant next to the code that owns it), and it has one small cost in cohesion, but it is not wrong.
- **Importing a module "for one name" is fine.** Python loads a module once per process and caches it in `sys.modules`; a second `from x import NAME` costs a dictionary lookup. PEP 8 accepts `from module import name`. Google's guide (S2) says to import modules rather than names, but that is a namespace-readability rule for Google's monorepo, not a performance or layering rule, and scenewise sensibly does not follow it (§6).

The real gaps are small and sit in the details, not the structure: error codes are free-form strings that already disagree with their documentation, the wire `Literal`s that mirror domain enums have no parity test, the job-record path and status-read logic live partly in the HTTP layer, and the new constants rule is applied unevenly (a content-type literal in five places, `Final` in one constants module but not the other). None is a High. Details in §4.

---

## 2. Source reliability

### S1 — python-clean-architecture, `docs/PRINCIPLES.md`

**What it says.** Six principles: domain-first design; KISS (pure functions, self-contained classes, single responsibility — "entities should not depend on persistence or validation"); layered architecture with the dependency rule pointing inward; coupling management through a stateful, non-global DI container and interfaces written as abstract classes; depend on contracts so components can be re-implemented; and "batteries included" integrations.

**Right.** The dependency rule, pure functions with dependencies passed in, single responsibility, and depending on contracts are mainstream and agree with S3, cosmicpython (cited by q8a §2.1) and Brandon Rhodes' talk (q8a §2.1).

**Dated, wrong or context-bound.** The repository was last pushed on 2021-08-15 (GitHub API, read 2026-10-09), so it predates PEP 695 `type` aliases and most of the ecosystem's move to `Protocol`. "Interfaces (abstract classes)" is the pre-PEP-544 idiom. The DI container and "batteries included" are a pitch for the library itself, not general principles. "Entities should not depend on validation" is aimed at framework validation (Django's `ModelForm` is its example); read literally it contradicts the well-established practice of always-valid domain objects (Evans), which is what scenewise does in `__post_init__`. **Weight: low** — used only where S3 or Python practice independently agree.

### S2 — Google Python Style Guide

**What it says (structural parts).** §2.2 imports: "Use import statements for packages and modules only, not for individual types, classes, or functions", exempting `typing`, `collections.abc` and `typing_extensions`; no relative imports. §2.3: import by full package name. §2.4: built-in exceptions where they fit, custom ones end in `Error`, no `assert` for preconditions, never catch `Exception` except to re-raise or at an isolation point, small `try` blocks. §2.5: avoid mutable global state; "Module-level constants are permitted and encouraged", `CAPS_WITH_UNDER`, `_CAPS` when internal. §2.6: nest a function only to close over a value. §2.12: no mutable defaults. §2.13: properties only when needed, not as trivial getters. §2.21/§3.19: annotate public APIs, `X | None` explicitly, `TYPE_CHECKING` imports only in exceptional cases, typing-caused cycles are a smell. §3.16 naming. §3.17: logic in `main()` behind `if __name__ == '__main__'`. §3.18: prefer small functions, reconsider past about 40 lines. §4: "BE CONSISTENT".

**Right.** Almost all of it is sound, current and consistent with PEP 8 and the Python docs: the exception rules, mutable defaults, avoiding mutable globals, constants as module-level `UPPER_CASE` names, small functions, annotating public APIs.

**Context-bound.** The modules-only import rule exists for Google's monorepo, where a bare class name in a large file should reveal its origin; PEP 8 has no such rule, and FastAPI, Pydantic, Django and the standard library's own documentation routinely use `from x import Name`. The guide's type-checking advice targets pytype and Google's build system. The `if __name__ == '__main__'` rule is for scripts; the Python docs (`__main__` — "Top-level code environment") say the contents of a package's `__main__.py` are typically not fenced with that guard, so `src/scenewise/__main__.py` is idiomatic as it stands. **Weight: high** for exceptions, state, defaults, properties, function size and annotations; **low** for the import-form rule.

### S3 — Deep Engineering, "Clean Architecture Essentials"

**What I could read.** The fetch returned the article through its chapter summary and a "Further reading" list (Martin, Evans, Hunt and Thomas), followed by a book promotion and a "Subscribe" prompt; no paywall or truncation notice appeared. The page is a republished book chapter. The fetch tool returned a faithful summary rather than the verbatim text, so I cite its claims, not its wording, and nothing beyond what the summary covered.

**What it says.** Separation of concerns; "Screaming Architecture"; the four circles (entities, use cases, interface adapters, frameworks and drivers) with dependencies pointing inward; depend on abstractions; interfaces as ABCs **or** `typing.Protocol` (the book mainly uses ABCs because existing codebases do); type hints throughout; wrap standard-library calls such as `smtplib` behind abstractions; Python's import system makes everything reachable, so enforce the rules deliberately; dependency injection; scale the architecture to the project and adopt only patterns that add value (e.g. skip presenters in a small API); tests as first-class clients, with heavy mocking as a design smell.

**Right.** The dependency rule, enforcing it deliberately, pragmatism over completeness, and the testing advice are sound and match cosmicpython and q8a.

**Overreaching or context-bound.** "Wrap standard-library calls in abstractions" taken literally produces a port for every clock read and file read; cosmicpython's test ("What do we get for this? And what does it cost us?", quoted in `ARCHITECTURE.md` §14) is the better rule, and scenewise applies it. Preferring ABCs "because existing codebases do" is a reason of habit, not merit; PEP 544 exists precisely so that an adapter need not inherit from its interface. **Weight: medium.**

### Where the sources disagree

| Question | S1 | S2 | S3 | Who is right, and why |
|---|---|---|---|---|
| How to write an interface | Abstract classes | (silent) | ABCs mainly, `Protocol` acceptable | `Protocol` for a project like this: PEP 544 structural typing lets adapters and fakes satisfy a port without importing a base class, which keeps `adapters` and `tests/fakes.py` free of inheritance. ABCs win only when you want runtime enforcement of abstract methods, which mypy `--strict` already gives here. |
| DI container | Yes (stateful, non-global) | (silent) | DI, unspecified | Manual DI through one composition root (cosmicpython ch. 13, q8a §2.1). A container pays off with many entry points or deep dependency chains; scenewise has two entry points. |
| Validation in entities | Entities should not depend on validation | Exceptions for violated preconditions (§2.4, `ValueError`) | (silent) | S2 and DDD practice: a value object rejects invalid state in its constructor. S1's point is against framework validators inside entities, which scenewise also avoids (Pydantic stays in `app`). |
| Wrapping the standard library | (silent) | (silent) | Wrap calls like `smtplib` | Wrap what is slow, nondeterministic, external or has two implementations; pass simple facts such as "now" in as data. S3's example (`smtplib`, a network call) fits that rule; generalising it to all stdlib calls does not. |
| Import form | (silent) | Modules only | (silent) | PEP 8 permits both; choose one per codebase and be consistent. Not a clean-architecture question at all. |

---

## 3. Principle table

| Principle | Sources | scenewise | Verdict | Evidence |
|---|---|---|---|---|
| Dependency rule: source dependencies point inward | S1, S3 agree | `service > (adapters \| app) > ports > domain`, exhaustive | follows | `pyproject.toml` contract "Layers: service > (adapters \| app) > ports > domain"; `lint-imports` 6/6 kept |
| Enforce the rule deliberately (Python imports reach everything) | S3 | import-linter layers, independence, protected and allow-list contracts in CI | follows (stronger than the sources ask) | `pyproject.toml` `[tool.importlinter]`; `scripts/import_contracts.py` `AllowedExternalsContract`; `ARCHITECTURE.md` §16 |
| Domain independent of frameworks | S1, S3 | `domain` stdlib-only, frozen slotted dataclasses | follows | contract "Domain and ports: stdlib only"; `src/scenewise/domain/media.py` `Frame`; `src/scenewise/domain/jobs.py` `Job` |
| Ports owned by the inner side | S3 (interfaces in inner circle) | Ports in their own layer below `app` and `adapters`, above `domain` | deliberate departure (sound) | `src/scenewise/ports.py`; q8a §1.5. Classic clean architecture puts interfaces in the use-case circle; a separate `ports` layer lets `adapters` implement them without importing `app`, so `adapters` and `app` can be independent siblings. The interfaces still sit inward of their implementations, which is what the rule requires. |
| Interfaces as ABCs vs Protocols | S1: ABC; S3: ABC or Protocol | `typing.Protocol`, no ABC ports | deliberate departure from S1 (sound) | `src/scenewise/ports.py` `BlobStore`, `MediaTool`; `ARCHITECTURE.md` §14 "ABCs for ports" left out; PEP 544 |
| Interface segregation | S3 (implicit) | Small single-purpose ports; `ImageReader` separate from `MediaTool` | follows | `src/scenewise/ports.py` `ImageReader`, `TextGenerator` |
| Liskov / substitutability | S1 "open to reimplementation" | Behavioural contract in each port docstring; one contract mixin per port, run against fakes and adapters | follows | `tests/contract/imagereader_contract.py`; `tests/contract/test_imagereader_fake.py`, `tests/contract/test_imagereader_pillow.py`; `ARCHITECTURE.md` §13 |
| Dependency injection | S1 container; S3 DI | Manual DI: one composition root, a frozen `Dependencies` bundle | follows S3, deliberate departure from S1 (sound) | `src/scenewise/service/bootstrap.py` `build_dependencies`; `src/scenewise/app/deps.py` `Dependencies`; contract "Only the composition root imports adapters" |
| Use cases as orchestration | S3 | Plain functions over ports, not classes | follows (Pythonic form) | `src/scenewise/app/runner.py` `run_job`; `src/scenewise/app/delivery.py` `handle_delivery`; `ARCHITECTURE.md` §14 "a class whose only method is `run()` is a function" |
| Interface adapters translate data at the boundary | S3 | Wire ↔ domain only in `app/contract/` | follows, with one leak (F3) | `src/scenewise/app/contract/mapping.py` `to_domain`, `record_to_json`, `status_json` |
| Presenters | S3: optional in small APIs | `*_json()` functions act as presenters | follows | `src/scenewise/app/contract/mapping.py` `result_json` |
| Pure functions, I/O at the edge (functional core) | S1 2a; S3 | Domain pure; time passed in as data | follows | `src/scenewise/domain/jobs.py` `decide_attempt` takes `AttemptInfo.now`; `wire_status(record, now)` |
| Wrap standard-library calls | S3 | `subprocess` wrapped behind `MediaTool`; clock read directly in `app` and `service` | deliberate departure (sound) | `src/scenewise/adapters/media/ffmpeg.py` `_run`; `src/scenewise/app/delivery.py` `_terminal` calls `time.time()`; `ARCHITECTURE.md` §14 "a `Clock` port (time is passed in as data)" left out |
| Screaming architecture | S3 | Top level named by layer; modules inside named by business concept | deliberate departure (sound at this size) | `src/scenewise/domain/` (`speech.py`, `labels.py`, `plan.py`); q8a §1.4. Layer-first packages are what makes import-linter's `layers` contract possible. |
| Scale ceremony to the project | S3 | Explicit "line against ceremony" table and a left-out list | follows | `ARCHITECTURE.md` §14; q8a §2.2, §12 |
| Tests respect boundaries; heavy mocking is a smell | S3 | In-memory fakes held to the contract suite; `unittest.mock` never replaces a port that has a fake | follows | `tests/fakes.py` `fake_dependencies`; `.claude/context/conventions.md` "Testing bar" |
| Exceptions: custom names end in `Error`, catch-all only at isolation points | S2 §2.4 | `ScenewiseError` hierarchy; broad `except Exception` only at stage, delivery and request boundaries, each logged | follows | `src/scenewise/domain/errors.py`; `src/scenewise/app/runner.py` `_run_stage`; `src/scenewise/app/delivery.py` `_run`; `src/scenewise/service/http/push.py` `_admitted`; `src/scenewise/service/http/routes.py` `get_job` |
| Error codes as a closed vocabulary | (none directly; S2 §4 consistency) | Free-form `str`, vocabulary only in docstrings | gap (F1) | see F1 |
| Avoid mutable global state | S2 §2.5 | No mutable module state, one mutable-typed constant | follows, one nit (F7) | `src/scenewise/service/http/health.py` keeps the registry on the instance; `src/scenewise/service/http/push.py` `_TASK_HEADERS` |
| Module-level constants, `UPPER_CASE`, `_` when internal | S2 §2.5, §3.16; PEP 8 | Single-module constants are module-level names; shared ones in `<layer>/constants.py`; public/private naming mixed | follows, with unevenness (F5, F6) | `src/scenewise/adapters/media/ffmpeg.py` `PROBE_TIMEOUT_S`, `_STDERR_TAIL`; `src/scenewise/domain/constants.py`; §5 below |
| Import modules, not names | S2 §2.2 | Names imported directly, absolute imports only | deliberate departure (sound) | ruff `ban-relative-imports = "all"`; e.g. `src/scenewise/app/runner.py` `from scenewise.domain.jobs import Job, SkipReason, StageName`; §6 |
| No relative imports | S2 §2.2 | Enforced | follows | `pyproject.toml` `[tool.ruff.lint.flake8-tidy-imports]` |
| Nested functions only to close over a value | S2 §2.6 | One nested function, closing over `settings` | follows | `src/scenewise/service/http/app.py` `create_app` → `lifespan` |
| No mutable default arguments | S2 §2.12 | None found; defaults are `None`, tuples, frozensets or frozen models | follows | `src/scenewise/adapters/storage/local.py` `LocalBlobStore.__init__` `excluded=()`; `src/scenewise/service/config.py` `ServiceSettings.required_stages` |
| Properties only when necessary | S2 §2.13 | Computed values only, no trivial getters | follows | `src/scenewise/domain/time.py` `TimeSpan.duration`; `src/scenewise/domain/errors.py` `ScenewiseError.retryable`; `src/scenewise/service/config.py` `ServiceSettings.lease_s` |
| Annotate public APIs; `X \| None`; avoid `TYPE_CHECKING` | S2 §2.21, §3.19 | mypy `--strict`, no explicit `Any` in inner layers, no `TYPE_CHECKING` blocks | follows (stronger) | `ARCHITECTURE.md` §16 "Types"; grep finds no `TYPE_CHECKING` in `src` |
| `main()` and the `__main__` guard | S2 §3.17 | `main()` in the CLI; package `__main__.py` unguarded | follows (S2's guard rule does not apply to a package `__main__.py`) | `src/scenewise/service/cli.py` `main`; `src/scenewise/__main__.py` |
| Small functions | S2 §3.18 (~40 lines) | ruff statements ≤ 40, complexity ≤ 8, arguments ≤ 5 | follows (enforced) | `pyproject.toml` `[tool.ruff.lint.pylint]`, `[tool.ruff.lint.mccabe]` |
| Exhaustive `match` over unions | (project rule) | `assert_never` arm everywhere but one | gap, minor (F6) | `src/scenewise/service/http/push.py` `_admitted` |

---

## 4. Findings

Only real gaps. Severity: **Medium** = a defect class the gates cannot catch today and that touches the wire; **Low** = inconsistency or duplication with a cheap fix.

### F1 (Medium) — Error codes are free-form strings; their documented vocabulary has already drifted

**Evidence.** `ScenewiseError.__init__(code: str = "internal", …)` in `src/scenewise/domain/errors.py` takes any string. There are 45 `code="…"` literals across `src` (20 distinct codes, grep `code="[a-z_]+"`); `"unexpected"` appears 8 times and `"corrupt_media"` 6 times in different modules. The only list of valid codes is the class docstrings, and it is incomplete: `job_not_found` (`src/scenewise/service/http/routes.py` `get_job`) is missing from `InputError`'s docstring, `capacity_exceeded` (`src/scenewise/service/http/push.py` `push`) is not listed under `CapacityError` or `RetryableError`, `store_unavailable` (`src/scenewise/service/bootstrap.py` `_stores`) and `ffmpeg_unavailable` / `ffmpeg_too_old` (`src/scenewise/adapters/media/ffmpeg.py` `find_binaries`) are not listed under `ConfigurationError`, and the default `"internal"` is in no list. These codes reach callers in `ErrorInfoV1.code` and the RFC 9457 `code` member (`src/scenewise/app/contract/mapping.py` `problem`, `_stage_fields`), so a typo is a silent wire change. It also sits awkwardly with the project's own rule that "a literal that carries a meaning … is a named constant" (`.claude/context/conventions.md` "Constants and configuration").

**Recommendation.** Make the vocabulary a type, not a docstring: `type ErrorCode = Literal["invalid_request", "uri_not_allowed", …]` in `src/scenewise/domain/errors.py`, and annotate `code: ErrorCode` on `ScenewiseError.__init__` and `Failed.error_code`. mypy then rejects a misspelt code and the list cannot drift; the call sites keep their readable `code="corrupt_media"` form. A `Literal` fits better than a `StrEnum` here because the codes are strings on the wire and the call sites stay unchanged. Keep the per-class docstrings as the "which class carries which code" index.

### F2 (Medium) — Wire `Literal`s that mirror domain enums have no parity test

**Evidence.** `StageNameV1` in `src/scenewise/app/contract/requests.py` repeats the six values of `StageName` (`src/scenewise/domain/jobs.py`); `JobRecordV1.state` in `src/scenewise/app/contract/records.py` repeats `JobState`. Keeping the wire types separate is deliberate and right (`ARCHITECTURE.md` §5: the wire evolves apart from the domain), but nothing checks the two stay aligned: grep finds no test referencing `StageNameV1`, and `tests/unit/test_mapping.py` exercises single values only. If `JobState` gains a value, `record_to_json` fails Pydantic validation at the moment it writes a record (the pydantic mypy plugin does not type-check `BaseModel.__init__` arguments without `init_typed`, so mypy will not catch it). If `StageName` gains a stage, it is silently not requestable.

**Recommendation.** One unit test per pair: `assert set(get_args(StageNameV1.__value__)) == {s.value for s in StageName}` and the same for `JobRecordV1.model_fields["state"]` against `JobState`. Where the sets are meant to differ (a domain-only value), the test states the difference explicitly.

### F3 (Low) — The job-record location and the status read live partly in the HTTP layer

**Evidence.** The record path is composed twice, as `f"{job_prefix(...)}/status.json"`: in `src/scenewise/app/delivery.py` `_Delivery.uri` and in `src/scenewise/service/http/routes.py` `get_job`. `get_job` also does the use case itself: read the record through the store port, parse it with `mapping.record_from_json`, and render it with `mapping.status_json`. The service conventions record this as the observed pattern (`.claude/context/service.md`), but no reason is given for it, and it is the one place where knowledge of the store layout sits in a driving adapter. The `run-job` CLI path that `src/scenewise/service/cli.py` announces will need the same read.

**Recommendation.** Add `record_uri(state_prefix, job_id)` beside `job_prefix` in `src/scenewise/app/delivery.py` and use it in both places; optionally a small `job_status(job_id, *, store, state_prefix, now) -> bytes | None` use case in `app`, leaving `get_job` with HTTP concerns only (404, `Retry-After`, problem bodies).

### F4 (Low) — `RECORD_SCHEMA_VERSION` exists because of a redundant domain field, and is not the single source of the version

**Evidence.** `src/scenewise/app/constants.py` `RECORD_SCHEMA_VERSION` is "shared" by `src/scenewise/app/delivery.py` `_attempt` (which stores it in the domain `JobRecord.schema_version`) and `src/scenewise/app/contract/mapping.py` `record_to_json` (which ignores `record.schema_version` and writes the constant). No code in `src` reads `JobRecord.schema_version` after `record_from_json` fills it (grep `\.schema_version`). Meanwhile `JobRecordV1.schema_version` is typed `Literal["1"]` in `src/scenewise/app/contract/records.py`, a third copy, so bumping the constant alone would make every record write fail validation. A wire-format version is a contract detail; the domain record does not need it (`ARCHITECTURE.md` §5 keeps wire concerns in `app/contract`).

**Recommendation.** Drop `JobRecord.schema_version` from `src/scenewise/domain/jobs.py`, give `JobRecordV1.schema_version` the default `"1"` as `JobResultV1` and `JobStatusV1` already do (`src/scenewise/app/contract/results.py`), and delete `RECORD_SCHEMA_VERSION`. This is a good example of the constants rule masking a design smell: the constant was shared only because the same fact was written twice.

### F5 (Low) — The new constants rule is applied unevenly

**Evidence.**
- `"application/json"` appears as `JSON` in `src/scenewise/app/delivery.py` and as a bare literal in `src/scenewise/app/publish.py` `publish` (two `app` modules), and as a bare literal twice in `src/scenewise/service/http/push.py` and once in `src/scenewise/service/http/routes.py` (two `service` modules). `"audio/wav"` and `"status.json"` (F3) are bare too. By `.claude/context/conventions.md` "Constants and configuration", a constant used by more than one module belongs in that layer's `constants.py`.
- `Final` is used in `src/scenewise/app/constants.py` and `src/scenewise/domain/plan.py`, but not in `src/scenewise/domain/constants.py` or for `ABSENT_GENERATION`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS` in `src/scenewise/ports.py`. PEP 591 `Final` makes mypy reject a rebinding and keeps the literal type (which is what lets `RECORD_SCHEMA_VERSION` type-check against `Literal["1"]` today).
- Single-module constants mix public and private names with no rule: `PROBE_TIMEOUT_S` and `DEMUXERS` are public but used only inside `src/scenewise/adapters/media/ffmpeg.py`, next to private `_STDERR_TAIL`, `_FRAMES_PER_SEEK`. S2 §3.16 and PEP 8 say internal names take a leading underscore.

**Recommendation.** One media-type constant per layer (`JSON_MEDIA_TYPE` in `src/scenewise/app/constants.py`; the service layer either imports it upward or gets its own `src/scenewise/service/constants.py`, since `service` may import `app`). Annotate every constant in a constants module and in `ports.py` with `Final`. Underscore single-module constants unless a test or another module reads them (`.claude/context/conventions.md` already cites `PROBE_TIMEOUT_S` as the public example; update the rule rather than the code if the public form is intended).

### F6 (Low) — One `match` over a union lacks the `assert_never` arm

**Evidence.** `src/scenewise/service/http/push.py` `_admitted` matches `outcome` (`DeliveryOutcome = Finished | TryLater`) with no `case _: assert_never(outcome)`; every other union match in `src` has one (5 `assert_never` arms: `delivery.handle_delivery`, `audio.acquire_audio`, `mapping._audio`, `mapping._stage_fields`, `jobs.wire_status`). `.claude/context/conventions.md` "Errors" makes the arm a rule. mypy still treats this match as exhaustive today, so this is a consistency fix, not a live bug.

**Recommendation.** Add the arm.

### F7 (Low) — Two small code-level nits

- `src/scenewise/service/http/push.py` `_TASK_HEADERS` is a module-level `dict`. It is never mutated, but it is the only mutable-typed module constant in `src`, against "No mutable module-level state" (`.claude/context/conventions.md` "Code shape") and S2 §2.5. `src/scenewise/domain/plan.py` `PREREQUISITES` shows the house form: `Final[Mapping[…]] = MappingProxyType(…)`, or a tuple of pairs.
- `src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool.audio_track` concatenates parts with `joined.write(part.read_bytes())`, holding each whole segment in memory. Harmless for the single-file path the skeleton wires (it is skipped when `len(parts) == 1`), but segment stitching arrives with roadmap item 1; `shutil.copyfileobj` streams it.

---

## 5. Constants placement

**The question.** Is a per-layer `constants.py` (`src/scenewise/domain/constants.py`, `src/scenewise/app/constants.py`) better than module-level names in the owning module, or a class of constants?

**What clean architecture requires.** Only that a constant is defined in a layer at or below every module that reads it. Checked for every shared constant (grep of each name):

| Constant | Defined in | Read by | Rule holds |
|---|---|---|---|
| `JOB_ID_PATTERN` | `domain/constants.py` | `domain/jobs.py`, `app/contract/requests.py`, `app/contract/records.py` | yes |
| `FIRST_ATTEMPT` | `domain/constants.py` | `domain/jobs.py`, `app/delivery.py`, `app/contract/records.py`, `service/cli.py` | yes |
| `MS_PER_SECOND` | `domain/constants.py` | `domain/time.py`, `app/contract/mapping.py` | yes |
| `RGB24_BYTES_PER_PIXEL` | `domain/constants.py` | `domain/media.py`, `adapters/media/ffmpeg.py`, `tests/fakes.py` | yes |
| `RECORD_SCHEMA_VERSION` | `app/constants.py` | `app/delivery.py`, `app/contract/mapping.py` | yes (but see F4) |
| `ABSENT_GENERATION`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS` | `ports.py` | `app/delivery.py`, `adapters/storage/local.py`, `adapters/media/ffmpeg.py`, `tests/fakes.py` | yes; these are part of a port's behavioural contract, so `ports.py` is the right owner |

So placement breaks no layering principle, and `domain/constants.py` importing nothing removes any chance of an import cycle through a constant.

**What idiomatic Python usually does.** PEP 8 ("Constants are usually defined on a module level") and S2 §2.5 both mean "a module-level `UPPER_CASE` name", without saying *which* module. The standard library overwhelmingly keeps a constant in the module that owns its meaning (`logging.INFO`, `re.IGNORECASE`, `http.HTTPStatus`, `string.ascii_letters`), and readers import it from there. A shared `constants.py` is common in applications (Django apps, Home Assistant's `const.py`) and is not unidiomatic, but its known risk is becoming a grab-bag of unrelated values. Here the cohesion cost is visible: `JOB_ID_PATTERN` *defines* `JobId`, yet it now lives apart from `job_id()` in `domain/jobs.py`; `MS_PER_SECOND` belongs with `domain/time.py`.

**On the stated reason.** The rule says "a caller never imports a types or logic module only to reach a constant" (`.claude/context/conventions.md`, maintainer decision 2026-10-09). There is no runtime cost to avoid: importing `scenewise.domain.jobs` from `app` costs nothing extra, because every `app` module that runs already causes it to be loaded (and the layer rule allows it). The reason that does hold is organisational: one predictable place per layer to look, and no cycles. That is a legitimate preference; it is not a principle the sources or Python practice demand.

**A class of constants** (`class Limits: MAX = 5`) is the weakest option in Python. It is a Java habit (Java has no module-level names); in Python the module already is the namespace, a class adds an attribute lookup and invites instantiation or subclassing, and type checkers treat its attributes as mutable unless each is `Final`/`ClassVar`. Where values form a closed set, use a `StrEnum` or `Literal` (as F1 recommends for error codes); otherwise module-level names.

**Answer.** Keep the per-layer `constants.py`: it is consistent, enforced by review, harmless to the layering, and the topic-split rule (`<layer>/constants/` package) handles growth. Three refinements would make it fully idiomatic: annotate every entry `Final` (F5); use it only for values genuinely shared across modules, and resist moving a constant there when the "sharing" is a symptom of duplicated logic (F4); and prefer a closed type (`Literal`, `StrEnum`) over a list of string constants when the values form a vocabulary (F1). Single-module constants stay module-level, `_`-prefixed when internal.

---

## 6. Not adopted, and why

| Source recommendation | Why scenewise should not adopt it |
|---|---|
| S1: interfaces as abstract base classes | PEP 544 `Protocol` gives the same static checking without making adapters and fakes inherit from the port; `ARCHITECTURE.md` §14 and q8a §2.1 already reject ABC ports, and the contract suite supplies the behavioural check an ABC cannot. |
| S1: a stateful DI container | Two entry points and one composition root (`src/scenewise/service/bootstrap.py`); a container would add indirection with no wiring problem to solve. q8a §2.2 names `svcs` as the upgrade path if that changes. |
| S1: "batteries included" integrations | A pitch for the pcah library; scenewise's adapters are chosen per back end and kept behind optional extras (`ARCHITECTURE.md` §12). |
| S1: entities free of validation | Domain values that reject invalid state in `__post_init__` (`src/scenewise/domain/time.py` `TimeSpan`, `src/scenewise/domain/media.py` `Frame`) are the stronger design; framework validation stays at the edge, which is what S1 actually objects to. |
| S2 §2.2: import modules only, not names | PEP 8 allows `from module import Name`; the project's ruff isort setup and absolute-import ban already keep origins clear, and the layered package names (`scenewise.domain.jobs`) make every import's layer obvious. Switching would churn every file for a readability gain the gates already deliver. Being consistent (S2 §4) matters more than which form. |
| S2 §3.17: `if __name__ == '__main__'` guard | Does not apply to a package's `__main__.py` (Python docs, `__main__` module page); `src/scenewise/__main__.py` is idiomatic. |
| S2 §2.21: pytype | mypy `--strict` with the Pydantic plugin is the project's checker (`ARCHITECTURE.md` §16); the guide's pytype advice is Google-build-specific. |
| S3: wrap standard-library calls behind abstractions | Only where the cosmicpython cost test passes. `subprocess` is wrapped (`MediaTool`); the clock is passed as data into `domain` and read directly in the shell, so a `Clock` port would add a type and a fake for no test that needs it (`ARCHITECTURE.md` §14). |
| S3: screaming architecture at the top level | Layer-named top-level packages are what lets one import-linter `layers` contract enforce the dependency rule; the business vocabulary screams one level down (`domain/speech.py`, `domain/labels.py`, `app/stages.py`). Revisit only if the package grows features large enough to need their own layers. |
| S3: separate controller, presenter and gateway classes | Plain functions (`mapping.result_json`, `push.push`) do the job; S3 itself says to skip presenters in a small API. |
