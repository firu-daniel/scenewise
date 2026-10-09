# Review 1: docs/features/audio-stage.md

verdict: FAIL

Mode: catalog, with no `existing_doc`. `phases.parity` is false, so check 7 is skipped.

## What was checked

- **Anchors (check 1):** every cited path and symbol resolves in the cited file. That covers all of `## Anchor files` and every inline anchor in the body, including the tests, the fixtures, `README.md` and `docs/skeleton-notes.md`.
- **Line numbers (check 2):** `grep -nE ':[0-9]+'` finds one hit, `-map 0:a:0`. That is an ffmpeg stream specifier, so it is a value, not a line coordinate. The colon-free detector finds nothing.
- **Backend surface (check 3):** `POST /v1/jobs` follows `routes.py` (`post_job`) → `push.py` (`push`) → `delivery.py` (`handle_delivery`). `scenewise analyse` matches `cli.py` (`main`, `analyse`). The `reachable? ❌` mark on `AudioSegments` / `AudioManifest` is correct: `requests.py` has only `AudioFileV1` / `NoAudioV1`, and `audio.py` (`acquire_audio`) raises `unsupported_media`.
- **Data shapes (check 4):** `AudioStageV1`, `ProbedMediaV1`, `StageResultsV1`, `_audio`, `result_json` and `publish` / `attempt_prefix` / `AUDIO_FILE_NAME` / `WAV_MEDIA_TYPE` all match the source. So do `artifacts_prefix` / `job_prefix` and the `LocalBlobStore._path` / `materialise` error codes.
- **Depth (check 6):** good. The document traces the input store / output store split, how the `{prefix}` is derived, the protocol and demuxer whitelists, the start-up checks and the CLI's local-root injection. It does not stop at the hints.

## Must Fix

1. **The `deadline_exceeded` cause is wrong for the probe path.**
   - Claim (Business behaviour, failure codes): "`deadline_exceeded`: the attempt budget ran out (`ffmpeg.py` (`_run`); `runner.py` (`remaining`))". The adapters section only gives "Timeout = `deadline - time.monotonic()`" for `audio_track`.
   - Contradicted by: `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool.probe`). The probe calls `self._media(argv, timeout=PROBE_TIMEOUT_S)`, a fixed 60 s that does not depend on the attempt deadline. `_run` raises `InternalError(code="deadline_exceeded")` on `TimeoutExpired`, so a probe that runs past 60 s also fails the job with `deadline_exceeded`, even when plenty of attempt budget is left.
   - Correction: say that `deadline_exceeded` arises when the attempt budget runs out (`remaining`, or the `audio_track` timeout) **or** when ffprobe runs past the fixed `PROBE_TIMEOUT_S` (`ffmpeg.py` (`PROBE_TIMEOUT_S`, `FfmpegMediaTool.probe`)). Add the probe timeout to the `FfmpegMediaTool.probe` bullet in `### adapters`.

2. **The `stages.audio.uri` value is stated for every surface, but it only holds over HTTP.**
   - Claim (Business behaviour, flows): "`stages.audio.uri` points at `{prefix}/a{attempt}/audio.wav`". The Result shape block repeats it as `"uri": "{prefix}/a{attempt}/audio.wav"|null`.
   - Contradicted by: `src/scenewise/service/cli.py` (`analyse`). The CLI writes `out / AUDIO_FILE_NAME` and passes `audio_uri = target.resolve().as_uri()` to `mapping.result_json`. Over the CLI, `stages.audio.uri` is therefore the `file://` URI of `DIR/audio.wav`, not an `a{attempt}/` path.
   - Correction: scope the `{prefix}/a{attempt}/audio.wav` value to the HTTP path (`publish`). State that over the CLI the uri is the absolute `file://` URI of `DIR/audio.wav`.

3. **"Wire names never appear here" is contradicted by the domain layer.**
   - Claim (`### domain`, last bullet): "Wire names never appear here. They stay in `src/scenewise/app/contract` (`src/scenewise/domain/inputs.py` module docstring)."
   - Contradicted by: `src/scenewise/domain/jobs.py` (`StageName`). Its docstring says "the values are the wire names", and `SkipReason` values such as `no_audio_stream` reach the wire unchanged through `src/scenewise/app/contract/mapping.py` (`_stage_fields`, `reason.value`).
   - Correction: narrow the claim to the input shapes. `domain/inputs.py` carries no wire names: `kind`, `mime` and `reason` live only in `app/contract/requests.py`. Alternatively, drop the bullet.

## Notes (not blocking)

- `POST /v1/jobs` returns `→ JobStatusV1` only on `Finished`. `push.py` (`_rejected`, `problem_response`) also answers with a rejection body, or a problem body plus `Retry-After`. The feature does not hinge on this, and `[[job-delivery]]` is the natural home for it.
