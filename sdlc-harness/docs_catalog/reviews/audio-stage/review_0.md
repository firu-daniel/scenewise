# Review 0: docs/features/audio-stage.md

mode: catalog · iteration: 0 · verdict: FAIL

## Scope of verification

- Every `path` (`symbol`) anchor in the document was checked mechanically: the path exists from the repo root, and the named symbol greps inside the cited file. Everything resolves except the items under Must Fix 1.
- Line-number detectors (check 2): the colon detector's one hit is `-map 0:a:0` on the ffmpeg argv line. That is an ffmpeg stream specifier, which is a value, so it stays. The shape detector had no hits.
- These claims were read against the source and are correct: the acquisition branches (`src/scenewise/app/audio.py` `acquire_audio`); the runner flow, skip reason, `_run_stage` boundary and `remaining` (`src/scenewise/app/runner.py`); `job_state` (skips do not make a job `partial`); the publish order and media type (`src/scenewise/app/publish.py`); the `artifacts_prefix` rules and whole-job failure in `_run` (`src/scenewise/app/delivery.py`); the wire models and the dropped `mime`/`reason` (`src/scenewise/app/contract/requests.py`, `mapping.py` `_audio`); `result_json`/`_stage_fields`; the ffprobe/ffmpeg argv, `attached_pic`, `joined`, `scenewise-audio-`, `_PROTOCOLS`/`DEMUXERS`, `find_binaries` and `min_major = 6`; the input allow-list and exclusion in `LocalBlobStore._path`/`materialise`; the `_stores`/`build_dependencies` wiring; the CLI behaviour (`_with_local_root`, default stage, `EXIT_FAILED`, `FIRST_ATTEMPT`, no `publish`); the ports constants; skeleton-notes A1/A2 (32 kB per second); and the README artifact-path claims.
- Reachability: `POST /v1/jobs` is reached through `src/scenewise/service/http/routes.py` (`post_job`) → `push.py` (`push`) → `handle_delivery`, so ✅ is correct. `scenewise analyse` ✅ is correct. `AudioSegments`/`AudioManifest` ❌ is correct: `mapping._audio` produces only `AudioFile`/`NoAudio`, and `acquire_audio` raises `unsupported_media`.
- Research depth is adequate. The trace follows `audio.wav` from acquisition to the writer (`publish`, and the CLI's own write), covers the input/output store split, and covers how the HTTP and CLI paths differ. No material omission was found.
- Check 7 (parity) was skipped because `phases.parity` is `false`. Check 10 does not apply because no `existing_doc` was passed.

## Must Fix

1. **Paths that do not resolve from the repo root (check 1).**
   - Claim (Technical implementation → tests): "Fixtures: `tests/fixtures/clip.mp4`, `silent.mp4`, `tone.m4a`". `silent.mp4` and `tone.m4a` are written as bare filenames and do not exist at the repo root. They exist only at `tests/fixtures/silent.mp4` and `tests/fixtures/tone.m4a`.
     Correction: write them as `tests/fixtures/silent.mp4` and `tests/fixtures/tone.m4a`.
   - Claim (Technical implementation → domain): "They stay in `app/contract`". The path `app/contract` does not exist from the repo root.
     Correction: write `src/scenewise/app/contract`.

## Should Fix (non-blocking)

2. **Wrong role given for a test file.** In the tests sub-section, the line "`tests/e2e/test_http.py`, `tests/e2e/test_isolation.py`: no cross-job reads of `audio.wav`" gives both files the same role. Only `tests/e2e/test_isolation.py` tests isolation (`test_cross_job_read_is_refused`, `test_cross_job_overwrite_is_refused`, plus the artifact-root scoping tests). `tests/e2e/test_http.py` runs the HTTP path end to end: `test_job_runs_to_a_terminal_record` (which reads `a1/audio.wav`), `test_video_without_audio` and `test_corrupt_media_fails_the_job`.
   Correction: split the line. Give `tests/e2e/test_http.py` the role "HTTP end-to-end: WAV under `a1/`, no-audio skip, corrupt media fails the job". Give `tests/e2e/test_isolation.py` the role "cross-job read and overwrite are refused (`uri_not_allowed`)".
3. **The audio `stage_unavailable` start-up failure cannot actually happen.** Business behaviour says start-up fails with `stage_unavailable` "if a deployment cannot run it". But `enabled_stages` always adds `StageName.AUDIO` (`src/scenewise/app/deps.py`, comment "needs only the media tool, which is always present"). A deployment without ffmpeg fails earlier in `find_binaries`, with `ffmpeg_unavailable`/`ffmpeg_too_old`.
   Correction: say that the `required_stages` check can never fail for `audio` today, and that a missing or old ffmpeg is the start-up failure that actually applies.
4. **`input_unavailable` precision.** `LocalBlobStore.materialise` raises it when `not path.is_file()`, so it also covers a path that exists but is a directory.
   Correction: "the path is not an existing regular file".
