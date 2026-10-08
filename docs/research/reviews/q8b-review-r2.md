# Review r2 of `q8b-tooling-gates.md` (final round)

Reviewer: a fresh review agent. I did not write this file or review it before. Review date: **2026-10-08**.

## Method

**Skeleton.** I built a new skeleton in `scratchpad/q8b-review2/sk` with q8a §1.4's package tree.
- The configs were extracted **verbatim** from the doc with `sed`: §11 + §12 `pyproject.toml`, the three §3/§4 scripts, `check_lock.sh`, both workflows, `dependabot.yml` and `CODEOWNERS`. q8a §9.4's `[project]`, extras, `conflicts`, sources and indexes were added around them.
- The source stubs started from the author's skeleton. I removed `adapters/asr/onnx.py`, which is not in q8a's tree. I added the q8a modules the author's skeleton lacked: `llm/openai_compat`, `llm/fallback`, `storage/https`, `vision/nsfw`, `media/ffmpeg`, `domain/errors`, `service/http/push` and `service/http/problems`. I made `parakeet.py` import `onnx_asr`.
- I also tried a q8a-faithful `notify/http_callback.py` with the OIDC path (google-auth).

**Tools.** uv **0.12.23** (installed so that `required-version` is satisfied), ruff 0.16.10, mypy 2.4.0, import-linter 2.15, pytest 9.1.1, coverage 7.16.2, pytest-cov 7.1.0, pytest-timeout 2.4.0, pytest-randomly 5.0.0, deptry 0.25.1, vulture 2.16, typos 1.51.1 and zizmor 1.30.1.
- Static gates ran with all CPU extras installed.
- The PR tier (`--extra service`) ran on CPython 3.12.14, 3.13 and 3.14.7.
- e2e used a static ffmpeg 7.1.

**Sources.** PyPI JSON for every version checked. GitHub API `repos/tach-org/tach/releases`. The GitHub CODEOWNERS docs. The zizmor audits page.

Severity scale: **wrong** / **unsupported** / **missing option** / **design concern** / **minor**.

## Overall

- **The headline claims reproduce.**
  - `uv lock --check`: 126 packages.
  - `check_lock.sh` passes. Both negative cases fail as claimed.
  - format, ruff, mypy ("no issues found in 72 source files") and deptry are clean.
  - `lint-imports` reports "7 kept, 0 broken (2 ignored imports)".
  - The size, suppression and vulture gates behave as described, after whitelisting.
  - Core coverage is 100% from `tests/unit` on all three Pythons. Overall coverage is 95.08% / 95.08% / 94.84%.
  - typos is clean. zizmor reports "No findings… (5 suppressed)".
- **Every planted violation for every gate failed as claimed.** The list is under "Verified correct" below.
- **The defects are in the anti-silencing layer, which is the part the doc leans on most.**
  - Three silencing routes bypass the core ban and CODEOWNERS entirely: findings 1–3.
  - One "advisory" step is in fact failing: finding 6.

---

## Findings

### 1. `# pragma nocover` / `# pragma no cover` bypass the core ban and still exclude lines from coverage (wrong)
- **Claim (§4.2, layer 3):** the core ban catches "*any* suppression … including `pragma: no cover`, so the 100% core target cannot be met by exclusion".
- **What the run shows:**
  - The script's regex is `pragma\s*:\s*no\s+(?:cover|branch)`. It needs a colon and whitespace.
  - coverage's default exclude regex is `#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(cover|COVER)`, which needs neither.
  - I seeded an untested function in `domain/time.py` with `# pragma nocover`, `# pragma no cover` and `#pragma:nocover`. Each one gave "suppressions: 2 (budget 2)" (exit 0), and the unit-only core report still showed **100%** (exit 0).
  - Only `# PRAGMA: NO COVER` was caught.
