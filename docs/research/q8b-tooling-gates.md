# Q8 part B: testing, tooling and Run gates

Status: research finding plus proposed configuration, **final after review round 2** (see "Review round 1 — resolution", §10, and "Review round 2 — resolution", §15). Anything not settled is a user decision in §8.
Research date: **2026-10-08**. Every version and date was read that day, either from the PyPI JSON API
(`https://pypi.org/pypi/<pkg>/json`, latest release and its upload date) or from the URL cited next to it.

Settled inputs:
- user-decisions.md U2 (2026-10-08): Python floor **3.12**, CI matrix **3.12–3.14**.
- q8a-architecture-layout.md (final, committed):
  - Layers are `service > adapters > app > ports > domain`.
  - `service/` is the driving side: bootstrap, config, logs, CLI and HTTP, including `http/health.py`.
  - `adapters/` holds only driven port implementations and never imports `app` (including `app.contract`) or `service`.
  - `app/` holds the use cases **and the pydantic wire contract `app/contract/`**, plus the new `app/audio.py`.
  - `ports` is the single module `scenewise/ports.py`, to be split into a `ports/` package at about 200 lines.
  - `domain` is stdlib-only and now includes `manifests.py` and `uris.py`.
  - Only `service.bootstrap` imports adapters. It also probes `onnxruntime` and `torch` at start-up (q8a §9.4).
  - The extras are `service`, `asr`, `asr-whisper`, `llm-anthropic`, `vision` (open-clip, timm and **pillow**) and `gcs`, plus two independent selector pairs, `ort-cpu`/`ort-cu130` and `torch-cpu`/`torch-cu130`, declared as uv `conflicts`. httpx, pydantic-settings and structlog are base dependencies.
  - q8a's section "Follow-ups for q8b" lists 12 changes. Each is resolved in §10.1.
  - Where q8a's text and this document now differ, the difference is listed as an erratum in §15.1 for the implementer.

