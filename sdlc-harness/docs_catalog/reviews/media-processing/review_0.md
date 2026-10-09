# Review 0: docs/concepts/media-processing.md

verdict: PASS

## Must Fix

None.

## Verified

- Anchors (check 1): every cited path exists, and every named symbol resolves by grep in its cited file. Checked: `MediaTool`, `ImageReader`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`; `MediaInfo`, `Frame`, `Tile`, `Rect`, `RGB24_BYTES_PER_PIXEL`, `FrameRef`, `SpriteGrid`; `FfmpegMediaTool`, `find_binaries`, `scaled_size`, `_run`, `_media`, `_media_info`, `_file`, `DEMUXERS`, `_PROTOCOLS`, `PROBE_TIMEOUT_S`, `_STDERR_TAIL`, `_MIN_SIDE_PX`, `_VERSION`, `_INSTALL_HINT`; `PillowImageReader`; `MediaSettings`, `Settings`; `build_dependencies`; `Dependencies`; `acquire_audio`, `AcquiredAudio`; `audio` (stages); `run_job`, `remaining`; `_media` (mapping), `ProbedMediaV1`; `EXIT_CONFIGURATION`; `create_app`; `MediaToolContract`, `test_audio_track_after_the_deadline`, `test_timeout_is_deadline_exceeded`, `test_a_playlist_cannot_reach_other_files`, `ImageReaderContract`, `FakeMediaTool`, `FakeImageReader`. Prose references also resolve: `vulture_whitelist.py` `_.video_frames`, `pyproject.toml` `"subprocess.call".msg` and the pillow comment "ImageReader is always needed (D3)", `docs/skeleton-notes.md` A10/G13/G19, `ARCHITECTURE.md` §11 bullets ("Why subprocess", "Never given a URL", "Checked at start-up", "Which ffmpeg (U17)"), `README.md` "Requirements", `docs/research/q10-pyav-ffmpeg-licence.md`, and the fixture files under `tests/fixtures/`.
- Line numbers (check 2): neither detector finds a line coordinate. The hits are all values: the stream specifier `0:a:0`, `pipe:1`, and `_STDERR_TAIL` (500).
- Mechanism claims (checks 4 and 5): checked against `src/scenewise/adapters/media/ffmpeg.py` and found exact. These cover the argv for probe, audio_track and video_frames; the protocol and demuxer whitelists; the fixed `PROBE_TIMEOUT_S` for probe and for the version check; the deadline-derived timeouts; the `timeout <= 0` pre-check in `_run`; `TimeoutExpired` mapped to deadline_exceeded with the basename as detail; the exclusion of `attached_pic`; the exception set that becomes "unreadable probe"; the byte-wise join; the never-upscale `scaled_size` with its 1 px clamp; and the "no frame at" size check. The validation rules in `src/scenewise/domain/media.py` match the doc, as does the Pillow crop/copy/thumbnail behaviour with `invalid_sprite_grid`.
- Callers and reachability (checks 6 and 9): `acquire_audio` is called from `run_job` with `store=deps.inputs` and is the only `src` caller of `probe` and `audio_track`. `run_job` is reached from `src/scenewise/app/delivery.py` (HTTP) and `src/scenewise/service/cli.py`. A search of every layer path found no `src` caller of `video_frames` or `ImageReader.read`, so the "Not yet reached" claim is correct. The result mapping to `ProbedMediaV1` drops width and height, which is also correct.
- Start-up: `build_dependencies` → `find_binaries` with `MediaSettings` (defaults `ffmpeg`, `ffprobe`, 6). The `SCENEWISE_` prefix with the `__` delimiter is confirmed. The CLI maps `ConfigurationError` to `EXIT_CONFIGURATION` = 2. The FastAPI lifespan builds the dependencies.
- No `⚠️ unverified` markers are present. Parity is skipped because `phases.parity` is false. No `existing_doc` was passed, so check 10 does not apply.

## Notes (not blocking)

- `Frame.__post_init__` also rejects a width or height that is not positive (`_check_positive`). The doc mentions only the buffer-length check. This is optional to add.
