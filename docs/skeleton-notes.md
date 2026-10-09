# Skeleton notes

What the repository skeleton (decision document §8, step 2) does differently from `ARCHITECTURE.md`, q8a, q8b and
q8c, and every gate configuration that did not work as documented. Each entry may become an architecture or harness
finding. Built 2026-10-08 on macOS (arm64), Homebrew ffmpeg 9.0.2, CPython 3.12.14 / 3.13.16 / 3.14.7, uv 0.12.23.

## Deviations from the architecture

| # | Where | Architecture says | Skeleton does | Why / follow-up |
|---|---|---|---|---|
| A1 | `domain/jobs.py` `StageName`, wire `stages` | Stages are captions, summary, chapters, moderation, labels | Adds `audio` (wire `"audio"`): publishes the normalised track as `a{n}/audio.wav` | The one wired stage needs a name a request can ask for. Item 1 decides whether `audio` stays as an opt-in artifact or is removed (no consumer yet). |
| A2 | `domain/results.py` `Analysis` | `(job_id, media, outcomes, transcript, cues, summary, chapters, moderation, labels)` | `(job_id, media, outcomes, audio_wav)`; `media` may be `None` | Result fields join with their stages. The WAV is held in memory (32 kB per second of audio); fine for short media, revisit if `audio` stays. |
| A3 | `domain/results.py` `Failed` | `Failed(error_code, detail)` | `Failed(error_code, category, detail)`, category `input` or `internal` | The wire `ErrorInfo.category` of a failed stage cannot be derived from the code alone. |
| A4 | `domain/inputs.py` `AudioManifest` | `(uri, format, rendition)` | `(uri, rendition)` | D10: HLS only in v1, so a one-value `format` is dropped. |
| A5 | `app/contract/requests.py`, `results.py` | q1 §4–§5 contract | Subset: audio `file` / `none`; notify `none` only; no `media`, `visual`, `context`, `options` (so `extra="forbid"` rejects them). `JobResultV1` has no `failed` status, `error`, `supersedes`, `models`, `created_at`, `finished_at`. Domain `Job` has no `context`; `JobSpec` has no `options` | Only what the audio stage reads. A job that fails before its stages writes no `result.json`; its record carries `error_code`. Each field arrives with the feature that uses it. |
| A6 | URI policy (§10) | `file://` from the CLI only; `storage/by_scheme.py` enforces the allow-list | Two stores (fixed in review r1): `Dependencies.inputs` reads inputs only below `inputs.local_roots` and never below the state prefix or an artifact root; `Dependencies.store` writes records and artifacts only below the state prefix and `service.artifact_roots`. `file://` inputs are accepted on HTTP only when `local_roots` is configured (default empty). A requested `artifacts.uri_prefix` may not lie under the state prefix, and artifacts always go to `{uri_prefix}/{job_id}/a{n}/` | With no remote store yet, the HTTP endpoint could take no input at all. Appending the job id changes q1's `uri_prefix` meaning (callers already make it unique per media and revision). `by_scheme` and the GCS store must keep the same input/output split. Now in ARCHITECTURE.md §10. |
| A7 | `service/config.py` | Groups media, asr, captions, llm, vision, labels, storage, inputs, delivery, service, log; `inputs.allow_local_paths` | Groups media, inputs, service, log; `inputs.local_roots` instead of `allow_local_paths`; `service.probe_period_s` and `probe_failure_threshold` added for the timing invariant | Groups arrive with their back ends. Unspecified defaults chosen here: `max_attempts = 5`, `media.min_major = 6` (Ubuntu 24.04 ships 6.1). `inputs.local_roots` now in ARCHITECTURE.md §10. |
| A8 | `app/deps.py` `Dependencies` | `notifier: Notifier` (required); `guard` (item 3) | `notifier: Notifier \| None = None`; no `guard`; delivery never notifies | No callback kind exists on the wire yet. |
| A9 | `app/delivery.py` | Fenced terminal write: re-read the record and answer as step 2 would | Answers 503 `job_in_progress` | Cloud Tasks has normally cancelled that request already; the next delivery reads the record. No record at all calls `_attempt(1)` directly (`decide_attempt(None, …)` is `Start(1)`, still unit-tested). |
| A10 | Tree (§2) | Full v1 tree | Present: `domain/{time,media,inputs,jobs,results,speech,labels,errors,plan}`, `ports.py` (all ten ports, 176 lines), `app/{contract/{envelope,requests,results,records,mapping},constants,deps,audio,stages,runner,publish,delivery}`, `adapters/{media/{ffmpeg,images},storage/local}`, `service/{bootstrap,config,logs,cli,http/{app,routes,push,problems,health,state}}`. Absent: the other domain modules, `app/{frames,llm_output,calibrate}`, `contract/taxonomy`, every model/GCS/notify adapter | Model adapters are left out rather than stubbed (README lists which item brings which). New: `app/contract/records.py` (the stored record model) and `service/http/state.py`. `adapters/media/images.py` is implemented although no stage reads images yet, because Pillow is a base dependency (D3) and `Dependencies.images` is required. |
| A11 | Error codes (§9) | Code lists per category | Adds configuration codes `ffmpeg_unavailable`, `ffmpeg_too_old`, `store_unavailable`, `stage_unavailable`; `capacity_exceeded` for `CapacityError`; `job_not_found` for the GET 404 | §9 lists no configuration or capacity codes. |
| A12 | Error construction | `InternalError("model_output_invalid", detail=…)` | `InternalError(code="model_output_invalid", detail=…)` | ruff EM101 flags a positional string literal in `raise`; keywords pass without a suppression. Now in ARCHITECTURE.md (§3, §9, §11, §13). |
| A13 | Files | `NOTICE`, `Dockerfile`, `tests/models.lock`, `scripts/fetch_models.py` | Not created | NOTICE: deferred to item 1. q2 §5.3 ties the MIT/Apache notices to weights "baked into a distributed image", and CC BY 4.0 attaches to sharing the model; the skeleton neither uses nor distributes any weights, so a NOTICE now would credit material the repository does not contain. README states the planned attribution (U4). Dockerfile: with the Cloud Run benchmark. models.lock / fetch_models.py: with item 1 (the `models` job is gated on the lock file, G16). |
| A14 | D8 test | "a test enforces" no transcript text or signed URIs in logs | Not written | Nothing logs transcripts yet; validation errors already omit input values (`include_input=False`), which a unit test checks. Write the D8 test with item 1. |

