# Skeleton review, round 1

Reviewer: a fresh review agent that did not build the skeleton. Scope: commits `a7fec58`, `4cf6de7`, `2e948b7` and
`c390617` after `e72eaa0`, against `ARCHITECTURE.md`, `user-decisions.md`, q8b, q8c and `initial-research.md` §8
(Part 2, step 2). The repository was not changed except for this file. Every gate ran in a clean `git clone` of
`HEAD` in the session scratchpad (`skeleton-review/repo`), with `uvx uv@0.12.23` on `PATH` as `uv` and `UV_LOCKED=1`.
The planted violations ran in further scratch clones (`plant1`, `plant2`, `plant3`). The probes are in
`skeleton-review/probe/`.

Severities: **must-fix** blocks accepting the skeleton. **should-fix** belongs in this step or in the first roadmap
item. **nice-to-have** is optional.

## 1. Gate results (re-run, 2026-10-08, macOS arm64, Homebrew ffmpeg 9.0.2)

| Gate | Command (CI order) | Result |
|---|---|---|
| Stray config | `python3 scripts/check_stray_config.py` (the repo itself, ignored files included, and the clone) | pass (exit 0) |
| Lock | `uv lock --check` | pass |
| Lock routing | `bash scripts/check_lock.sh` | pass ("lock routing ok") |
| Sync, static env | `uv sync --extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cpu` (3.14) | pass |
| Format | `ruff format --config pyproject.toml --check .` | pass |
| Lint | `ruff check --config pyproject.toml .` | pass ("All checks passed!") |
| Types | `mypy --config-file pyproject.toml` | pass (81 source files, 0 errors) |
| Layers | `lint-imports --no-cache --config pyproject.toml` | pass (6 kept, 0 broken) |
| Module size | `scripts/check_module_size.py` | pass (largest: `tests/unit/test_delivery.py`, 261 lines) |
| Suppressions | `scripts/check_suppressions.py` | pass (2, budget 2) |
| deptry | `deptry --config pyproject.toml src` | pass |
| vulture | `vulture --config pyproject.toml` | pass |
| typos | `typos --isolated --config pyproject.toml` | pass |
| zizmor | `zizmor --offline --no-config .github` | pass |

Tests, `uv sync --extra service` only, in the CI sequence:

| Python | Model-marker check | Unit tests | Core coverage (unit only, `$CORE`) | All tiers | Overall coverage | JUnit skip/xfail check |
|---|---|---|---|---|---|---|
| 3.12 | pass (nothing collected) | 139 passed | 100% (874 stmts, 88 branches) | 226 passed | 99.62% | pass; 0 skipped, 0 failures, 0 errors |
| 3.13 | pass | 139 passed | 100% (874 / 88) | 226 passed | 99.62% | pass |
| 3.14 | pass | 139 passed | 100% (697 / 88) | 226 passed | 99.57% | pass |

These match `docs/skeleton-notes.md` exactly. On 3.14 the statement count is lower (697 against 874) because of
PEP 649 deferred annotations: annotation-only lines in dataclasses and Pydantic models are no longer statements. The
branch counts are identical, so this is not a coverage gap.

**Planted violations.** All of them were caught.

| Plant (scratch clone) | Gate | Result |
|---|---|---|
| `adapters/storage/local.py` imports `scenewise.app.publish` | Layers | BROKEN, as expected |
| `service/http/state.py` imports `scenewise.adapters.media.images` | Composition root (`protected`) | BROKEN |
| `domain/labels.py` imports `pydantic` | Allowed externals, domain/ports | BROKEN (`not on the allow-list`) |
| `app/stages.py` imports `scenewise.service.cli` | Layers | BROKEN |
| `adapters/media/ffmpeg.py` imports `adapters.storage.local` | Adapter independence | BROKEN |
| `service/logs.py` imports `numpy` | Driving side forbidden | BROKEN |
| `# noqa: E501` in `domain/` | Suppressions | exit 1, banned in core |
| A reasoned `# noqa` in `service/` | Suppressions | exit 1, 3 against a budget of 2 |
| A reasonless `# type: ignore[...]` in `tests/` | Suppressions | exit 1, reason missing and over budget |
| `# ruff: noqa` / `# pragma: no cover` | Suppressions | exit 1, file-level or coverage pragma banned |
| `sub/ruff.toml`, `.typos.toml`, `uv.toml`, `setup.cfg`, `.ruff.toml`, `tests/pytest.ini`, `tests/x/pyproject.toml` | Stray config | exit 1, each listed |
| `pytest.skip()` and a non-strict `xfail` test | `check_junit.py` | exit 1, both named |