- **Correction:** pick one of these.
  - Copy coverage's own pattern into `COMMENT`: `pragma[:\s]?\s*no\s*(?:cover|branch)`, case-insensitive.
  - Better: set `[tool.coverage.report] exclude_lines` explicitly to the three `exclude_also` patterns. `exclude_lines` replaces the default, so pragmas stop working at all. If pragmas are wanted outside the core, keep a `# why:`-style pragma that only the script knows about.

### 2. `# flake8: noqa: <codes>` silences ruff file-wide in the core and is not detected (wrong)
- **Claim (§4.2):** the core ban covers "any suppression", and file-level directives (`# ruff: noqa`) are listed among the routes it closes.
- **What the run shows:**
  - I put `# flake8: noqa: S307, TID251, E402` at the top of `domain/time.py` and appended `import pickle` and `eval("1")`.
  - ruff then reported only F401 (unused import). S307, TID251 (pickle) and E402 were silenced file-wide.
  - PGH004 fires only for the code-less `# flake8: noqa`.
  - `check_suppressions.py` reported "suppressions: 2 (budget 2)", exit 0. Its regex anchors `noqa` right after `#\s*` and recognises only `ruff:` as a prefix.
- **Correction:** match `\bnoqa\b` anywhere in a comment token, or add `flake8\s*:\s*noqa` to `COMMENT`. Add a seeded case to the doc.

### 3. Alternative config files silently override the gates, and CODEOWNERS does not cover them (wrong)
- **Claim (§4.2 layer 6, §13 CODEOWNERS):** config escape hatches are closed by CODEOWNERS on `/pyproject.toml`, `/uv.lock`, `/scripts/`, `/vulture_whitelist.py` and `/.github/`, which "makes every silencing a reviewed config change".
- **What the run shows.** Each tool also reads other config files, and none of them is code-owned. Each of these was a new, unowned file:
  - **ruff:** a nested `src/scenewise/domain/ruff.toml` (`extend = "../../../pyproject.toml"`, `extend-ignore = ["S307","TID251","E402","F401"]`) silenced all four findings in the core. Hierarchical config wins for that subtree.
  - **mypy:** a root `mypy.ini` with `ignore_errors = True` turned a seeded `X: int = "a"` in domain into "Success: no issues found". mypy prefers `mypy.ini` over `pyproject.toml`.
  - **pytest:** a root `pytest.ini` replaced `[tool.pytest]`. It deselected a test module, and `filterwarnings=error`, `strict` and `timeout` were gone ("3 warnings").
  - **coverage:** a root `.coveragerc` (`fail_under = 10`, `omit = service/*`, `branch = False`) replaced the pyproject coverage config: "Required test coverage of 10.0% reached".
  - **import-linter:** a root `.importlinter` containing only `root_package` gave "Contracts: 0 kept, 0 broken", exit 0.
  - **Not tested:** typos also reads `_typos.toml`, `typos.toml` and `.typos.toml`. A `conftest.py` can deselect or skip tests (`collect_ignore`, `pytest_collection_modifyitems`).
- **Correction (cheap, deterministic):**
  1. Pin the config file on every invocation:
     - `ruff check --config pyproject.toml`: verified, the nested `ruff.toml` is then ignored;
     - `ruff format --config pyproject.toml`;
     - `mypy --config-file pyproject.toml`: verified;
     - `pytest -c pyproject.toml`;
     - `--cov-config=pyproject.toml` and `coverage report --rcfile=pyproject.toml`;
     - `lint-imports --config pyproject.toml`;
     - `typos --config pyproject.toml`.
  2. **And/or** add a ten-line step that fails if any of these exist anywhere in the tree: `ruff.toml`, `.ruff.toml`, `mypy.ini`, `.mypy.ini`, `setup.cfg`, `tox.ini`, `pytest.ini`, `.pytest.ini`, `.coveragerc`, `.importlinter`, `_typos.toml`, `typos.toml`, `.typos.toml`.
  3. Add `**/conftest.py` to CODEOWNERS.