## Gate configuration that did not work as documented

| # | Gate | What happened | What the skeleton does |
|---|---|---|---|
| G1 | uv `required-version = "==0.12.23"` | Homebrew uv is 0.12.21 and refuses to run on the project | Every command ran through `uvx uv@0.12.23`. Contributors with a packaged uv hit this too. |
| G2 | ruff format / check | `ruff format .` (0.16.10) rewrote the Python code blocks inside `ARCHITECTURE.md` and the research Markdown, and reformatted `docs/research/q7_cost_grid.py` (reverted) | `extend-exclude` adds `docs/`, `ARCHITECTURE.md`, `ROADMAP.md`. q8b's skeleton had no docs. |
| G3 | typos 1.51.1 | About 50 findings in `docs/research` (Appen, FPR, CPY001, nothink, …) | `docs/**` excluded from typos. |
| G4 | `uv lock` | sherpa-onnx 1.13.8's armv7l wheel has no `Requires-Dist`; the universal lock took that metadata and dropped `sherpa-onnx-core` (which the x86_64/arm64 wheels require) | `sherpa-onnx-core>=1.13.8` declared in `asr`; `check_lock.sh` asserts it is in the lock. Keep the two versions equal. |
| G5 | Version pins | `uv lock` resolved fastapi 0.143.0, released 2026-10-08 12:29 UTC (hours old), not the verified 0.142.4 | Locked to 0.142.4 with `uv lock --upgrade-package fastapi==0.142.4`. Every other package resolved to the decision document's versions. Consider `exclude-newer` or Dependabot's cooldown as the policy. |
| G6 | huggingface-hub pin (q2 §5.2) | Not imported by any code yet | Not declared; the lock has 1.33.0 transitively (faster-whisper; since U16 only via `asr-whisper` and the vision stack). Pin with item 1. |
| G7 | pytest `filterwarnings = error` | starlette 1.7's `TestClient` warns that httpx is deprecated in favour of `httpx2` | `httpx2==2.13.1` in the dev group. The base dependency `httpx>=0.28.1` stays (ARCHITECTURE §12) but nothing imports it yet; consider httpx2 for the adapters. |
| G8 | deptry 0.25.1 | DEP003 `anyio` (imported by `service/http` for admission and threads, only transitive); DEP002 for every extra without an adapter, for `uvicorn` (run, not imported) and for `httpx` | `anyio>=4.15.1` added to the `service` extra; `DEP002` ignore list extended, each entry commented with the item that removes it. |
| G9 | Core coverage 100% | A `match` without a wildcard leaves a partial "no case matched" branch even when mypy proves it exhaustive | `case _: assert_never(x)` arms plus `exclude_lines` pattern `case _:\n\s*assert_never\(` (multi-line). Reviewed config; mypy's exhaustive-match keeps it honest. |
| G10 | coverage `omit` | q8b's six entries name files that do not exist yet | `omit = []`; each heavy adapter adds itself (D4). |
| G11 | mypy | `ignore_missing_imports` for the untyped heavy libraries and `untyped_calls_exclude` for google-auth have no importer yet | Left out; add with the adapters. |
| G12 | import-linter | `ignore_imports = ["scenewise.service.bootstrap -> torch"]` with no such import is an unmatched-ignore error | Left out (comment in pyproject); add with the vision adapters' torch probe. Contracts: 6 kept, 0 broken. |
| G13 | Suppression budget | ruff S603 fires on every `subprocess.run` | Budget 2: ffmpeg's single `_run` helper and the e2e CLI helper, each with `# why:`. The gate scripts use none: the stray-config check walks the tree (git-ignored files included, which tools also read) instead of calling `git ls-files`, and the JUnit check is a text search, not an XML parser (S314/S405). |
| G14 | CI `static` stray step | q8b inlines a `git ls-files` + grep step | `scripts/check_stray_config.py`, run with the runner's `python3` before `setup-uv` (which itself reads a stray `uv.toml`). |
| G15 | CI skip check | q8b greps one `pytest.xml` | `scripts/check_junit.py` over both reports; the unit run also writes `--junitxml`. |
| G16 | `extended.yml` `models` | With no model tests, `pytest -m model` exits 5 and `fetch_models.py` does not exist, so the nightly would be red | A first step sets `run=false` with a notice when `tests/models.lock` is absent; every later step is conditional. |
| G17 | typos, zizmor | q8b runs `uvx typos@1.51.1` and `uvx zizmor@1.30.1` | Both are in the locked dev group and run with `uv run` (decision document §8 lists them in the dev group). zizmor offline: no findings (5 suppressed infos). |
| G18 | Python 3.12 | `HTTPStatus.UNPROCESSABLE_CONTENT` exists only from 3.13 | Literal 422 constant in `problems.py`. |
| G19 | Fixtures | q8b: commit fixtures and "let CI regenerate and diff them" | Bytes differ between ffmpeg builds (Homebrew 9.0.2 vs apt 6.1.1), so CI uses the committed files and tests assert decoded properties only. No flite: Homebrew ffmpeg 9.0.2 lacks it; no speech fixture yet (item 1, q8b OQ9). |
| G20 | Canonical request digest | q8a §5.1: `json.dumps(sort_keys=True, separators=…)` of the parsed body | Not a deviation (review r1, finding 19): the digest equals q8a's, whose default `ensure_ascii=True` output is ASCII. The first draft used `ensure_ascii=False`, which hypothesis broke with a lone surrogate; the property test now pins the q8a form. |
| G21 | `scripts/import_contracts.py` | q8b's listing is 120 columns | Reformatted to 88 (U11); behaviour unchanged. |