(`"# noqa"` inside a string literal is correctly not counted, because only comment tokens are read.)

**Pins.** Every package locked in `uv.lock` equals the versions in `initial-research.md` §8 and q8c §3: pydantic 2.13.5
(core 2.46.5), pydantic-settings 2.15.0, structlog 26.1.0, httpx 0.28.1, Pillow 12.3.0; fastapi 0.142.4, uvicorn 0.54.0,
anyio 4.15.1; sherpa-onnx and sherpa-onnx-core 1.13.8, onnx-asr 0.12.0, onnxruntime 1.30.0, faster-whisper 1.2.1,
ctranslate2 4.8.2, numpy 2.5.3; anthropic 1.12.1; open-clip-torch 3.3.0, timm 1.0.30; google-cloud-storage 3.16.0,
google-auth 2.61.0; torch 2.14.1 and torchvision 0.29.1 (`+cpu`, `+cu130`); every dev tool. `onnxruntime-gpu` is
absent. The base install (`uv export --no-dev`) has no torch, no numpy and no model runtime. `service + asr` has no
torch and no `onnxruntime-gpu`; it does pull `av` 19.0.1 through faster-whisper, as q8c §3 expects. The action SHAs
match their tags: checkout v7.0.1, setup-uv v10.2.0 and cache v6.1.0 were each checked with `git ls-remote`.
setup-uv v10.2.0's README confirms that it reads `required-version` from `pyproject.toml`. `uv audit` exists in
0.12.23.

## 2. Findings

### 1. The `file://` allow-list does not hold on HTTP: one request can read another job's artifacts and overwrite its `result.json`

- **Location:** `src/scenewise/service/bootstrap.py:26`; `src/scenewise/adapters/storage/local.py:30-41`;
  `src/scenewise/app/contract/mapping.py:74`; `src/scenewise/app/delivery.py:120`; `docs/skeleton-notes.md` A6.
- **Problem:** `_store` builds one `LocalBlobStore` whose roots are the state directory plus `inputs.local_roots`.
  That store serves inputs, job records and artifacts alike. So (a) the state directory is always an *input* root, and
  A6's claim that "HTTP refuses `file://` unless configured" is false. (b) `delivery.artifacts.uri_prefix` comes from
  the request and is checked only against the same roots, so a request can point it at another job's folder and
  overwrite that job's `a{n}/result.json` and `audio.wav` with unconditional writes. That job's terminal record still
  names the overwritten file.
- **Evidence:** `probe/a6_probe.py`. With `local_roots` set, it runs job `victim`. A second app with
  `local_roots=()` then posts job `attacker`, whose input is `file://<state>/victim/a1/audio.wav` and whose
  `uri_prefix` is `file://<state>/victim`. Output: `attacker ... succeeded None`, and
  `victim result.json now names job: "attacker"`.
- **Severity:** must-fix. A documented security property is violated, and the fix is small.
- **Suggested fix:** separate the roles. Give inputs their own allow-list (`local_roots` only; on HTTP, empty means
  no `file://` at all). Write records and artifacts through a store rooted at the state prefix, or at an allow-listed
  artifacts root. Reject an `artifacts.uri_prefix` that is outside that root or that falls under another job's
  `{state_prefix}/{job_id}`; on HTTP, simplest is to accept only prefixes under an operator-configured root. Add e2e
  tests for both cases. When `by_scheme.py` lands, it should apply the same input-versus-output split.

