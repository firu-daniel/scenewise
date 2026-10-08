# Review r1 of `q8b-tooling-gates.md`

Reviewer: fresh review agent (did not write the file). Review date: **2026-10-08**.

Method:
- Re-read every cited source: the PyPI JSON API for all packages; the GitHub API for actions, tach, import-linter and runner-image READMEs; the Launchpad and Debian `debian/rules`; the HF model API; the coverage, ruff, import-linter, hypothesis, deptry, setup-uv, pyrefly and pydevtools pages; and the pytest and mypy changelogs (raw from GitHub).
- Rebuilt a skeleton (`domain / ports / app / adapters{fake,ffmpeg} / service`, a contract mixin, and the size script) in `scratchpad/q8b-review/sk`, using the doc's §8 `pyproject.toml` and §3 contracts verbatim. Ran ruff 0.16.10, mypy 2.4.0, import-linter 2.15 (also with seeded violations), pytest 9.1.1 + coverage, deptry, vulture, `uv audit`, `uv lock --check`, and zizmor 1.30.1 on the §9 workflow. Python 3.12.14, uv 0.12.21.

Severity scale: **wrong** / **unsupported** / **missing option** / **design concern** / **minor**.

Overall verdict: the research is unusually accurate on facts. Nearly every version, date, SHA and rule status checks out. The real problems are a few config defects that its own "ran clean" claims hide, and some places where the gate set is either easy for agents to game or tighter than it needs to be.

---

## Findings

