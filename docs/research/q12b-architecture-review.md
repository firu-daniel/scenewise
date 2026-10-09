# q12b — Independent architecture review: clean architecture and idiomatic Python

**Status (2026-10-09).** Independent review, one of three (q12a, q12c are separate and were not read). Sources fetched
that day with WebFetch:

- **S1** — pcah, "python-clean-architecture" principles:
  https://github.com/pcah/python-clean-architecture/blob/master/docs/PRINCIPLES.md (read through the raw.githubusercontent.com fallback)
- **S2** — Google Python Style Guide: https://google.github.io/styleguide/pyguide.html
- **S3** — Sam Keen, "Clean Architecture Essentials: Transforming …" (Deep Engineering):
  https://deepengineering.net/p/clean-architecture-essentials-transforming

WebFetch returns a model-written digest of a page, not its raw text. Wording attributed to a source below is the
digest's, checked for consistency across fetches, and is not a verbatim quotation. Checked against `ARCHITECTURE.md`
§1–§5, §13, §14, §16, `docs/research/q8a-architecture-layout.md` (§1.5, §2, §11, §12),
`.claude/context/conventions.md`, `.claude/context/domain.md`, and every module under `src/scenewise/` in the working
tree as of this date, uncommitted changes included. `uv run --frozen lint-imports` reported 6 contracts kept and 0 broken,
`ruff check src` passed, and `mypy` reported no issues in 46 source files.

---

## Summary verdict

**Yes, this is sound clean architecture, and it is idiomatic modern Python.** It is not a textbook copy of the
Java-style version.

- The one rule that defines clean architecture is that dependencies point inward. scenewise has it, and a tool enforces
  it on every pull request: `pyproject.toml` `[tool.importlinter]` holds six contracts, and all six passed today.
  - `domain` imports only the standard library.
  - `ports` (the `typing.Protocol` interfaces) import only `domain`.
  - The use cases in `app` never import an adapter.
  - Only `service/bootstrap.py` wires the concrete adapters together.
  - Most projects that claim this architecture only describe the rule in prose. Few check it mechanically.
- Where scenewise departs from the sources, it departs toward Python practice, and it gives a reason each time. It uses
  `Protocol` instead of abstract base classes, plain functions instead of use-case classes, and a frozen dataclass
  bundle instead of a DI container. All three choices are recorded with their reasons in `ARCHITECTURE.md` §14 and q8a
  §2.2, and the reasons hold.
