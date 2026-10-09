# Review 1: ARCHITECTURE.md (catalog, merge with existing_doc = committed ARCHITECTURE.md)

Verdict: PASS

Scope: the uncommitted edit (`git diff -- ARCHITECTURE.md`), re-checked against the source under every `layers[].path`
(`src/scenewise/{domain,app,adapters,service}`, `src`, `tests`, `.`), `pyproject.toml` and `docs/skeleton-notes.md`,
with the review_0 findings as the fix targets.

## review_0 findings: status

1. **Must Fix (§7 "One delivery", step 1): fixed.** Step 1 now lists the fourth ending: "any other non-retryable
   rejection outside the run, such as an unreadable record (200, no record; review r1 finding 4)". This matches
   `src/scenewise/service/http/push.py` (`_admitted`). The `except ScenewiseError` and `except Exception` branches
   return `_rejected`. It also matches skeleton-notes "Review r1 fixes", finding 4, and the §7 table row.
2. **Should Fix (§12 `asr` row): fixed.** It now reads "sherpa-onnx, sherpa-onnx-core (G4), …". `pyproject.toml`
   declares `"sherpa-onnx-core>=1.13.8"`, and G4 records why.
3. **Should Fix (§2 partial modules): fixed.** "Built so far" now names what `domain/speech.py`, `domain/labels.py`,
   `domain/jobs.py` and `app/deps.py` lack. It also says that `tests/fakes.py` holds only `InMemoryBlobStore`,
   `FakeMediaTool` and `FakeImageReader`, which matches the classes in that file.
4. **Should Fix (§15 word-end rule): fixed.** "Built so far" lists "the word-end rule (with `captions`)".

## Re-verified in this round

- §2 "Built so far" module list against `git ls-files`. `app/contract/records.py` (`JobRecordV1`) and
  `service/http/state.py` (`ServiceState`) exist. `scripts/check_stray_config.py` and `scripts/check_junit.py` exist.
- §3: `build_dependencies` imports `FfmpegMediaTool` and `PillowImageReader` at the top of its body, and `_stores`
  imports `LocalBlobStore` inside `case "file"` (`service/bootstrap.py`).
- §7 timing: `probe_period_s` = 10 and `probe_failure_threshold` = 3, read in `ServiceSettings` (`probe_window`). The
  probe's 60 s matches review r1 finding 14. `/readyz` returns `{"status": "ready", "stages": …}`
  (`service/http/routes.py` (`readyz`)).
- §10: only the `media`, `inputs`, `service` and `log` groups exist on `Settings`. `min_major` = 6, `local_roots`,
  `artifact_roots`, and `log.format` `json | console` are in `service/config.py`. The log bindings match the
  `bound_contextvars` calls in `runner.py`, `delivery.py` and `push.py`.
- §13: the CLI `analyse` calls `run_job` and writes `out / AUDIO_FILE_NAME` itself. It imports only the constant from
  `publish` and never calls `publish` (`service/cli.py` (`analyse`)).
- Every skeleton-notes row cited by the new text (A9, A13, A14, G4, G8, G12, G14–G16, review r1 findings 4 and 14)
  says what the document attributes to it. The `[notes]` link reference resolves to `docs/skeleton-notes.md`.
- Line-coordinate detectors were run over the whole file. The colon detector has no hits. The shape detector hits only
  values: `(200`, `429/503`, the ruff codes `PLR0911/0912/…` and the date `2026-10-09`.
- Merge/supersede: still-true committed content is kept. The design statements are kept and marked "not built yet",
  and the document keeps its structure, numbering and source citations.

## Must Fix

None.

## Should Fix

None.