## Review r1 fixes

From `docs/research/reviews/skeleton-review-r1.md` (deleted with the other review files; see `docs/research/reviews/README.md`).

| Finding | Fix |
|---|---|
| 1 (must) `file://` allow-list bypass | Separate input and output stores (A6). `LocalBlobStore` gained `excluded` roots; the input store excludes the state prefix and artifact roots even when an input root contains them. Artifacts are job-scoped (`{uri_prefix}/{job_id}`) and never under the state prefix. `tests/e2e/test_isolation.py` reproduces the reviewer's probe: the cross-job read (with no input root, and with one that contains the state) and the cross-job overwrite (direct, the state root itself, and two `..` spellings) now end `failed` / `uri_not_allowed`, and the victim's `result.json` is unchanged. |
| 2 (must) HLS playlist following | Every ffprobe and ffmpeg input gets `-format_whitelist mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mpegts,wav,mp3,aac,flac,ogg` next to the protocol whitelist. A contract test plants a playlist pointing at another local file, named `.m3u8` and `.mp4`: probe and extraction both fail with `corrupt_media`. ARCHITECTURE.md §11 has one sentence on it. Not checked: apt ffmpeg 6.1's behaviour without the list (CI now has the list either way). |
| 3 Errors inside a stage | `_run_stage`: a `RetryableError` still fails the attempt; any other `ScenewiseError` fails the stage with its code; a `ValueError` is `invariant_violation` and any other exception `unexpected`, both internal, for the stage only (§9). Unit tests for both. |
| 4 Unmapped errors on HTTP | Push path: a non-retryable `ScenewiseError` or any unexpected exception from the delivery answers **200** with a rejection body (`outcome: rejected`, problem with code), so Cloud Tasks stops; retryable stays 503. GET: problem+json for every error (an unreadable record is 500 `invariant_violation`). e2e test with a corrupt `status.json`. |
| 5 Reads write to disk | `LocalBlobStore.read` returns `None` for an absent object before taking the lock; only writes create directories and lock files. Contract and e2e tests (a GET of an unknown id leaves the state tree unchanged). |
| 6 `GITHUB_TOKEN` PRs start no CI | **Not fixed, by instruction; open harness/CI question.** PRs opened by a harness run on GitHub Actions with `GITHUB_TOKEN` trigger no `pull_request` workflow, so `static` and `test` never run on them. Options: a GitHub App installation token for agent PRs (author becomes the app, U13 needs a note), or `workflow_dispatch` on `ci.yml` dispatched by the agent workflow on the PR head. Decide before the ruleset is set up (decision document §8 step 1), together with ARCHITECTURE.md §17 open items (b) and (c). **Settled by U18 (2026-10-09):** harness runs on GitHub Actions open pull requests with a machine collaborator's token, so CI runs on them. |
| 7 `required-version` exact pin | **Left as `==0.12.23`, by instruction.** Recorded risk: Dependabot's `uv` ecosystem runs its own bundled uv, which will likely refuse `uv lock` whenever its version differs, so uv dependency updates may fail and become manual (confirm on the first scheduled run). The `uv-lock` and every `uv run` pre-commit/prek hook fail the same way for contributors on a packaged uv (G1: Homebrew 0.12.21); the workaround is `uvx uv@0.12.23` or a matching uv. The alternative is setup-uv `version: "0.12.23"` plus `required-version = ">=0.12.23,<0.13"`. |
| 8 vulture whitelist by bare name | Not fixed (not a few lines). Rule for item 1 onwards: each item deletes the entries it starts reading and adds no generic names; prefer `_.name` forms. One entry was added: `PREREQUISITES` (finding 13 removed its only reader). |
| 9 model-marker step hides collection errors | Fixed: the step fails unless pytest exits 0 or 5. |
| 10 `^\s*\.\.\.$` exclusion is loose | Not fixed; accepted gap: a `-> None` function with a bare `...` body in the core would be excluded from coverage. A check in `check_suppressions.py` would close it. |
| 11 `cancel-in-progress` on main | Fixed: cancels only pull-request runs. |
| 12 Empty test | Deleted. |
| 13 `_dispatch` ceremony | `match stage:` only. |
| 14 `probe()` ignores the deadline | Not fixed (port signature question): `probe` may overrun the attempt deadline by up to 60 s (`PROBE_TIMEOUT_S`), which stays inside the 120 s watchdog grace. Decide with item 1 whether `MediaTool.probe` takes a deadline. |
| 15 Adapter exception mapping | Fixed: unparsable or incomplete ffprobe output and Pillow's `DecompressionBombError` are `corrupt_media`; the full image is copied only for whole-image tiles. |
| 16 CLI traceback on bad settings | Fixed: one line naming the fields, exit 2. |
| 17 No fsync | Partly: the temporary file is fsynced before the rename; the directory is not. The local store remains a single-host development and self-hosting store (D14). |
| 18 Pre-commit runner not pinned | `prek==0.5.5` added to the dev group. |
| 19 G20 wording | Reworded. |

