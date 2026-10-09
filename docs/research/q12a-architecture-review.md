# Q12 part A: independent architecture review against three external sources

Status: independent review, 2026-10-09. Sources, all read on 2026-10-09:
S1 https://github.com/pcah/python-clean-architecture/blob/master/docs/PRINCIPLES.md (read through its raw copy, https://raw.githubusercontent.com/pcah/python-clean-architecture/master/docs/PRINCIPLES.md);
S2 https://google.github.io/styleguide/pyguide.html;
S3 https://deepengineering.net/p/clean-architecture-essentials-transforming.
Scope: `ARCHITECTURE.md` §1–§5, §13, §14 and §16; `docs/research/q8a-architecture-layout.md` (with q8b for the gates);
`.claude/context/conventions.md`; and every module under `src/scenewise/`. Formatting is out of scope because ruff owns
it (`pyproject.toml`, `line-length = 88`). Checks run for this review: `uv run --frozen lint-imports` (6 contracts kept,
0 broken), `uv run --frozen mypy --config-file pyproject.toml src` (no issues in 46 files) and
`uv run --frozen ruff check --config pyproject.toml src` (all checks passed). Every code claim below was confirmed with
a grep over `src/`.

---

## 1. Summary verdict

**Yes, this is solid clean architecture, and it is idiomatic modern Python.** It does not copy Java-style clean
architecture. It applies the Python version of the same idea, from *Architecture Patterns with Python* (cosmicpython)
and PEP 544:

- **The dependency rule holds and a machine enforces it.** `service > (adapters | app) > ports > domain` is an
  import-linter `layers` contract, and the current tree keeps it. The domain is plain standard-library code: frozen
  dataclasses and pure functions such as `domain.jobs.decide_attempt`. It knows nothing about HTTP, Pydantic, ffmpeg
  or storage.
- **Interfaces are `typing.Protocol`s, not abstract base classes.** This is the better choice for a typed Python 3.12
  codebase. S1 and S3 lean towards ABCs; §3 explains why they are the weaker guide here.
- **There is no framework ceremony.** No DI container, no repository or unit of work, no class per use case. One
  composition root (`service/bootstrap.py` `build_dependencies`) wires everything. This is the "spectrum, not binary"
  stance that S3 itself recommends.

**On the two details you asked about.**

- **Constants placement.** Neither the per-layer `constants.py` rule nor module-level constants break any principle.
  Clean architecture only asks which way imports point, and a constant obeys that wherever it lives. Section 6 gives the
  details. The real issue is the reverse: a few values the code shares across modules are still repeated as literals,
  so the new rule is not yet applied everywhere (finding F3).
- **Importing a module for one name.** This breaks nothing either. `import m` and `from m import x` create the same
  dependency edge; import-linter sees them identically. PEP 8 accepts both. Google (S2) prefers importing modules, but
  for monorepo reasons that do not apply here. The code's habit is sensible: modules for verb-like functions
  (`mapping.result_json`, `plan.ordered`), names for types.

**The real problems are small, and they are in the code, not the design.**

- The `GET /v1/jobs/{id}` route does use-case work inside the HTTP layer (F1).
- `domain.jobs.JobRecord.schema_version` is a field that nothing reads back (F2).
- A few shared literals are duplicated (F3).
- Two convention rules are not applied at a handful of sites (F4, F5).

None of them is a layering violation that a gate misses in a dangerous way.

---

## 2. Source reliability