### 4. Skip and xfail routes the suppression budget does not count (design concern)
- **Claim (§4.2):** the routes include "skip or xfail markers". The script counts `@pytest.mark.skip/skipif/xfail` decorators. Runtime `pytest.skip()` / `importorskip` "in fixtures" is deliberately not counted.
- **What the run shows.** Each of these passed `check_suppressions.py` with exit 0 while disabling a failing test:
  - module-level `pytestmark = pytest.mark.skip(...)`;
  - `pytest.skip("later")` inside a **test body**, since the script cannot tell a fixture from a test;
  - `pytest.param(..., marks=pytest.mark.xfail(...))`;
  - `from pytest import mark` followed by `@mark.xfail`.

  The e2e fixture also *skips* when ffmpeg is missing, so a broken ffmpeg install would turn the e2e tier into skips rather than a failure.
- **Correction:** all skip routes can be closed with one runtime check instead of a regex arms race.
  - The PR tier has apt ffmpeg, and model tests are deselected, not skipped. So in CI the `test` job should **fail on any skipped or xfailed test**.
  - Do it with a 10-line `pytest_terminal_summary` / `pytest_sessionfinish` hook in the root `tests/conftest.py`, gated on an env var `SCENEWISE_NO_SKIPS=1`. Alternatively, parse `-rsx` output.
  - Keep the decorator count for the budget if desired. The runtime check is what binds.

### 5. The `slow` marker is a silent quarantine: no job ever runs it (design concern)
- **Claim (§11):** `addopts = [... "-m", "not model and not slow"]`, with marker `slow: tests slower than ~5 s`.
- **What the run shows:**
  - `ci.yml` `test` runs `pytest tests/unit` and `pytest`; both inherit the deselection.
  - `models` runs only `-m model`.
  - `property-nightly` runs `tests/unit` with the same addopts.
  - So a `slow` test runs **nowhere**. Seeded `@pytest.mark.slow def test_z(): assert False` gave "25 passed, 1 deselected", and the suppression script did not count it.
  - `@pytest.mark.model` on a unit test likewise moves it into a job that is not required for merge.
- **Correction:**
  - Drop the `slow` marker, which is my preference: pytest-timeout already bounds runtime. Otherwise run `-m slow` in `property-nightly`/`models` and count `mark.slow` in the budget.
  - Restrict `model` to `tests/contract` with a collection hook, or count `mark.model` outside `tests/contract/test_*` adapter modules.

### 6. The models job's "advisory" adapter coverage report fails the job (wrong)
- **Claim (§13 table):** `models` gives "advisory adapter coverage". The step is `coverage report --omit=__none__ --include='src/scenewise/adapters/*'`.
- **What the run shows:**
  - That command still reads `[report] fail_under = 90` from pyproject.
  - On the skeleton the model tier covers 43% of adapters, so the step prints "Coverage failure: total of 43 is less than fail-under=90" and exits **2**.
  - With `--fail-under=0` it exits 0.
  - The `models` job would therefore be red on every main push, nightly run and labelled PR.
- **Correction:** add `--fail-under=0` to that `coverage report` line, or decide on a real adapter threshold (open question 2).

### 7. File-level directives cost one budget unit but silence a whole file (design concern)
- **Claim (§4.2):** each suppression outside the core needs `# why:` and counts as one against an exact budget.
- **What the run shows:**
  - `# mypy: ignore-errors  # why: …` counts as 1, the same as a single-line `noqa`. So do `# ruff: noqa: …` and a file-top `# type: ignore` (which mypy treats as ignoring the whole module).
  - A seeded `# mypy: ignore-errors` was correctly reported only because it lacked `# why:`.
- **Correction:** ban file-level directives everywhere, not only in the core: `ruff: noqa`, `flake8: noqa`, `mypy:` and a first-line `type: ignore`. A whole-file exemption belongs in a reviewed `per-file-ignores` or mypy override. This also simplifies the budget.