Suppression budget unchanged (2).

## U16/U17 changes

Applied 2026-10-08 from `docs/research/user-decisions.md` U16/U17, [q10](research/q10-pyav-ffmpeg-licence.md) and
[q11](research/q11-asr-without-pyav.md) (§4).

| Where | Change |
|---|---|
| `pyproject.toml` | `asr` drops faster-whisper (and with it ctranslate2, `av`, tokenizers, huggingface-hub); new opt-in `asr-whisper = ["faster-whisper>=1.2.1"]`, commented as bringing GPL x264/x265 through PyAV and left out of published images. deptry's DEP002 entry for faster-whisper now names `asr-whisper`; the import-linter `forbidden` list keeps `ctranslate2` and `faster_whisper` (they still apply to `asr-whisper` builds). Every other pin unchanged |
| `uv.lock` | `uv lock` (0.12.23): 130 packages, no resolved version changes; only faster-whisper's marker (`extra == 'asr-whisper'`), the new optional-dependency group and `provides-extras` change |
| `scripts/check_lock.sh` | Also asserts that `service + asr` and both image sets (`-cpu`, `-cuda`) resolve no `av`, `ctranslate2` or `faster-whisper`, and that `asr-whisper` does resolve faster-whisper. Checked to fail when `asr-whisper` is added to the `asr` set |
| `src/scenewise/ports.py` | Docstrings only: `LanguageIdentifier` is the Whisper-tiny ONNX adapter (q11); `SpeechRecognizer`'s faster-whisper is in `asr-whisper`. No adapter is implemented (roadmap item 1) |
| CI | No workflow change needed: neither job selects `asr-whisper`, and `tests/models.lock` does not exist yet. When item 1 adds the fallback adapter, a separate job with `--extra asr --extra asr-whisper` runs its contract suite (q11 §4) |
| `docs/research/q11/` | Research scripts; already outside every gate (ruff and typos exclude `docs/`, mypy, module size and vulture read only `src`/`tests`/`scripts`) |
| Docs | ARCHITECTURE.md (§2, §4 LID adapter and gate rule, §6, §11 U17, §12 extras, §15, §17), the decision document (findings list, §1.1, Q2, Q8, §4 U16/U17, §4.3, §7.2, §7.5, §8 steps 1–3, §9), ROADMAP.md item 1, README.md, and "superseded" notes in q2 §4.4, §5.2, §5.3 and q8c §2, §3 |