| Source | What it gets right | What is dated, wrong or context-bound | Weight given |
|---|---|---|---|
| **S1** pcah *python-clean-architecture* PRINCIPLES.md | Principles 1–3 are sound and well sourced (Evans, Martin): domain first, KISS with pure functions and side-effect-free value objects, single responsibility, and the dependency rule ("Nothing in an inner circle can know anything at all about something in an outer circle"). Principle 5, depending on a shared interface so that implementations can be replaced, is the port idea. | It is a framework pitch. Principle 4 (the library's own stateful DI container, "passed explicitly, usually as the only constructor argument"), principle 6 ("batteries included" integrations) and the ABC-as-interface advice serve that library. They are not general Python practice. A container passed as the only constructor argument is a service locator, which q8a §2.2 rejects for two entry points, and rightly so. Its view that entities should be free of "validation schemes" is about framework validation (Django `ModelForm`), not invariant checks; read literally, it would contradict Evans's own guidance that a value object enforces its invariants. | **Medium** for principles 1–3 and 5. **Low** for 4 and 6 and for the ABC advice. |
| **S2** Google Python Style Guide | Sound and widely shared: no relative imports (2.2); `Error` suffix and no `foo.FooError` stutter (2.4); catch-alls only at isolation points that log or record (2.4); no `assert` for preconditions (2.4); module-level constants "permitted and encouraged", in `UPPER_CASE` (2.5, 3.16); avoid mutable global state (2.5); nested functions only to close over a local value (2.6); no mutable defaults (2.12); properties only for cheap, attribute-like access (2.13); a `main()` function (3.17); about 40 lines per function as a prompt, not a limit (3.18); type annotations and `from __future__` imports encouraged (2.20, 2.21). | Context-bound to a Google monorepo checked by pytype, pylint and absl. Its rule to import "packages and modules only, not … individual types, classes, or functions" (2.2) exists for namespace clarity across a huge codebase. PEP 8, the standard library documentation and nearly every large open-source Python project (FastAPI, Pydantic, Django) import names freely, and mypy plus editors answer "where does this come from" anyway. "Never use `staticmethod`" (2.17) is a house rule that neither PEP 8 nor the Python documentation shares. It names pytype, while scenewise uses mypy `--strict`, which is stricter. It says nothing about dedicated constants modules, `typing.Final` or `Enum` beyond allowing `enum` and `dataclasses` (2.19). | **High** for exceptions, global state, defaults, naming and main. **Low** for the module-only import rule and the `staticmethod` ban. |
| **S3** Sam Keen, "Clean Architecture Essentials" (Packt chapter 1, 2025-09-17) | Readable in full, with no paywall cut: the chapter runs to its Summary and Further reading, followed by a book promotion. Its four figures are images, so I could read them only through their captions and the surrounding text. It describes the dependency rule and the four rings correctly. It is honest that clean architecture is "a spectrum, not a binary choice" and warns against over-engineering. It names the right Python pitfalls: calling `smtplib`-style libraries directly from use cases, "all imports are effectively public", and too much dynamism. It shows `typing.Protocol` as a valid alternative to ABCs, and treats tests as first-class clients. | It mainly uses ABCs "because they are more common in existing codebases", which is a teaching convenience, not a design argument. Its web-app layout (Figure 1.2, from the text) places "abstract repositories" in an outer `interfaces/` folder. If a use case imports from there, the inner ring depends outward, which is a known inconsistency in clean-architecture tutorials. Martin's own dependency inversion puts the abstraction with its consumer. It is an introductory chapter, so it shows no composition root, no error mapping and no boundary validation. | **Medium**: good on the concepts, weak on layout detail. |

**Cross-check.**

- **ABC versus Protocol.** S1 and S3 both prefer ABCs; S3 also allows Protocols. PEP 544, the `typing` documentation
  and cosmicpython (which uses ABCs "for didactic reasons" and mentions protocols as the alternative, q8a §2.1) side
  with Protocols for typed code. A Protocol is defined by its consumer, needs no inheritance, and is checked statically
  wherever an implementation is assigned to it. In scenewise that is `Dependencies(...)` in `bootstrap` and
  `_stores`' return type, which mypy `--strict` verifies. **scenewise is right.**
- **DI container versus composition root.** S1 builds its own container; S3 shows plain constructor injection.
  Cosmicpython ch. 13 says a container pays off only when dependencies chain or are needed in many places.
  **S3 and scenewise are right for a two-entry-point service.**

---

## 3. Principle table

| Principle | Sources (S1/S2/S3, with any disagreement) | scenewise | Verdict | Evidence |
|---|---|---|---|---|
| Dependency rule: imports point inward | S1 §3, S3 "What is Clean Architecture?"; no disagreement | `service > (adapters \| app) > ports > domain`; adapters and app are independent siblings | follows | `pyproject.toml` `[tool.importlinter]` contract "Layers: …", `exhaustive = true`; `lint-imports`: 6 kept, 0 broken |
| Interfaces owned by the inner side (dependency inversion) | S1 §4–5; S3 notifier example. S3's Figure 1.2 text puts abstract repositories in outer `interfaces/` | Ports sit in their own layer below `app`, so use cases depend on the abstraction and adapters implement it | follows (S3's layout is the weaker one) | `src/scenewise/ports.py` (`BlobStore`, `MediaTool`, …); `app/deps.py` `Dependencies` typed by ports |
| Interface mechanism | S1 ABCs; S3 ABCs mainly, Protocol allowed; S2 silent | `typing.Protocol`, structural, no inheritance; behavioural contract in the docstring plus one contract suite per port | deliberate departure from S1/S3; the reason holds | `ports.py` module docstring; `tests/contract/imagereader_contract.py` `ImageReaderContract`; `ARCHITECTURE.md` §14 "ABCs for ports" left out |
| Entities and values free of frameworks | S1 §2c; S3 entities ring | `domain` is stdlib-only, frozen slotted dataclasses; invariants checked in `__post_init__` with plain `ValueError` | follows (and S1's "no validation" read literally would be wrong) | `domain/time.py` `TimeSpan.__post_init__`; `domain/media.py` `Frame.__post_init__`; contract "Domain and ports: stdlib only" |
| Pure functions, functional core | S1 §2a (pass the exchange rate in, do not fetch it) | Time enters as data; the state machine is pure | follows | `domain/jobs.py` `decide_attempt(record, request_digest, info)`, `AttemptInfo.now`; `wire_status(record, now)` |
| Use cases at the centre, frameworks at the edge | S1 §3; S3 rings 2 and 4 | Use cases are plain functions in `app`; FastAPI only in `service/http` | follows, with gap F1 | `app/runner.py` `run_job`; `app/delivery.py` `handle_delivery`; `service/http/routes.py` `get_job` (F1) |
| Wire DTOs belong to the interface-adapter ring | S3 ring 3 (controllers, presenters, gateways); S1 §2c (mapping separate from entities) | The Pydantic wire contract lives in `app/contract/`, so `app` may import Pydantic | deliberate departure; the reason holds: `status.json` and `result.json` are read by callers straight from storage (`result_uri`), so their schema is the product contract, not a persistence detail | `ARCHITECTURE.md` §3 "One wire contract", §5 table; contract "Use cases: stdlib, pydantic and structlog only"; `app/contract/mapping.py` |
| Composition root, no container | S1 §4 own container; S3 constructor injection | One `build_dependencies(settings)`, `match` per back end, lazy adapter imports | deliberate departure from S1; the reason holds | `service/bootstrap.py` `build_dependencies`, `_stores`; contract "Only the composition root imports adapters"; `ARCHITECTURE.md` §14 |
| Avoid over-engineering | S3 "a spectrum"; S1 §2 KISS | Explicit ceremony table; no repository, unit of work, message bus or `Stage` class | follows | `ARCHITECTURE.md` §14; q8a §2.2, §12 |
| Screaming architecture | S3 | Top-level packages are layers, not features; features scream inside `domain` (speech, labels, moderation) | deliberate departure; the reason holds for one bounded context (cosmicpython layout) | `ARCHITECTURE.md` §2 tree; q8a §1.4 |
| Import modules, not names | S2 2.2; PEP 8 allows both | Mixed: modules for function namespaces (`mapping`, `plan`, `stages`, `logs`), names for types | deliberate departure from S2; S2 is the context-bound one | `service/http/push.py` `from scenewise.app.contract import mapping`; `app/runner.py` `from scenewise.domain import plan` |
| No relative imports | S2 2.2 | `ban-relative-imports = "all"` | follows | `pyproject.toml` `[tool.ruff.lint]` |
| Exceptions: `Error` suffix, built-ins for preconditions, catch-all only at isolation points | S2 2.4 | Four categories plus leaves; domain raises `ValueError`; `except Exception` only where the error is logged and recorded | follows; constructor style is gap F5 | `domain/errors.py`; `app/runner.py` `_run_stage`; `app/delivery.py` `_run`; `service/http/push.py` `_admitted`; `routes.py` `get_job` |
| No `assert` for logic | S2 2.4 | None in `src` (grep finds only `assert_never`) | follows | grep `^\s*assert ` over `src/` returns nothing |
| No mutable global state | S2 2.5 | The rule is written down; the watchdog registry lives on the app instance | follows, with nit F4 | `service/http/health.py` `Watchdog`; `.claude/context/conventions.md` "Code shape"; `push.py` `_TASK_HEADERS` (F4) |
| Module-level constants, `UPPER_CASE` | S2 2.5, 3.16; PEP 8 "Constants" | Yes, plus a per-layer `constants.py` for shared values | follows; rule partly unapplied (F3) | `domain/constants.py`; `app/constants.py`; `adapters/media/ffmpeg.py` `PROBE_TIMEOUT_S` |
| Nested functions only to close over locals | S2 2.6 | `lifespan` closes over `settings` | follows | `service/http/app.py` `create_app` |
| No mutable default arguments | S2 2.12 | Immutable defaults (`()`, `None`, `frozenset`) | follows | `adapters/storage/local.py` `LocalBlobStore.__init__(excluded=())`; `service/config.py` |
| Properties only for cheap attribute-like access | S2 2.13 | Cheap derived values only | follows | `domain/time.py` `TimeSpan.duration`; `domain/errors.py` `ScenewiseError.retryable`; `service/config.py` `ServiceSettings.lease_s` |
| Never `staticmethod` | S2 2.17 only | Two private static helpers | deliberate departure; S2's rule is a house rule, not adopted | `adapters/media/ffmpeg.py` `FfmpegMediaTool._media`; `adapters/storage/local.py` `LocalBlobStore._meta` |
| Type annotations everywhere | S2 2.21, 3.19; S3 "type hints throughout" | mypy `--strict` + `disallow_any_explicit` in core | follows (stricter than S2) | `ARCHITECTURE.md` §16 "Types"; mypy: no issues |
| `main()` entry point | S2 3.17 | `main(argv) -> int`; `__main__.py` raises `SystemExit(main())` | follows (the Python docs' `__main__` pattern) | `service/cli.py` `main`; `__main__.py` |
| Small functions | S2 3.18 (~40 lines, soft); S1 §2 | ruff: complexity ≤ 8, statements ≤ 40, arguments ≤ 5 | follows | `ARCHITECTURE.md` §16 "Complexity" |
| Exhaustive handling of closed sets | none of the sources; project rule | `match` ends in `assert_never` almost everywhere | gap F4 (one site) | `service/http/push.py` `_admitted` |
| Pure decision used by the shell | S1 §2a | An absent record bypasses `decide_attempt` | deliberate departure, `docs/skeleton-notes.md` A9; the reason is weak (see §5) | `app/delivery.py` `handle_delivery` "no record: decide_attempt would start the first attempt" |

---

## 4. Findings

Only real gaps. Severity: **Medium** means it is worth fixing before the next feature lands on that path; **Low** means
it can be fixed opportunistically.

### F1 (Medium): `GET /v1/jobs/{id}` is a use case implemented in the HTTP route

**Evidence.**

- `src/scenewise/service/http/routes.py` `get_job` validates the id (`job_id`), builds the record's storage path
  itself (`f"{job_prefix(...)}/status.json"`), reads the port directly (`state.deps.store.read(uri)`), parses the
  record (`mapping.record_from_json`) and maps it to a status (`mapping.status_json`).
- The same path rule exists a second time in `src/scenewise/app/delivery.py` `_Delivery.uri`.
- import-linter allows all of this, because `service` may import `ports` and `app`. But it is application knowledge
  (where the record lives and how it is read) sitting in the driving adapter. That is what S3's ring 3 and S1 §3 put on
  the other side of the use-case boundary.
- `.claude/context/conventions.md` "Storage paths" records the duplication as the current practice ("each reader or
  writer of the record composes its path as `job_prefix(...)` + `/status.json`"). That records it; it does not justify
  it.
- The cost shows up as soon as a GCS store or a record schema "2" lands: two layers must change in step.

**Recommendation.**

- Add one `app` function, for example `app.delivery.job_status(job: str, *, store: BlobStore, state_prefix: str,
  now: float) -> bytes | None`, plus one `record_uri(state_prefix, job_id)` helper that `_Delivery.uri` also uses.
- `get_job` then only maps "no such job" to 404 and errors to problem responses.
- Amend the "Storage paths" bullet in `.claude/context/conventions.md`.

### F2 (Low): `domain.jobs.JobRecord.schema_version` is a wire field in the domain that serialisation ignores

**Evidence.**

- `src/scenewise/domain/jobs.py` `JobRecord` carries `schema_version: str`. `app/delivery.py` `_attempt` fills it from
  `app.constants.RECORD_SCHEMA_VERSION`, and `app/contract/mapping.py` `record_from_json` fills it from the stored
  document.
- But `mapping.record_to_json` writes `RECORD_SCHEMA_VERSION`, not `record.schema_version`.
- grep finds no other reader outside `app/contract/`. The domain value is therefore never used, and a re-written record
  (`delivery._give_up`, `_release`, both via `dataclasses.replace`) would silently be relabelled with the current
  version.
- This is harmless while only `"1"` exists (`records.JobRecordV1.schema_version: Literal["1"]`), but it is the wrong
  place for the fact: schema versions are wire concerns, and `.claude/context/conventions.md` says "Domain class and
  field names carry no wire names".

**Recommendation.**

- Drop `schema_version` from `JobRecord` and let `mapping` own it in both directions.
- If a future migration needs to know the stored version, return it from `record_from_json` beside the record.

### F3 (Low): the new constants rule is not yet applied to values shared across modules

The maintainer's rule (`.claude/context/conventions.md` "Constants and configuration") says a constant used by more
than one module lives in the lowest layer's `constants.py`, and a meaningful literal is never inline. grep over `src/`
finds four values that break it:

| Value | Where it is repeated | Fix |
|---|---|---|
| `"application/json"` | `app/delivery.py` `JSON`; inline in `app/publish.py` `publish`; inline in `service/http/routes.py` `get_job`; inline twice in `service/http/push.py` (`_rejected`, `_admitted`) | Move it to `app/constants.py` (for example `JSON_MEDIA_TYPE`) and import it upward. |
| `"status.json"` | `app/delivery.py` `_Delivery.uri`; `service/http/routes.py` `get_job` | Solved by F1's `record_uri`. |
| `"audio.wav"` | `app/publish.py` `publish`; `service/cli.py` `analyse` | Move it to `app/constants.py`. `cli.analyse` also re-implements the artifact write that `ARCHITECTURE.md` §13 says the CLI does not do ("calls `run_job` and prints, without publishing"); either say so in `docs/skeleton-notes.md` or route it through one `app` helper. |
| Schema version `"1"` | `Literal["1"]` in `app/contract/requests.py` `JobRequestV1`, `records.py` `JobRecordV1`, and twice in `results.py` (`JobResultV1`, `JobStatusV1`); `app/constants.py` `RECORD_SCHEMA_VERSION` | A `Final` name cannot appear inside `Literal[...]` (PEP 586), so the constants module cannot remove this repetition. Use one type alias, `type SchemaVersionV1 = Literal["1"]`, in `app/contract/`, and use it in all four models. |

`Final` is also used unevenly: `app/constants.py` and `domain/plan.py` annotate with `typing.Final`, while
`domain/constants.py`, `ports.py` and `adapters/media/ffmpeg.py` do not. Without `Final`, mypy lets a constant be
reassigned. Annotate every module-level constant `Final` (PEP 591); the cost is nil.

### F4 (Low): two code-shape rules are not applied at one site each

- **Exhaustive `match`.** `src/scenewise/service/http/push.py` `_admitted` matches `outcome` (`Finished | TryLater`)
  with no `case _: assert_never(outcome)`. That breaks the rule in `.claude/context/conventions.md` "Errors", which every
  other union `match` follows (`app/delivery.py` `handle_delivery`, `app/audio.py` `acquire_audio`,
  `app/contract/mapping.py` `_audio`, `_stage_fields`, `domain/jobs.py` `wire_status`). mypy accepts the code today, but
  the arm is what turns a third `DeliveryOutcome` variant into a loud error. Add the arm.
- **Mutable module-level value.** `src/scenewise/service/http/push.py` `_TASK_HEADERS` is a plain `dict`. The
  convention says "No mutable module-level state", and `domain/plan.py` `PREREQUISITES` shows the house form:
  `Final[Mapping[...]] = MappingProxyType({...})`. Use that form, or a tuple of pairs.
- The module-level FastAPI `router` in `service/http/routes.py` is the framework's own idiom and is filled once, at
  import. It is not a finding.

### F5 (Low): `ScenewiseError.__init__` accepts positional arguments

`src/scenewise/domain/errors.py` `ScenewiseError.__init__(self, code="internal", detail="")` takes positional
parameters. Meanwhile:

- `.claude/context/conventions.md` "Errors" requires the keyword form `InternalError(code="…", detail=…)`.
- "Code shape" makes constructors keyword-only.
- ruff EM101 catches only a positional string literal.

grep finds no positional call in `src/` or `tests/`, so changing the signature to `(self, *, code: str = "internal",
detail: str = "")` costs nothing and makes the rule enforced instead of observed. The port docstrings
(`ports.py` `BlobStore`, `MediaTool`) write `InputError("uri_not_allowed")` as shorthand; reword them to the keyword
form at the same time.

---

## 5. Deliberate departures whose reason was judged

These are recorded choices, not findings. The reason holds for each, except the last, where it is weak.

- **The Pydantic wire contract in `app`** (`ARCHITECTURE.md` §3, §5). The reason holds: the stored record and
  `result.json` are documents that callers read, so their schema belongs to the application's contract, and one
  serialisation path (`app/contract/mapping.py`) is easier to keep honest than three. The allow-list contract stops
  `app` from importing anything else.
- **`wire_status` and `WireStatus` in `domain/jobs.py`.** The reason holds: the `retry_wait` rule is pure lease logic.
  The name leaks the word "wire", but `.claude/context/domain.md` documents that its strings are contract strings.
- **`StageNameV1` duplicating `StageName`'s values** (`app/contract/requests.py`). The reason holds: the wire and the
  domain may evolve apart, and the drift fails safe, because `mapping.to_domain` turns an unknown name into
  `InputError("invalid_request")`.
- **HTTP status inside `app`** (`app/delivery.py` uses `HTTPStatus.CONFLICT` for the rejection body). The reason holds:
  the RFC 9457 problem body is part of the wire contract, and the HTTP response code itself is still chosen in
  `service/http/problems.py` `http_status`.
- **An absent record skips `decide_attempt`** (`app/delivery.py` `handle_delivery`; `docs/skeleton-notes.md` A9). The
  reason is weak. "`decide_attempt(None, …)` is `Start(1)`, still unit-tested" explains why the shortcut is safe, not
  why it exists. The production path no longer runs the pure decision it unit-tests for that case. Calling
  `decide_attempt(None, …)` with `generation = ABSENT_GENERATION` would remove the duplicated rule at no cost. This is
  optional.
- **`from scenewise import __version__` in `app`** (`app/delivery.py`, `app/contract/mapping.py`). The root package is
  outside every import-linter layer, so this edge is unchecked. It is harmless while `src/scenewise/__init__.py` holds
  only `__version__`, which `ARCHITECTURE.md` §2 requires. Keep it that way.

---

## 6. Constants placement

**The direct answer: all three options are legitimate Python, none breaks clean architecture, and scenewise's rule is a
reasonable house choice.**

- **Why no option breaks the architecture.** The dependency rule constrains which modules import which. A constant
  obeys it as long as it lives at or below the lowest layer that uses it. That is exactly what the rule "the lowest
  layer that needs it, imported upward" in `.claude/context/conventions.md` says.
- **Module-level `UPPER_CASE` names in the module that owns the concept are the Python default.** PEP 8 says
  "Constants are usually defined on a module level"; S2 2.5 says module-level constants are "permitted and encouraged".
  The standard library does this almost everywhere (`math.pi`, `os.sep`, `string.ascii_letters`). scenewise uses it for
  single-module constants (`adapters/media/ffmpeg.py` `PROBE_TIMEOUT_S`, `app/delivery.py` `RETRY_AFTER_CONFLICT`,
  `service/cli.py` `EXIT_OK`).
- **A dedicated constants module is also standard Python when it is cohesive.** The standard library's `stat` and
  `errno` modules are exactly that. The per-layer `constants.py` has two real benefits:
  - It is a leaf module with no imports, so a constant can never cause an import cycle between sibling modules such as
    `domain/time.py` and `domain/media.py`.
  - It makes the shared values easy to find.

  Its known risk is the "grab-bag" module, whose items share only the fact that they are constants. It also separates a
  value from the type whose invariant it defines: `domain/constants.py` `JOB_ID_PATTERN` now lives apart from
  `domain/jobs.py` `job_id()`, which is what it validates. At 11 lines and three topics (jobs, time, media), that is
  fine. The rule already names the cure: split into the package `src/scenewise/<layer>/constants/` with one module per
  topic when it grows. A reasonable trigger is when a topic has more than a handful of names.
- **The rule "never import a types or logic module only to reach a constant"** comes from none of the three sources
  and from no PEP. It is a cohesion and cycle-avoidance preference, not a principle. Importing `domain.jobs` to reach
  `JOB_ID_PATTERN` would cost nothing measurable: a module is executed once per process, and the dependency edge is
  the same one `app/contract/mapping.py` already has. Keep the rule as a house convention if it helps you, but do not
  treat a breach as an architecture defect.
- **The contract constants in `ports.py`** (`ABSENT_GENERATION`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`) are correctly
  placed. They are part of the ports' behavioural contracts, which the `BlobStore` and `MediaTool` docstrings cite.
  Moving them away would split each contract in two.
- **A class of constants** (`class Limits: MAX = 5`) is a Java and C# habit. In Python the class adds nothing a module
  does not already give: it is not a type anyone instantiates, it does not stop reassignment, and it adds one more
  dotted level. Use instead:
  - a **module** for loose constants;
  - an **`Enum`/`StrEnum`** when the values form a closed set that code `match`es on (`domain/jobs.py` `StageName`,
    `JobState`, `SkipReason`, which is already the house practice);
  - a **frozen dataclass** when the values travel together as one argument (`domain/jobs.py` `AttemptInfo`,
    `app/delivery.py` `DeliveryPolicy`).

  S2 2.19 explicitly allows `enum` and `dataclasses`.
- **What to tighten.** Apply the rule to the literals listed in F3, and annotate every constant `Final` so mypy enforces
  the "constant" part.

---

## 7. Not adopted, and why

| Source advice | Why it is not adopted |
|---|---|
| S1 §4: a library DI container, passed as a component's only constructor argument | It is a service locator. With two entry points and one composition root, a frozen `Dependencies` dataclass gives the same decoupling, and mypy can check it. Cosmicpython ch. 13 and q8a §2.2 agree; `svcs` remains the documented upgrade path. |
| S1 §4, S3: abstract base classes as interfaces | `typing.Protocol` (PEP 544) is consumer-owned, needs no inheritance, and mypy `--strict` checks it where adapters are wired. Runtime enforcement is replaced by the contract suite per port. S3's own reason for ABCs, that they are "more common in existing codebases", does not apply to a new 3.12 codebase. |
| S1 §2c read literally: no validation in entities | Invariant checks in `__post_init__` with plain `ValueError` are domain logic (Evans), not a "validation scheme". Untrusted input is validated by Pydantic at the edge. Both kinds of check are needed, and scenewise has both. |
| S1 §6, "batteries included" | It describes a framework's product scope, not a design principle for an application. |
| S2 2.2: import modules only, never names | It is a monorepo readability rule. PEP 8 and common Python practice import names, and the dependency graph is the same either way. The code's mix (modules for function namespaces, names for types) reads well. Do not churn imports for it. |
| S2 2.17: never `staticmethod` | It is a house rule found in neither PEP 8 nor the Python documentation. The two private static helpers (`FfmpegMediaTool._media`, `LocalBlobStore._meta`) could become module functions, but nothing is gained by changing them. |
| S2 2.21: pytype | mypy `--strict` with `disallow_any_explicit` in the core is already stricter. |
| S3 Figure 1.2: abstract repositories in an outer `interfaces/` folder | Use cases would then depend outward. scenewise's `ports` layer below `app` is the correct dependency-inversion placement. |
| S3: screaming architecture at the top level | scenewise has one bounded context, so layer-first top-level packages, with feature-named modules inside `domain`, is the cosmicpython layout and keeps the import-linter contract to one line. Revisit only if the service grows a second bounded context. |
| A repository or unit of work for the job record (implied by S3's gateways) | The record is one compare-and-swap document behind `BlobStore`. A repository would wrap one read and one conditional write (q8a §12, `ARCHITECTURE.md` §14). F1's `job_status` / `record_uri` helpers are the right-sized fix for the one duplication found. |