### 8. q8a's tree needs two more lazy optional imports and a google-auth typing override; the skeleton avoided both (missing option)
- **Claim (§2, §1):** only `service/bootstrap.py` needs `PLC0415`, and exactly six untyped libraries need `ignore_missing_imports`.
- **What q8a and the run show:**
  - q8a §6.5 says outbound callbacks carry a **Google ID token via google-auth**. But google-auth sits only in the `gcs` extra, while `http_callback` is PR-tier and contract-tested there (§6).
  - My q8a-faithful `http_callback.py` imported `google.oauth2.id_token` lazily in the OIDC branch. That failed ruff `PLC0415` (not exempt) and mypy `no-untyped-call` ("Call to untyped function "fetch_id_token""). `google.oauth2` ships `py.typed` but this function is untyped.
  - q8a §1.5 rule 3 also allows `storage/by_scheme.py → storage/gcs.py`. A top-level import makes `by_scheme` unimportable without the `gcs` extra. The author's skeleton's `by_scheme` routes only `local`, so neither case was exercised.
- **Correction:**
  - Record as q8a follow-ups: either move `google-auth` to base dependencies or an `oidc` extra, or inject a token-provider callable from bootstrap.
  - Have `by_scheme` take an injected `Mapping[str, BlobStore]` so it imports no sibling.
  - If lazy imports in adapters are accepted, say so and extend `PLC0415` per-file in config, not inline.
  - Add `[[tool.mypy.overrides]] module = ["google.oauth2.*", "google.auth.*"]`, `disallow_untyped_calls = false`, or wrap the call in a typed helper.

### 9. vulture's whole-package exclusion of `app/contract/` hides dead mapping code (design concern, small)
- **Claim (§7):** `app/contract/` is excluded because pydantic fields look unused.
- **What the run shows:** a seeded `def dead_mapping()` in `app/contract/envelope.py` was not reported, exit 0. Without the exclusion, vulture reports it next to the field noise (`model_config`, `schema_version`). q8a puts `mapping.py` (`to_domain`/`from_domain`) and `request_digest` in that package, which is exactly where dead functions hide.
- **Correction:** exclude only the model-only modules (`requests.py`, `results.py`). Alternatively, add `ignore_names = ["model_config"]` and whitelist the fields. Either way, keep `mapping.py` and `envelope.py` scanned.

### 10. `extended.yml` concurrency cancels nightly runs (minor)
- **Claim (§13):** `concurrency: group: ${{ github.workflow }}-${{ github.ref }}`, `cancel-in-progress: true`.
- **What the YAML implies:**
  - `schedule` and `push` to main share the group `extended-refs/heads/main`, so any merge cancels a running nightly (`models` + `property-nightly`, which can run for up to `--timeout=1800` per test).
  - On PRs, adding *any* label (`labeled`) to a PR that carries `run-model-tests` cancels and restarts the model run.
- **Correction:** `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, or include `github.event_name` in the group. Optionally make the `labeled` trigger relevant only when `github.event.label.name == 'run-model-tests'`.

### 11. `property-nightly` syncs no extras (minor)
- **Claim (§13):** `uv sync`, then `pytest tests/unit …`.
- **What the doc implies:** the doc says `service/http/health.py` (the watchdog) has a unit test in `tests/unit`. In q8a it is the `/healthz` route module, so it plausibly imports FastAPI (the `service` extra). The skeleton's `health.py` is framework-free, so this did not show up.
- **Correction:** use `uv sync --extra service`, the same as the `test` job, so the two unit runs see the same environment.

### 12. `zizmor --offline` skips the audits that check the SHA pins (missing option, minor)
- **Claim (§7/§13):** zizmor offline is gating and deterministic.
- **What the source says:** the zizmor audits page marks `impostor-commit`, `known-vulnerable-actions`, `ref-confusion` and `stale-action-refs` as online-only. The SHA pins and their `# vX` comments are therefore never verified. `dependabot-cooldown` exists since v1.15.0 and is offline, as the doc says.
- **Correction:** keep offline zizmor as the gate. Add an online run (`GH_TOKEN`) to the nightly as an alert, next to `audit`.

