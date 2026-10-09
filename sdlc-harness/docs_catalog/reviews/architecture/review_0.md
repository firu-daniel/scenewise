# Review 0: ARCHITECTURE.md (catalog, merge with existing_doc = committed ARCHITECTURE.md)

Verdict: FAIL (one Must Fix)

Scope: the uncommitted edit (`git diff -- ARCHITECTURE.md`) checked against the source under every `layers[].path`
(`src/scenewise/{domain,app,adapters,service}`, `src`, `tests`, `.`), `pyproject.toml` and `docs/skeleton-notes.md`.
The edit's stated purpose: correct statements about code that exists, mark designed-but-unbuilt behaviour as not built yet,
cite skeleton-notes rows, and keep the structure, numbering, voice and research citations.

## Verified correct (no action)

- §4 `Dependencies` block matches `src/scenewise/app/deps.py` (`Dependencies`): `inputs`, the `= None` defaults,
  `notifier: Notifier | None`, no `guard`. `bootstrap` builds only stores/media/images, so `enabled_stages` is `{audio}`
  (`service/bootstrap.py` (`build_dependencies`), `app/deps.py` (`enabled_stages`)).
- §4 "implemented so far": three adapters, seven of ten Protocols unimplemented, no `ImageGuard` (`ports.py`).
  `acquire_audio` raises `unsupported_media` for segments and manifests (`app/audio.py` (`acquire_audio`)).
- §5 type block: every line not marked "not built yet" exists with the stated fields (`domain/jobs.py`, `domain/results.py`
  (`Failed`, `Analysis`), `domain/speech.py`, `domain/labels.py` (`LabelScores`), `domain/media.py`). Every line
  marked "not built yet" is absent. `plan.PREREQUISITES` has no reader, and nothing constructs `DEPENDENCY_FAILED`.
- §6: a requested stage outside `enabled_stages` raises `InputError(code="stage_unavailable")` before the stages
  (`app/runner.py` (`run_job`)). The wire accepts all six stage names (`app/contract/requests.py` (`StageNameV1`)).
- §7: job id appended to `uri_prefix` and the state prefix refused (`app/delivery.py` (`artifacts_prefix`)). No-record
  shortcut (`handle_delivery`). Terminal-write conflict gives `job_in_progress` 503 (`_finish`, `_in_progress`).
  Probe settings are read only by `ServiceSettings._timing`. `exceeds_push_budget` is declared and never raised. Probe
  timeout is `PROBE_TIMEOUT_S` = 60 s; audio and frame decoding use `deadline - time.monotonic()`
  (`adapters/media/ffmpeg.py`). `/readyz` (`service/http/routes.py` (`readyz`)).
- §9: `_run_stage` maps any other exception to `unexpected` (`app/runner.py`).
- §10: groups and `service` fields match `service/config.py`. The log context bindings match `runner.py`,
  `delivery.py` (`handle_delivery`, `_attempt`) and `push.py` (`_TASK_HEADERS`). The only input-value test is
  `tests/unit/test_mapping.py` (`test_to_domain_hides_input_values`). `_stores` refuses non-`file` schemes with
  `store_unavailable`.
- §12 `service` extra = fastapi, uvicorn, anyio (`pyproject.toml`). §13 CLI `analyse` (`service/cli.py` (`analyse`)).
  §15 hypothesis targets (`test_envelope.py`, `test_jobs.py`, `test_time.py`). §16 G10/G11/G12 statements (`omit = []`,
  no `ignore_missing_imports` override, no `ignore_imports` entry).
- §2 "Built so far" module lists match `git ls-files` and A10/A13.
- Every skeleton-notes row cited (A1–A3, A5–A10, A13, A14, G8, G10–G12, G14–G16, review r1 findings 4 and 14) says what
  the document attributes to it.
- No line coordinates. Both detectors were run over the whole file. The only hits are values: HTTP statuses `429/503`,
  ruff rule codes `PLR0911/0912/…`, the date `2026-10-09`.
- Merge/supersede: nothing true from the committed version was dropped. Each removed line is replaced by its code form
  with the design kept as a comment ("gains options", "gains context", "v1 adds …", `guard` comment, `backend` "to be
  bound").

## Must Fix

1. **§7 "One delivery", step 1 is contradicted by the edit's own new table row and by the code.**
   - Claim (unchanged line in step 1): "From here on, every path ends in a terminal record, a `job_id_conflict`
     rejection (200, no record), or a retryable 429/503."
   - Code: `src/scenewise/service/http/push.py` (`_admitted`) answers any non-retryable `ScenewiseError`, and any
     unexpected exception, that escapes `handle_delivery` with `_rejected`. That is 200 with a rejection body and no
     terminal record. One example is an unreadable `status.json`: `src/scenewise/app/contract/mapping.py`
     (`record_from_json`) raises `InternalError(code="invariant_violation")`. The edit added this case to the table
     ("Unreadable record, or another non-retryable error outside the run | 200 + rejection …; no record written (review
     r1 finding 4)"), but left step 1 listing only three endings.
   - Correction: add the fourth ending to step 1, in the same voice. For example: "… a `job_id_conflict` rejection (200,
     no record), any other non-retryable rejection outside the run, such as an unreadable record (200, no record; review
     r1 finding 4), or a retryable 429/503."

## Should Fix (do not block)

2. **§12 extras table, `asr` row.** `pyproject.toml` `asr` also lists `sherpa-onnx-core`, a recorded departure (G4). The
   row lists "sherpa-onnx, onnx-asr, onnxruntime, numpy". The edit fixed the `service` row with a G8 citation, so this
   row should get the same treatment: add `sherpa-onnx-core` (G4).
3. **§2 tree comments for modules that exist only in part.** "Built so far" names the absent modules, but some present
   modules still carry comments that describe unbuilt content:
   - `domain/speech.py`: VAD runs, cuts, LID windows, language rule, merge. Only the three value types exist.
   - `domain/labels.py`: `Label`, prompt set, `frame_scores()`, `select()`. Only `LabelScores` exists.
   - `domain/jobs.py`: `StageOptions`.
   - `app/deps.py`: `CalibrationDeps`.
   - `tests/fakes.py`: "in-memory fakes of every port". It holds three, `InMemoryBlobStore`, `FakeMediaTool` and
     `FakeImageReader`.
   §4 and §5 cover most of these, but `frame_scores()`/`select()` and the fakes are flagged nowhere. One sentence in
   "Built so far" would close it.
4. **§15 "Built so far".** The list of tests not built yet omits the word-end rule, which the "Pure core" bullet says
   hypothesis covers. That rule arrives with captions (`domain/captions.py` is absent).
