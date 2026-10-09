# Review 2: docs/features/audio-stage.md

mode: catalog · iteration: 2 · verdict: PASS

No `existing_doc` was passed, so check 10 does not apply. `phases.parity` is `false`, so check 7 was skipped.

## What review 1 asked for, and whether it was fixed

1. **The `deadline_exceeded` cause on the probe path: fixed.** Business behaviour and the `FfmpegMediaTool.probe` bullet now give both causes. One is the attempt budget (`remaining`, or the `audio_track` timeout). The other is ffprobe running past the fixed `PROBE_TIMEOUT_S` (60 s), whatever budget is left. This matches `src/scenewise/adapters/media/ffmpeg.py` (`PROBE_TIMEOUT_S`, `FfmpegMediaTool.probe` calling `self._media(argv, timeout=PROBE_TIMEOUT_S)`, and `_run` raising `InternalError(code="deadline_exceeded")` on `TimeoutExpired`).
2. **The `stages.audio.uri` value was given for every surface: fixed.** The document now says the uri is `{prefix}/a{attempt}/audio.wav` over HTTP (`publish`) and the absolute `file://` URI of `DIR/audio.wav` over the CLI. The result-shape block shows both. This matches `src/scenewise/service/cli.py` (`analyse`: `audio_uri = target.resolve().as_uri()`).
3. **"Wire names never appear here" was too broad: fixed.** The claim now covers only the input shapes. It also says that `StageName` values are the wire names and that `SkipReason` values reach the wire through `_stage_fields`. This matches `src/scenewise/domain/jobs.py` (`StageName` docstring) and `src/scenewise/app/contract/mapping.py` (`_stage_fields`, `reason.value`).

The non-blocking points from review 0 are also in place:
- `tests/e2e/test_http.py` and `tests/e2e/test_isolation.py` now have separate roles.
- The document says the `required_stages` check can never fail for `audio`, and names `find_binaries` (`ffmpeg_unavailable` / `ffmpeg_too_old`) as the start-up failure that does apply.
- The `input_unavailable` cause now reads "the path is not an existing regular file".

## What was re-checked this round

- **Check 1 (anchors):** a script checked every `path` (`symbol`) anchor and every backticked repo path in the document. Every path exists from the repo root, and every named symbol greps inside the file it is cited in.
- **Check 2 (line numbers):** the colon detector has one hit, `-map 0:a:0`. That is an ffmpeg stream specifier, so it is a value and stays. The colon-free detector has no hits.
- **Checks 3–5 (backend surface, data shapes, behaviour):** these were read again against the source and hold:
  - `acquire_audio`'s branches and the `AcquiredAudio` shape (`src/scenewise/app/audio.py`).
  - In `src/scenewise/app/runner.py`, acquisition runs outside the per-stage boundary, so its errors fail the whole job. The same file holds the stage-loop calls to `remaining`, the `_dispatch` / `_audio_stage` / `_run_stage` behaviour, and the `audio_wav` capture.
  - `_run`'s whole-job failure (`src/scenewise/app/delivery.py`).
  - `enabled_stages` always includes `AUDIO` (`src/scenewise/app/deps.py`).
  - The `_stores` / `build_dependencies` wiring and the order of its checks (`src/scenewise/service/bootstrap.py`).
  - The `LocalBlobStore._path` / `materialise` error codes (`src/scenewise/adapters/storage/local.py`).
  - The defaults `local_roots = ()`, `required_stages = {AUDIO}` and `min_major = 6` (`src/scenewise/service/config.py`), and `_with_local_root` (`src/scenewise/service/cli.py`).
  - The reachability marks are still correct: `POST /v1/jobs` ✅, `scenewise analyse` ✅, and `AudioSegments` / `AudioManifest` ❌, because no wire model produces them and `acquire_audio` raises `unsupported_media`.
- **Checks 6, 8 and 9:** the research goes well beyond the hints. It covers the input store / output store split, how `{prefix}` is derived, the protocol and demuxer whitelists, start-up checks and the CLI-only path. There are no `⚠️ unverified` markers, and I found no material omission.

## Must Fix

None.