### 1. `uv run mypy tests scripts` fails with the proposed config (wrong)
- **Claim (§8 notes, §10):** "Run mypy twice … `uv run mypy tests scripts` … [verified locally]"; "0 errors in src, tests, scripts".
- **What I found:** the config ignores `INP001` for `tests/**`, which implies `tests/` has no `__init__.py`. With that layout, and with contract suites imported as `tests.contract.*` (which the doc's own §6 pattern and `pythonpath = ["."]` require), mypy 2.4.0 aborts: `tests/contract/transcriber_contract.py: error: Source file found twice under different module names: "transcriber_contract" and "tests.contract.transcriber_contract"`. Reproduced in `sk/`.
- **Correction:** add `explicit_package_bases = true` and `mypy_path = ["src", "."]` to `[tool.mypy]` (verified to fix it), or commit `tests/__init__.py` and `tests/contract/__init__.py` and drop the `INP001` ignore. State which layout is assumed.

### 2. ruff isort treats `tests.*` as third-party, so the doc's own contract example fails I001 (wrong)
- **Claim (§8):** `src = ["src", "tests"]`, and everything "ran clean".
- **What I found:** `src = ["src","tests"]` makes modules *inside* `tests/` first-party, but not the package name `tests` itself. `from tests.contract.transcriber_contract import …` is therefore sorted as third-party, above `scenewise`. The §6 example `test_fake_transcriber.py` raises `I001` under ruff 0.16.10.
- **Correction:** use `[tool.ruff.lint.isort] known-first-party = ["scenewise", "tests"]` or `src = ["src", "."]`. Both verified clean.

### 3. The models job never triggers when the `run-model-tests` label is added (wrong)
- **Claim (§9):** `if: … contains(github.event.pull_request.labels.*.name, 'run-model-tests')`, with `on: pull_request:` and no `types`.
- **What the source says:** the default `pull_request` activity types are `opened`, `synchronize` and `reopened` (GitHub Actions "Events that trigger workflows"). `labeled` is not among them, so adding the label does nothing until the next push.
- **Correction:** `pull_request: { types: [opened, synchronize, reopened, labeled] }`. Alternatively, put models in a separate workflow triggered on `labeled` + `schedule` + `push`, so that labelling does not rerun the whole CI.

### 4. Test per-file ignores miss PLR0917/PLR0913, and fixture-heavy tests break the gate (design concern)
- **Claim (§2/§8):** `max-positional-args = 3`, `max-args = 5`. Tests ignore only `S101, D, ANN201, PLR2004, INP001`.
- **What I found:** ruff excludes `self` from the count but counts every pytest fixture parameter. A contract test such as `def test_x(self, transcriber, speech_wav, tmp_path, monkeypatch, capsys)` fails with `PLR0917 Too many positional arguments (5 > 3)`. With 6+ fixtures it also fails PLR0913. An adapter `__init__(self, model, device, compute_type, cache_dir)` also fails PLR0917 (4 > 3).
- **Correction:** add `PLR0913`, `PLR0917` and probably `ARG002` (fixtures requested only for their side effect), `FBT001` and `SLF001` to the `tests/**` ignores. For `src/`, `max-positional-args = 3` is defensible, but say explicitly that constructors must use `*,` keyword-only parameters.

### 5. vulture at `min_confidence = 80` mostly duplicates ruff (design concern)
- **Claim (§7/§8):** vulture 2.16, `min_confidence = 80`, "Protocol methods and pytest fixtures may need a whitelist file."
- **What the source says:** the vulture README (https://github.com/jendrikseipp/vulture, read 2026-10-08) assigns 100% to arguments and unreachable code, 90% to imports, and **60%** to attributes, classes, functions, methods, properties and variables. At 80, vulture reports only unused imports, arguments and unreachable code, which ruff's F401, ARG and F841 already cover. Unused functions and classes, the things vulture exists to find, are filtered out. The whitelist remark contradicts the threshold, because fixtures and Protocol methods are 60% findings and would never appear.
- **Correction:** either drop vulture (fewer gates for agents to satisfy), or run it at `min_confidence = 60` over `src` only with a committed `vulture_whitelist.py`. Dead public functions are a real risk in agent-written code, so the 60 + whitelist option is preferred.

### 6. No gate against gate suppression (`noqa`, `type: ignore`, `pragma: no cover`) (missing option, important for agents)
- **Claim:** the gate table assumes the gates bind.
- **What's missing:** agents meet failing gates by adding `# noqa: C901`, `# type: ignore[...]`, `# pragma: no cover` or new `per-file-ignores` entries. RUF100, PGH003/PGH004, `warn_unused_ignores` and `ignore-without-code` stop *unused* or *blanket* suppressions, but not justified-looking specific ones. The 100% core coverage target in particular can be met with `pragma: no cover`.
- **Correction:**
  - Add a tiny check, either in the size script or as a separate one, that fails on any `# pragma: no cover` / `# noqa` / `# type: ignore` under `src/scenewise/{domain,app}`, and enforces a small committed budget elsewhere.
  - Require a trailing reason on each suppression (e.g. `# noqa: S603 -- args are a static list`).
  - Protect `pyproject.toml` tool sections and the scripts with CODEOWNERS.

### 7. The layers contract lets adapters import use cases (design concern)
- **Claim (§3):** `layers = ["service", "adapters", "app", "ports", "domain"]`.
- **What the source says:** in a layers contract, higher layers may import lower ones (import-linter layers docs). Placing `adapters` above `app` therefore allows `scenewise.adapters.* -> scenewise.app.*`. In ports-and-adapters, driven adapters should depend only on ports and domain, and `service` (the composition root) is the only place that wires app and adapters.
- **Correction:** use `layers = ["service", "adapters | app", "ports", "domain"]`. The pipe makes them independent siblings, which the docs support. This forbids app→adapters (already caught) and adapters→app (currently allowed). I verified the rest of §3, including the seeded-violation output and the wildcard independence contract.

### 8. Hypothesis nightly profile and the CI profile interact (design concern)
- **Claim (§6):** the `ci` profile is auto-active when `CI` is set (`derandomize=True`, `deadline=None`, `print_blob=True`); register `nightly` with `max_examples=1000`.
- **What the source says:** correct as far as it goes (hypothesis API reference, read 2026-10-08). The `ci` profile also sets `database=None` and suppresses `HealthCheck.too_slow`. GitHub Actions always sets `CI=true`. A `nightly` profile derived from `ci`, or one that does not override `derandomize`, replays the same fixed examples every night and finds nothing new.
- **Correction:** register `nightly` with `parent=settings.get_profile("default")`, `derandomize=False` and `max_examples=1000`. Load it explicitly in the scheduled job (`--hypothesis-profile=nightly`). Neither the `schedule:` trigger nor `HF_HUB_OFFLINE=1` is actually wired in the §9 YAML; add both, or mark them TODO.

### 9. The 100% core coverage target is measured from the whole suite, not the unit tier (design concern)
- **Claim (§5/§9):** the `coverage report --include=domain,app --fail-under=100` step runs after `pytest --cov`, which also runs contract and e2e tests.
- **Assessment:** 100% line+branch on a small, pure domain and app with fakes is realistic, and it is a good showcase signal. However, e2e tests can execute app lines without asserting on them, which inflates the number. The include filter itself works [re-verified].
- **Correction:** either run the core report from a unit-only data file (`pytest tests/unit --cov … ; coverage report --include …`), or accept the current setup and say so. Combine this with finding 6 (no `pragma: no cover` in core). Consider a nightly advisory mutation-testing run (mutmut 3.8.0, 2026-09-12) on domain only, as the honest check behind "100%".

### 10. Complexity limits: mostly sensible, two are tighter than they need to be (design concern)
- **Claim (§2):** C901 ≤ 8, args ≤ 5, positional ≤ 3, branches ≤ 10, returns ≤ 4, statements ≤ 40.
- **Assessment for ML adapter code:**
  - C901 ≤ 8, statements ≤ 40, args ≤ 5 and branches ≤ 10 are realistic. Model wrappers split naturally into load / preprocess / infer / postprocess, and ruff's C901 does not count boolean operators.
  - `max-returns = 4` (default 6) mostly punishes mapping and guard-clause functions such as codec→container or exception→domain-error mapping. Agents will "fix" these with contortions or dict lookups that lose type narrowing.
  - `max-positional-args = 3` is fine for `src/` (see finding 4 for tests).
- **Correction:** keep `max-returns` at the default 6. Keep the others. Forbid raising limits through inline `noqa`, and allow it only by an explicit per-file config entry (see finding 6).

### 11. Module-size script: sound, but the 400-line count includes docstrings while the D rules require them everywhere (design concern)
- **Claim (§4):** `MAX_LINES = 400` physical lines including docstrings, enforced by a custom script.
- **Assessment:**
  - The script is correct and passes ruff ALL and mypy strict [re-verified].
  - `select = ALL` with the google convention requires a docstring on every public object (D1xx). Counting docstring lines against a 400 budget therefore pushes agents to write terse docs or split modules artificially. 400 lines of code-plus-docs is roughly 250–300 lines of code, which is tight for a model adapter.
  - CI runs the script on `src` only, while `main()` defaults to `src tests`.
  - A zero-code alternative the doc understates: `pylint --disable=all --enable=too-many-lines --max-module-lines=400 src` is a single command with no config file. The cost is pulling pylint/astroid into the dev group.
- **Correction:** keep the script (fine), but either raise the limit to 500 or count non-blank lines outside docstrings, and document which. Make the CI invocation match the decided roots.

### 12. uv itself is not pinned in CI (missing option)
- **Claim (§9):** setup-uv v10.2.0 SHA-pinned; uv 0.12.21 is the "pinned" version (header).
- **What the source says:** PyPI shows uv's latest as **0.12.23 (2026-10-03)**; 0.12.21 was 2026-09-29. Without a `version:` input, setup-uv installs the latest uv, so the "experimental" `uv audit` and `uv lock --check` behaviour can change under the gate.
- **Correction:** set `with: { version: "0.12.23" }` (or a `[tool.uv] required-version`) and bump it through Dependabot or Renovate along with the SHAs.

### 13. Missing cheap test-hygiene plugins (missing option)
- Adding these is not overkill for an agent-developed suite with subprocess e2e:
  - **pytest-timeout 2.4.0** (2025-05-05): an ffmpeg subprocess that hangs otherwise stalls CI until the 6 h job limit.
  - **pytest-randomly 5.0.0** (2026-09-01): agents often write order-dependent tests.
- pytest-xdist 3.8.0 is optional.
- **Correction:** add `pytest-timeout` with a global `timeout = 60` (the model tier can override it). Consider `pytest-randomly`.

### 14. ffmpeg install options (missing option, minor)
- **Claim (§9):** FedericoCarboni/setup-ffmpeg last released v3.1 on 2024-02-04, so use apt. Verified: noble ships `7:6.1.1-3ubuntu5` and resolute ships `7:8.0.1-3ubuntu2` (Launchpad), noble's `debian/rules` has `--enable-libflite`, and neither runner README lists ffmpeg.
- **What's missing:** **AnimMouse/setup-ffmpeg v1.2.5 (2026-06-11)** is a maintained action that was not considered. It probably lacks libflite, so apt remains the right pick, but `apt-get install ffmpeg` pulls a large dependency tree on every job.
- **Correction:** mention AnimMouse as an option that was considered and rejected because of flite. Optionally cache the apt archives, or install only in the e2e and model jobs (already the case).

### 15. tach ownership: the history is longer than stated (unsupported, minor)
- **Claim (§3, open question 7):** recent releases 0.35.1–0.35.3 (Sep–Oct 2026) by DetachHead; "no official handover announcement".
- **What the source says:**
  - GitHub API `repos/tach-org/tach/releases`: **v0.35.0 (2026-05-12)** was also published by DetachHead.
  - PyPI `dtach`: DetachHead earlier published a fork, **dtach** (0.30.2 on 2025-10-10 through 0.31.2 on 2025-11-07, homepage github.com/detachhead/dtach), which describes tach as unmaintained. The handover therefore went fork → takeover of the `tach-org` repo, not a quiet change in Sep 2026.
- **Correction:** restate it as "Gauge stopped maintaining tach around late 2025. DetachHead forked it (dtach) and has released tach from tach-org since 0.35.0 (May 2026)." This is irrelevant to the pick.

### 16. The test ignores and mypy strict on tests contradict each other (minor)
- **Claim (§8):** tests ignore `ANN201`, but mypy `--strict` also checks tests.
- **Assessment:** `disallow_untyped_defs` still requires `-> None` on every test, so the ruff ignore is a no-op that suggests tests may be unannotated.
- **Correction:** drop `ANN201` from the test ignores, or drop strict mypy on tests. Keeping strict typing on tests is better for a showcase.

### 17. ruff rule counts (minor)
- **Claim (§2):** 0.16.10 has "970 rules, 829 stable".
- **What I found:** `ruff rule --all` returns 971 entries. One is a code-less preview rule (`pytest-fixture-autouse`, preview since 0.16.5). The 829 non-preview entries include 17+ *Removed* rules (ANN101, PT004, UP038, …).
- **Correction:** "970 coded rules; 829 non-preview (including removed)". This is cosmetic.

### 18. The `lint.pylint` key list is incomplete (minor)
- **Claim (§2):** lists 10 `lint.pylint` keys "available in 0.16.10".
- **What I found:** `ruff config lint.pylint` also lists `allow-magic-value-types` and `allow-dunder-method-names`.
- **Correction:** add both, or say "limit keys".

### 19. pytest 9.0.0 date (minor)
- **Claim (§6):** "9.0.0 was released 2025-11-05". The header says dates come from PyPI.
- **What the source says:** the changelog says `pytest 9.0.0 (2025-11-05)`, but the PyPI files were uploaded **2025-11-08**.
- **Correction:** cite the changelog for this date, or use 2025-11-08.

### 20. `required-version` is not what makes the rule set reproducible (minor)
- **Claim (§0/§2):** "Pinning `required-version` means a ruff upgrade is an explicit PR."
- **Assessment:** `>=0.16.10,<0.17` allows patch upgrades. What actually pins the rule set is `ruff==0.16.10` in the dev group plus `uv.lock` + `UV_LOCKED`. The conclusion holds, but for that reason.
- **Correction:** reword, or set `required-version = "==0.16.10"`.

### 21. Redundant or implicit workflow details (minor)
- `uv sync --group dev` is redundant, because `dev` is a default group.
- The `audit` job runs on every PR. "Not required for merge" depends on branch-protection settings that are not stated; add `continue-on-error: true`, or document that it is not a required check.
- The matrix's default `fail-fast: true` hides failures on other Python versions; consider `fail-fast: false`.

### 22. Overkill check (design concern)
- **Worth keeping:** ruff ALL, mypy strict, import-linter, size script, coverage, deptry, typos and zizmor. Each is cheap, deterministic and unambiguous for an agent.
- **Overkill:**
  - **The pyrefly advisory job.** A second, non-gating checker produces a stream of findings that agents either ignore or "fix" in ways that fight mypy. Drop it from CI and keep it as an editor tool.
  - **vulture at 80** (finding 5).
- **The 3.12–3.14 matrix is appropriate,** because coverage's sysmon/ctrace default changes at 3.14.

---

## Claims verified correct

- **PyPI versions and dates (all exact):**
  - Type checkers: mypy 2.4.0 (2026-10-01, Stable), mypy 2.0.0 (2026-05-06); pyrefly 1.3.2 (2026-09-28, Stable), pyrefly 1.0.0 (2026-05-12); ty 0.0.85 (2026-10-06, Beta); pyright 1.1.414 (2026-09-10); basedpyright 1.40.2 (2026-10-04).
  - Lint and boundaries: ruff 0.16.10 (2026-10-01); import-linter 2.15 (2026-09-04, Stable); tach 0.35.3 (2026-10-06, Beta); pytestarch 4.0.1 (2025-08-08).
  - Tests and coverage: coverage 7.16.2 (2026-09-27); pytest-cov 7.1.0 (2026-03-21); pytest 9.1.1 (2026-06-19, Mature); hypothesis 6.168.5 (2026-10-05).
  - Other gates: deptry 0.25.1 (2026-03-18, Alpha); vulture 2.16 (2026-03-25); typos 1.51.1 (2026-10-06); codespell 2.4.3 (2026-07-15); pip-audit 2.10.1 (2026-06-10); zizmor 1.30.1 (2026-09-09).
  - Complexity: radon 6.0.1 (2023-03-26); xenon 0.9.3 (2024-10-21); wily 1.25.0 (2023-10-11); pylint 4.1.2 (2026-10-02); complexipy 8.0.1 (2026-09-07).
  - Hooks: prek 0.5.5 (2026-10-05); pre-commit 4.6.2 (2026-08-10); lefthook 2.2.0 (2026-10-07).
- **mypy 2.0 changelog:** local-partial-types and strict-bytes on by default, new `--allow-redefinition`, Python 3.9 targets dropped, experimental `-n/--num-workers`. The `--strict` flag list matches `mypy --help`. All ten extra error codes exist and are off by default.
- **pyrefly 1.0:** declared stable on 2026-05-12 with pydantic support. The pydevtools figures are accurate: page updated 2026-09-07, ~96% vs ~76% (July 2026), ty's gaps in generics, Protocols and aliases, and the basic preset without config.
- **ruff rules:**
  - PLC0302 is invalid ("a similar value exists: PLC3002").
  - C901, PLR0911/0912/0913/0915 are stable; PLR0917 is stable since 0.16.0.
  - PLR0904, PLR0914, PLR0916, PLR1702 and PLW0717 are preview.
  - All 7 DOC rules are preview.
  - CPY001 is stable since 0.16.0, so ignoring it is meaningful.
  - The formatter-conflict list matches the docs, including that ISC001 is not listed and ISC002 is listed conditionally.
- **The six ignores** are all valid codes and correctly reasoned.
- **TID251 / the banned-api config** is accepted.
- **import-linter:**
  - All four contracts run.
  - Seeded violations reproduce: not-listed `scenewise.utils`, adapters fake→ffmpeg, domain→pydantic.
  - The wildcard independence contract works.
  - The forbidden check passes with torch absent.
  - The contract types, `exhaustive` (containers only), `|` / `:` / `(optional)` syntax and the shared options (`unmatched_ignore_imports_alerting` default `error`, `broken_contract_guidance`) match the docs.
- **coverage:**
  - `core` defaults: ctrace up to 3.13, sysmon on 3.14+; sysmon has no branch coverage on 3.12/3.13.
  - `patch` was added in 7.10; `exclude_also` in 7.2.0; `fail_under` exits with 2; there is no per-package threshold.
  - The include-filtered report works, and pytest-cov honours `fail_under`.
- **pytest 9.0:** native `[tool.pytest]` (not combinable with `ini_options`); `strict` enables the four options listed, with the pinning advice; Python 3.9 dropped. The proposed `[tool.pytest]` config runs with `strict` and `filterwarnings=error`, and the contract-mixin pattern works.
- **uv:** `uv lock --check` exists. `uv audit` prints the experimental warning, and `--preview-features audit-command` silences it.
- **GitHub Actions:**
  - Latest releases: setup-uv v10.2.0 (2026-09-21), checkout v7.0.1 (2026-07-20), cache v6.1.0 (2026-06-26). All three SHAs resolve to those tags.
  - setup-uv `enable-cache` defaults to `auto`, the `cache-dependency-glob` defaults include `pyproject.toml` and `uv.lock`, and `python-version` sets `UV_PYTHON`.
  - FedericoCarboni v3.1 is dated 2024-02-04.
  - The ubuntu-latest → 26.04 rollout runs 2026-10-19 to 2026-11-19 (GitHub changelog, 2026-09-17).
  - Neither runner-image README (versions 20260927) lists ffmpeg.
  - zizmor 1.30.1 `--offline` reports no findings on the §9 workflow; the 4 suppressed ones are pedantic `anonymous-definition`.
- **ffmpeg:** flite is §9.7 of ffmpeg-filters, with `voice=slt`. Noble and Debian 8.1.2-2 rules have `--enable-libflite`.
- **HF models:** faster-whisper-tiny and tiny.en are model.bin 75.5 MB + tokenizer ~2.2 MB, MIT. tiny-random-CLIP is 2.9 MB and tiny-random-Siglip 5.1 MB, neither with a licence. openai/whisper-tiny is ~151 MB × 4 formats, Apache-2.0.
- **deptry:** PEP 735 groups count as dev, and extras count as regular dependencies.
- **Script:** the size script passes ruff ALL and mypy strict.
