# Review: docs/features/cli-analyse.md (catalog, iteration 0)

verdict: PASS

## Scope reviewed
I ran the full catalog review (checks 1-10; check 7 skipped because `phases.parity` is `false`). I also checked the uncommitted diff, which touches only the `## Related` line.

## Cross-links (the diff)
Every `[[slug]]` resolves to a file in the corpus, and each target covers the topic it is linked for:
- `[[job-submission]]` -> docs/features/job-submission.md (the HTTP push path, which the CLI contrasts with)
- `[[audio-stage]]` -> docs/features/audio-stage.md
- `[[layering-and-ports]]` -> docs/concepts/layering-and-ports.md (composition root, `build_dependencies`)
- `[[configuration]]` -> docs/concepts/configuration.md (`Settings`, `SCENEWISE_*`)
- `[[storage-and-uri-policy]]` -> docs/concepts/storage-and-uri-policy.md (input/output store split, `LocalBlobStore`)
- `[[job-results-and-artifacts]]` -> docs/features/job-results-and-artifacts.md (`result_json`, `JobResultV1`, `AUDIO_FILE_NAME`)
- `[[error-model]]` -> docs/concepts/error-model.md (states that it covers CLI exit codes)

`git diff` shows that no other line in the document changed.

## Accuracy
- Anchors: every cited path exists, and every named symbol resolves by grep in its cited file (including `LocalBlobStore._path`/`materialise`, `FfmpegMediaTool.probe`/`audio_track`, `_run`, `DEMUXERS`, `ServiceSettings._timing`, and the e2e test names).
- Line numbers: both detectors return no hits.
- Claims checked against source and found correct:
  - CLI and argparse shape, the exit-code mapping, the stderr line formats, and the write after the `try` block (src/scenewise/service/cli.py).
  - `enabled_stages` offers only audio, and the `_stores` `file://`-only rule (src/scenewise/app/deps.py, src/scenewise/service/bootstrap.py).
  - Settings defaults: `attempt_budget_s` 1500, `min_major` 6, state prefix `cwd/.scenewise/state`, log format json, logging to stderr (src/scenewise/service/config.py, src/scenewise/service/logs.py).
  - `job_state`: partial only on Failed, and a skip is not a failure.
  - `result_json`: `indent=2`.
  - The CLI e2e tests: assertions and fixtures.
  - The ARCHITECTURE.md quote, which is in §13.

## Findings
None (no Must Fix).

Non-blocking note, not a finding: "An error inside a stage fails only that stage" leaves out that `_run_stage` (src/scenewise/app/runner.py) re-raises `RetryableError`, which would exit 1. The only wired stage (`stages.audio`) cannot raise one today, so this is not a material error.