### 2. ffmpeg follows an HLS playlist in an uploaded file to other local files

- **Location:** `src/scenewise/adapters/media/ffmpeg.py:26` (`_PROTOCOLS`), `:94-95` (probe), `:128-129` (audio),
  `:151-152` (frames); `ARCHITECTURE.md` §11.
- **Problem:** §11 relies on `-protocol_whitelist file,pipe` to stop ffmpeg fetching anything itself. But `file` has
  to be allowed, so a materialised input whose *content* is an HLS playlist makes ffmpeg's `hls` demuxer open
  `file:/any/local/path` with a media extension, outside every store allow-list. User uploads are the primary input,
  and the caller controls the input's name.
- **Evidence:** `probe/hls_probe.py`. A playlist that references `file:<scratch>/secret.m4a`:
  - Named `upload.mp4`, Homebrew ffmpeg 9.0.2 refuses it ("Not detecting m3u8/hls with non standard extension").
  - Named `upload.m3u8`, `probe()` reports `duration=2.0, has_audio=True`, and `audio_track()` extracts 2.0 s from the
    referenced file.
  - Whether apt ffmpeg 6.1 (the CI and image build) detects HLS by content regardless of extension was not tested.
    The extension check is a newer ffmpeg behaviour.
- **Severity:** must-fix. The control §11 depends on is shown not to hold, and the fix is one argv option.
- **Suggested fix:** add an input demuxer allow-list to every ffprobe and ffmpeg argv, before `-i`. For example:
  `-format_whitelist mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mpegts,wav,mp3,aac,flac,ogg`. Verified here: ffmpeg 9.0.2
  then answers "Format not on whitelist" for the playlist. Add a contract test with a planted playlist under both a
  `.mp4` and a `.m3u8` name, and note the change in §11 (an architecture finding).

### 3. An unexpected exception inside a stage fails the whole job, not the stage

- **Location:** `src/scenewise/app/runner.py:51-62`; `src/scenewise/app/delivery.py:129-131`.
- **Problem:** `_run_stage` catches only `InputError` and `InternalError`. A `ValueError` from a domain constructor,
  or any other exception, raised inside a stage leaves `run_job` and becomes `FAILED("unexpected")` for the whole job.
  §9 says two things here: input and internal errors inside a stage fail that stage only; and a domain `ValueError`
  is `InternalError("invariant_violation")` "anywhere else in the runner". Neither is implemented, and the skeleton
  notes do not mention it.
- **Evidence:** code reading. `tests/unit/test_runner.py` covers only `InputError` and `InternalError` raised from a
  stage.
- **Severity:** should-fix. It is harmless with one stage, but it is the shape item 1 will copy.
- **Suggested fix:** in `_run_stage`, map `ValueError` to `Failed("invariant_violation", "internal")`. Decide, and
  record, whether a non-scenewise exception fails the stage (`"unexpected"`) or the job; §9 reads as "the stage".
  Leave `RetryableError` to propagate. Add one unit test.

### 4. Errors other than `RetryableError` from the delivery or the GET route escape as plain 500s

- **Location:** `src/scenewise/service/http/push.py:77-97`; `src/scenewise/service/http/routes.py:48`.
- **Problem:** `push` catches only `RetryableError`. Two paths escape FastAPI as a text 500 with no problem+json:
  `mapping.record_from_json` raising `InternalError("invariant_violation")` for an unreadable `status.json`, and any
  bug outside `_run`'s broad `except`. On the push path, Cloud Tasks then retries that delivery until
  `maxRetryDuration`. `GET /v1/jobs/{id}` has the same gap.
- **Evidence:** code reading. No test sends a corrupt record.
- **Severity:** should-fix.
- **Suggested fix:** register an exception handler for `ScenewiseError` (via `problems.problem_response`) and a
  catch-all that renders `InternalError("unexpected")`. Decide what the push path answers for an unreadable record:
  a 200 with a problem body, as for `job_id_conflict`, stops the retry storm. Add a test.