### 13. CODEOWNERS works only if agents have their own GitHub identity, and it should cover more paths (design concern)
- **Claim (§4.2 layer 6, open question 7):** "Agent identities must not be code owners."
- **What the source says:**
  - GitHub requires owners to have write access.
  - The CODEOWNERS file applies from the PR's **base** branch, so a PR cannot weaken its own review. This is good, and the doc could say it.
  - Invalid lines are skipped silently. A typo in `@<maintainers>` therefore disables protection without an error, though errors are shown in the file view (about-code-owners docs).
  - GitHub does not count a PR author's own approval. If agents push PRs with the maintainer's credentials (the default for a solo maintainer running Claude Code), "Require review from Code Owners" either blocks every gate-config PR or gets bypassed by an admin.
- **Correction:**
  - State the precondition: agents open PRs from a separate bot account or GitHub App without write access to protected settings. Branch protection must enable "Do not allow bypassing the above settings".
  - Add a CI check (or zizmor-style lint) that CODEOWNERS has no errors, via the API's `codeowners/errors` endpoint.
  - Extend CODEOWNERS to the files in finding 3, including `**/conftest.py`.

### 14. `uv audit` with `continue-on-error: true` is an alert nobody sees (design concern / proportionality)
- **Claim (§7/§13):** `audit` is nightly and "alerts, never blocks".
- **Assessment:** with `continue-on-error`, the run is green whatever `uv audit` finds. No issue, summary or notification is wired, so it is not an alert.
- **Correction:** pick one.
  - Cut the job and rely on Dependabot security alerts for `uv.lock`, if GitHub's dependency graph covers it for this repo. Check this.
  - Let the nightly job fail (nightly runs are not merge checks) so the failure notification is the alert.

### 15. The "ports and use cases" forbidden contract duplicates the allow-list (minor, proportionality)
- **Claim (§3):** the overlap is deliberate: the forbidden list is q8a's rule verbatim.
- **Assessment:**
  - Every seed that broke the forbidden contract also broke an allow-list contract, so the run shows no unique catch. Two failures per seed double the output an agent must read.
  - The forbidden contract's only extra is indirect chains. But first-party links in such a chain (for example `app → domain → PIL`) are already caught at their source by the domain allow-list.
- **Correction:** this is optional. Drop it and note in §3 that the allow-list implements q8a rule 6 more strictly. Keep it only if literal traceability to q8a matters more than noise.

### 16. `max-bool-expr = 3` is dead config (minor)
- **Claim (§2):** "Effective only if preview PLR0916 is ever enabled", and preview is forbidden.
- **Correction:** remove it, or move it to a comment. Dead settings invite agents to "tune" them.

### 17. The author's skeleton was not q8a's tree in two places (minor)
- **Claim (Method, §7 deptry):** "one stub per adapter … `asr/{parakeet,onnx,faster_whisper}`", and deptry is clean.
- **What I found:**
  - `adapters/asr/onnx.py` is not in q8a §1.4.
  - It was the only module importing `onnx_asr`. The `parakeet.py` stub imports nothing, so without `onnx.py` deptry reports DEP002 for `onnx-asr`.
  - With `parakeet.py` importing `onnx_asr`, as the real adapter would, deptry is clean. The conclusion holds.
- **Correction:** describe the skeleton accurately, or drop `onnx.py` and make `parakeet.py` import `onnx_asr`.

### 18. The script blocks' filename header trips ERA001 when copied verbatim (minor)
- **What the run shows:** the first line `# scripts/import_contracts.py` raises `ERA001 Found commented-out code`. `check_suppressions.py`'s header does not.
- **Correction:** drop the header comments from the code blocks, or mark them as presentational.