How this was checked. The final configuration (round 2) was run on a throwaway skeleton with **q8a §1.4's package tree**, `scratchpad/q8b-final/sk/`, which is not in the repo. It starts from the round-2 reviewer's skeleton (which corrected mine: round 1's had an `asr/onnx.py` that q8a does not have, and `parakeet.py` did not import `onnx_asr`; finding r2-17). It contains:
- `domain/{time,results,captions,errors,uris,manifests}.py` and `ports.py` (including `Notifier`);
- `app/{deps,stages,audio}.py` and `app/contract/{envelope,requests,results,mapping}.py` (pydantic);
- one stub per q8a adapter that really imports its library: `media/{ffmpeg,images}` (PIL), `storage/{local,https,by_scheme,gcs}`, `asr/{parakeet,faster_whisper}` (parakeet imports `onnx_asr`), `llm/{openai_compat,anthropic,fallback}`, `vision/{open_clip,nsfw}`, `notify/http_callback` (httpx) and **`notify/google_id_token`** (google-auth; §2, finding r2-8);
- `service/{bootstrap,config,logs,cli}.py` and `service/http/{app,routes,push,health,problems}.py`, with bootstrap's lazy adapter imports and its onnxruntime/torch probes;
- `tests/{unit,contract,e2e}` as packages, with fakes, a contract mixin, a model-marked contract module and `tests/e2e/conftest.py`;
- **q8a §9.4's exact `[project]` extras, `[tool.uv] conflicts`, sources and PyTorch indexes**, locked with uv (126 packages).

I ran **every config in §11–§13** against it with the pinned versions: uv **0.12.23**, ruff 0.16.10, mypy 2.4.0, import-linter 2.15, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.2, pytest-timeout 2.4.0, pytest-randomly 5.0.0, hypothesis 6.168.5, deptry 0.25.1, vulture 2.16, typos 1.51.1 and zizmor 1.30.1.
- Every CI step was run as written in §13, with the same flags (including the pinned `--config` options).
- The static gates ran with all CPU extras installed (`--extra service --extra asr --extra asr-whisper --extra llm-anthropic --extra vision --extra gcs --extra ort-cpu --extra torch-cpu`) on CPython 3.14.7.
- The PR tier (`--extra service` only) ran on **CPython 3.12.14, 3.13.16 and 3.14.7**.
- Seeded violations were applied to the same tree one at a time and reverted with `git reset --hard` between seeds.
- ffmpeg: a static ffmpeg 7.1 (the imageio-ffmpeg binary), because apt ffmpeg is not available on the dev machine. That build has no ffprobe, so the local e2e run used a 5-line ffprobe shim that parses `ffmpeg -i` output. apt's ffmpeg package ships the real ffprobe.

Results marked **[verified locally]** come from those runs. Round-1 results that the round-2 reviewer re-ran on an independent skeleton keep the mark.

---

## 0. TL;DR recommendations

| Area | Pick | Why (short) |
|---|---|---|
| Type gate | **mypy 2.4.0 `strict`** over `src`, `tests` and `scripts` in one run, always with `--config-file pyproject.toml`; plus 10 extra error codes, the pydantic plugin, and `disallow_any_explicit` in domain/app/ports; `ignore_missing_imports` only for the six untyped heavy libraries; `untyped_calls_exclude` only for `google.oauth2.id_token` | Stable, with a first-party pydantic plugin. **No second checker in CI.** pyrefly, ty and basedpyright are editor tools only (finding 22). |
| Lint/format | **ruff 0.16.10**, `select = ["ALL"]`, six justified ignores, `required-version = "==0.16.10"` + `ruff==0.16.10` in the locked dev group; run with `--config pyproject.toml` | One tool. The exact pin plus `uv.lock` + `UV_LOCKED` makes the rule set reproducible. |
| Dependency direction | **import-linter 2.15**, six contracts: layers `service > (adapters \| app) > ports > domain` with `exhaustive_ignores = ["__main__"]`; independent adapter kinds; **protected** `scenewise.adapters`, importable only by `service.bootstrap`; a 25-line **custom allow-list contract** (stdlib only in domain and ports; stdlib + pydantic + structlog in app), which implements q8a rule 6 more strictly than its deny-list; a forbidden list of ML/cloud SDKs for `service`, excepting bootstrap's two start-up probes | Every q8a rule maps to a contract, and every one catches a seeded violation [verified locally]. |
| Lock routing | `uv lock --check` with q8a's two conflict pairs, plus `scripts/check_lock.sh` (16 lines, reads only `uv.lock`): torch/torchvision come from the PyTorch index under each `torch-*` selector, and `service + asr + ort-cu130` contains no torch | q8a follow-up 8. Positive and negative cases verified locally. |
| Gate-suppression control | **`scripts/check_suppressions.py`** (stdlib, ~90 lines): file-level directives (`ruff: noqa`, `flake8: noqa`, `mypy:`, `pyright:`, `isort: skip_file`, a module-top `type: ignore`) and every coverage-pragma spelling are **banned everywhere**; **zero** line-level `noqa` / `type: ignore` / `fmt: off\|skip` in domain, app and ports; elsewhere each needs `# why:` and the total must **equal** a committed budget. Coverage's `exclude_lines` replaces its default, so pragmas are inert anyway. **CI fails on any skipped or xfailed test** (JUnit check). **Every tool is run with its config pinned to `/pyproject.toml`**, and a step fails on stray config files. Plus ruff RUF100/PGH003/PGH004, mypy `warn_unused_ignores` + `ignore-without-code`, and CODEOWNERS (which binds only under the conditions in §4.2) | Agents silence gates instead of fixing code. Every comment, skip and stray-config route is closed by a deterministic check [verified locally, §4.2]; edits to the gate files themselves still depend on review. |
| Module size | Custom script, **500 physical lines**, over `src`, `tests` and `scripts`; the limit is read from `[tool.scenewise.gates]` | ruff has no too-many-lines rule. 500 leaves room for the mandatory docstrings (finding 11); measured code share puts it at roughly 220–390 code lines (§4.1). |
| Complexity | ruff C901 ≤ 8; args ≤ 5; positional ≤ 3 (src); branches ≤ 10; **returns ≤ 6** (ruff default); statements ≤ 40 | Tests are exempt from the argument limits, because pytest injects fixtures positionally (finding 4). |
| Coverage | coverage 7.16.2 + pytest-cov 7.1.0, branch on, `exclude_lines` (no pragmas) and `partial_branches = []`. **Core (`domain/*`, `app/*` including `app/contract/*` and `app/audio.py`, `ports.py` or `ports/*`) at 100%, measured from `tests/unit` only.** Overall ≥ 90% in the PR tier, with heavy-extra adapters omitted there and reported (not gated) in the models job | The unit-only run stops e2e tests from inflating core coverage (finding 9). |
| Tests | pytest 9.1.1 native `[tool.pytest]` (`-c pyproject.toml`), `strict`, `filterwarnings=error`, **pytest-timeout** (`timeout = "60"`), **pytest-randomly**; tests are packages (`__init__.py`); contract mixins; e2e on ffmpeg-generated media; one opt-in marker, `model`, allowed only in `tests/contract`; **no skipped or xfailed test in any CI job** | Hangs, order-dependent tests and quietly skipped tests are all common in agent-written suites (findings 13, r2-4). |
| Dead code | **vulture 2.16 at `min_confidence = 60`** over `src` with a committed `vulture_whitelist.py`; only the two model-only wire modules are excluded | At 80 it only duplicated ruff (finding 5). |
| Extra gates | `uv lock --check` + `UV_LOCKED=1`, deptry, typos, zizmor (gating, offline); a nightly `supply-chain` job that **fails** on `uv audit` findings or on zizmor's online audits (impostor commits, stale/mismatched pins), never a merge gate | The merge gates stay deterministic; the nightly failure email is the alert (finding r2-14). |
| CI | Two workflows. `ci.yml` (PR + main): `static`, which syncs all CPU extras (`… --extra ort-cpu --extra torch-cpu`) and runs the stray-config and lock-routing checks, plus `test` (`--extra service`) on 3.12/3.13/3.14 with `fail-fast: false`. `extended.yml` (PR `labeled` + main + nightly + manual): `models`, `property-nightly`, `supply-chain`; a merge never cancels the nightly. setup-uv v10.2.0, checkout v7.0.1, cache v6.1.0, all SHA-pinned; uv pinned via `[tool.uv] required-version`; ffmpeg from apt; `ubuntu-24.04` | The label now actually triggers the model job (finding 3). |

---

## 1. Type checking

### Current status (read 2026-10-08)

| Tool | Version / date | Status | Source |
|---|---|---|---|
| mypy | **2.4.0**, 2026-10-01 (2.0.0 released 2026-05-06) | Production/Stable | https://pypi.org/pypi/mypy/json ; https://pypi.org/project/mypy/2.0.0/ |
| pyright | 1.1.414, 2026-09-10 | Production/Stable | https://pypi.org/pypi/pyright/json |
| basedpyright | 1.40.2, 2026-10-04 | pyright fork; all rules on by default; baseline support | https://pypi.org/pypi/basedpyright/json ; https://docs.basedpyright.com/latest/ |
| ty (Astral) | 0.0.85, 2026-10-06 | **Beta**. README: no stable API; diagnostics may change between any two versions | https://pypi.org/project/ty/ |
| pyrefly (Meta) | 1.3.2, 2026-09-28; 1.0.0 on 2026-05-12 | Stable | https://pypi.org/pypi/pyrefly/json ; https://pyrefly.org/blog/v1.0/ |

mypy 2.0 changes that matter (https://mypy.readthedocs.io/en/stable/changelog.html, read 2026-10-08):
- `--local-partial-types` and `--strict-bytes` are on by default.
- `--allow-redefinition` has new semantics.
- Python 3.9 targets are dropped.
- Parallel checking (`-n N`) is experimental.

`--strict` in 2.4.0 includes `--warn-unused-ignores` (from `mypy --help`) [verified locally].

### Recommendation

- **Gate: mypy 2.4.0 `strict = true`**, plus:
  - `warn_unreachable`;
  - the 10 extra error codes in §11, including `ignore-without-code`;
  - `plugins = ["pydantic.mypy"]`;
  - **`disallow_any_explicit = true` for `scenewise.domain.*`, `scenewise.app.*` and `scenewise.ports`**, so the core cannot escape typing by writing `Any`.
- **One invocation over `files = ["src", "tests", "scripts"]`**, run as `mypy --config-file pyproject.toml` so that a stray `mypy.ini` cannot replace the config (§4.2) [verified locally: "no issues found in 77 source files" with all CPU extras installed].
- **Test layout: `tests/` and every subdirectory are packages** (`__init__.py`). This keeps ruff's `INP001` enforced in tests and gives contract suites a stable module name (`tests.contract.recognizer_contract`).
  - Without `__init__.py`, mypy aborts with "Source file found twice under different module names". This is reviewer finding 1, which I reproduced [verified locally].
  - Packages alone fix it. `explicit_package_bases = true` with `mypy_path = ["src", "."]` also fixes it, even without `__init__.py`. I keep both, so module naming does not depend on someone remembering an `__init__.py` [both verified locally].
- **Untyped third-party packages.** With all CPU extras installed, mypy strict reports `import-untyped` for six of them: onnxruntime, faster_whisper, ctranslate2, open_clip, torchvision and google.cloud. torch, onnx_asr, PIL, anthropic, fastapi, structlog, pydantic_settings, timm and huggingface_hub are typed [verified locally]. One `[[tool.mypy.overrides]]` sets `ignore_missing_imports = true` for exactly those six. That is a config entry, so it is CODEOWNERS-reviewed, unlike inline ignores. Values from them are `Any`, so adapters must convert at the boundary; `warn_return_any` stays on.
- **google-auth is typed but not annotated where it matters.** `google.oauth2` ships `py.typed`, but `google.oauth2.id_token.fetch_id_token` has no annotations, so strict mypy reports `Call to untyped function "fetch_id_token" in typed context [no-untyped-call]` [verified locally]. mypy's global `untyped_calls_exclude = ["google.oauth2.id_token"]` exempts exactly that module's functions; the result is `Any`, and the adapter assigns it to a `str` variable before returning it, so `warn_return_any` stays satisfied [verified locally: clean with the setting, the error above without it]. Where that adapter lives is in §2.
- **pyrefly, ty and basedpyright: editor only, not in CI.** A non-gating second checker gives agents a stream of findings to ignore, or to "fix" against mypy. This is reviewer finding 22, accepted.

---

## 2. Lint and format: ruff

- Version **0.16.10**, 2026-10-01 (https://pypi.org/pypi/ruff/json).
- `ruff rule --all --output-format json` returns 971 entries, one of them without a code. Of the **970 coded rules: 812 stable, 141 preview, 17 removed** [verified locally]. `select = ["ALL"]` selects only stable rules unless `preview = true`.
- Reproducibility comes from `ruff==0.16.10` in the dev group, plus `uv.lock` and `UV_LOCKED=1`. `required-version = "==0.16.10"` additionally makes an out-of-band ruff refuse to run on the config. A ruff upgrade is therefore always an explicit PR (finding 20).
- Rules that conflict with the formatter (https://docs.astral.sh/ruff/formatter/, read 2026-10-08) are W191, E111, E114, E117, D203, D206, D300, Q000–Q004, COM812, COM819, and ISC002 in some settings. With only `COM812` ignored, `format --check` and `check` agree [verified locally].
- Complexity rule status in 0.16.10:
  - Stable: C901, PLR0911, PLR0912, PLR0913, PLR0915, and PLR0917 (stable since 0.16.0).
  - Preview: PLR0904, PLR0914, PLR0916, PLR1702 and PLW0717.
  - `PLC0302` does not exist, so ruff has no too-many-lines rule [verified locally].
- `ruff config lint.pylint` lists 12 keys: `allow-magic-value-types`, `allow-dunder-method-names`, and the ten limit keys `max-args`, `max-positional-args`, `max-branches`, `max-returns`, `max-statements`, `max-statements-in-try`, `max-locals`, `max-public-methods`, `max-bool-expr` and `max-nested-blocks` [verified locally].

### Rule-set decisions

| Decision | Rules | Reason |
|---|---|---|
| Keep, via `ALL` | everything stable, including **RUF100** (unused `noqa`), **PGH003** (blanket `type: ignore`), **PGH004** (blanket `noqa`), N818, INP001 and TID | A strict showcase. These are cheap to satisfy in new code. RUF100/PGH are the first line of the suppression control (§4.2). |
| Ignore | `COM812` | Formatter conflict. |
| Ignore | `D203`, `D213` | Mutually exclusive pydocstyle pairs (google convention). |
| Ignore | `CPY001` | No per-file licence header. |
| Ignore | `TD002`, `FIX002` | A TODO is allowed if it links an issue (TD003 enforced). |
| Ignore | `DOC` | All 7 DOC rules are preview. Listed so that enabling preview later does not require Args/Returns sections everywhere. |
| Tests ignores | `S101`, `D1`, `PLR2004`, **`PLR0913`, `PLR0917`**, **`FBT001`**, **`SLF001`**, **`PLC0415`** | pytest injects fixtures positionally: a 6-fixture contract test raises PLR0913 *and* PLR0917 without these ignores [verified locally]. Parametrised bool arguments trigger FBT001. Tests may inspect private state. Heavy adapters are imported inside fixtures after `importorskip`. **`ANN201` and `INP001` are no longer ignored**, because mypy strict needs `-> None` anyway and tests are packages (finding 16). |
| Scripts ignores | `INP001`, `T201` | Standalone scripts that print their output. |
| Per-file | `src/scenewise/service/bootstrap.py`: `PLC0415` | q8a §1.5 rule 4: bootstrap imports adapters lazily. Putting this in config rather than inline `noqa`s keeps it reviewable and out of the suppression budget. It is the **only** module in `src` with lazy imports (next subsection). |
| Do not enable | `preview = true` | Unstable rules would make the gate nondeterministic. |

`ARG002` stays on in tests. A fixture requested only for its side effect should use `@pytest.mark.usefixtures`.

CI runs `ruff format --config pyproject.toml --check .` and `ruff check --config pyproject.toml .`. With an explicit `--config`, ruff ignores nested `ruff.toml` / `.ruff.toml` files, which otherwise win for their subtree (§4.2) [verified locally].

### Optional SDKs in adapters: google-auth and google-cloud-storage (finding r2-8)

q8a puts `google-cloud-storage` and `google-auth` in the `gcs` extra, but two modules that run without that extra need them: the OIDC branch of `notify/http_callback.py` (q8a §6.5, contract-tested in the PR tier), and `storage/by_scheme.py`, which may route `gs://` to `storage/gcs.py` (q8a §1.5 rule 3). A lazy `import google.oauth2.id_token` inside `notify()` fails ruff `PLC0415` and mypy `no-untyped-call` [verified locally, reproducing the reviewer's run], and a top-level import makes `by_scheme` unimportable without the extra.

Resolution: **no lazy imports outside `service/bootstrap.py`**. Each SDK is imported at the top of the one adapter module that wraps it, and bootstrap injects it:
- `adapters/notify/google_id_token.py` (new, 10 lines): top-level `import google.auth.transport.requests` and `import google.oauth2.id_token`; `fetch_id_token(audience: str) -> str`.
- `adapters/notify/http_callback.py`: `HttpCallbackNotifier(*, client: httpx.Client, id_token: Callable[[str], str] | None = None)`. It imports only httpx. With an `audience` and no provider it raises a configuration error. The PR-tier contract tests use `id_token=lambda aud: ...` and assert `Authorization: Bearer …` [verified locally].
- `adapters/storage/by_scheme.py`: `SchemeRouter(*, stores: Mapping[str, BlobStore])`. It imports only `ports`, so it no longer imports a sibling at all [verified locally].
- `adapters/storage/gcs.py`: top-level `from google.cloud import storage`; it builds its own client, so `service` never imports `google` (the service contract forbids it).
- `service/bootstrap.py` (already `PLC0415`-exempt) imports `storage.gcs` only when a `gs://` store is configured, and `notify.google_id_token` only when callbacks use OIDC.

How the gates are satisfied without suppressions [verified locally]: ruff needs no new per-file ignore; mypy needs only `untyped_calls_exclude = ["google.oauth2.id_token"]` (§1); import-linter keeps all six contracts (bootstrap reaches `google` only indirectly, which the service contract allows); deptry is clean (`google-auth` is now imported); `google_id_token.py` joins `gcs.py` in the PR-tier coverage `omit`. Two q8a consequences, one new module and OIDC callbacks requiring the `gcs` extra, are recorded in §15.1 and open question 12.

**`N818` vs q8a's `WriteConflict`:** ruff's N818 (exception names end in `Error`) flags `class WriteConflict(Exception)` from q8a §4. I confirmed it fires: a `noqa: N818` there was *used*, so RUF100 stayed silent [verified locally]. The skeleton uses `WriteConflictError`. See open question 6.

### Limits

| Setting | Value | Ruff default | Reason |
|---|---|---|---|
| `mccabe.max-complexity` (C901) | **8** | 10 | Small pure functions. Model wrappers split into load / preprocess / infer / postprocess. |
| `pylint.max-args` (PLR0913) | **5** | 5 | More means a parameter dataclass. |
| `pylint.max-positional-args` (PLR0917) | **3** | 5 | In `src/`, constructors and options are **keyword-only (`*,`)**. q8a already builds adapters as `ParakeetRecognizer(model=..., device=..., lock=...)`. Tests are exempt. |
| `pylint.max-branches` (PLR0912) | **10** | 12 | |
| `pylint.max-returns` (PLR0911) | **6** | 6 | Default kept. 4 punished guard-clause and mapping functions: a 5-way codec mapper fails at 4 [verified locally]. Finding 10. |
| `pylint.max-statements` (PLR0915) | **40** | 50 | |
| `line-length` | 120 | 88 | **Open question 1.** |

Limits can be raised only by editing `pyproject.toml`, which is CODEOWNERS-protected. An inline `noqa` for a limit counts against the suppression budget, and in the core it fails outright (§4.2).

`TID251 banned-api`: `pickle`, `torch.load`, `subprocess.call` and **`typing.no_type_check`**. The config is accepted; `import pickle` raises TID251 [verified locally].

---

## 3. Import boundaries

### Options (read 2026-10-08)

| Tool | Version / date | Maintenance | Notes |
|---|---|---|---|
| **import-linter** | **2.15**, 2026-09-04 | Active (GitHub API `repos/seddonym/import-linter`). | Contract types: forbidden, **protected**, layers, independence, acyclic siblings, plus custom contract types. https://import-linter.readthedocs.io/en/stable/contract_types/ |
| tach | 0.35.3, 2026-10-06, Beta | Gauge's last release was **v0.29.0 (2025-04-18, emdoyle)**. DetachHead forked it as **dtach** (PyPI 0.30.2, 2025-10-10, to 0.31.2, 2025-11-07; its README calls tach "unmaintained"). DetachHead has published every `tach-org/tach` release since **v0.32.0 (2025-11-19)**, through v0.35.3. Sources: GitHub API `repos/tach-org/tach/releases`; https://pypi.org/pypi/dtach/json. | Irrelevant to the pick. |
| pytestarch | 4.0.1, 2025-08-08 | No release for 14 months | — |
| ruff TID251 | ruff 0.16.10 | Active | Bans names, not directions. Complements import-linter. |

**Recommendation: import-linter 2.15.**

### How q8a's rules map to contracts

"FU n" refers to item n of q8a's "Follow-ups for q8b".

| q8a §1.5 rule / follow-up | Contract | Seeded violation caught [verified locally] |
|---|---|---|
| Rule 1 / FU 1: layers, exhaustive, `__main__` exempt | `layers = ["service", "adapters \| app", "ports", "domain"]`, `exhaustive = true`, `exhaustive_ignores = ["__main__"]` | Removing `exhaustive_ignores` with `__main__.py` present gives "The following modules are not listed as layers: scenewise.__main__". Also caught: a stray `scenewise.utils` and `app.stages -> adapters.storage.local`. |
| Rule 2 / FU 4: adapters never import `app`, including `app.contract` | the `adapters \| app` independent siblings (see below) | `adapters.notify.http_callback -> app.contract.envelope`; `adapters.asr.parakeet -> app.deps` |
| Rule 3: adapter kinds independent; same-kind composition allowed | `independence` over `scenewise.adapters.*` | kept: `storage/by_scheme -> storage/local` is allowed |
| Rule 4 / FU 3: only `service.bootstrap` imports adapters | **`protected`** `scenewise.adapters`, `allowed_importers = ["scenewise.service.bootstrap"]`. This is a superset of q8a's suggested forbidden contract from `service.http`/`service.cli` | `service.http.routes -> adapters.notify…`; `service.cli -> adapters.storage.local`; `app.stages -> adapters…` |
| Rule 6: domain stdlib only (stricter than a deny-list) | custom **`allowed_externals`** over `scenewise.domain`, `scenewise.ports`, with nothing extra allowed | `domain.manifests -> PIL`; `domain.time -> pydantic`; `ports -> PIL`; `ports -> structlog` |
| Rule 6: app may use pydantic (`app/contract/`, `TypeAdapter`) and structlog, nothing else | `allowed_externals` over `scenewise.app`, allowed `pydantic`, `pydantic_core`, `structlog` | `app.audio -> numpy`; `app.contract.envelope -> torchvision`; `app.stages -> onnxruntime`; `app.stages -> onnx_asr` (**not installed**, still caught) |
| Rule 6 / FU 2: q8a's literal list for ports and app | **no separate contract** (dropped in round 2, finding r2-15): every name on q8a's list is outside both allow-lists, so the allow-list contracts above implement the rule more strictly | `app.audio -> numpy`, `ports -> PIL`, `app.stages -> onnxruntime`, `app.deps -> httpx`, `app.deps -> fastapi`: all five reported by the allow-lists [verified locally] |
| (q8b addition) the driving side loads no ML or cloud SDK | `forbidden` from `scenewise.service` to torch, torchvision, onnxruntime, onnx_asr, ctranslate2, faster_whisper, open_clip, timm, transformers, huggingface_hub, safetensors, numpy, PIL, anthropic and google; `allow_indirect_imports = true`; `ignore_imports` for exactly `service.bootstrap -> onnxruntime` and `-> torch` (q8a §9.4 start-up probes) | `service.http.health -> torch` (the ignored bootstrap probes stay legal: "KEPT (2 ignored imports)") |

The clean skeleton gives "Contracts: 6 kept, 0 broken" with `lint-imports --no-cache --config pyproject.toml` [verified locally]. The seeds in the table were reported as above, each by one contract.

Round 1 also had q8a's literal deny-list as a seventh `forbidden` contract for ports and app. Every seed that broke it also broke an allow-list contract, so it caught nothing extra and doubled the output an agent must read. Its only extra power, indirect chains, is covered because the first-party link in any such chain (for example `app -> domain.manifests -> PIL`) is caught at its source by the domain allow-list. It was dropped.

CI runs `lint-imports --no-cache --config pyproject.toml`. `--config` stops a stray `.importlinter` or `setup.cfg` from replacing the contracts: a root `.importlinter` containing only `root_package` gave "Contracts: 0 kept, 0 broken" without it [verified locally]. `--no-cache` costs nothing on a fresh runner and avoids stale-graph surprises locally.

**Why `adapters | app`, and why it matches q8a exactly.**
- In a layers contract, a higher layer may import any lower one (https://import-linter.readthedocs.io/en/stable/contract_types/layers/, read 2026-10-08).
- With q8a's literal list `["service", "adapters", "app", "ports", "domain"]`, **`adapters -> app` is allowed**. q8a §1.5 rule 2 says the layers contract "already forbids" it, but it forbids only `adapters -> service`.
- `a | b` makes the two layers independent siblings, which is exactly q8a's arrow diagram:
  - `adapters ──► ports, domain [never app]`
  - `app ──► ports, domain [never adapters]`
  - `service` above both.
- q8a follow-up 4's seed, `adapters/notify -> app.contract`, is reported as "scenewise.adapters is not allowed to import scenewise.app" [verified locally].
- The layer names and their order are unchanged. The only change is that two of them are declared as independent peers.
- An equivalent alternative keeps q8a's literal list and adds a `forbidden` contract `scenewise.adapters -> scenewise.app`. I prefer the pipe, because one contract then states the whole rule.

**Why `protected` instead of q8a's suggested `forbidden` from `service.http`/`service.cli`.**
- The protected contract "prevents modules from being imported directly, except by modules on an allow-list". Its `as_packages` default lets descendants of the protected package import each other (https://import-linter.readthedocs.io/en/stable/contract_types/protected/, read 2026-10-08).
- So `storage/by_scheme -> storage/local` stays legal, and **every** non-bootstrap importer is caught: `service.http`, `service.cli`, `service.config`, `service.logs`, a future `service.worker`, and `app`. A forbidden contract would cover only the modules named in it.
- It checks direct imports, so `service.cli -> service.bootstrap -> adapters` is fine, which is q8a's design.

**Heavy libraries: why `forbidden` and not `protected`.**
- A `protected` contract over external packages fails with `"torch" not present in the graph` when the package is not installed [verified locally]. In the PR tier the heavy extras are not installed.
- `forbidden` tolerates absent packages.
- `allow_indirect_imports = true` is required on the service contract, because `service.bootstrap -> adapters -> PIL` is the intended path.
- The bootstrap probes are exempted by named `ignore_imports`. An unmatched entry is an error by default (`unmatched_ignore_imports_alerting = "error"`), so the exemptions cannot silently outlive the code.

**Domain "stdlib only" is now an allow-list (closes round-0 open question 10).**
- The custom contract below allows `sys.stdlib_module_names`, the root package, `__future__`, and an explicit `allowed` list. Anything else fails, **including packages nobody thought to deny-list**: a seeded `import onnx_asr` was caught with onnx_asr not installed [verified locally].
- The custom contract API (`Contract`, `ContractCheck`, `fields`, registration via `contract_types`) is documented at https://import-linter.readthedocs.io/en/stable/custom_contract_types/ (read 2026-10-08). Session options carry `root_packages` (a list), not `root_package` [verified locally against `importlinter/application/use_cases.py`].
- It lives in `scripts/import_contracts.py`, which `lint-imports` imports from the repo root [verified locally]. It passes ruff ALL and mypy strict [verified locally].

`scripts/import_contracts.py`:

```python
"""Custom import-linter contract: an allow-list for third-party imports."""

import sys
from typing import TYPE_CHECKING, cast, override

from grimp import ImportGraph
from importlinter import Contract, ContractCheck, fields, output

if TYPE_CHECKING:
    from importlinter.domain.imports import Module


class AllowedExternalsContract(Contract):
    """Modules in ``source_modules`` may import only stdlib, the root package and ``allowed``."""

    source_modules = fields.ListField(subfield=fields.ModuleField())
    allowed = fields.ListField(subfield=fields.StringField(), required=False, default=[])

    @override
    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:
        """Collect every import of a non-allowed external top-level package."""
        del verbose
        roots = set(self.session_options["root_packages"])
        permitted = set(sys.stdlib_module_names) | roots | {"__future__", *cast("list[str]", self.allowed)}
        bad: list[tuple[str, str, int]] = []
        for source in cast("list[Module]", self.source_modules):
            name = source.name
            for importer in sorted({name} | graph.find_descendants(name)):
                for imported in sorted(graph.find_modules_directly_imported_by(importer)):
                    if imported.split(".")[0] in permitted:
                        continue
                    details = graph.get_import_details(importer=importer, imported=imported)
                    bad += [(importer, imported, d["line_number"]) for d in details]
        return ContractCheck(kept=not bad, metadata={"bad": bad})

    @override
    def render_broken_contract(self, check: ContractCheck) -> None:
        """Print one line per forbidden import."""
        for importer, imported, line in check.metadata["bad"]:
            output.print_error(f"{importer} -> {imported} (l.{line}) is not on the allow-list")
```

The full contract set is in §12.

---

## 4. Module size, complexity and gate-suppression control

### 4.1 Module size

| Tool | Status | Verdict |
|---|---|---|
| ruff | no too-many-lines rule [verified locally] | — |
| pylint 4.1.2 (2026-10-02) | `C0302`, `--max-module-lines` (default 1000). A no-config form also works: `pylint --disable=all --enable=too-many-lines --max-module-lines=500 src` | Works, but adds pylint and astroid to the dev group for one check. Kept as the fallback. |
| radon / xenon / wily | no release since 2023–2024 | Not used. |
| **Custom script** | 25 lines, reads its limit from `pyproject.toml` | **Recommended.** |

**Limit: 500 physical lines, for `src`, `tests` and `scripts` alike** (closes round-0 open question 4).
- `select = ALL` with the google convention requires docstrings on every public object (D1xx). A 400-line budget that counts them pushes agents toward terse docs or artificial splits (finding 11).
- How much code 500 physical lines holds was **measured**, not assumed (finding r2-19). An AST + tokenize pass counted code lines (not blank, not comment-only, not a docstring) in every 200–600-line module of eight installed libraries [verified locally]:

  | Library | Modules | Code share, median | Code share, pooled | Docstring share |
  |---|---|---|---|---|
  | structlog | 9 | 0.43 | 0.44 | 0.38 |
  | google-cloud-storage | 10 | 0.50 | 0.49 | 0.33 |
  | huggingface_hub | 45 | 0.59 | 0.62 | 0.18 |
  | hypothesis | 33 | 0.65 | 0.64 | 0.11 |
  | httpx | 11 | 0.69 | 0.66 | 0.14 |
  | import-linter | 8 | 0.74 | 0.68 | 0.16 |
  | pydantic-settings | 5 | 0.74 | 0.70 | 0.12 |
  | fastapi | 13 | 0.80 | 0.77 | 0.10 |

  So 500 physical lines hold about **220–390 lines of code** (pooled shares 0.44–0.77). The docstring-heavy, google-style libraries sit at the low end, which is where scenewise will be with D1xx enforced. The round-1 figure "roughly 350" was an estimate inside that range. That one module stays readable in one sitting is a judgment, not a measurement. Counting physical lines (`wc -l`) keeps the rule unambiguous for agents.
- Excluding docstrings would need an AST pass and would be gameable in the other direction.
- CI calls the script **without arguments**, and its default roots match the decided ones.
- q8a still quotes `MAX_LINES = 400` and asks for no exemptions (FU 6). Its size-driven layout choices still hold, and are easier to meet under 500:
  - `app/contract/` is a package from the start;
  - `adapters/media/ffmpeg.py` may split into `probe.py`/`decode.py`;
  - `ports.py` becomes a `ports/` package at about 200 lines.
- Every ports-related setting already covers both shapes: the coverage include, the suppression core paths, the mypy override (`scenewise.ports`, `scenewise.ports.*`), and the import contracts (`scenewise.ports` as a module or a package).

`scripts/check_module_size.py`:

```python
"""Fail if any Python module exceeds the line budget (physical lines, as ``wc -l``)."""

import sys
import tomllib
from pathlib import Path


def max_lines() -> int:
    """Read ``[tool.scenewise.gates] max_module_lines`` from pyproject.toml."""
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return int(config["tool"]["scenewise"]["gates"]["max_module_lines"])


def main(roots: list[str]) -> int:
    """Return 1 if any module under ``roots`` exceeds the budget."""
    limit = max_lines()
    offenders = [
        (path, n)
        for root in roots
        for path in sorted(Path(root).rglob("*.py"))
        if (n := len(path.read_text(encoding="utf-8").splitlines())) > limit
    ]
    for path, n in offenders:
        print(f"{path}: {n} lines > {limit}; split the module")
    return 1 if offenders else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["src", "tests", "scripts"]))
```

### 4.2 Gate-suppression control (round 1 findings 6 and 9; round 2 findings 1–4, 7 and 13)

**Threat:** an agent meets a failing gate and silences it instead of fixing the code. The silencing routes are:
- line-level comments: `# noqa: C901`, `# type: ignore[...]`, `# fmt: off`;
- coverage pragmas, in any spelling coverage accepts: `# pragma: no cover`, `# pragma nocover`, `#pragma:nocover`, `# pragma: no branch`;
- file-level directives: `# ruff: noqa`, `# flake8: noqa: <codes>`, `# mypy: ignore-errors`, a module-top `# type: ignore`;
- skips: `@pytest.mark.skip/skipif/xfail`, module-level `pytestmark`, `pytest.param(..., marks=…)`, `pytest.skip()` or `importorskip` in a test body, `from pytest import mark`;
- moving a test out of the required tier: marking a unit test `@pytest.mark.model`;
- **another config file that overrides `pyproject.toml`**: a nested `ruff.toml`, a root `mypy.ini`, `pytest.ini`, `.coveragerc`, `.importlinter`, `_typos.toml`, `uv.toml`;
- edits to `pyproject.toml`, the scripts or the workflows: `per-file-ignores`, coverage `omit`, a whitelist entry, `ignore_imports`, a raised limit, a deleted CI step; and a `conftest.py` that deselects tests.

Round 2 showed that regex-matching each spelling is an arms race the doc had lost three times (findings r2-1, r2-2, r2-4). So each route is now closed by the cheapest **deterministic** check that does not depend on spelling, and review is the last layer, not the main one.

| Layer | What it catches | Tool / setting | Verified |
|---|---|---|---|
| 1. Unused suppressions | a `noqa` or `type: ignore` that no longer suppresses anything | ruff **RUF100** (in ALL); mypy **`warn_unused_ignores`** (in strict) | RUF100 fired on a stale `noqa: S603` [verified locally in round 1] |
| 2. Blanket suppressions | `# noqa` or `# type: ignore` without codes | ruff **PGH004**, **PGH003**; mypy **`ignore-without-code`** | reviewer-verified in round 2 |
| 3. **Coverage pragmas are inert** | every `pragma … no cover / no branch` spelling | `[tool.coverage.report] exclude_lines` **replaces** coverage's default regex (which is what recognises pragmas), and `partial_branches = []` replaces the `no branch` default | with the old `exclude_also`, `# pragma nocover` on an untested function kept core at 100%; with `exclude_lines` the same seed gives "total of 99 is less than fail-under=100". `# pragma: no branch` on a one-sided `if`: 100% with coverage's default `partial_branches`, 99% (exit 2) with `[]` [verified locally] |
| 4. **File-level directives and pragmas banned everywhere** | `ruff: noqa`, `flake8: noqa` (with or without codes), any `mypy:` comment, `pyright:`, `isort: skip_file`, a `type: ignore` before the module's first statement, and any coverage-pragma spelling (coverage's own regex, case-insensitive) | `scripts/check_suppressions.py`. A whole-file exemption belongs in a reviewed `per-file-ignores` or `[[tool.mypy.overrides]]` entry | each of `# flake8: noqa: S307, TID251, E402` (in domain, where ruff then reported only F401), `# ruff: noqa: E501  # why:`, `# mypy: ignore-errors  # why:`, `# mypy: disable-error-code=…`, a module-top `# type: ignore  # why:`, `# pyright: basic`, `# isort: skip_file` (outside the core, each with a reason) and the five pragma spellings was reported, exit 1 [verified locally] |
| 5. **Core ban** | any line-level `noqa`, `type: ignore`, `fmt: off/skip` or `isort: skip/off` in `domain/`, `app/` (including `app/contract/`), `ports.py` / `ports/` | the same script; `noqa` is matched anywhere in the comment (`\bnoqa\b`) | `# why: x  # noqa: E501`, `#NOQA:E501` in domain and `# fmt: off` in app were reported [verified locally] |
| 6. **Reason required + exact budget** | a line-level suppression elsewhere without `# why: <text>`; a growing count | the same script; the count must **equal** `[tool.scenewise.gates] suppression_budget` | budget 2 on the skeleton; adding a reasoned `# type: ignore[assignment]` mid-module needs the budget raised to 3 [verified locally] |
| 7. **No skipped or xfailed test in CI** | every skip and xfail route above, whatever its spelling | every pytest step in CI writes `--junitxml=pytest.xml`, and the next step fails if the report contains a `<skipped` element (pytest writes both skips and xfails that way). xpass already fails under `strict` | each of module-level `pytestmark = skip`, `pytest.skip()` in a test body, `pytest.param(marks=xfail)`, `from pytest import mark` + `@mark.xfail`, `skipif(True)` and an `importorskip` of a missing module passed pytest (exit 0) and failed the check (exit 1) [verified locally] |
| 8. **`model` only in `tests/contract`** | a test moved into the non-required model tier | `pytest -m model --collect-only -q` in the `test` job; any node id outside `tests/contract/` fails | a `@pytest.mark.model` unit test was deselected by the default run and reported by the check [verified locally] |
| 9. **Config pinned to `/pyproject.toml`** | a stray config file that overrides the gates | every tool gets the file explicitly (table below), and a first `static` step fails if any of `uv.toml`, `ruff.toml`, `.ruff.toml`, `mypy.ini`, `.mypy.ini`, `setup.cfg`, `tox.ini`, `pytest.ini`, `.pytest.ini`, `.coveragerc`, `.importlinter`, `_typos.toml`, `typos.toml`, `.typos.toml` or a nested `pyproject.toml` is in the tree | below [verified locally] |
| 10. Typing escapes | `Any`, `@no_type_check` | mypy `disallow_any_explicit` in core; TID251 bans `typing.no_type_check` | reviewer-verified in round 2 |
| 11. Edits to gate files | everything that remains: `pyproject.toml`, `uv.lock`, `scripts/`, `vulture_whitelist.py`, `.github/` (workflows, CODEOWNERS), every `conftest.py` | **CODEOWNERS** + branch protection, which binds **only under the conditions below** | not testable locally |

**Config pinning, per tool.** Each row is a stray file that silently replaced the gate without the flag, and was ignored with it [verified locally; the stray-file step also failed on every one of these files, plus `uv.toml` and `tests/pyproject.toml`]:

| Tool | Flag in CI | Stray file seeded | Without the flag | With the flag |
|---|---|---|---|---|
| ruff check | `--config pyproject.toml` | `src/scenewise/domain/ruff.toml` with `extend-ignore = ["S307","TID251","E402","F401"]`, plus `import pickle` and `eval` | 1 finding | 4 findings |
| ruff format | `--config pyproject.toml` | `domain/.ruff.toml` with `quote-style = "single"` | "1 file would be reformatted" | clean |
| mypy | `--config-file pyproject.toml` | root `mypy.ini` with `ignore_errors = True` + a seeded `str` → `int` | config replaced (it aborted: no `files`) | the assignment error |
| pytest | `-c pyproject.toml` | root `pytest.ini` with `--deselect` of a failing test; `tests/unit/pytest.ini` (the ini nearest the args) dropping `filterwarnings` | "26 passed, 1 deselected"; "27 passed, 1 warning" | "1 failed" in both |
| coverage | `--cov-config=pyproject.toml`, `coverage report --rcfile=pyproject.toml` | root `.coveragerc` with `fail_under = 10`, `branch = False`, `omit` service | "Required test coverage of 10.0% reached" | 90% threshold, branch data |
| import-linter | `--config pyproject.toml` | root `.importlinter` with only `root_package` + `app -> numpy` | "0 kept, 0 broken", exit 0 | the allow-list breach, exit 1 |
| typos | `--isolated --config pyproject.toml` | `_typos.toml` accepting `teh` | exit 0 | exit 2. **`--config` alone is not enough**: typos merges discovered files with it |
| zizmor | `--no-config` | (not seeded) | — | — |
| deptry, vulture | `--config pyproject.toml` | (both read only `pyproject.toml`; the flag documents it) | — | — |

`tox.ini` and `setup.cfg` lost to `pyproject.toml` for pytest and mypy in the seeds, but they are banned anyway, because the order differs per tool. `uv.toml` beats `[tool.uv]` and uv has no flag to pin its project config: with a root `uv.toml` containing only `required-version = ">=0.1"`, uv printed "The following fields from `[tool.uv]` will be ignored in favor of the `uv.toml` file: required-version, index" and `uv lock --check` still passed [verified locally]. The stray step is the only guard for it.

**What CODEOWNERS can and cannot enforce here (finding r2-13).** Facts from the GitHub docs (about-code-owners, read 2026-10-08, confirmed by the round-2 reviewer): owners need write access; the file is read from the PR's **base** branch, so a PR cannot weaken its own review; invalid lines are skipped silently (errors appear only in the file view and through the `codeowners/errors` API); and a PR author's own approval never counts.
- **It binds only if all of these hold:** agents open PRs under their **own** identity (a bot account or GitHub App) that is not a code owner and has no admin or bypass rights; the maintainer (the code owner) reviews; and the branch ruleset or protection enables "Require review from Code Owners" **and** "Do not allow bypassing the above settings".
- **In a solo repo where agents push with the maintainer's own credentials, it enforces nothing.** The author cannot approve their own PR, so the maintainer either merges as admin (bypass) or turns the rule off; and a token with admin rights can change branch protection itself. Nothing in this document closes that hole. What still binds in that setup are layers 1–10, which run on every PR; but a PR may also edit the workflow that runs them (a `pull_request` run uses the PR's own workflow files), which only review can catch.
- **Cost of the binding setup for a solo maintainer:** every gate-config PR the maintainer authors needs a second identity's approval, or a bypass. That trade-off is open question 7.
- A nightly step that fails on a non-empty `GET /repos/{owner}/{repo}/codeowners/errors` would catch a typo'd owner line. It is not in the workflows, because it needs the real repo to test; see open question 7.

Format facts that decided the `# why:` convention [verified locally in round 1]:
- mypy rejects `# type: ignore[assignment] -- reason` ("Invalid "type: ignore" comment"), but accepts `# type: ignore[assignment]  # why: …`.
- ruff accepts both `# noqa: F401 -- reason` and `# noqa: F401  # why: …`.

So the one convention both tools accept is "directive, then a second comment `# why: …`".

The script uses `tokenize`, so text inside strings is not counted: `S = "# noqa: E501 # pragma: no cover # mypy: ignore-errors"` in domain was ignored [verified locally]. It no longer counts skip markers: layer 7 catches every skip at run time, whatever its spelling. `pytest.importorskip` in a model-tier fixture is still how a module stays importable in the PR tier; in the models job, where every extra is installed, a skip fails layer 7 too.

`scripts/check_suppressions.py` (91 lines; ruff ALL and mypy strict clean [verified locally]):

```python
"""Ban gate suppressions in the core and hold line-level ones to a budget elsewhere.

Rules:

1. Banned everywhere: file-level directives (``# ruff: noqa``, ``# flake8: noqa``,
   ``# mypy: ...``, ``# pyright: ...``, ``# isort: skip_file``, a ``# type: ignore``
   before the first statement) and coverage pragmas (inert: ``exclude_lines`` replaces
   coverage's default regex). A whole-file exemption is a reviewed pyproject.toml entry.
2. No line-level suppression (``noqa``, ``type: ignore``, ``fmt: off|skip``,
   ``isort: skip|off``) under the core paths (domain, app, ports).
3. Every other one carries a reason: ``# noqa: S603  # why: static argv``.
4. Their total equals ``suppression_budget`` in pyproject.toml, so adding one is a
   reviewed config change and removing one lowers the budget.

Skip and xfail markers are not counted here: CI fails on any skipped or xfailed test.
"""

import io
import re
import tokenize
import tomllib
from pathlib import Path

ROOTS = ("src", "tests", "scripts")
CORE = ("src/scenewise/domain/", "src/scenewise/app/", "src/scenewise/ports.py", "src/scenewise/ports/")
FILE_LEVEL = re.compile(
    r"#\s*(?:(?:ruff|flake8)\s*:\s*noqa|mypy\s*:|pyright\s*:|isort\s*:\s*skip_file)"
    r"|pragma[:\s]?\s*no\s*(?:cover|branch)",  # coverage's own default regex, made case-insensitive
    re.IGNORECASE,
)
LINE_LEVEL = re.compile(r"\bnoqa\b|type\s*:\s*ignore|fmt\s*:\s*(?:off|skip)|isort\s*:\s*(?:skip|off)", re.IGNORECASE)
TYPE_IGNORE = re.compile(r"#\s*type\s*:\s*ignore", re.IGNORECASE)
REASON = re.compile(r"#\s*why:\s*\S")
NON_CODE = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING}


def comments(path: Path) -> list[tuple[int, str, bool]]:
    """Return ``(line, text, before_first_statement)`` for every comment token."""
    found: list[tuple[int, str, bool]] = []
    seen_code = False
    for tok in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline):
        if tok.type == tokenize.COMMENT:
            found.append((tok.start[0], tok.string, not seen_code))
        elif tok.type not in NON_CODE:
            seen_code = True
    return found


def check(path: Path) -> tuple[list[str], int]:
    """Return the errors in ``path`` and its count of budgeted suppressions."""
    in_core = path.as_posix().startswith(CORE)
    errors: list[str] = []
    counted = 0
    for line, text, at_top in comments(path):
        where = f"{path}:{line}: {text}"
        if FILE_LEVEL.search(text) or (at_top and TYPE_IGNORE.search(text)):
            errors.append(f"{where}  [file-level directive or coverage pragma: banned; use reviewed config]")
        elif not LINE_LEVEL.search(text):
            continue
        elif in_core:
            errors.append(f"{where}  [suppressions are banned in domain/app/ports]")
        else:
            counted += 1
            if not REASON.search(text):
                errors.append(f"{where}  [add a reason: '  # why: ...']")
    return errors, counted


def budget() -> int:
    """Read ``[tool.scenewise.gates] suppression_budget`` from pyproject.toml."""
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return int(config["tool"]["scenewise"]["gates"]["suppression_budget"])


def main() -> int:
    """Print violations and return 1 if any rule is broken."""
    errors: list[str] = []
    counted = 0
    for path in sorted(p for root in ROOTS for p in Path(root).rglob("*.py")):
        file_errors, file_count = check(path)
        errors += file_errors
        counted += file_count
    allowed = budget()
    if counted != allowed:
        errors.append(f"{counted} suppressions outside the core, budget is {allowed}; a change needs review")
    print("\n".join(errors) or f"suppressions: {counted} (budget {allowed})")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Alternatives considered:
- **Align the script's regex with coverage's and keep pragmas usable outside the core** (the reviewer's first option). Rejected: it keeps a second, spelling-dependent route open; with `exclude_lines` a pragma does nothing anywhere, and an exclusion becomes a reviewed `omit` or `exclude_lines` entry.
- **Count every skip spelling in the script** (round 1). Rejected after finding r2-4: four spellings got through. The JUnit check is spelling-proof.
- **A `pytest_sessionfinish` hook in the root `conftest.py`** instead of the JUnit check. Equivalent, but it lives in a file a nested `conftest.py` can interfere with; the JUnit check lives in the workflow.
- **A ruff-only approach**: there is no ruff rule that bans *specific, justified* suppressions.
- **A pre-commit grep**: hooks are bypassable, and CI is the gate.
- **A suppression baseline file** (as in basedpyright): it is heavier, and the budget achieves the same ratchet.

---

## 5. Coverage

| Tool | Version / date | Source |
|---|---|---|
| coverage.py | **7.16.2**, 2026-09-27 | https://pypi.org/pypi/coverage/json |
| pytest-cov | **7.1.0**, 2026-03-21 | https://pypi.org/pypi/pytest-cov/json |

Relevant options (https://coverage.readthedocs.io/en/latest/config.html, read 2026-10-08):
- `branch`, `source_pkgs`, `relative_files`;
- `patch = ["subprocess"]` (7.10+);
- `core`: the default is `sysmon` on 3.14+ and `ctrace` before, and sysmon has no branch coverage on 3.12/3.13, so leave it unset;
- `fail_under`, which exits 2;
- `exclude_also` (adds to the default exclusion regexes) versus `exclude_lines` (**replaces** them, including the one that recognises `pragma: no cover`), and `partial_branches` (whose default recognises `pragma: no branch`);
- `[report] omit`.

There is no per-package threshold.

Policy:
- **Branch coverage on.**
- **Core = `src/scenewise/domain/*`, `src/scenewise/app/*`, `src/scenewise/ports.py`, `src/scenewise/ports/*`** (q8a FU 5).
  - coverage's `*` matches nested paths: the report listed `app/contract/__init__.py`, `app/contract/envelope.py`, `app/audio.py`, `domain/manifests.py` and `domain/uris.py`, all at 100% [verified locally].
  - **100%, measured from `tests/unit` only**: `COVERAGE_FILE=.coverage.unit pytest -c pyproject.toml tests/unit --cov --cov-config=pyproject.toml --cov-fail-under=0`, then `coverage report --rcfile=pyproject.toml --data-file=.coverage.unit --include="$CORE" --fail-under=100` [verified locally: 100%, exit 0, on 3.12.14, 3.13.16 and 3.14.7].
  - Contract and e2e tests therefore cannot cover core lines without asserting on them (finding 9).
  - Ports' Protocol bodies are `...`, which `exclude_lines` excludes. The same pattern also excludes a `...` body in domain or app (finding r2-21). Accepted, because mypy's `empty-body` error (on by default) is the backstop for any function that returns a value: a seeded `def later(x: int) -> int: ...` in domain gave `Missing return statement [empty-body]` [verified locally]. A `-> None` stub with a `...` body is not caught by either tool; it is caught only by the unit test that should exercise it.
  - **No pragma works anywhere.** `exclude_lines` replaces coverage's default regex, and `partial_branches = []` replaces the `no branch` default, so `# pragma: no cover` in any spelling, and `# pragma: no branch`, exclude nothing; the suppression script also rejects them (§4.2, layers 3–4). An exclusion outside the core is a reviewed `omit` or `exclude_lines` entry.
  - `service/http/health.py` (the watchdog) is not core, but it gets a unit test (FU 5).
- Rejected alternative: a single run with `--cov-context=test` and `coverage report --contexts='^tests/unit/'`. Under `patch = ["subprocess"]` every test errored with a coverage exception, and the filtered report showed 0% [verified locally]. The two-run approach is simpler and robust. Unit tests are fast, so running them twice costs seconds.
- **Overall ≥ 90%** over the PR tier (unit + contract + e2e, synced with `--extra service` only). `[report] omit` covers the adapters whose libraries are not installed there:
  - `adapters/asr/*` (asr / asr-whisper);
  - `adapters/vision/*` (vision);
  - **`adapters/media/images.py`**, because q8a puts Pillow in the `vision` extra;
  - `adapters/llm/anthropic.py` (llm-anthropic);
  - `adapters/storage/gcs.py` and **`adapters/notify/google_id_token.py`** (gcs: google-cloud-storage, google-auth).

  The models job reports them with `coverage report --rcfile=pyproject.toml --omit=__none__ --include='src/scenewise/adapters/*' --fail-under=0`. A CLI `--omit` replaces the config `omit`. **`--fail-under=0` is required** (finding r2-6): without it the command inherits `fail_under = 90` and on the skeleton printed "Coverage failure: total of 36 is less than fail-under=90", exit 2; with it, exit 0 and a 36% adapter table [verified locally, in the all-extras environment]. Whether that number should become a gate is open question 2. Skeleton result in the PR tier: 93.20% on 3.12 and 3.13, 92.83% on 3.14 [verified locally].
- **`patch = ["subprocess"]`** measures `python -m scenewise` started by e2e tests. `__main__.py` went from 0% to covered [verified locally with pytest-cov 7.1.0].
- **Mutation testing** (mutmut 3.8.0, 2026-09-12, https://pypi.org/pypi/mutmut/json) is the honest check behind "100%". It is **not** added as a gate, to keep the gate set proportionate. See open question 8.

---

## 6. Testing strategy

### pytest and plugins

- **pytest 9.1.1** (2026-06-19).
  - 9.0.0's changelog date is 2025-11-05 (https://docs.pytest.org/en/stable/changelog.html), but its PyPI files were uploaded **2025-11-08** (https://pypi.org/pypi/pytest/9.0.0/json) (finding 19).
  - 9.0 added native `[tool.pytest]` and `strict = true` (strict_config, strict_markers, strict_parametrization_ids, strict_xfail).
- **pytest-timeout 2.4.0** (2025-05-05), `timeout = "60"` globally. Under native `[tool.pytest]` **the value must be a string**: `timeout = 60` aborts with "config option 'timeout' expects a string, got int" [verified locally]. Model and nightly jobs pass `--timeout=600` and `--timeout=1800`.
- **pytest-randomly 5.0.0** (2026-09-01) shuffles test order and prints `--randomly-seed=…` for reproduction [verified locally]. The nightly hypothesis job passes `-p no:randomly` so that hypothesis controls randomness alone.
- pytest-xdist 3.8.0 is not needed at this size.
- Tests are packages: `tests/__init__.py` plus one per subdirectory. Contract suites are imported as `tests.contract.*` via `pythonpath = ["."]` and `--import-mode=importlib` [verified locally].
- Every CI invocation is `pytest -c pyproject.toml …`. Without `-c`, pytest uses the ini file nearest the given paths, so a `tests/unit/pytest.ini` silently replaced `[tool.pytest]` (§4.2) [verified locally]. With `-c`, rootdir is still the repo root.
- **Markers: `e2e` and `model` only.** Round 1's `slow` marker was dropped (finding r2-5): it was deselected by `addopts` and no job selected it, so a `slow` test ran nowhere. pytest-timeout already bounds runtime. `model` is allowed only in `tests/contract/` (checked in CI, §4.2 layer 8).
- **No skipped or xfailed test in CI** (§4.2 layer 7). Each CI pytest step writes a JUnit report, and a following step fails if it contains a skip or an xfail. Locally, skips still work (e2e without ffmpeg, model tests without extras); the check runs only in CI, where apt ffmpeg is installed in `test` and every extra in `models`. A broken ffmpeg install therefore fails the e2e tier instead of turning it into skips.

### Test tiers

| Tier | Marker | Runs where | Content |
|---|---|---|---|
| Unit | (none), in `tests/unit` | every PR, 3 Pythons | Pure domain and use cases with fakes (`tests/fakes.py`). The source of the 100% core number. |
| Contract | (none) | every PR | One mixin per port, run against fakes and against every light adapter. |
| E2E | `e2e` | every PR (apt ffmpeg) | CLI and HTTP on ffmpeg-generated media. The session fixture (`tests/e2e/conftest.py`) skips without ffmpeg locally; in CI a skip fails the job [verified locally: 41 passed, 0 skipped with ffmpeg; the skip check failed when ffprobe was missing]. |
| Model | `model`, in `tests/contract` only | `extended.yml`: main, nightly, manual, or a PR with label `run-model-tests` | Real adapters, tiny models, cached `HF_HOME`, `HF_HUB_OFFLINE=1`. No skips allowed. |
| Property (nightly) | — | `extended.yml` schedule/manual | `tests/unit` under the hypothesis `nightly` profile, synced with `--extra service` like the `test` job (finding r2-11) [verified locally: 26 passed]. |

### Contract tests (pattern verified locally)

```python
# tests/contract/recognizer_contract.py
class SpeechRecognizerContract:
    def test_segments_are_ordered(self, recognizer: SpeechRecognizer, speech_wav: Path) -> None:
        segments = recognizer.transcribe(speech_wav, language=None).segments
        assert all(a.span.end <= b.span.start for a, b in pairwise(segments))

# tests/contract/test_fake_recognizer.py
class TestFakeRecognizer(SpeechRecognizerContract):
    @pytest.fixture
    def recognizer(self) -> FakeRecognizer:
        return FakeRecognizer()

# tests/contract/test_parakeet_recognizer.py
pytestmark = pytest.mark.model
class TestParakeetRecognizer(SpeechRecognizerContract):
    @pytest.fixture
    def recognizer(self, tmp_path: Path) -> SpeechRecognizer:
        pytest.importorskip("onnx_asr")
        from scenewise.adapters.asr.parakeet import ParakeetRecognizer   # import after the skip
        return ParakeetRecognizer(model="tiny", device="cpu", cache_dir=tmp_path)
```

The adapter is imported **inside the fixture**. A deselected module is still imported at collection, so a top-level `import onnx_asr` would break the PR tier, where the `asr` extra is not installed. Hence `PLC0415` in the tests ignores.

Required contract suites per port (q8a FU 9):

| Port | Contract cases | Implementations it runs against |
|---|---|---|
| `BlobStore` | round-trip read/write; `read` of an absent URI → `None`; **`WriteConflict` on create-if-absent** (`if_generation=0` on an existing object); **`WriteConflict` on a stale generation** (the fencing case: two writers read generation g, the first CAS wins, the second must fail); allow-list and unknown-scheme rejection in `by_scheme`, which is tested with injected stores | fake (in-memory), `local` (PR tier); `gcs` against an in-memory fake of the client or the fake-gcs-server emulator (open question 2) |
| `Notifier` | POSTs the **pre-serialised `bytes`** unchanged, with `idempotency_key` as `webhook-id`; with an `audience`, adds `Authorization: Bearer <token>` from the injected ID-token provider, and refuses without one; bounded retries end in `RetryableError` | `http_callback` over `httpx.MockTransport` with a fake token provider (PR tier; the bytes, header and both OIDC cases pass on the skeleton [verified locally]); `google_id_token` itself only with real credentials, so it is not contract-tested (it is a 3-line wrapper) |
| `SpeechRecognizer` | segments ordered, non-overlapping, absolute seconds | fake (PR), parakeet and faster-whisper (`model`) |
| `MediaTool`, `ImageReader`, `TextGenerator`, `ImageModerator`, `ZeroShotLabeller` | the q8a §4 docstring contracts (frame order, `max_side`, score ranges) | fakes (PR); ffmpeg (e2e); Pillow, open_clip, nsfw and anthropic (`model`); `openai_compat` over `httpx.MockTransport` (PR) |

### Fixtures made for this project (no downloaded clips)

- **Tones and video:** lavfi `sine`, `anullsrc`, `testsrc2`.
- **Speech:** lavfi **`flite`** (`flite=text='…':voice=slt`, https://ffmpeg.org/ffmpeg-filters.html §9.7, read 2026-10-08) needs `--enable-libflite`.
  - Ubuntu noble's and Debian's `debian/rules` enable it (https://git.launchpad.net/ubuntu/+source/ffmpeg/plain/debian/rules?h=ubuntu/noble ; https://sources.debian.org/data/main/f/ffmpeg/7:8.1.2-2/debian/rules, read 2026-10-08).
  - Commit the few generated fixtures (< 100 kB) with their generator script, and let CI regenerate and diff them.
- **Composite clip:** two `testsrc2` patterns concatenated (a scene cut), plus flite speech.
- **Images:** generated with Pillow or from `testsrc2` frames.
- **HLS fMP4 audio (q8a FU 11),** to exercise the stitch path (`app/audio.py` → `domain/manifests.parse` → init + segments byte-concatenated → one ffmpeg extraction):

  ```
  ffmpeg -f lavfi -i sine=frequency=440:duration=12 -c:a aac -b:a 64k \
         -f hls -hls_time 4 -hls_playlist_type vod -hls_segment_type fmp4 \
         -hls_fmp4_init_filename init.mp4 -hls_segment_filename 'seg%03d.m4s' audio.m3u8
  ```

  Verified with a static ffmpeg 7.1 build (imageio-ffmpeg), not with apt ffmpeg 6.1.1:
  - it produced `init.mp4` (764 B), four `.m4s` segments (about 99 kB in total), and a VOD playlist with `#EXT-X-MAP:URI="init.mp4"` and `#EXT-X-ENDLIST`;
  - the skeleton's `domain.manifests.parse` returned the init plus four segment URIs;
  - the byte-concatenated file decoded to a 16 kHz mono WAV with `Duration: 00:00:12.02, start: 0.000000` [verified locally].

  Use the flite speech source instead of `sine` for ASR contract tests on CI. A master playlist with an `#EXT-X-MEDIA:TYPE=AUDIO` rendition is a hand-written text fixture, which needs no ffmpeg.

### Avoiding large model downloads

| Model | Size (HF API, read 2026-10-08) | Licence |
|---|---|---|
| `Systran/faster-whisper-tiny` / `tiny.en` | model.bin 75.5 MB + tokenizer 2.2 MB | MIT |
| `hf-internal-testing/tiny-random-CLIPModel` | 2.9 MB | no licence field |
| `hf-internal-testing/tiny-random-SiglipModel` | 5.1 MB | no licence field |
| `openai/whisper-tiny` | ~151 MB per format | Apache-2.0 |

The models job is wired as follows:
- `actions/cache` on `.hf-cache`, keyed on `hashFiles('tests/models.lock')` (repo ID + revision per model);
- on a cache miss, `scripts/fetch_models.py` downloads the pinned revisions;
- the tests then run with **`HF_HUB_OFFLINE=1`** (https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables, read 2026-10-08), so a missing model fails instead of downloading.

`fetch_models.py` is a TODO for implementation. The workflow step is in place.

### Property-based testing

- hypothesis **6.168.5** (2026-10-05). Targets:
  - VTT timestamp monotonicity and round-trips;
  - segment-merging invariants;
  - pydantic boundary models in `app/contract/` (`st.from_type` / `st.builds`);
  - and, per q8a FU 10:
    - **`domain.jobs.decide_attempt`**: every `Decision` branch, plus the lease boundary (`lease_until == now`, ±1 ms);
    - **`domain.manifests.parse`**: encrypted (`#EXT-X-KEY` other than `METHOD=NONE`), `#EXT-X-BYTERANGE`, live (no `#EXT-X-ENDLIST`), master vs media playlists, and relative URIs;
    - **`domain.uris.resolve`** for `gs://` (the result stays in the bucket; absolute paths and absolute URIs).
- The skeleton's parser tests cover not-a-playlist, live, encrypted, the init map and relative `gs://` and `https://` URIs, plus a hypothesis property that `gs://` resolution stays in the bucket. All pass, with 100% branch coverage of `manifests.py` and `uris.py` [verified locally].
- The built-in **`ci` profile** is loaded automatically when `CI` is set. It has `derandomize=True`, `database=None`, `deadline=None` and `print_blob=True` [`database None`, `derandomize True` verified locally] (https://hypothesis.readthedocs.io/en/latest/reference/api.html, read 2026-10-08).
- A nightly profile derived from `ci` would replay the same examples every night. So `tests/conftest.py` registers:

```python
settings.register_profile(
    "nightly",
    parent=settings.get_profile("default"),
    derandomize=False,
    max_examples=1000,
)
```

- The scheduled job runs `pytest tests/unit --hypothesis-profile=nightly`. With `CI=true`, the explicit profile wins: "Stopped because settings.max_examples=1000" [verified locally] (finding 8).

---

## 7. Other gates

| Gate | Tool / version | Notes |
|---|---|---|
| Lockfile fresh | `uv lock --check`; `UV_LOCKED=1` | Passes with q8a's two `conflicts` pairs (`ort-cpu`/`ort-cu130`, `torch-cpu`/`torch-cu130`) and the explicit PyTorch indexes; 126 packages resolved [verified locally] (q8a FU 8). |
| Lock routing (q8a FU 8) | `scripts/check_lock.sh` (§13), run in `static` | Reads only `uv.lock`, through `uv export --locked`. It asserts four things: `--extra torch-cpu` yields `torch==2.14.1+cpu ; sys_platform == 'linux'` and `torchvision==0.29.1+cpu` (same marker); `--extra torch-cu130` yields `+cu130` builds of both; `--extra service --extra asr --extra ort-cu130` contains **no** torch or torchvision. Passes on the skeleton. Two negative cases fail as intended: a wrong local tag, and an `asr` extra that transitively pulls open-clip-torch ("FAIL: asr + ort-cu130 pulls torch") [verified locally]. Gotcha found on the way: `uv export … \| grep -q` under `set -o pipefail` fails with "Broken pipe", so the script captures the output first. On macOS the `torch-cpu` source marker is Linux-only, so PyPI's torch 2.14.1 is used there (q8a §9.4). |
| uv version | `[tool.uv] required-version = "==0.12.23"` | uv **0.12.23** (2026-10-03) is the latest (https://pypi.org/pypi/uv/json). setup-uv: "If you do not specify a version, this action will look for a required-version in a uv.toml or pyproject.toml file in the repository root" (https://github.com/astral-sh/setup-uv README, read 2026-10-08). The local run used uv 0.12.23 with this setting [verified locally] (finding 12). |
| Dependency hygiene | deptry 0.25.1 | Clean on the skeleton, with every q8a extra imported by a stub adapter [verified locally]. deptry maps distributions to modules through installed metadata (e.g. pillow → PIL), so the static job syncs all CPU extras. Two settings are needed (q8a FU 12): **`package_module_name_map = { "onnxruntime-gpu" = "onnxruntime" }`**, because the GPU selector is not installed on CPU runners (without it, DEP002 "'onnxruntime-gpu' defined as a dependency but not used" [verified locally]); and **`per_rule_ignores.DEP002 = ["torchvision", "timm"]`**, because both are declared only for index routing and open-clip's floor, and are never imported. https://deptry.com/usage/ (read 2026-10-08). |
| Dead code | **vulture 2.16, `min_confidence = 60`**, `paths = ["src", "vulture_whitelist.py"]`, run as `vulture --config pyproject.toml` | The README assigns 100% to arguments and unreachable code, 90% to imports, and **60% to attributes, classes, functions, methods, properties and variables** (https://github.com/jendrikseipp/vulture, read 2026-10-08). At 60, round 1's skeleton showed 7 findings, all true dead code there; `vulture --make-whitelist src > vulture_whitelist.py` then gives 0 [verified locally]. Framework-registered handlers go in `ignore_decorators = ["@router.*", "@app.*"]` (README "--ignore-decorators"), not the whitelist. **Only the two model-only wire modules, `app/contract/requests.py` and `app/contract/results.py`, are excluded** (finding r2-9), because pydantic fields exist for the JSON shape; `ignore_names = ["model_config"]` covers pydantic's class config everywhere. `envelope.py` and `mapping.py` stay scanned: seeded `dead_mapping()` in `mapping.py` and `dead_env()` in `envelope.py` were both reported, exit 3 [verified locally]; On the skeleton the only field vulture then reported, `Envelope.schema_version`, went into the regenerated whitelist. The whitelist is ruff-excluded and CODEOWNERS-protected. |
| Suppressions | `scripts/check_suppressions.py` | §4.2 |
| Spelling | **typos 1.51.1**, `--isolated --config pyproject.toml` | Clean [verified locally]. `--isolated` is needed: with `--config` alone, typos still merged a stray `_typos.toml` (§4.2). |
| Workflow security | **zizmor 1.30.1 `--offline --no-config .github`**, **gating** in `static`; **online** (`--no-config`, `GH_TOKEN`) in the nightly `supply-chain` job | Offline: no findings on both workflows and `dependabot.yml` [verified locally]. Its `dependabot-cooldown` audit fires unless a `cooldown` is set, so the Dependabot config sets 14 days. The 5 suppressed findings are pedantic `anonymous-definition` infos. **Offline mode skips the audits that verify the SHA pins** (`impostor-commit`, `ref-confusion`, `known-vulnerable-actions`, `stale-action-refs`; zizmor audits page; finding r2-12). Online mode needs a GitHub token; in Actions, `GH_TOKEN: ${{ github.token }}` with `contents: read` should suffice for public-repo reads (not run on GitHub). Locally with a user token: the real workflows gave no findings; a copy with a wrong `# v4.0.0` comment gave `ref-version-mismatch`, and one with a fabricated setup-uv SHA gave `error[impostor-commit]`, exit non-zero; offline mode reported neither [verified locally]. Online stays out of the merge gate because an upstream advisory would fail unrelated PRs. |
| Vulnerabilities | `uv audit --preview-features audit-command` (experimental), in the nightly `supply-chain` job, **which fails** (no `continue-on-error`) | Round 1's `continue-on-error` made the run green whatever it found, so nobody would see it (finding r2-14). Decision: keep it, failing. A red scheduled run notifies the maintainer by GitHub's default notifications, so the failure is the alert; it is never a required check, so new advisories cannot block unrelated merges. Removing it in favour of Dependabot alerts was rejected because whether GitHub's dependency graph reads `uv.lock` for security alerts was not verified. Clean skeleton: "Found no known vulnerabilities … in 125 packages", exit 0; a project pinning `requests==2.19.0`: advisories listed, exit 1 [verified locally]. pip-audit 2.10.1 is the fallback if the preview command changes. |
| Pin updates | Dependabot `github-actions` and `uv` ecosystems | Dependabot updates SHA-pinned actions and the same-line version comment (https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories, read 2026-10-08; uv is listed as `uv`). Whether it bumps `[tool.uv] required-version` is not stated: open question 4. |
| Hooks | prek 0.5.5 or pre-commit 4.6.2 | Local convenience only (https://prek.j178.dev/, read 2026-10-08). |

---

## 8. Open questions (user decisions)

Each item is a decision for the user. The configuration in §11–§13 implements the option marked "current".

1. **Line length: 120 (current) or ruff's default 88?** For 120: fewer wrapped signatures with keyword-only parameters and type annotations. For 88: the ecosystem default, side-by-side diffs fit narrow screens.
2. **Heavy-adapter coverage and the GCS contract.**
   - Coverage: **report only (current)**, or gate the models job's adapter coverage on main? Report only keeps a non-required job from going red over stub-level numbers (36% on the skeleton). A gate would stop real adapters from shipping untested, but needs a threshold chosen once real adapters exist.
   - GCS `BlobStore` contract (FU 9): an in-memory fake of the client in the PR tier (fast, no service, but tests the fake's preconditions, not GCS's), or the fake-gcs-server emulator as a service container (closer to real `ifGenerationMatch` behaviour, slower, not tested here).
3. **`uv audit` (preview) or pip-audit 2.10.1 in the nightly job?** Current: `uv audit`, which reads `uv.lock` directly and needs no extra tool, but is a preview feature whose CLI may change (the job would then fail, visibly). pip-audit is stable but audits an exported requirements file.
4. **uv version bumps:** if Dependabot's `uv` ecosystem does not update `[tool.uv] required-version` (not stated in its docs), bump it by hand with the lock (current), or add a scheduled job that opens the PR? Hand bumps are one line; a job is more config to own.
5. **Licences:** accept the CMU flite voice data for generated speech fixtures, and the `hf-internal-testing/tiny-random-*` models (no licence field), or replace them? Replacing costs real-model downloads in the models job.
6. **q8a naming vs ruff N818:** rename `WriteConflict` to `WriteConflictError` (recommended; the core ban makes an inline `noqa` impossible), or add a reviewed per-file ignore `"src/scenewise/ports.py" = ["N818"]` to keep q8a's name?
7. **Who may change the gates (CODEOWNERS identity; finding r2-13).**
   - Option A, binding: agents push and open PRs from a separate bot account or GitHub App without admin or bypass rights; the maintainer is the only code owner; the ruleset requires code-owner review and disallows bypass. For: gate edits by agents cannot merge unseen. Against: every gate-config PR the maintainer writes needs a second identity's approval or a temporary bypass, and a second account to manage.
   - Option B, routing only: agents use the maintainer's credentials; CODEOWNERS only marks gate files in the PR view. For: no extra identity. Against: CODEOWNERS enforces nothing, and an agent PR can also edit the workflow that runs the gates.
   - Either way: add a nightly step that fails on a non-empty `codeowners/errors` API response? It needs the real repo to test.
8. **Mutation testing:** add a nightly advisory `mutmut` run on `domain` once it has real code (honest check behind "100%", costs runtime and triage), or not (current)?
9. **macOS dev ffmpeg:** Homebrew's build probably lacks libflite (not verified). Commit the generated fixtures plus their generator script (current), or require a flite-enabled ffmpeg locally?
10. **Hook runner:** prek 0.5.5 or pre-commit 4.6.2 as the documented default? Hooks are local convenience only; CI is the gate.
11. **Pillow placement (q8a):** keep `pillow` in the `vision` extra (current; `adapters/media/images.py` is then omitted from PR-tier coverage), or move it to the base dependencies so the PR tier can contract-test `ImageReader`, which `Dependencies` needs even without vision models?
12. **google-auth placement (q8a; finding r2-8):** OIDC callbacks need google-auth, which q8a puts in the `gcs` extra.
    - Current: leave it there; a deployment with `callback_auth = "oidc"` must install `gcs`. No q8a change, but the extra's name no longer says what it is for.
    - Alternative: an `oidc` extra with `google-auth[requests]` (clear, one more extra), or the same in the base dependencies (simplest, but every install gains google-auth 2.61.0 with its locked dependencies `cryptography` and `pyasn1-modules`, plus `requests` for `google.auth.transport.requests`, which the `gcs` extra currently brings in through google-cloud-storage). The `[requests]` part matters: plain `google-auth` does not depend on `requests` in the lock.
    - Either way, q8a's tree gains `adapters/notify/google_id_token.py` (§2).
13. **Online zizmor in the merge gate?** Current: offline in `static` (deterministic), online nightly. Moving online to `static` would catch a bad pin in the PR that introduces it, but an upstream advisory or API outage would then fail unrelated PRs.

Closed this round:
- Skip and xfail markers (CI fails on any skip; the `slow` marker is gone).
- Config overrides (pinned on every tool, stray files rejected).
- The `audit` job (kept as the failing nightly `supply-chain` job, with online zizmor).
- The duplicate q8a deny-list contract (dropped).

Closed earlier:
- Python floor (U2: 3.12, matrix 3.12–3.14).
- Module size for tests (one 500-line limit for all roots).
- Second type checker (dropped from CI).
- tach ownership (§3; irrelevant).
- Stdlib-only domain (custom allow-list contract).
- The q8a follow-ups (all 12, §10.1).

---

## 9. Sources (all read 2026-10-08)

- PyPI JSON API for every version, date and classifier: `https://pypi.org/pypi/<name>/json`; pytest 9.0.0 upload date: https://pypi.org/pypi/pytest/9.0.0/json ; dtach: https://pypi.org/pypi/dtach/json
- mypy changelog: https://mypy.readthedocs.io/en/stable/changelog.html
- ty: https://pypi.org/project/ty/ ; pyrefly: https://pyrefly.org/blog/v1.0/ ; basedpyright: https://docs.basedpyright.com/latest/
- ruff: https://docs.astral.sh/ruff/rules/ , https://docs.astral.sh/ruff/settings/ , https://docs.astral.sh/ruff/formatter/ ; local `ruff rule --all`, `ruff config lint.pylint`
- import-linter: https://import-linter.readthedocs.io/en/stable/contract_types/ , …/contract_types/layers/ , …/contract_types/protected/ , …/contract_types/forbidden/ , https://import-linter.readthedocs.io/en/stable/custom_contract_types/
- tach releases: GitHub API `repos/tach-org/tach/releases`
- coverage: https://coverage.readthedocs.io/en/latest/config.html
- pytest: https://docs.pytest.org/en/stable/changelog.html , https://docs.pytest.org/en/stable/reference/customize.html
- hypothesis: https://hypothesis.readthedocs.io/en/latest/reference/api.html
- vulture: https://github.com/jendrikseipp/vulture (README)
- deptry: https://deptry.com/usage/ ; prek: https://prek.j178.dev/
- setup-uv: https://github.com/astral-sh/setup-uv (README; release and SHA data via GitHub API for astral-sh/setup-uv, actions/checkout, actions/cache)
- zizmor audits (offline vs online): https://docs.zizmor.sh/audits/ (online-only audits as cited by the round-2 reviewer; behaviour verified locally with zizmor 1.30.1)
- GitHub Actions events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows ("By default, a workflow only runs when a pull_request event's activity type is opened, synchronize, or reopened"; `labeled` is available)
- CODEOWNERS: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
- Dependabot ecosystems: https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories
- ubuntu-latest → 26.04 (2026-10-19 to 2026-11-19): https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration
- Runner images: GitHub API `repos/actions/runner-images/contents/images/ubuntu/Ubuntu2404-Readme.md`, `Ubuntu2604-Readme.md`
- ffmpeg flite: https://ffmpeg.org/ffmpeg-filters.html ; Debian/Ubuntu rules: URLs in §6
- AnimMouse/setup-ffmpeg: GitHub API `repos/AnimMouse/setup-ffmpeg` (release v1.2.5, 2026-06-11; README: Ubuntu builds from BtbN/FFmpeg-Builds); BtbN dependency list: GitHub API `repos/BtbN/FFmpeg-Builds/contents/scripts.d` (no flite)
- HF: https://huggingface.co/api/models/Systran/faster-whisper-tiny , …/hf-internal-testing/tiny-random-CLIPModel , …/hf-internal-testing/tiny-random-SiglipModel , …/openai/whisper-tiny ; https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables

---

## 10. Review round 1 — resolution

Every finding was re-checked. "Verified" means rerun on the q8b-rev skeleton on 2026-10-08. This table is kept as the round-1 record. Where round 2 changed a resolution (row 6's suppression layers, row 21's `continue-on-error` audit, and the `app/contract/` vulture exclusion in §10.1), §15 and the current sections govern.

| # | Severity | Resolution |
|---|---|---|
| 1 | wrong | **Fixed.** Reproduced: without `tests/__init__.py`, mypy aborts with "Source file found twice". Tests are now packages (INP001 enforced), and `explicit_package_bases = true` + `mypy_path = ["src", "."]` are kept as well. One mypy run over `files = ["src","tests","scripts"]` is clean (§1). |
| 2 | wrong | **Fixed.** Reproduced: I001 on `from tests.contract…` in the no-`__init__` layout with `src = ["src","tests"]`. Now `src = ["src"]` and `known-first-party = ["scenewise", "tests"]`; clean (§2). |
| 3 | wrong | **Fixed.** The GitHub docs confirm the default types exclude `labeled`. Models moved to `extended.yml` with `pull_request: types: [opened, synchronize, reopened, labeled]`, so labelling no longer reruns all of CI (§13). |
| 4 | design | **Fixed.** Reproduced PLR0913 + PLR0917 on a 6-fixture test. Tests ignore PLR0913, PLR0917, FBT001 and SLF001; `src` constructors are keyword-only. ARG002 is kept (use `usefixtures`). |
| 5 | design | **Fixed (60 + whitelist).** The README confidence table was confirmed. At 60 vulture found true dead code in the skeleton. |
| 6 | missing | **Fixed.** Seven-layer mechanism in §4.2: RUF100/PGH003/PGH004, mypy `warn_unused_ignores`/`ignore-without-code`, a core ban, a `# why:` reason, an exact budget, CODEOWNERS, and `disallow_any_explicit`. Mypy rejects `-- reason` after `type: ignore`, hence the `# why:` convention. |
| 7 | design | **Fixed, in q8a's terms.** `layers = ["service", "adapters \| app", "ports", "domain"]` encodes q8a's arrows exactly. The literal 5-layer list would allow adapters → app, so q8a §1.5 rule 2's "already forbids" holds only for `service`. Seeded adapters → app and adapters → app.contract are both caught (§3). |
| 8 | design | **Fixed.** `nightly` derives from `default`, with `derandomize=False` and 1000 examples; a scheduled job runs it; `HF_HUB_OFFLINE=1` and `schedule:` are wired in `extended.yml`. |
| 9 | design | **Fixed.** Core 100% comes from a unit-only data file. The coverage-contexts alternative was tried and rejected (it errors under `patch=subprocess`). Mutation testing is left as open question 8. |
| 10 | design | **Fixed.** `max-returns = 6`; the others are kept; limits change only via CODEOWNERS-protected config. |
| 11 | design | **Fixed.** 500 physical lines, read from pyproject; CI calls the script without arguments, so the roots match (`src tests scripts`). The pylint one-liner is listed as the fallback. |
| 12 | missing | **Fixed.** `[tool.uv] required-version = "==0.12.23"`, which setup-uv reads per its README. Verified with uv 0.12.23. |
| 13 | missing | **Fixed.** pytest-timeout 2.4.0 (it needs `timeout = "60"` as a string under native TOML, verified) and pytest-randomly 5.0.0 added. xdist was not added. |
| 14 | missing | **Fixed (rejected option recorded).** AnimMouse/setup-ffmpeg v1.2.5 (2026-06-11) is maintained, but its Ubuntu builds come from BtbN/FFmpeg-Builds, whose `scripts.d` has no flite, so speech fixtures could not be generated. apt stays. ffmpeg is installed only in the test and models jobs. |
| 15 | unsupported | **Fixed, and corrected beyond the review.** DetachHead has released tach since **v0.32.0 (2025-11-19)**, not 0.35.0. Gauge's last release was v0.29.0 (2025-04-18); the dtach fork ran 0.30.2–0.31.2 (Oct–Nov 2025). |
| 16 | minor | **Fixed.** ANN201 was dropped from the test ignores; tests stay mypy-strict. |
| 17 | minor | **Fixed.** 970 coded rules: 812 stable, 141 preview, 17 removed. |
| 18 | minor | **Fixed.** All 12 `lint.pylint` keys are listed. |
| 19 | minor | **Fixed.** Changelog date 2025-11-05; PyPI upload 2025-11-08. |
| 20 | minor | **Fixed.** Reproducibility is attributed to the dev-group pin + lock; `required-version = "==0.16.10"`. |
| 21 | minor | **Fixed.** Plain `uv sync` (dev is a default group); `audit` is nightly-only with `continue-on-error: true`; `fail-fast: false`. |
| 22 | design | **Fixed.** pyrefly was removed from CI. vulture is fixed per finding 5. zizmor moved into the gating `static` job (offline, deterministic). |


### 10.1 q8a "Follow-ups for q8b" — resolution

q8a was finalised after review round 1. Each of its 12 follow-ups was re-checked against q8a's final package tree (§1.4), dependency rule (§1.5) and extras (§9.4).

| FU | q8a asks | Resolution |
|---|---|---|
| 1 | `exhaustive_ignores = ["__main__"]`; exercise it with a `__main__.py` | **Done.** The skeleton has `__main__.py`. Without the setting, the layers contract reports `scenewise.__main__` as not listed [verified locally]. |
| 2 | add onnxruntime, onnx_asr, torchvision, PIL and numpy to the ports/app forbidden list; pydantic stays allowed in app | **Done, verbatim** as the contract "Ports and use cases do not import heavy or IO libraries" (q8a's full rule-6 list). Also backed by the stricter allow-list contract (app: pydantic, pydantic_core, structlog). |
| 3 | forbidden `service.http`/`service.cli` → `adapters` | **Done as a superset:** a `protected` contract with only `service.bootstrap` allowed. Seeded `service.http.routes` and `service.cli` imports were both caught. |
| 4 | seeded test `adapters/notify` → `app.contract` | **Done.** Caught by `adapters \| app`. With q8a's literal 5-layer list this import would be **allowed** (§3). |
| 5 | coverage includes `app/contract/*`, `app/audio.py`, `domain/manifests.py`, `domain/uris.py`; a unit test for `service/http/health.py` | **Done.** `--include` globs listed all of them at 100% from unit tests; the watchdog has a unit test (§5). |
| 6 | size gate: contract package, ffmpeg split, `ports/` split; no exemptions | **Done.** The limit is 500 lines (finding 11), with no exemptions; every ports setting covers both `ports.py` and `ports/` (§4.1). |
| 7 | models job adds `--extra ort-cpu --extra torch-cpu`; drop the placeholder note | **Done.** `static` and `models` sync `--extra service --extra asr --extra asr-whisper --extra llm-anthropic --extra vision --extra gcs --extra ort-cpu --extra torch-cpu`. That exact set synced and ran on the skeleton (macOS; torch from PyPI there) [verified locally]. |
| 8 | `uv lock --check` with both conflict pairs; script asserting torch routing and torch-free ASR | **Done.** `scripts/check_lock.sh` (§7, §13), verified with positive and negative cases. |
| 9 | `Notifier` takes `bytes`; `BlobStore` contract covers `WriteConflict` on create-if-absent and on a stale generation, for local and gcs | **Done** as the required contract suites (§6). The Notifier bytes and idempotency-key case runs on the skeleton. How to run GCS is open question 2. |
| 10 | hypothesis on `decide_attempt`, `manifests.parse`, `uris.resolve` (gs://) | **Done** as listed targets (§6). The manifests and gs:// cases run on the skeleton. `decide_attempt` is not in the skeleton. |
| 11 | HLS fMP4 audio fixture via `-f hls -hls_segment_type fmp4` | **Done.** The exact command, parse, stitch and extraction were verified with static ffmpeg 7.1 (§6). |
| 12 | deptry maps `onnxruntime-gpu` → `onnxruntime` | **Done**, plus `DEP002` ignores for `torchvision` and `timm` (routing-only declarations) [verified locally]. |

Also found while applying q8a's final tree, and fixed [verified locally]:
- **mypy strict needs `ignore_missing_imports` for six untyped libraries** (§1).
- **bootstrap's onnxruntime/torch probes** need named `ignore_imports` on the service contract (§3).
- **vulture must exclude `app/contract/`** (§7).
- **Pillow sits in `vision`**, so `images.py` joins the PR-tier coverage `omit` (open question 11).
---

## 11. Complete `pyproject.toml` tool section

Final after round 2. Checked by script against the skeleton's `pyproject.toml` that every round-2 run used: the dev group appears there verbatim, and everything from `# ---- project gates` on, followed by the §12 block, is byte-identical to the end of that file [verified locally]. Only the `[tool.uv]` lines differ: here they are abbreviated to the one key this document adds. The static gates ran with all CPU extras on CPython 3.14.7; the PR-tier tests ran on 3.12.14, 3.13.16 and 3.14.7, all green: static gates exit 0, core 100% from unit tests, overall 93.20% / 93.20% / 92.83%, "41 passed, 2 deselected", no skips. `[project]`, the extras and the rest of `[tool.uv]` are q8a's. Only the dev group, `required-version` and the other tool tables are this document's.

**This file is the only tool configuration in the repo.** CI rejects `uv.toml`, `ruff.toml`, `.ruff.toml`, `mypy.ini`, `.mypy.ini`, `setup.cfg`, `tox.ini`, `pytest.ini`, `.pytest.ini`, `.coveragerc`, `.importlinter`, `_typos.toml`, `typos.toml`, `.typos.toml` and nested `pyproject.toml` files, and passes this file explicitly to every tool (§4.2).

Changes from round 1: `suppression_budget` counts line-level suppressions only; `max-bool-expr` and the `slow` marker removed; `untyped_calls_exclude` for google-auth; coverage `exclude_lines` + `partial_branches = []` instead of `exclude_also`; `google_id_token.py` in the coverage `omit`; vulture excludes two modules instead of `app/contract/`, plus `ignore_names`; the duplicate deny-list contract removed (§12).

```toml
[dependency-groups]
dev = [
  "mypy==2.4.0",
  "ruff==0.16.10",
  "import-linter==2.15",
  "pytest==9.1.1",
  "pytest-cov==7.1.0",
  "pytest-timeout==2.4.0",
  "pytest-randomly==5.0.0",
  "coverage[toml]==7.16.2",
  "hypothesis==6.168.5",
  "deptry==0.25.1",
  "vulture==2.16",
]

# ---------------------------------------------------------------- uv
[tool.uv]                          # q8a §9.4 owns this table; q8b adds one key
required-version = "==0.12.23"     # setup-uv installs exactly this; bump by PR
# conflicts = [...ort-cpu/ort-cu130..., ...torch-cpu/torch-cu130...]   (q8a §9.4, unchanged)
# [tool.uv.sources] torch/torchvision and [[tool.uv.index]] pytorch-cpu / pytorch-cu130     (q8a §9.4, unchanged)

# ---------------------------------------------------------------- project gates (read by scripts/)
[tool.scenewise.gates]
max_module_lines = 500             # physical lines, src + tests + scripts
suppression_budget = 2             # line-level noqa / type: ignore outside domain, app, ports

# ---------------------------------------------------------------- ruff
[tool.ruff]
required-version = "==0.16.10"
target-version = "py312"
line-length = 120
src = ["src"]
extend-exclude = ["vulture_whitelist.py"]   # generated by `vulture --make-whitelist`, reviewed by hand

[tool.ruff.lint]
select = ["ALL"]
ignore = [
  "D203", "D213",   # mutually exclusive pydocstyle pairs (google convention below)
  "COM812",         # conflicts with ruff format (documented)
  "CPY001",         # no per-file copyright header
  "TD002",          # TODO author tag not required; TD003 (issue link) is enforced
  "FIX002",         # TODO allowed when it links an issue
  "DOC",            # pydoclint is preview-only in 0.16.x; not enforcing section lists
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = [
  "S101",                # assert is the pytest idiom
  "D1",                  # no docstrings required on test modules/functions/classes
  "PLR2004",             # literal expectations
  "PLR0913", "PLR0917",  # pytest injects fixtures as positional parameters
  "FBT001",              # parametrized bool parameters
  "SLF001",              # tests may inspect private state
  "PLC0415",             # heavy adapters are imported inside fixtures, after importorskip
]
"scripts/**" = ["INP001", "T201"]   # standalone scripts, print is their output
"src/scenewise/service/bootstrap.py" = ["PLC0415"]   # the only lazy imports in src (q8a §1.5 rule 4)

[tool.ruff.lint.isort]
known-first-party = ["scenewise", "tests"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.pylint]
max-args = 5
max-positional-args = 3    # src: constructors and options use keyword-only parameters (`*,`)
max-branches = 10
max-returns = 6            # ruff default; mapping functions need early returns
max-statements = 40

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"torch.load".msg = "Load weights with safetensors; torch.load unpickles arbitrary code."
"pickle".msg = "No pickle: untrusted model/cache files must not execute code."
"subprocess.call".msg = "Use subprocess.run(check=True) via the ffmpeg adapter."
"typing.no_type_check".msg = "Do not switch off type checking; fix the types."

[tool.ruff.lint.flake8-pytest-style]
fixture-parentheses = false
mark-parentheses = false

[tool.ruff.format]
docstring-code-format = true

# ---------------------------------------------------------------- mypy
[tool.mypy]
python_version = "3.12"
files = ["src", "tests", "scripts"]
mypy_path = ["src", "."]
explicit_package_bases = true
strict = true
warn_unreachable = true
enable_error_code = [
  "ignore-without-code", "redundant-expr", "truthy-bool", "possibly-undefined",
  "redundant-self", "unused-awaitable", "explicit-override", "mutable-override",
  "deprecated", "exhaustive-match",
]
plugins = ["pydantic.mypy"]
untyped_calls_exclude = ["google.oauth2.id_token"]   # ships py.typed, but fetch_id_token is unannotated

[[tool.mypy.overrides]]
module = ["scenewise.domain.*", "scenewise.app.*", "scenewise.ports", "scenewise.ports.*"]
disallow_any_explicit = true

[[tool.mypy.overrides]]
# installed but untyped (no py.typed, no stubs) as of 2026-10-08; only adapters and bootstrap import them
module = ["onnxruntime.*", "faster_whisper.*", "ctranslate2.*", "open_clip.*", "torchvision.*", "google.cloud.*"]
ignore_missing_imports = true

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true

# ---------------------------------------------------------------- pytest
[tool.pytest]
minversion = "9.0"
strict = true
testpaths = ["tests"]
addopts = ["-ra", "--import-mode=importlib", "-m", "not model"]
markers = [
  "e2e: end-to-end tests that need ffmpeg on PATH",
  "model: tests that load real (tiny) ML models; tests/contract only; opt-in",
]
filterwarnings = ["error"]
pythonpath = ["."]          # lets tests import tests.contract.* shared suites
timeout = "60"              # pytest-timeout; the model tier overrides with --timeout

# ---------------------------------------------------------------- coverage
[tool.coverage.run]
branch = true
source_pkgs = ["scenewise"]
relative_files = true
patch = ["subprocess"]       # measure `python -m scenewise` started by e2e tests

[tool.coverage.report]
fail_under = 90
omit = [                     # heavy-extra adapters: measured in the models job, not the PR tier
  "src/scenewise/adapters/asr/*",
  "src/scenewise/adapters/vision/*",
  "src/scenewise/adapters/media/images.py",            # Pillow ships in the vision extra (q8a §9.4)
  "src/scenewise/adapters/llm/anthropic.py",
  "src/scenewise/adapters/storage/gcs.py",
  "src/scenewise/adapters/notify/google_id_token.py",  # google-auth ships in the gcs extra (q8a §9.4)
]
show_missing = true
skip_covered = true
# exclude_lines REPLACES coverage's default, so no "pragma: no cover" spelling excludes anything.
exclude_lines = [
  "if TYPE_CHECKING:",
  "^\\s*\\.\\.\\.$",           # Protocol bodies; mypy's empty-body error is the backstop elsewhere
  "@overload",
]
partial_branches = []          # likewise disables "pragma: no branch"

[tool.coverage.paths]
source = ["src/", "*/site-packages/"]

# ---------------------------------------------------------------- deptry / vulture / typos
[tool.deptry]
known_first_party = ["scenewise"]

[tool.deptry.package_module_name_map]
onnxruntime-gpu = "onnxruntime"     # GPU selector: same import name (q8a §9.4); not installed on CPU runners

[tool.deptry.per_rule_ignores]
DEP002 = ["torchvision", "timm"]     # declared only to route torchvision via the PyTorch index / pin open-clip's floor

[tool.vulture]
paths = ["src", "vulture_whitelist.py"]
min_confidence = 60
exclude = [                          # model-only wire modules: fields exist for the JSON shape
  "src/scenewise/app/contract/requests.py",
  "src/scenewise/app/contract/results.py",
]
ignore_names = ["model_config"]      # pydantic class configuration
ignore_decorators = ["@router.*", "@app.*"]  # FastAPI-registered handlers

[tool.typos.files]
extend-exclude = ["uv.lock", "tests/fixtures/**"]
```

Companion files:
- `scripts/check_module_size.py` (§4.1), `scripts/check_suppressions.py` (§4.2), `scripts/import_contracts.py` (§3), `scripts/check_lock.sh` (§13);
- `tests/conftest.py` with the `nightly` profile (§6);
- `vulture_whitelist.py` (generated, then hand-reviewed);
- `.github/CODEOWNERS` (§13).

---

## 12. import-linter contracts (part of `pyproject.toml`)

Six contracts. Clean skeleton: "Contracts: 6 kept, 0 broken"; the service contract reports "2 ignored imports". Seeds: the allow-list, layers and protected cases in §3 each broke the expected contract [verified locally].

```toml
[tool.importlinter]
root_package = "scenewise"
include_external_packages = true
contract_types = ["allowed_externals: scripts.import_contracts.AllowedExternalsContract"]

[[tool.importlinter.contracts]]
name = "Layers: service > (adapters | app) > ports > domain"
type = "layers"
containers = ["scenewise"]
layers = ["service", "adapters | app", "ports", "domain"]
exhaustive = true
exhaustive_ignores = ["__main__"]

[[tool.importlinter.contracts]]
name = "Adapter kinds are independent of each other"
type = "independence"
modules = ["scenewise.adapters.*"]

[[tool.importlinter.contracts]]
name = "Only the composition root imports adapters"
type = "protected"
protected_modules = ["scenewise.adapters"]
allowed_importers = ["scenewise.service.bootstrap"]

[[tool.importlinter.contracts]]
name = "Domain and ports: stdlib only (q8a §1.5 rule 6, as an allow-list)"
type = "allowed_externals"
source_modules = ["scenewise.domain", "scenewise.ports"]

[[tool.importlinter.contracts]]
name = "Use cases: stdlib, pydantic and structlog only (q8a §1.5 rule 6, as an allow-list)"
type = "allowed_externals"
source_modules = ["scenewise.app"]
allowed = ["pydantic", "pydantic_core", "structlog"]

[[tool.importlinter.contracts]]
name = "Driving side imports no ML or cloud SDK (bootstrap's start-up probes excepted)"
type = "forbidden"
source_modules = ["scenewise.service"]
forbidden_modules = [
  "torch", "torchvision", "onnxruntime", "onnx_asr", "ctranslate2", "faster_whisper",
  "open_clip", "timm", "transformers", "huggingface_hub", "safetensors", "numpy", "PIL",
  "anthropic", "google",
]
allow_indirect_imports = true   # bootstrap reaches adapters, and through them these libraries, by design
ignore_imports = [
  "scenewise.service.bootstrap -> onnxruntime",   # CUDAExecutionProvider probe (q8a §9.4)
  "scenewise.service.bootstrap -> torch",         # torch.version.cuda probe (q8a §9.4)
]
```

When a new third-party dependency is added, the allow-list contracts reject it in `domain`, `ports` and `app` automatically. Only the service contract's deny-list may need a new entry.

---

## 13. CI job list and workflows

Versions (GitHub API, read 2026-10-08):

| Action | Version | SHA (re-verified) |
|---|---|---|
| `actions/checkout` | v7.0.1 (2026-07-20) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `astral-sh/setup-uv` | v10.2.0 (2026-09-21) | `c18668ad3cf93ea998bef934396af7bb5c839dc7` |
| `actions/cache` | v6.1.0 (2026-06-26) | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |

Other workflow choices:
- **ffmpeg from apt.** noble ships 6.1.1 with libflite. FedericoCarboni/setup-ffmpeg's last release was 2024-02-04. AnimMouse/setup-ffmpeg v1.2.5 lacks flite (§10, finding 14).
- **`runs-on: ubuntu-24.04`.** `ubuntu-latest` moves to 26.04 between 2026-10-19 and 2026-11-19.
- **Extras (q8a FU 7).** The `static` and `models` jobs sync every extra plus the CPU selectors: `uv sync --extra service --extra asr --extra asr-whisper --extra llm-anthropic --extra vision --extra gcs --extra ort-cpu --extra torch-cpu`. mypy, deptry and vulture need the real packages, and q8a's `conflicts` forbid selecting both members of a pair. The `test` job syncs `--extra service` only (FastAPI for the HTTP e2e tests). It runs fakes, light adapters and e2e. Both sync commands ran on the skeleton [verified locally on macOS; on Linux the `torch-cpu` extra resolves `+cpu` builds per the lock check].

| Workflow | Job | Trigger | Gates | Required for merge |
|---|---|---|---|---|
| `ci.yml` | `static` | PR, push main | stray config files, lock, lock routing, format, lint, mypy, import-linter, module size, suppressions, deptry, vulture, typos, zizmor (offline) | yes |
| `ci.yml` | `test` ×3 (3.12, 3.13, 3.14), `fail-fast: false` | PR, push main | `model` only in `tests/contract`; core 100% (unit only); all PR tiers + overall 90%; no skipped or xfailed test | yes |
| `extended.yml` | `models` | push main, nightly, manual, PR when labelled `run-model-tests` or pushed while carrying it | tiny real models, offline, no skips; adapter coverage reported with `--fail-under=0` | no (a required check would block unlabelled PRs) |
| `extended.yml` | `property-nightly` | nightly, manual | hypothesis `nightly` profile, `--extra service` | no |
| `extended.yml` | `supply-chain` | nightly, manual | `uv audit`; zizmor online (pins, impostor commits); the job **fails** on findings | no (a red scheduled run notifies) |

Concurrency (finding r2-10). `ci.yml` keeps one group per ref with `cancel-in-progress`, which is right for PRs and harmless on main. `extended.yml` puts the event name into the group and cancels only for `pull_request`, so a merge to main no longer cancels a running nightly. A `labeled` event for any label other than `run-model-tests` gets a group of its own (the run id), so it neither cancels nor replaces a running model job, and the `models` job's `if` skips it. These expressions were checked by zizmor's parser only; their runtime behaviour on GitHub was not tested.

Each step's command was run on the skeleton exactly as written (with a local ffprobe shim; see the method note at the top). zizmor offline reports no findings on both workflows and `dependabot.yml`; zizmor online (with a user token) also reports none [verified locally]. The YAML was not run on GitHub.

`.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:            # default types: opened, synchronize, reopened
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
env:
  UV_LOCKED: "1"
  HF_HUB_DISABLE_TELEMETRY: "1"
  CORE: "src/scenewise/domain/*,src/scenewise/app/*,src/scenewise/ports.py,src/scenewise/ports/*"

jobs:
  static:                  # every tool is pointed at /pyproject.toml explicitly; stray config files fail first
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { persist-credentials: false }
      - name: all tool config lives in /pyproject.toml
        run: |
          stray=$(git ls-files --cached --others --exclude-standard \
            | grep -E '(^|/)(uv\.toml|\.?ruff\.toml|\.?mypy\.ini|setup\.cfg|tox\.ini|\.?pytest\.ini|\.coveragerc|\.importlinter|_?\.?typos\.toml)$|/pyproject\.toml$' || true)
          if [ -n "$stray" ]; then echo "::error::tool config must live in /pyproject.toml; remove:"; echo "$stray"; exit 1; fi
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7  # v10.2.0
        with: { enable-cache: true }   # uv version comes from [tool.uv] required-version
      - run: uv lock --check
      - run: bash scripts/check_lock.sh
      - run: uv sync --extra service --extra asr --extra asr-whisper --extra llm-anthropic --extra vision --extra gcs --extra ort-cpu --extra torch-cpu
      - run: uv run ruff format --config pyproject.toml --check .
      - run: uv run ruff check --config pyproject.toml --output-format=github .
      - run: uv run mypy --config-file pyproject.toml
      - run: uv run lint-imports --no-cache --config pyproject.toml
      - run: uv run python scripts/check_module_size.py
      - run: uv run python scripts/check_suppressions.py
      - run: uv run deptry --config pyproject.toml src
      - run: uv run vulture --config pyproject.toml
      - run: uvx typos@1.51.1 --isolated --config pyproject.toml
      - run: uvx zizmor@1.30.1 --offline --no-config .github

  test:                    # unit + contract (fakes, light adapters) + e2e on generated media
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix: { python: ["3.12", "3.13", "3.14"] }
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7  # v10.2.0
        with: { enable-cache: true, python-version: "${{ matrix.python }}" }
      - run: sudo apt-get update && sudo apt-get install -y --no-install-recommends ffmpeg
      - run: uv sync --extra service
      - name: model marker only in tests/contract
        run: |
          bad=$(uv run pytest -c pyproject.toml -m model --collect-only -q | grep '::' | grep -v '^tests/contract/' || true)
          if [ -n "$bad" ]; then echo "::error::model-marked tests outside tests/contract:"; echo "$bad"; exit 1; fi
      - name: core coverage from unit tests only (100%)
        env: { COVERAGE_FILE: .coverage.unit }
        run: |
          uv run pytest -c pyproject.toml tests/unit --cov --cov-config=pyproject.toml --cov-report= --cov-fail-under=0
          uv run coverage report --rcfile=pyproject.toml --data-file=.coverage.unit --include="$CORE" --fail-under=100
      - name: all PR tiers, overall coverage (90%)
        run: uv run pytest -c pyproject.toml --cov --cov-config=pyproject.toml --cov-report=xml --junitxml=pytest.xml
      - name: no skipped or xfailed test in CI
        run: |
          if grep -q '<skipped' pytest.xml; then
            echo "::error::CI runs every selected test; skips and xfails are not allowed:"
            grep -o '<testcase classname="[^"]*" name="[^"]*"[^>]*><skipped[^>]*' pytest.xml
            exit 1
          fi
```

`.github/workflows/extended.yml`:

```yaml
name: extended
on:
  push:
    branches: [main]
  pull_request:
    types: [opened, synchronize, reopened, labeled]
  schedule:
    - cron: "17 3 * * *"   # nightly, default branch
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  # One group per event kind, so a merge never cancels the nightly. Labelling a PR with any other
  # label gets a group of its own (the run id), so it neither cancels nor replaces a model run.
  group: >-
    ${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}-${{
    github.event.action == 'labeled' && github.event.label.name != 'run-model-tests' && github.run_id || 'run' }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
env:
  UV_LOCKED: "1"
  HF_HUB_DISABLE_TELEMETRY: "1"

jobs:
  models:                  # tiny real models; PRs only with the run-model-tests label
    if: >-
      github.event_name != 'pull_request' ||
      (contains(github.event.pull_request.labels.*.name, 'run-model-tests') &&
       (github.event.action != 'labeled' || github.event.label.name == 'run-model-tests'))
    runs-on: ubuntu-24.04
    env:
      HF_HOME: ${{ github.workspace }}/.hf-cache
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7  # v10.2.0
        with: { enable-cache: true }
      - run: sudo apt-get update && sudo apt-get install -y --no-install-recommends ffmpeg
      - id: hf
        uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9  # v6.1.0
        with:
          path: .hf-cache
          key: hf-${{ hashFiles('tests/models.lock') }}
      - run: uv sync --extra service --extra asr --extra asr-whisper --extra llm-anthropic --extra vision --extra gcs --extra ort-cpu --extra torch-cpu
      - if: steps.hf.outputs.cache-hit != 'true'
        run: uv run python scripts/fetch_models.py tests/models.lock   # snapshot_download(repo, revision=...)
      - name: model tier, offline; adapter coverage is reported, not gated (open question 2)
        env: { HF_HUB_OFFLINE: "1" }
        run: |
          uv run pytest -c pyproject.toml -m model --timeout=600 --cov --cov-config=pyproject.toml --cov-report= --cov-fail-under=0 --junitxml=pytest.xml
          uv run coverage report --rcfile=pyproject.toml --omit=__none__ --include='src/scenewise/adapters/*' --fail-under=0
      - name: no skipped or xfailed model test
        run: |
          if grep -q '<skipped' pytest.xml; then grep -o 'name="[^"]*"[^>]*><skipped[^>]*' pytest.xml; exit 1; fi

  property-nightly:        # hypothesis with fresh randomness and 1000 examples
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7  # v10.2.0
        with: { enable-cache: true }
      - run: uv sync --extra service   # the same environment as the test job's unit run
      - run: uv run pytest -c pyproject.toml tests/unit --hypothesis-profile=nightly --timeout=1800 -p no:randomly

  supply-chain:            # fails loudly (a red scheduled run notifies); never a merge requirement
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7  # v10.2.0
      - name: known vulnerabilities in uv.lock
        run: uv audit --preview-features audit-command
      - name: zizmor online audits (impostor-commit, ref-confusion, known-vulnerable-actions, stale-action-refs)
        env: { GH_TOKEN: "${{ github.token }}" }
        run: uvx zizmor@1.30.1 --no-config .github
```

`scripts/check_lock.sh` (q8a FU 8; reads only `uv.lock`):

```bash
#!/usr/bin/env bash
# Assert the accelerator routing q8a §9.4 relies on, from uv.lock alone (nothing is installed).
set -euo pipefail
reqs() { uv export --locked --no-dev --no-hashes --no-annotate --quiet "$@"; }
need() { grep -qE "$2" <<<"$1" || { echo "FAIL: $3"; exit 1; }; }

cpu=$(reqs --extra torch-cpu)
gpu=$(reqs --extra torch-cu130)
asr=$(reqs --extra service --extra asr --extra ort-cu130)

need "$cpu" "^torch==[^ ]+\+cpu ; sys_platform == 'linux'"       "torch-cpu: torch not from pytorch-cpu"
need "$cpu" "^torchvision==[^ ]+\+cpu ; sys_platform == 'linux'" "torch-cpu: torchvision not from pytorch-cpu"
need "$gpu" "^torch==[^ ]+\+cu130"                                "torch-cu130: torch not from pytorch-cu130"
need "$gpu" "^torchvision==[^ ]+\+cu130"                          "torch-cu130: torchvision not from pytorch-cu130"
if grep -qE "^(torch|torchvision)==" <<<"$asr"; then echo "FAIL: asr + ort-cu130 pulls torch"; exit 1; fi
echo "lock routing ok"
```

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
    cooldown: { default-days: 14 }
  - package-ecosystem: uv
    directory: /
    schedule: { interval: weekly }
    cooldown: { default-days: 14 }
```

`.github/CODEOWNERS` (what it can and cannot enforce: §4.2):

```text
# Branch protection / ruleset on main: "Require review from Code Owners", "Do not allow bypassing".
# Owners must be a human account (or team) with write access; agents push from a separate identity.
/pyproject.toml          @<maintainers>
/uv.lock                 @<maintainers>
/scripts/                @<maintainers>
/vulture_whitelist.py    @<maintainers>
/.github/                @<maintainers>
**/conftest.py           @<maintainers>
```

---

## 14. Gate table (gate → tool → config → threshold)

Every row was run on the skeleton with the command in §13 [verified locally], except the two CODEOWNERS rows and the GitHub-side behaviour of the workflow triggers.

| Gate | Tool (version) | Config | Threshold / pass condition |
|---|---|---|---|
| Config lives in one file | `git ls-files` + `grep` step in `static` | file-name list in `ci.yml` | no `uv.toml`, `ruff.toml`, `.ruff.toml`, `mypy.ini`, `.mypy.ini`, `setup.cfg`, `tox.ini`, `pytest.ini`, `.pytest.ini`, `.coveragerc`, `.importlinter`, `_typos.toml`, `typos.toml`, `.typos.toml`, nested `pyproject.toml` |
| Lock is current | uv 0.12.23 `uv lock --check`, `UV_LOCKED=1` | `[tool.uv] required-version = "==0.12.23"`; q8a's two `conflicts` pairs | exit 0 |
| Lock routing | `scripts/check_lock.sh` (uv export) | q8a §9.4 sources and indexes | torch/torchvision `+cpu` under torch-cpu (Linux) and `+cu130` under torch-cu130; no torch in `service+asr+ort-cu130` |
| Formatting | ruff 0.16.10 `format --config pyproject.toml --check` | `[tool.ruff.format]` | no diff |
| Lint | ruff 0.16.10 `check --config pyproject.toml` | `select = ALL`, 6 ignores, per-file ignores (§11) | 0 findings |
| Function complexity | ruff C901, PLR0911/0912/0913/0915/0917 | `[tool.ruff.lint.mccabe]`, `[tool.ruff.lint.pylint]` | CC ≤ 8; returns ≤ 6; branches ≤ 10; args ≤ 5; positional ≤ 3 (src); statements ≤ 40 |
| Banned APIs | ruff TID251 | `banned-api` | 0 uses of pickle / torch.load / subprocess.call / typing.no_type_check |
| Unused or blanket suppressions | ruff RUF100, PGH003, PGH004; mypy `warn_unused_ignores`, `ignore-without-code` | in ALL / strict / `enable_error_code` | 0 findings |
| Suppression ban + budget | `scripts/check_suppressions.py` | `[tool.scenewise.gates] suppression_budget = 2` | no file-level directive or coverage pragma anywhere; no line-level suppression in domain/app/ports; each other one has `# why:`; count == budget |
| Types | mypy 2.4.0 `--config-file pyproject.toml` | `strict`, 10 extra codes, pydantic plugin, `disallow_any_explicit` in core; `ignore_missing_imports` only for onnxruntime, faster_whisper, ctranslate2, open_clip, torchvision, google.cloud; `untyped_calls_exclude` only for google.oauth2.id_token; `files = src, tests, scripts` | 0 errors |
| Layers | import-linter 2.15 `layers` (`lint-imports --no-cache --config pyproject.toml`) | `service > (adapters \| app) > ports > domain`, exhaustive, `exhaustive_ignores = ["__main__"]` | KEPT |
| Adapter independence | import-linter `independence` | `scenewise.adapters.*` | KEPT |
| Only bootstrap imports adapters | import-linter `protected` | allowed importer `scenewise.service.bootstrap` | KEPT |
| Stdlib-only domain/ports; app allow-list (q8a rule 6) | custom `allowed_externals` | `scripts/import_contracts.py`; app may add pydantic, pydantic_core, structlog | KEPT |
| Driving side loads no ML/cloud SDK | import-linter `forbidden` | service → 15 packages; `allow_indirect_imports`; `ignore_imports` for bootstrap → onnxruntime, torch | KEPT |
| Module size | `scripts/check_module_size.py` | `max_module_lines = 500` | no module in src/tests/scripts > 500 lines |
| Tests | pytest 9.1.1 `-c pyproject.toml` + pytest-timeout 2.4.0 + pytest-randomly 5.0.0 | `[tool.pytest] strict`, `filterwarnings = error`, `timeout = "60"`, `-m "not model"` | all pass on 3.12, 3.13, 3.14 |
| No skips in CI | `--junitxml` + `grep '<skipped'` step | `test` and `models` jobs | 0 skipped, 0 xfailed |
| `model` marker placement | `pytest -m model --collect-only -q` step | `test` job | every model-marked test is under `tests/contract/` |
| Core coverage | coverage 7.16.2 from `tests/unit` only (`--cov-config` / `--rcfile` pinned) | `--include` domain/*, app/* (incl. app/contract, app/audio), ports.py, ports/*; `exclude_lines` (no pragmas), `partial_branches = []` | 100% line + branch |
| Overall coverage | coverage 7.16.2 + pytest-cov 7.1.0 | `branch`, `patch = subprocess`, `[report] omit` asr/*, vision/*, media/images.py, llm/anthropic.py, storage/gcs.py, notify/google_id_token.py | ≥ 90% |
| Property tests | hypothesis 6.168.5 | `ci` profile (auto) on PRs; `nightly` profile scheduled | pass |
| Deps hygiene | deptry 0.25.1 `--config pyproject.toml` | map onnxruntime-gpu → onnxruntime; DEP002 ignores torchvision, timm | 0 DEP001–DEP004 |
| Dead code | vulture 2.16 `--config pyproject.toml` | `min_confidence = 60`, `vulture_whitelist.py`, `app/contract/{requests,results}.py` excluded, `ignore_names = ["model_config"]` | 0 findings |
| Spelling | typos 1.51.1 `--isolated --config pyproject.toml` | `[tool.typos]` | 0 findings |
| Workflow security | zizmor 1.30.1 `--offline --no-config` | default audits + Dependabot cooldown | 0 findings |
| Gate-config changes | GitHub CODEOWNERS + ruleset | `.github/CODEOWNERS` incl. `**/conftest.py`; "Require review from Code Owners", no bypass | code-owner approval; binds only with a separate agent identity (§4.2, open question 7) |
| Model tier (not required) | pytest `-m model` | tiny models, cached `HF_HOME`, `HF_HUB_OFFLINE=1` | pass, no skips (main / nightly / label); adapter coverage reported only |
| Supply chain (nightly, not required) | `uv audit` (preview); zizmor 1.30.1 online | `supply-chain` job, `GH_TOKEN` | 0 advisories, 0 findings; a failure is the alert |

---

## 15. Review round 2 — resolution

Every finding of `reviews/q8b-review-r2.md` was re-run on the final skeleton (`scratchpad/q8b-final/sk`, q8a's tree) on 2026-10-08 before it was fixed. None is rejected outright; two are resolved with a different mechanism than the reviewer's first suggestion, and two are accepted as documented limits.

| # | Severity | Re-check | Resolution |
|---|---|---|---|
| 1 | wrong | **Reproduced.** `# pragma nocover`, `# pragma no cover` and `#pragma:nocover` passed the old script and kept core at 100%. | **Fixed, both ways.** Coverage `exclude_lines` replaces the default regex, so no pragma spelling excludes anything, and `partial_branches = []` does the same for `no branch`. The script also bans coverage's own regex (case-insensitive) everywhere. All five spellings and `no branch`: reported by the script and core < 100%. Controls: with the old `exclude_also` or the default `partial_branches`, the same seeds kept 100% (§4.2 layer 3) [verified locally]. |
| 2 | wrong | **Reproduced.** `# flake8: noqa: S307, TID251, E402` in domain left only F401 visible and passed the script. | **Fixed.** `flake8: noqa` is a file-level directive, banned everywhere; line-level `noqa` is matched anywhere in a comment (`\bnoqa\b`), so `# why: x  # noqa: E501` and `#NOQA:E501` are caught too [verified locally]. |
| 3 | wrong | **Reproduced** for nested `ruff.toml`, `.ruff.toml` (format), root `mypy.ini`, `pytest.ini` (root and `tests/unit/`), `.coveragerc`, `.importlinter` and `_typos.toml`. **Found beyond the review:** `uv.toml` overrides `[tool.uv]` (including `required-version` and the indexes) with only a warning, and typos merges discovered files even with `--config`. | **Fixed, both ways.** Every tool gets `/pyproject.toml` explicitly (`ruff --config`, `mypy --config-file`, `pytest -c`, `--cov-config` / `--rcfile`, `lint-imports --config`, `typos --isolated --config`, `deptry` / `vulture --config`, `zizmor --no-config`), and a first `static` step fails on any stray config file. Each seed: silenced without the flag, caught with it, and rejected by the stray step (§4.2 table) [verified locally]. `**/conftest.py` added to CODEOWNERS. |
| 4 | design | **Reproduced** all four routes, plus `skipif(True)` and `importorskip` of a missing module. | **Fixed, as the reviewer proposed.** Every CI pytest step writes `--junitxml`, and a step fails on any `<skipped` element (skips and xfails). The script no longer counts markers. All six seeds: pytest exit 0, check exit 1 [verified locally]. Chosen over a conftest hook because the check lives in the workflow, not in a file a nested conftest can affect. |
| 5 | design | **Reproduced:** `slow` tests ran in no job; a `model`-marked unit test left the required tier. | **Fixed.** `slow` dropped (`addopts` is now `-m "not model"`). A `test`-job step fails if `pytest -m model --collect-only` lists anything outside `tests/contract/` [verified locally]. |
| 6 | wrong | **Reproduced:** "total of 36 is less than fail-under=90", exit 2. | **Fixed.** `--fail-under=0` on the models job's report (exit 0). Gating it is open question 2. |
| 7 | design | Confirmed by reading the script: a file-level directive counted as one. | **Fixed.** File-level directives are banned everywhere, not budgeted; a module-top `type: ignore` is detected by position (before the first statement). The budget now counts only line-level suppressions (§4.2 layer 4) [verified locally]. |
| 8 | missing option | **Reproduced:** the lazy OIDC import fails `PLC0415` and `no-untyped-call`. | **Fixed without lazy imports in adapters.** New `adapters/notify/google_id_token.py` imports google-auth at top level; `HttpCallbackNotifier` takes an injected `id_token` callable; `SchemeRouter` takes injected `stores`; `gcs.py` builds its own client; only bootstrap imports lazily. mypy needs `untyped_calls_exclude = ["google.oauth2.id_token"]` (clean with it; the error without it). All gates clean, OIDC contract tests pass in the PR tier (§2) [verified locally]. q8a consequences: §15.1 and open question 12. |
| 9 | design | **Reproduced:** dead functions in `app/contract/` were not reported. | **Fixed.** Only `requests.py` and `results.py` are excluded; `ignore_names = ["model_config"]`. Seeded dead functions in `mapping.py` and `envelope.py` are reported, exit 3 [verified locally]. |
| 10 | minor | Confirmed from the YAML. | **Fixed.** `extended.yml` groups by event name, cancels only PR runs, and isolates unrelated `labeled` events; `models` runs on `labeled` only for `run-model-tests`. Parsed by zizmor; not run on GitHub. |
| 11 | minor | Confirmed. | **Fixed.** `property-nightly` syncs `--extra service`; 26 passed under the nightly profile [verified locally]. |
| 12 | missing option | **Confirmed:** offline zizmor missed both a wrong version comment and a fabricated SHA; online mode reported `ref-version-mismatch` and `impostor-commit` [verified locally, user token]. | **Fixed.** Online zizmor runs in the nightly `supply-chain` job with `GH_TOKEN: ${{ github.token }}`; offline stays the merge gate. Moving it into the gate is open question 13. |
| 13 | design | Facts as stated by the reviewer (GitHub docs). | **Fixed in the text, not solvable in config.** §4.2 now states when CODEOWNERS binds (separate agent identity without bypass, maintainer as owner, "no bypass" ruleset) and that it enforces nothing when agents use the maintainer's credentials. `**/conftest.py` is owned. The identity choice and a `codeowners/errors` check are open question 7, because both need the real repo. |
| 14 | design | Confirmed: `continue-on-error` hid every result. | **Fixed: kept and made failing** (job `supply-chain`, nightly and manual only, never required). Removal was rejected because Dependabot's coverage of `uv.lock` for security alerts was not verified. Clean lock: exit 0; vulnerable lock: exit 1 [verified locally]. |
| 15 | minor | **Confirmed:** after removal, each of the five q8a-list seeds is still reported by an allow-list contract. | **Fixed.** Contract dropped; 6 contracts. |
| 16 | minor | Confirmed. | **Fixed.** `max-bool-expr` removed. |
| 17 | minor | Confirmed. | **Fixed.** The skeleton is now the reviewer's q8a-faithful tree (no `asr/onnx.py`; `parakeet.py` imports `onnx_asr`), plus `app/contract/{requests,results,mapping}.py`; deptry is clean. Method note updated. |
| 18 | minor | Confirmed for `# scripts/import_contracts.py`. | **Fixed.** File-name header comments removed from the script code blocks; each is labelled in prose. (The §6 contract-test sketch keeps its comments, because it shows three files in one block.) |
| 19 | unsupported | Confirmed: the 350 figure was unmeasured. | **Fixed by measurement.** Pooled code share 0.44–0.77 over 8 libraries, so 500 physical lines ≈ 220–390 code lines; the readability part is labelled a judgment (§4.1). |
| 20 | minor | Confirmed. | **Recorded as errata** in §15.1 (q8a is read-only here). |
| 21 | minor | Confirmed. | **Accepted and documented** (§5): mypy `empty-body` catches value-returning `...` stubs (verified); `-> None` stubs are left to the unit tests. |

Also changed while resolving: the e2e `sine_wav` fixture moved to `tests/e2e/conftest.py` and the ffprobe e2e test now probes that generated file (the inherited skeleton test probed a non-existent path, so it could only skip or fail); `ports.py` gained the `Notifier` Protocol that bootstrap returns.

### 15.1 Errata for q8a (q8a is final; apply these when implementing)

| q8a says | Use instead | Why |
|---|---|---|
| §1.5: `layers = ["service", "adapters", "app", "ports", "domain"]`, and rule 2 "the layers contract already forbids" adapters → app | `layers = ["service", "adapters \| app", "ports", "domain"]` (§12) | With the literal list a higher layer may import any lower one, so adapters → app is allowed; the pipe makes them independent siblings, matching q8a's own arrows [verified locally, and by the round-2 reviewer] |
| §1.4 naming notes and FU 6: `MAX_LINES = 400` | 500 physical lines, from `[tool.scenewise.gates] max_module_lines` | Docstrings count (§4.1). q8a's size-driven layout still applies |
| §1.4 tree: `adapters/notify/` holds only `http_callback.py` | add `adapters/notify/google_id_token.py`; `http_callback` takes an injected `id_token` callable | google-auth is an optional SDK; no lazy imports outside bootstrap (§2) |
| §1.5 rule 3: `storage/by_scheme.py` importing `storage/gcs.py` is allowed | `by_scheme` takes injected `stores: Mapping[str, BlobStore]` and imports no sibling | Importing `gcs.py` would make `by_scheme` unimportable without the `gcs` extra (§2) |
| §6.5: callbacks carry a Google ID token (google-auth), with google-auth only in the `gcs` extra | OIDC callbacks require the `gcs` extra, unless the user moves google-auth (open question 12) | Documented dependency, not a code change |
| §4: `class WriteConflict(Exception)` | `WriteConflictError`, unless the user decides otherwise (open question 6) | ruff N818; the core ban forbids an inline `noqa` |