### 5. `LocalBlobStore.read` creates directories and lock files, so any GET writes to disk

- **Location:** `src/scenewise/adapters/storage/local.py:47-50` and `:73-80`.
- **Problem:** `read()` goes through `_locked()`, which runs `mkdir(parents=True)` and creates `.name.lock`. Every
  `GET /v1/jobs/<any valid id>`, including unknown ids, therefore leaves `state/<id>/.status.json.lock` behind. That
  is unbounded clutter, created by unauthenticated reads.
- **Evidence:** a probe in `probe/readroot/`: three `read()` calls on absent `job-{0,1,2}/status.json` left
  `job-0/.status.json.lock`, `job-1/.status.json.lock` and `job-2/.status.json.lock`.
- **Severity:** should-fix.
- **Suggested fix:** in `read`, return `None` when the parent directory does not exist, before taking the lock. Only
  `write` creates directories.

### 6. Agent PRs opened with `GITHUB_TOKEN` will not run `static` and `test` (U13, U13a; `ARCHITECTURE.md` §17 (a))

- **Location:** `.github/workflows/ci.yml:2-5`.
- **Problem:** `ci.yml` triggers only on `push` to main and on `pull_request`. Events created with `GITHUB_TOKEN`
  start no new workflow runs, except `workflow_dispatch` and `repository_dispatch`. So a PR that a harness run on
  GitHub Actions opens as `github-actions[bot]` gets no `static` or `test` check. If the ruleset requires those
  checks, the PR waits forever, and the admin bypass becomes the routine path. That defeats U13's premise that bot
  PRs "get normal code-owner review". If the checks are not required, gate-file changes merge ungated. The YAML
  itself is runnable: the SHA pins are correct, `pull_request` uses the default types, setup-uv reads
  `required-version`, and ffmpeg comes from apt.
- **Evidence:** GitHub's documented `GITHUB_TOKEN` trigger rule; the triggers in `ci.yml`.
- **Severity:** should-fix. It must be settled before the ruleset is set up (`initial-research.md` §8 step 1).
  It is not a skeleton defect.
- **Suggested fix:** pick one of the following.
  - (a) Open agent PRs with a GitHub App installation token. Check-runs then fire, and the author becomes the app,
    not `github-actions[bot]`. U13's text would need a note.
  - (b) Add `workflow_dispatch:` to `ci.yml` and have the agent workflow dispatch it on the PR branch. Check runs
    attach to the head SHA, so required checks named `static` and `test (3.12)` and so on are satisfied. Also confirm
    open items (b) and (c): the "Allow GitHub Actions to create pull requests" setting, and `workflows: write` for
    agent edits under `.github/workflows/`.

### 7. `required-version = "==0.12.23"` probably breaks Dependabot's `uv` updates, and contributors on packaged uv (G1)

- **Location:** `pyproject.toml:74`; `.github/dependabot.yml:7-10`; `.pre-commit-config.yaml` (`uv-lock` hook runs
  bare `uv`).
- **Problem:** Dependabot's `uv` ecosystem runs its own bundled uv. An exact `==` requirement makes `uv lock` refuse
  to run whenever the bundled version differs. In this session the same happened with Homebrew uv 0.12.21 (G1), and
  the `uv-lock` pre-commit hook fails the same way.
- **Evidence:** G1. Dependabot's behaviour is inferred and should be confirmed on the first scheduled run.
- **Severity:** should-fix (verify).
- **Suggested fix:** pin the CI version with setup-uv's `version: "0.12.23"` input, and loosen `required-version` to
  `">=0.12.23,<0.13"`. Alternatively, keep the exact pin and accept that Dependabot's uv updates are manual; record
  that choice.

### 8. The vulture whitelist and excludes mask future dead code by name

- **Location:** `vulture_whitelist.py:9-73`; `pyproject.toml:257-260`.
- **Problem:** vulture matches whitelist entries by bare name. Entries such as `span`, `language`, `model`, `score`,
  `interval`, `report`, `images`, `callback`, `segments` and `tokens` silence *every* unused attribute or variable
  with those names, anywhere in `src`, throughout items 1–4. Two whole wire modules are excluded as well. The
  whitelist is honestly documented, but it turns the dead-code gate into a near no-op for the names the next items
  will add.