- **Constants placement and importing a module for one name do not break any architectural principle.** Clean
  architecture cares about which *layer* a module imports from, never about how many names it takes from it. In Python,
  `from x import NAME` executes the whole of `x` either way, and only once per process. The per-layer `constants.py`
  rule is a style choice. It is defensible, but it carries a small cohesion cost, covered under
  [Constants placement](#constants-placement).
- The code has a few real gaps, all small (see [Findings](#findings)):
  - One use case picks an HTTP status code. This is the only place the transport leaks inward.
  - The constants rule written today is already broken by one shared literal.
  - Use of `Final` is inconsistent.
  - One mutable module-level table remains.
  - The record path is composed in two layers.
  - A storage-format version is carried on a domain value.

  None of these threatens the design.

---

## Source reliability

### S1 — pcah PRINCIPLES.md

- **Right:** domain first; pure functions with inputs passed in (its exchange-rate example is the same move as
  scenewise passing `now` into `decide_attempt`); entities free of persistence and validation; the dependency rule;
  replaceable components behind contracts.
- **Dated or context-bound:** this is the manifesto of a framework that ships its own DI container and integrations
  ("Batteries Included"). It equates interfaces with abstract classes. It predates wide use of `typing.Protocol` in
  this sense. The repository was last pushed on 2021-08-15, and the file was last changed on 2021-07-31 (GitHub API).
  Its prescription that a DI container be passed to every constructor serves its own product, not general practice.
  It says nothing about dataclasses or modern typing.
- **Weight:** medium for the principles, low for the mechanisms (container, ABCs).

### S2 — Google Python Style Guide

- **Right, and matching PEP 8 or the Python docs:** absolute imports only; avoid mutable global state; `CAPS_WITH_UNDER`
  module-level constants are "permitted and encouraged"; no mutable default arguments; custom exceptions end in
  `Error`; no catch-all `except` except at isolation points; cheap, unsurprising properties; annotate public APIs;
  functions of about 40 lines or less.
- **Context-bound:** "import modules, not names". This is Google monorepo policy. PEP 8 permits `from x import y`, and
  S2 itself exempts `typing` and `collections.abc` and allows `from x import y as z` for generic names. The
  `if __name__ == "__main__"` rule in 3.17 is right for scripts. The Python docs (`__main__` — "Idiomatic usage") say
  the body of a package's `__main__.py` is typically not fenced. pytype and pylint are Google's tools; scenewise
  uses mypy and ruff for the same ends.
- **Read in full:** the page is 103,535 characters. The first fetch stopped at 100,000, and a second fetch at offset
  100,000 read the rest, through 3.19.14–3.19.16 and "Parting Words".
- **Weight:** high on the structural rules that PEP 8 shares; low on the import-style rule.

### S3 — Sam Keen, Clean Architecture with Python, chapter 1 (Packt, excerpted 2025-09-17)

- **Readability:** the whole chapter was readable, with no paywall and no truncation. Its figures are images. Figure
  1.2's layout is described in the text, and only that description was used here. Chapters 2, 3 and 8 are referenced
  but not included.
- **Right:**
  - the dependency rule;
  - architecture "in proportion" to project size, "a spectrum, not a binary choice";
  - wrapping stdlib I/O (`smtplib`) behind an abstraction;
  - tests that respect boundaries;
  - "excessive mocking signals architectural problems";
  - constructor injection without a framework.
  - It presents `Protocol` as a valid alternative to ABCs.
- **Context-bound:**
  - It uses the four-ring vocabulary (entities, use cases, interface adapters, frameworks) from Martin's 2012 diagram.
  - Its directory layout (`entities/`, `use_cases/`, `interfaces/`, `frameworks/`) is organised by ring, not by
    feature.
  - It prefers ABCs "because they are more common in existing codebases", which is a teaching choice, not a technical
    one.
  - It says nothing about constants.
- **Weight:** medium. It is a sound introduction, but it is an introduction.

### Where the sources disagree

- **Interfaces.** S1 calls for abstract classes. S3 accepts ABCs or Protocols and leans to ABCs. PEP 544 and the
  cosmicpython authors cited in q8a §2.1 favour structural typing for ports. Protocols are the better fit when the
  fakes and adapters have no reason to share code, because nothing should force them into an inheritance chain.
  scenewise's contract suites (`tests/contract/*_contract.py`) supply the behavioural guarantee that an ABC would not
  give anyway.
- **Dependency injection.** S1 wants a container. S3 wants plain constructor injection. S3 and cosmicpython ch. 13
  (q8a §2.1) are right for a project with two entry points.
- **Imports.** S2 alone asks for module-only imports. PEP 8 and S1/S3's own examples import names.

---

## Principle table

| Principle | Sources | scenewise | Verdict | Evidence |
|---|---|---|---|---|
| Dependencies point inward only | S1 §3, S3 "Dependency Rule"; agree. S2 silent | `service > (adapters \| app) > ports > domain`, exhaustive | follows | `pyproject.toml` contract "Layers: …" KEPT; `ARCHITECTURE.md` §3 |
| Domain independent of frameworks | S1 §1, §2c; S3 "Entities" | `domain` and `ports` are stdlib-only by allow-list | follows | contract "Domain and ports: stdlib only" KEPT; `src/scenewise/domain/*.py` imports only `dataclasses`, `enum`, `typing`, `re`, `math`, `types`, `collections.abc` |
| Interfaces as contracts | S1: abstract classes; S3: ABC or Protocol, prefers ABC; disagree | `typing.Protocol`, with the docstring as the contract and a mixin suite per port | deliberate departure (from S1/S3's ABC default); the reason holds | `src/scenewise/ports.py` `BlobStore`, `MediaTool` …; `ARCHITECTURE.md` §14 "ABCs for ports" left out; PEP 544 |
| Dependency injection | S1: explicit non-global container; S3: constructor injection; disagree | One composition root, `bootstrap.build_dependencies`, which returns a frozen `Dependencies` bundle; no container | deliberate departure from S1; follows S3; the reason holds | `src/scenewise/service/bootstrap.py`; `src/scenewise/app/deps.py` `Dependencies`; `ARCHITECTURE.md` §14 "DI container"; contract "Only the composition root imports adapters" KEPT |
| Pure functions, inputs passed in | S1 §2a | Time enters as data; pure state machine | follows | `src/scenewise/domain/jobs.py` `decide_attempt(record, request_digest, info)`, `wire_status(record, now)`; no `Clock` port (`ARCHITECTURE.md` §14) |
| Validation and mapping apart from entities | S1 §2c (criticises Django `ModelForm`) | Pydantic only at the edge; domain dataclasses check invariants and raise `ValueError` | follows | `src/scenewise/app/contract/mapping.py` `to_domain`; `src/scenewise/domain/time.py` `TimeSpan.__post_init__` |
| Four rings: wire format belongs to "interface adapters" | S3 | The wire contract sits in `app/contract/`, inside the use-case layer | deliberate departure; the reason holds | q8a §1.5 rule 5 "One wire contract": `app/publish.py` and `app/delivery.py` must write `result.json` and `status.json` without importing `service`; Pydantic is allow-listed for `app` only |
| Use cases do not know the delivery mechanism | S3 (rings), S1 §3 | Holds except in one place | **gap** (F1) | `src/scenewise/app/delivery.py` `handle_delivery` `case Conflict()` passes `status=HTTPStatus.CONFLICT` |
| Replaceable components | S1 §5; S3 benefits | New back end = new module + one `case` in `bootstrap` | follows | `ARCHITECTURE.md` §13 "Open/closed"; `src/scenewise/service/bootstrap.py` `_stores` |
| Architecture in proportion | S3 "spectrum"; S1 §2 KISS | "What do we get for this? And what does it cost us?" applied per construct | follows | `ARCHITECTURE.md` §14 table; q8a §2.2 |
| Tests respect boundaries; little mocking | S3 | In-memory fakes held to the same contract suite as adapters; `unittest.mock` never stands in for a port | follows | `tests/fakes.py`; `tests/contract/`; `.claude/context/conventions.md` § Testing bar |
| Imports: modules, not names | S2 §2.2 only; PEP 8 allows names | Names, absolute; a module import where the function name is generic (`mapping.to_domain`, `envelopes.parse`, `plan.ordered`) | deliberate departure from S2; matches PEP 8 | `ban-relative-imports = "all"`; `src/scenewise/service/http/push.py` imports |
| No relative imports | S2 §2.2; PEP 8 prefers absolute | Banned by ruff | follows | `pyproject.toml` `[tool.ruff.lint.flake8-tidy-imports]` |
| No mutable global state | S2 §2.5 | Rule stated; one table and the router are module-level and mutable | follows, with one small **gap** (F5) | `src/scenewise/service/http/push.py` `_TASK_HEADERS`; `.claude/context/conventions.md` § Code shape |
| Module-level `CAPS` constants | S2 §2.5, §3.16; PEP 8 "Constants" | Yes; `Final` used unevenly | follows, with a small **gap** (F4) | `src/scenewise/domain/constants.py`, `src/scenewise/app/constants.py`, `src/scenewise/ports.py` |
| Exceptions: built-ins, `Error` suffix, catch-all only at isolation points | S2 §2.4 | `ValueError` in domain; `ScenewiseError` tree; `except Exception` only where one stage, one job or one request is isolated | follows | `src/scenewise/domain/errors.py`; `src/scenewise/app/runner.py` `_run_stage`; `src/scenewise/app/delivery.py` `_run`; `src/scenewise/service/http/push.py` `_admitted`; `src/scenewise/service/http/routes.py` `get_job` |
| Nested functions only to close over a value | S2 §2.6 | One closure | follows | `src/scenewise/service/http/app.py` `create_app.lifespan` closes over `settings` |
| No mutable default arguments | S2 §2.12 | Defaults are immutable or frozen models; a `default_factory` where evaluation time matters | follows | `src/scenewise/service/config.py` `Settings.service` (`_default_state_prefix` reads `Path.cwd()` at construction) |
| Cheap, unsurprising properties | S2 §2.13 | Derived values only | follows | `TimeSpan.duration`, `ScenewiseError.retryable`, `ServiceSettings.lease_s`, `delivery._Delivery.uri` |
| Annotate public APIs | S2 §2.21, §3.19 | mypy `strict`; no explicit `Any` in `domain`, `app`, `ports`; PEP 695 aliases | follows (exceeds S2) | `pyproject.toml` `[tool.mypy]`, override `disallow_any_explicit` |
| `main()` and the `__main__` guard | S2 §3.17; Python docs say `__main__.py` is not fenced; disagree | `cli.main` returns an exit code; `__main__.py` is `raise SystemExit(main())` | follows the Python docs; S2 is written for scripts | `src/scenewise/__main__.py`; `src/scenewise/service/cli.py` `main` |
| Small functions (~40 lines) | S2 §3.18 | ruff `max-statements = 40`, complexity ≤ 8; the longest function is 41 physical lines | follows | `src/scenewise/app/delivery.py` `handle_delivery`, measured with `ast` |
| Exhaustive `match` ends in `assert_never` | project rule (no source) | Followed everywhere but one | **gap** (F2) | `src/scenewise/service/http/push.py` `_admitted` `match outcome` |
| Shared literals named once | project rule (2026-10-09) | Broken by `"application/json"` | **gap** (F3) | see F3 |

---

## Findings

### F1 — Medium: a use case chooses an HTTP status

**Evidence:**

- `src/scenewise/app/delivery.py` `handle_delivery`, branch `case Conflict()`, builds the rejection body itself with
  `mapping.rejection_json(..., status=HTTPStatus.CONFLICT, title="Job id already used")`.
- Every other choice of HTTP status is made in `src/scenewise/service/http/problems.py` `http_status`.
- `src/scenewise/service/http/push.py` `_rejected(job, error)` already renders exactly this kind of 200-plus-problem
  rejection from an error, using `http_status`.

So the mapping from error to status is split across two layers. `app` now knows that a job-id conflict is a 409, and
it does not learn this from the error type. The `HTTPStatus.CONFLICT` spelling was introduced in today's working-tree
change; the status had previously been the bare literal `409`, so the leak itself predates today. It also breaks the
project's own rule in `src/scenewise/domain/errors.py`, module docstring: "Leaf classes exist only where the HTTP
mapping differs". The mapping differs here (409, not 422), yet there is no leaf.

**Recommendation:**

1. Add `JobIdConflictError(InputError)` to `domain/errors.py`.
2. Map it to `HTTPStatus.CONFLICT` in `problems.http_status`.
3. Add a `Rejected(error: InputError)` variant to `DeliveryOutcome`, and have `handle_delivery` return it for
   `Conflict`.
4. Have `push._admitted` render it with the existing `_rejected`.

`app/delivery.py` then no longer imports `http`. The wire bytes are unchanged, because `_rejected` already answers 200
with the problem body. The match in step 4 is the one F2 asks to make exhaustive.

### F2 — Low: one `match` without `assert_never`

**Evidence:** `src/scenewise/service/http/push.py` `_admitted` ends with `match outcome:` over `Finished | TryLater`
and has no `case _: assert_never(outcome)`. `.claude/context/conventions.md` § Errors requires that arm. Every other
match over a union has it: `app/audio.py` `acquire_audio`, `app/delivery.py` `handle_delivery`, `app/contract/mapping.py`
`_audio` and `_stage_fields`, and `domain/jobs.py` `wire_status`. mypy would still report "Missing return statement" if
a third variant were added, so the risk is consistency, not a hidden bug.

**Recommendation:** add the arm. This becomes necessary if F1 adds a `Rejected` variant.

### F3 — Low: the constants rule written today is already broken by `"application/json"`

**Evidence:** the media type is used in four modules:

- named as public `JSON` in `src/scenewise/app/delivery.py`;
- inline in `src/scenewise/app/publish.py` `publish`;
- inline twice in `src/scenewise/service/http/push.py` (`_rejected`, `_admitted`);
- inline in `src/scenewise/service/http/routes.py` `get_job`.

`.claude/context/conventions.md` § Constants and configuration says that a constant used by more than one module lives
in the lowest layer's `constants.py`.

**Recommendation:** decide whether the rule covers standard protocol strings.

- If it does, add `JSON_MEDIA_TYPE: Final = "application/json"` to `src/scenewise/app/constants.py` and use it in all
  five places.
- If it does not, write the exemption into the rule ("a value fixed by an external standard — a media type, a header
  name — may stay inline"), and make `delivery.JSON` private.

The first option is cheaper than arguing about each new case.

### F4 — Low: `Final` is used unevenly on constants

**Evidence:**

- `src/scenewise/app/constants.py` `RECORD_SCHEMA_VERSION: Final` and `src/scenewise/domain/plan.py` `PREREQUISITES`,
  `_ORDER` use `Final`.
- `src/scenewise/domain/constants.py` (all four names), `src/scenewise/ports.py` `ABSENT_GENERATION`,
  `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`, and the module constants in adapters and `service` do not.

`grep -rn Final src` finds only those two files. PEP 591 `Final` is the only thing that makes mypy reject reassigning a
constant, whether at module level or through `import`; an UPPER_CASE name is only a convention.

**Recommendation:** annotate every constant in `constants.py` modules and in `ports.py` with `Final`, and state this in
§ Constants and configuration.

### F5 — Low: a mutable module-level table

**Evidence:** `src/scenewise/service/http/push.py` `_TASK_HEADERS` is a plain `dict`.
`.claude/context/conventions.md` § Code shape says "No mutable module-level state", and `.claude/context/domain.md`
makes tables `Final` with `MappingProxyType` (as in `domain/plan.py` `PREREQUISITES`).

**Recommendation:** use `_TASK_HEADERS: Final = MappingProxyType({...})`. `router = APIRouter()` in
`service/http/routes.py` is the FastAPI idiom: it is mutated only by decorators at import time. Leave it as it is.

### F6 — Low: the record path is composed in two layers

**Evidence:** `src/scenewise/app/delivery.py` `_Delivery.uri` and `src/scenewise/service/http/routes.py` `get_job` both
build `f"{job_prefix(...)}/status.json"`. `.claude/context/conventions.md` § Shared state documents this as current
practice but gives no reason for it. The storage layout is a use-case decision, and `service` should not re-derive it.

**Recommendation:** add `record_uri(state_prefix, job_id)` to `app/delivery.py` beside `job_prefix`, and call it from
both places. This is a function, not a constant: the path depends on arguments.

### F7 — Low: a storage-format version on a domain value, with two sources of truth

**Evidence:**

- `src/scenewise/domain/jobs.py` `JobRecord` has a `schema_version` field.
- `src/scenewise/app/delivery.py` `_attempt` fills it from `RECORD_SCHEMA_VERSION`.
- `src/scenewise/app/contract/mapping.py` `record_to_json` ignores it and writes `RECORD_SCHEMA_VERSION` again.
- `src/scenewise/app/contract/records.py` `JobRecordV1.schema_version` is `Literal["1"]`.

The version of `status.json` is a wire concern. `src/scenewise/domain/inputs.py`, module docstring, says wire names stay
in `app/contract`.

**Recommendation:** either drop `schema_version` from the domain `JobRecord`, letting `record_from_json` check it and
`record_to_json` stamp it, or have `record_to_json` write `record.schema_version`. The first option is cleaner. A
`Literal` cannot reference a constant (PEP 586), so the repeated `"1"` in `records.py` is unavoidable.

### Checked and not a gap

- **Wire `Literal`s that mirror domain enums can drift.** For the record direction, this is checked: a probe run under
  the project's mypy configuration showed that mypy types `JobState.value` as the union of its literal values and
  rejects it against a narrower `Literal`. `mapping.record_to_json` is therefore guarded. For the request direction,
  `StageName(s)` in `mapping.to_domain` fails safe, as `InputError("invalid_request")`.
- **`except Exception`.** Each use is an isolation point, which S2 §2.4 allows.

---

## Constants placement

**Short answer:** a per-layer `constants.py`, module-level names in the owning module, and a "class of constants" do
not differ in architectural correctness. The first two are both idiomatic Python. The third is not.

1. **Module-level `UPPER_CASE` names, annotated `Final`.** This is the Python default. PEP 8 ("Constants are usually
   defined on a module level"), S2 §2.5 ("permitted and encouraged") and PEP 591 all point here, and the standard
   library keeps constants beside their concept (`math.pi`, `os.sep`, `string.ascii_letters`). This is what scenewise
   does for single-module constants (`src/scenewise/adapters/media/ffmpeg.py` `PROBE_TIMEOUT_S`).
2. **A dedicated `constants.py` per layer.** Also an established pattern: CPython's `tkinter.constants`, Django's
   `django/db/models/constants.py`, and Home Assistant's `homeassistant/const.py`. It does not break clean architecture
   as long as each one sits in the lowest layer that needs it, and import-linter already enforces that
   (`domain/constants.py` is under the stdlib-only contract). Its costs are cohesion costs, and both are visible in
   today's change:
   - **A family split in two.** `MS_PER_SECOND` moved to `domain/constants.py`, while its siblings `_MS_PER_MINUTE`
     and `_MS_PER_HOUR` stay in `domain/time.py`.
   - **A rule separated from its validator.** `JOB_ID_PATTERN` now lives apart from `_JOB_ID` and `job_id()` in
     `domain/jobs.py`, and the `"."` / `".."` exclusion lives only in `job_id()`.

   A module named after a *kind* of thing also sits uneasily with q8a §1.4's naming rule, "Every helper is named after
   what it is about", which is the reason the project bans `utils.py`. The rule's own escape hatch, splitting into
   `constants/<topic>.py`, is the right guard against `constants.py` turning into `utils.py` by another name.
3. **A class of constants** (`class Limits: MAX = 5`). This is not adopted, and it should not be:
   - It is a namespace pretending to be a type.
   - mypy does not treat its attributes as `Final` unless each is annotated.
   - It can be instantiated and subclassed for no reason.
   - It adds a level of attribute lookup at every use.

   Where the set of values is closed and named, Python's answer is an `Enum`/`StrEnum`, which scenewise already uses
   (`StageName`, `SkipReason`, `JobState`, `plan.Needs`).

**Importing a module for one name.** This breaks nothing. `from scenewise.domain.jobs import JOB_ID_PATTERN` executes
`jobs.py` once, and every later import reuses it from `sys.modules`. The only real costs would be an import cycle,
import-time side effects, or a dependency on a higher layer. None applied here: `domain/jobs.py` has no side effects,
and `app/contract/records.py` may import `domain`. The maintainer's rule, that no caller imports a logic module only for
a constant, is a readability preference. It is a reasonable one, but it is not a principle.

**Recommendation:** keep the rule, but make one change. Allow a constant to stay in the module that *owns its concept*
when that module is the natural place for a reader to look: `JOB_ID_PATTERN` beside `job_id()`, and `MS_PER_SECOND`
beside `_MS_PER_HOUR` in `time.py`. Callers in other modules then import it from there. Reserve `constants.py` for
values with no owning module, such as `FIRST_ATTEMPT` (used by `jobs.py`, `records.py`, `delivery.py` and `cli.py`) and
`RECORD_SCHEMA_VERSION`. Whichever form is chosen, annotate with `Final` (F4). Contract constants stay in `ports.py`
(`ABSENT_GENERATION`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`), as the rule already says. They are part of the port's
contract, as the `BlobStore` and `MediaTool` docstrings show. This is a matter of taste. If the maintainer prefers the
uniformity of the current rule, that is also correct Python.

---

## Not adopted, and why

- **ABCs for ports (S1, S3's default).** `Protocol` (PEP 544) gives the same static check without forcing adapters and
  fakes into an inheritance tree. The contract suites provide the behavioural check that neither an ABC nor a Protocol
  gives (`ARCHITECTURE.md` §14; q8a §2.1).
- **A DI container passed to every constructor (S1 §4).** There are two entry points and one composition root.
  cosmicpython ch. 13 (q8a §2.1) and S3 both recommend manual injection at this size, and `svcs` is the recorded
  upgrade path (`ARCHITECTURE.md` §14).
- **S3's ring-named directories (`entities/`, `use_cases/`, `interfaces/`, `frameworks/`).** scenewise's
  `domain/ports/app/adapters/service` encode the same direction. They also separate the driving side (`service`) from
  the driven side (`adapters`), the hexagonal distinction q8a §2.1 cites from Cockburn. That is more informative than
  "interface adapters".
- **Moving the wire contract out to an interface-adapter layer (S3).** Use cases persist `status.json` and `result.json`
  themselves, and the notifier receives pre-serialised bytes. Moving the contract outward would force `app` to import
  `service`, or would duplicate the JSON shapes (q8a §1.5 rule 5).
- **S2's "import modules, not names".** This is a monorepo convention that PEP 8 does not share. The project already
  uses module imports where a name is generic (`mapping`, `envelopes`, `plan`), which is the case S2 itself carves out.
- **S2's `__main__` guard in `__main__.py`.** The Python docs advise against fencing a package's `__main__.py`.
  `src/scenewise/__main__.py` is correct as written.
- **Use-case classes (S3's `NotificationService`).** A stateless class with one method is a function (`ARCHITECTURE.md`
  §14). scenewise's `run_job`, `handle_delivery` and `publish` are functions taking their ports as keyword arguments,
  which is constructor injection without the constructor.
- **S1's "Batteries Included".** This is a framework's product goal, not an architectural principle.
- **Renaming `domain/jobs.py` `WireStatus` / `wire_status`.** The name mentions the wire, but the rule it holds (a
  running record whose lease has expired reads `retry_wait`) is pure and is tested in `domain`. `ARCHITECTURE.md` §2
  assigns it there, and `.claude/context/domain.md` § Closed sets records that its strings are wire strings. Moving it
  would gain nothing.