ffmpeg (U17): unchanged. Development uses Homebrew ffmpeg 9.0.2 (no libflite), CI Ubuntu's apt ffmpeg; the ffmpeg in
published images is decided with the first published Dockerfile.

## Gate results (local)

Static gates (CPython 3.14.7, all CPU extras synced): stray config, `uv lock --check`, `check_lock.sh`, ruff format,
ruff check, mypy strict (82 files), import-linter (6 kept, 0 broken), module size (≤ 500), suppressions (2 of 2),
deptry, vulture, typos, zizmor offline: all pass.

Tests, `--extra service` only, CI sequence, after the review r1 fixes (3.13 was not re-run):

| Python | Unit tests | Core coverage (unit only) | All tiers | Overall coverage | Skipped / xfailed |
|---|---|---|---|---|---|
| 3.12.14 | 143 passed | 100% | 247 passed | 98.97% | 0 |
| 3.14.7 | 143 passed | 100% | 247 passed | 98.84% | 0 |

Before the fixes: 139 unit and 226 total passed on 3.12, 3.13 and 3.14 (overall 99.62%, 99.62%, 99.57%).

After U16 (static gates on 3.14.7 with all CPU extras; tiers on 3.12.14 and 3.14.7): all pass, 143 unit and 247 total
on each, core coverage 100%, overall 98.97% (3.12) and 98.84% (3.14), nothing skipped.

Not run at first: the workflows on GitHub (no remote yet; later green in run 37792034530, before U16), and a real `uvicorn` process (the HTTP tests use FastAPI's
`TestClient` against the real app, lifespan and adapters).