- **Evidence:** the whitelist content; vulture's documented name-based whitelisting.
- **Severity:** nice-to-have. Make it a rule in item 1: each item deletes the entries it starts reading and must not
  add generic names.
- **Suggested fix:** keep the list, but add a check (or a review rule) that it only ever shrinks. Prefer `_.name`
  attribute forms over bare names where vulture allows them, so that module-level variables with those names are
  still checked. Revisit the wire-module exclusion once the models are read by `mapping.py`.

### 9. The model-marker CI step hides pytest collection errors

- **Location:** `.github/workflows/ci.yml:52-55`.
- **Problem:** `uv run pytest ... --collect-only -q | grep '::' | grep -v '^tests/contract/' || true` passes when
  pytest exits 2 (a collection error) or 5 (nothing collected). This review's run passed vacuously, with nothing
  collected. A broken `model` test module outside `tests/contract` would go unseen. Later steps would catch collection
  errors only in the default tier, which excludes `model`.
- **Evidence:** the pipeline above.
- **Severity:** nice-to-have.
- **Suggested fix:** capture pytest's exit code separately and fail when it is not 0 or 5. Alternatively, assert with
  `pytest -m model --collect-only -q tests --ignore=tests/contract` that the exit code is 5.

### 10. The coverage pattern `^\s*\.\.\.$` excludes more than Protocol bodies