### 19. The 500-line rationale ("roughly 350 lines of code") is an estimate (unsupported, minor)
- **Claim (§4.1):** 400 → 500 because D1xx docstrings count; "500 physical lines is still roughly 350 lines of code".
- **Assessment:**
  - The direction of the change is reasonable. It answers round-1 finding 11 and fits q8a's size-driven layout. FU 6 asked for no exemptions, and none are added.
  - The 30% docstring share is not measured anywhere.
- **Correction:** measure it on the skeleton or a comparable module (`radon raw`, or an AST pass that counts docstring lines), or call it a judgment.

### 20. q8a's text now disagrees with q8b in two places (minor)
- **What I found:** q8a §1.5 still gives the literal list `layers = ["service", "adapters", "app", "ports", "domain"]` and says the layers contract "already forbids" adapters → app. q8a §1.4 and FU 6 still quote `MAX_LINES = 400`.
- **Assessment:**
  - q8b is right on the layers. With the literal list, adapters → app is allowed. `adapters | app` encodes q8a's own arrows exactly: adapters → ports, domain [never app]; app → ports, domain [never adapters]. My seeds `adapters.notify → app.contract.envelope` and `adapters.asr.parakeet → app.deps` were both reported as "scenewise.adapters is not allowed to import scenewise.app".
  - But q8a is final and read-only.
- **Correction:** record both as errata in `user-decisions.md`, or in a q8a errata note, so the implementer does not copy q8a's contract.

### 21. `exclude_also = "^\s*\.\.\.$"` also excludes `...` stub bodies in the core (minor)
- **Assessment:** in domain or app, an agent can leave `def f(...) -> T: ...` unimplemented, and core coverage stays 100%, because the `def` line runs at import. The pattern is needed only for Protocol bodies in `ports`.
- **Correction:** accept this and say so, since mypy will usually flag a `...` body that returns a non-`None` type. Alternatively, rely on mypy's `empty-body` error, which is on by default, and note that it is the backstop.

---

## Round-1 findings and q8a follow-ups (check 1)

- **All 22 round-1 resolutions hold on re-run.**
  - Tests are packages, and mypy is clean over `src`, `tests` and `scripts` (1).
  - isort uses `known-first-party` (2).
  - `labeled` is a trigger in `extended.yml` (3).
  - The test ignores and keyword-only constructors are in place (4).
  - vulture runs at 60 (5).
  - The suppression layers exist (6). They are incomplete; see findings 1–4 and 7.
  - The `adapters | app` layers contract is in place (7).
  - Hypothesis has a `nightly` profile from `default` (8).
  - Core coverage comes from unit tests only, and the seeded core function covered only by a contract test gave "99% < 100" (9).
  - `max-returns = 6` (10).
  - The 500-line limit is read from pyproject, the CI call takes no arguments, and 501 lines fail (11).
  - uv `required-version` is set; setup-uv reads it, and a non-matching uv refuses (12).
  - Timeout as a string: an int aborts with "expects a string, got int: 60", and "1" times out a 3 s test (13).
  - Findings 14–22: text-level resolutions, consistent with their sources.
- **Follow-ups 1–12 are correctly applied.**
  - The contracts match q8a's arrows exactly, as shown in finding 20.
  - `protected` with `allowed_importers = [service.bootstrap]` is a strict superset of FU 3. It caught `service.http.routes`, `service.cli` and `service.config` imports, and still allowed `storage.by_scheme → storage.local` and bootstrap's lazy imports.
  - The coverage include and omit paths match q8a's tree, including `app/contract/*`, `app/audio.py`, `domain/manifests.py`, `domain/uris.py` and both `ports.py` and `ports/*`.
  - The deptry map is correct.
  - FU 9 now has a dependency on finding 8: OIDC in the notifier.

## Verified correct (seeded violations, all fail as claimed)

- **ruff:**
  - format diff;
  - C901 (10 > 8) and PLR0917 (4 > 3);
  - TID251 for pickle and `typing.no_type_check`;
  - PGH004 + RUF100 on a blanket `noqa`;
  - RUF100 on an unused coded `noqa`.
