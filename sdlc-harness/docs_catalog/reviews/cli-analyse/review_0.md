# Review 0: docs/features/cli-analyse.md (mode: catalog)

verdict: PASS

## Must Fix

None.

## What was verified

- **Anchors (check 1).** Every cited path exists, and every named symbol resolves in its file: `cli.py` (`main`, `analyse`, `_parser`, `_with_local_root`, `EXIT_*`), `bootstrap.py` (`build_dependencies`, `_stores`), `runner.py` (`run_job`, `_run_stage`, `remaining`), `audio.py` (`acquire_audio`), `stages.py` (`audio`), `deps.py` (`Dependencies`, `enabled_stages`), `publish.py` (`AUDIO_FILE_NAME`), `mapping.py` (`result_json`), `results.py` (contract models), the domain modules, `ffmpeg.py` (`find_binaries`, `FfmpegMediaTool`, `_run`, `DEMUXERS`), `local.py` (`LocalBlobStore._path`, `materialise`), `images.py` (`PillowImageReader`), `ports.py` (`AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`, `MediaTool`, `BlobStore`), `delivery.py` (`handle_delivery`), `config.py`, `logs.py`, `__init__.py`, `__main__.py`, `pyproject.toml` `[project.scripts]`, and the e2e test and fixture names. README "Run the audio stage" and the ARCHITECTURE.md §13 quote ("Ownership on the delivery path") both resolve.
- **Line numbers (check 2).** Both detectors return zero hits. The only parenthesised number is `FIRST_ATTEMPT` (1), which is a value.
- **Behaviour (checks 3-5).** The following all match the code: the exit-code mapping (ConfigurationError gives 2, any other ScenewiseError gives 1, ValidationError gives 2); the stderr formats; the default stage `audio`; `enabled_stages` returning only `audio` with every back end `None`; `stage_unavailable` being InputError for a requested stage and ConfigurationError for `required_stages`; the local-root append through `model_copy`; the input store excluding the state and artifact roots; no `--out` dir when there is no audio stream; the WAV format; `indent=2` plus a trailing newline; the uncaught OSError after the `try`; the `file://`-only `state_prefix`; and logging to stderr.
- **Depth (check 6).** The document traces CLI to bootstrap, run_job, acquire_audio, the ffmpeg/store adapters and result_json. It documents why publish is not reached, and what the CLI writes (audio.wav, stdout) and does not write (no record, no result.json).
- **Parity (check 7).** Skipped because `phases.parity` is `false`.
- **Omissions (check 9).** None material.

## Advisory (not blocking; optional precision fixes)

1. `## Business behaviour` "Partial": "An error inside a stage fails only that stage" is too broad. `src/scenewise/app/runner.py` (`_run_stage`) re-raises `RetryableError`, which then fails the whole job (exit 1). In the CLI the audio stage cannot raise one, so the claim holds for this feature as written. Suggested wording: "any error other than a retryable one".
2. `## Invoked from` says "Nothing imports `scenewise.service`". `src/scenewise/__main__.py` does import it. `.claude/context/service.md` § Responsibility calls `__main__` "the exempt caller". Suggested wording: "Nothing else imports `scenewise.service`".
3. `### Backend surface`: the `file,pipe` / `DEMUXERS` restriction applies to the probe and extraction runs (`_PROTOCOLS`). It does not apply to the `ffmpeg -version` run in `find_binaries`, which opens no input. Optionally scope the sentence to the media runs.