- **Location:** `pyproject.toml:228`.
- **Problem:** The pattern excludes any line consisting only of `...`. A `-> None` function or method with a `...`
  placeholder body (mypy's empty-body check does not fire for `None`) would be excluded from the 100% core
  coverage. G9's `case _:\n\s*assert_never\(` pattern is sound: mypy's `exhaustive-match` plus `assert_never`
  typing prove the arm unreachable, and coverage excludes exactly that arm. The `...` pattern is the looser of the
  two.
- **Evidence:** the config comment ("mypy's empty-body error is the backstop elsewhere").
- **Severity:** nice-to-have.
- **Suggested fix:** either add a small check (for example in `check_suppressions.py`) that bans a bare `...`
  body outside `ports.py` and `Protocol` classes, or accept the gap and note it next to the pattern.

### 11. `ci.yml` cancels in-progress runs on main

- **Location:** `.github/workflows/ci.yml:8-10`.
- **Problem:** `cancel-in-progress: true` with the group `workflow-ref` cancels the run for merge N when merge N+1
  lands, so some main commits never get a complete gate run. `extended.yml` already scopes cancellation to PRs.
- **Severity:** nice-to-have.
- **Suggested fix:** `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.

### 12. A test that asserts nothing meaningful

- **Location:** `tests/unit/test_delivery.py:260-261` (`test_blob_type_is_the_ports_value`).
- **Problem:** It constructs `Blob(data=b"", generation=1)` and asserts `.generation == 1`. That tests the
  `dataclass` decorator, not scenewise. `Blob` is already exercised by every store test.
- **Severity:** nice-to-have.
- **Suggested fix:** delete it.

### 13. A little ceremony in `runner._dispatch`

- **Location:** `src/scenewise/app/runner.py:40-48`.
- **Problem:** `match plan.PREREQUISITES[stage], stage: case plan.Needs.AUDIO, StageName.AUDIO:` matches a tuple
  whose first element is derived from the second. `match stage: case StageName.AUDIO:` says the same thing. Elsewhere
  the code is idiomatic, with no Java-style layering. Frozen keyword-only dataclasses, Protocols, plain functions and
  a single factory function are used as §14 prescribes. `_Delivery` is a reasonable parameter bundle, not a service
  object.
- **Severity:** nice-to-have.
- **Suggested fix:** match on `stage` alone. The prerequisite table belongs with the `dependency_failed` logic that
  item 1 adds.

### 14. `probe()` ignores the deadline

- **Location:** `src/scenewise/adapters/media/ffmpeg.py:96` and `:145`.
- **Problem:** `probe` always gets `PROBE_TIMEOUT_S = 60`. With less than 60 s of the budget left, it can overrun the
  attempt deadline that §7 says ffmpeg must respect ("ffmpeg gets `timeout = remaining`"). `video_frames` probes
  again on every call.
- **Severity:** nice-to-have. The port signature has no deadline for `probe`, so this is partly an architecture
  question.
- **Suggested fix:** either add `deadline` to `MediaTool.probe`, or document the 60 s overshoot bound next to the
  watchdog grace.

### 15. Adapter robustness: unmapped exceptions become `unexpected`

- **Location:** `src/scenewise/adapters/media/ffmpeg.py:97` and `:113-114`;
  `src/scenewise/adapters/media/images.py:17-21`.
- **Problem:** Two kinds of malformed input should map to `corrupt_media` and do not. ffprobe output that is not JSON
  (`json.loads`) raises a `ValueError`; a video stream without `width` raises a `KeyError`. Both surface as
  `unexpected`. Pillow's `Image.DecompressionBombError` is not an `OSError`, so a decompression-bomb image is not
  mapped either. Also, `PillowImageReader` copies the full image once per tile even when it then crops (`:24`).
- **Severity:** nice-to-have. No stage reads images yet.
- **Suggested fix:** map these to `InputError("corrupt_media")` and crop from `rgb` directly.

### 16. The CLI prints a traceback for invalid settings

- **Location:** `src/scenewise/service/cli.py:86`.
- **Problem:** `Settings()` raises a pydantic `ValidationError` for a bad `SCENEWISE_*` value, for example a broken
  timing invariant. That prints a traceback and exits 1, while every other configuration problem exits 2 with a
  one-line message.
- **Severity:** nice-to-have.
- **Suggested fix:** catch `ValidationError` in `main`, print the field paths, and return `EXIT_CONFIGURATION`.

### 17. The local store does not fsync the compare-and-swap record

- **Location:** `src/scenewise/adapters/storage/local.py:113-121`.
- **Problem:** `_replace` writes and renames without `fsync`, so after a power loss the meta file and the data file
  can disagree in either order. The generation-first comment covers crashes of the process, not of the host.
- **Severity:** nice-to-have. D14 says single-host; durability is not claimed.
- **Suggested fix:** `os.fsync` the temporary file before `replace`, and the directory after it. Alternatively,
  document that the local store is for development.

### 18. The pre-commit runner is not pinned

- **Location:** `pyproject.toml:54-70`; `.pre-commit-config.yaml`.
- **Problem:** `initial-research.md` §8 lists pre-commit 4.6.2 or prek 0.5.5 in the dev group. Neither is declared,
  so the hooks run on whatever pre-commit the contributor has installed.
- **Severity:** nice-to-have. D6 allows either runner.
- **Suggested fix:** add `prek==0.5.5` (or pre-commit 4.6.2) to the dev group, or note in the README that the runner
  is the contributor's choice.

### 19. G20 is not a deviation

- **Location:** `docs/skeleton-notes.md` G20; `src/scenewise/app/contract/envelope.py:36-39`.
- **Problem:** q8a §5.1 already uses `json.dumps(sort_keys=True, separators=...)`, and `ensure_ascii=True` is
  `json.dumps`'s default. Its output is pure ASCII, and UTF-8-encoding it never fails. Encoding it as `"ascii"` gives
  the same bytes, so the digest equals q8a's. Only a dump with `ensure_ascii=False` would hit lone surrogates. The
  code is fine; the note overstates the deviation.
- **Severity:** nice-to-have.
- **Suggested fix:** reword G20 to say that the digest equals q8a's, and that the hypothesis test pins it.

## 3. The builder's deviations (`docs/skeleton-notes.md`)

| # | Verdict | Note |
|---|---|---|
| A1 `audio` stage | Justified | The thin stage needs a requestable name; item 1 decides whether it stays. |
| A2 `Analysis` subset, WAV in memory | Justified | Fields join with their stages; memory is fine at push-budget media lengths. |
| A3 `Failed.category` | Justified | The wire `ErrorInfo.category` cannot be derived from the code alone. |
| A4 `AudioManifest` without `format` | Justified | D10. |
| A5 Contract subset | Justified | `extra="forbid"` rejects unbuilt fields loudly. `supersedes` and `mime` are accepted but unused. |
| A6 `file://` on HTTP | **Defect** | Finding 1: the state directory is always an input root, and the artifacts prefix is unconstrained. |
| A7 Settings groups, `local_roots`, probe fields | Justified | |
| A8 `notifier` optional | Justified | No callback kind exists yet. |
| A9 503 on a fenced terminal write | Justified | The next delivery re-decides from the record, so the end state is the same. |
| A10 Partial tree | Justified | `ports.py` has 176 lines, under the 200-line split point. Only 3 of the 10 ports have fakes, which is fine while nothing uses the rest. |
| A11 Extra error codes | Justified | §9 lists no configuration or capacity codes; record them in §9. |
| A12 Keyword error construction | Justified | Idiomatic and needs no suppression. |
| A13 No NOTICE, Dockerfile, models.lock | Justified | No weights in the repository; the README states the planned attribution (U4). |
| A14 D8 log test deferred | Justified | Nothing logs transcripts. Logged fields are codes only; `detail` (with the ffmpeg stderr tail, i.e. local paths) goes to `result.json`, not the logs. |
| G1 uv 0.12.21 refuses | Justified as recorded | See finding 7 (Dependabot, pre-commit). |
| G2, G3 docs excluded from ruff and typos | Justified | |
| G4 `sherpa-onnx-core` declared | Justified | Asserted by `check_lock.sh`. |
| G5 fastapi held at 0.142.4 | Justified | Consider uv `exclude-newer` as the policy. |
| G6 huggingface-hub not declared | Justified | Locked transitively at 1.33.0; pin with item 1. |
| G7 `httpx2` in the dev group | Justified | |
| G8 `anyio` in `service`, DEP002 list | Justified | Each entry is commented with the item that removes it. |
| G9 `assert_never` exclude pattern | Justified, sound | mypy proves the arm unreachable. See finding 10 for the looser `...` pattern. |
| G10, G11, G12 Entries for absent modules left out | Justified | Unmatched entries would error or mislead. |
| G13 Suppression budget 2 | Justified | Both carry `# why:`. |
| G14, G15 Script versions of q8b's inline steps | Justified | Both verified with plants. |
| G16 `models` job gated on `tests/models.lock` | Justified | |
| G17 typos and zizmor in the locked dev group | Justified | |
| G18 Literal 422 | Justified | |
| G19 Fixtures not regenerated in CI | Justified | |
| G20 Digest encoding | Justified, but not a deviation | Finding 19. |
| G21 Reformatted contract script | Justified | |

## 4. Layout and dependency rule

The tree matches `ARCHITECTURE.md` §2 for every module that exists. `domain` and `ports` import only the standard
library, and `app` only adds pydantic, pydantic_core and structlog; the custom allow-list contract enforces both.
Only `service/bootstrap.py` imports `adapters`, and lazily. `__main__` is the one exhaustive-layer exemption.
`ports.py` holds all ten Protocols plus `Blob` and `WriteConflictError`. The one thin stage is wired end to end: CLI
and HTTP → `delivery` → `runner` → `acquire_audio` → `BlobStore` → `MediaTool` (ffmpeg) → `publish`, and the e2e
tests cover it over real ffmpeg. Apart from findings 1–5, the code is correct and idiomatic. Its weak point is
security at the local-file boundary (findings 1, 2 and 5).

## Counts

| Severity | Count |
|---|---|
| must-fix | 2 (findings 1, 2) |
| should-fix | 5 (findings 3, 4, 5, 6, 7) |
| nice-to-have | 12 (findings 8–19) |