- **mypy:**
  - assignment error;
  - `explicit-any` in domain, including `cast("Any", …)` in app;
  - `ignore-without-code`;
  - `unused-ignore`;
  - `no-untyped-def` in tests.
- **import-linter (each of these is caught):**
  - adapters → app or app.contract;
  - adapters → service;
  - app → adapters (layers + protected);
  - app → service;
  - service.http, service.cli or service.config → adapters (protected);
  - llm → storage (independence);
  - domain → ports (layers);
  - domain → pydantic, and domain → onnx_asr (not installed);
  - ports → PIL;
  - app → numpy, httpx and typing_extensions (allow-list);
  - service.http.health → torch or google;
  - a stray `scenewise.utils`;
  - `__main__` reported once `exhaustive_ignores` is removed;
  - removing the torch probe gives "No matches for ignored import … -> torch".
- **Suppression script:**
  - `pragma: no cover` in app and `noqa … # why:` in domain are banned;
  - a missing `# why:` is flagged;
  - `@pytest.mark.skip` makes the count differ from the budget;
  - an exact-budget mismatch fails.
- **Other gates:**
  - vulture catches an unused function;
  - deptry flags DEP003 for transitive `requests` and `yaml`;
  - pytest fails on a `DeprecationWarning` (filterwarnings) and on an unknown marker (strict);
  - pytest-randomly makes an order-dependent pair fail on seeds 1–3 and pass on 4–6;
  - zizmor flags `unpinned-uses` and `template-injection`;
  - the check_lock negatives give "FAIL: asr + ort-cu130 pulls torch" and "FAIL: torch-cpu: torch not from pytorch-cpu".
- **Sources (check 3):**
  - **tach releases (GitHub API):**
    - v0.21.0–v0.29.0 by emdoyle; last release 2025-04-18;
    - **v0.32.0 (2025-11-19) through v0.35.3 (2026-10-06) by DetachHead**;
    - there are no v0.30/0.31 tags.
  - **dtach (PyPI):** 0.30.2 (2025-10-10) to 0.31.2 (2025-11-07). Its README says "DTach is a fork of the unmaintained tach project". §3 is exact.
  - **Other versions (PyPI):** pytest-timeout 2.4.0, uploaded 2025-05-05, `requires_dist pytest>=7.0.0`. pytest-randomly 5.0.0, 2026-09-01. zizmor 1.30.1, 2026-09-09.
  - **zizmor audits page:** `dependabot-cooldown` exists, since v1.15.0, offline.
  - **CODEOWNERS:** the location, the base-branch rule, the write-access requirement and the meaning of a trailing slash (`/scripts/` covers subdirectories) all match the GitHub docs.

## Proportionality (check 4)

**Verdict:** the gate set is rigorous, not absurd. Each gate is deterministic and cheap, and I would keep the core:
- ruff ALL;
- mypy strict;
- import-linter;
- size;
- unit-only 100% core coverage;
- deptry, vulture at 60, typos and zizmor;
- the lock checks;
- pytest-timeout and pytest-randomly.

**I would cut or simplify:**
1. The `slow` marker (finding 5): a tier nobody runs.
2. The `audit` job in its current form (finding 14): an invisible alert.
3. The duplicate ports/app `forbidden` contract (finding 15): it doubles the output and catches nothing extra.
4. `max-bool-expr` (finding 16): dead config.

**I would replace, not add:** close the skip routes with one runtime "no skips in the PR tier" check (finding 4) rather than growing the regex. Pin config files explicitly (finding 3) rather than growing CODEOWNERS.

## Count by severity

| Severity | Count | Findings |
|---|---|---|
| wrong | 4 | 1, 2, 3, 6 |
| unsupported | 1 | 19 |
| missing option | 2 | 8, 12 |
| design concern | 6 | 4, 5, 7, 9, 13, 14 |
| minor | 8 | 10, 11, 15, 16, 17, 18, 20, 21 |
