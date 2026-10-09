# Review 0: docs/concepts/stages-and-outcomes.md

verdict: PASS

## Must Fix
None.

## Checks performed
1. Anchors: I grepped every cited path and symbol and all of them resolve: `StageName`, `SkipReason`, `JobSpec` (domain/jobs.py); `ordered`, `unavailable`, `PREREQUISITES`, `Needs`, `_ORDER` (domain/plan.py); `Outcome`, `StageOutcome`, `Analysis`, `job_state`, `SkipReasonGeneral` (domain/results.py); `LanguageReport` (domain/speech.py); `run_job`, `_run_stage`, `_dispatch`, `_audio_stage`, `remaining` (app/runner.py); `audio` (app/stages.py); `acquire_audio` (app/audio.py); `enabled_stages`, `Dependencies`, `Speech` (app/deps.py); `build_dependencies` (service/bootstrap.py); `ServiceSettings` (service/config.py); `StageNameV1`, `JobRequestV1` (contract/requests.py); `to_domain`, `_stage_fields`, `result_json` (contract/mapping.py); `StageStatusV1`, `StageResultsV1` (contract/results.py); `_run` (app/delivery.py); `readyz` (service/http/routes.py); `main`, `analyse` (service/cli.py). Every test name cited is present in its file. `ARCHITECTURE.md` §6 and §9, `docs/skeleton-notes.md` A1–A3 and `.claude/context/domain.md` "Closed sets" all exist. The §6 quotation matches the text.
2. Line numbers: the colon detector returned 0 hits and the shape detector returned 0 hits. The document contains no coordinates.
3. and 4. Behaviour and data shapes: each of these matches the source.
   - The `enabled_stages` dependency rules.
   - `build_dependencies` passes all-`None` back ends. Its `required_stages` check uses the same detail text.
   - The default for `required_stages`.
   - The output of `/readyz`.
   - `min_length=1` on `JobRequestV1.stages`, and `to_domain` turning it into a frozenset.
   - The CLI's default `--stage`.
   - The `PREREQUISITES` table.
   - The order of the gate, the input acquisition and the loop in `run_job`.
   - `remaining` sits outside `_run_stage`.
   - The exception-to-`Failed` table in `_run_stage`.
   - The `invariant_violation` raised by `_dispatch`.
   - The `Literal` subsets of `Outcome`.
   - `job_state`, including an empty list giving `SUCCEEDED`.
   - `FAILED` and `error_code` in `delivery._run`.
   - The tuples `_stage_fields` returns. `LanguageReport` does not reach the wire.
   - `timings_ms` rounding.
5. Gating: these claims match the code. The per-request `stage_unavailable` is an `InputError` that makes the job record `failed` (tests/unit/test_delivery.py and tests/e2e/test_http.py `test_bad_requests_end_in_a_failed_record`). The start-up `stage_unavailable` is a `ConfigurationError`.
6. Depth: the document goes beyond the hints. It traces the offered set from its back ends to `/readyz`, follows the request and CLI routes to `JobSpec`, and covers how the outcome reaches the record and the wire.
7. Parity: skipped because `phases.parity` is false.
8. There are no `⚠️ unverified` markers to check.
9. No material omission found.
10. Merge or supersede: not applicable because no `existing_doc` was passed.

Two negative claims were checked by grep and hold:
- Nothing outside `plan.py` and `test_plan.py` reads `PREREQUISITES`.
- Under `src`, outside `domain`, the only `SkipReason` member constructed is `NO_AUDIO_STREAM`, in `runner._audio_stage`.

## Notes (not findings)
- The CLI has no job record. When the request asks for a stage that is not offered, `analyse` exits with `EXIT_FAILED`. The gotcha's wording, "so the job is `failed`", is accurate for the HTTP route and is a fair reading for the CLI. No change needed.
