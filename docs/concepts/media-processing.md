# Media Processing with ffmpeg

> One-line: every media read in scenewise goes through two ports. `MediaTool` runs the system ffmpeg and ffprobe as child processes, only ever on local files, to probe media, extract one normalised WAV track and decode RGB24 frames. `ImageReader` uses Pillow to cut still images into RGB frames.

## What it is & why

- **Two ports, two adapters.** `src/scenewise/ports.py` (`MediaTool`) is implemented by `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool`). `src/scenewise/ports.py` (`ImageReader`) is implemented by `src/scenewise/adapters/media/images.py` (`PillowImageReader`). Both adapters are built once in `src/scenewise/service/bootstrap.py` (`build_dependencies`) and carried in `src/scenewise/app/deps.py` (`Dependencies`) as the fields `media` and `images`. Neither field is optional.
- **Why subprocess, not a binding.** A decoder crash on hostile video kills a child process, not the service with its loaded models. A timeout can kill a child process but cannot kill a thread. PyAV and ffmpeg-python are rejected for this reason (`ARCHITECTURE.md` §11 "Why subprocess").
- **Why ffmpeg never sees a URL.** Every input is first fetched through `BlobStore` into a local file (`src/scenewise/app/audio.py` (`acquire_audio`) calls `store.materialise(uri)`). ffmpeg then runs with a protocol whitelist and a demuxer whitelist. Without them, an HLS playlist could make ffmpeg open files that bypass the store's URI allow-list (`ARCHITECTURE.md` §11 "Never given a URL").
- **A system dependency, checked at start-up.** ffmpeg and ffprobe are not Python packages. scenewise refuses to start when they are missing or too old (`README.md` "Requirements"; `ARCHITECTURE.md` §11 "Checked at start-up").

## How it works

### The port contracts: `src/scenewise/ports.py`
- `MediaTool` (docstring "never given a URL, only local files") has three methods:
  - `probe(path) -> MediaInfo` describes one file.
  - `audio_track(parts, *, deadline) -> AbstractContextManager[Path]` concatenates `parts` and yields **one** 16 kHz mono `pcm_s16le` WAV. The file is valid only inside the context.
  - `video_frames(path, times, *, max_side, deadline)` yields one `Frame` per requested time, in order, with the longer side `<= max_side`.
  - Errors: undecodable input is `InputError(code="corrupt_media")`. Running out of time is `InternalError(code="deadline_exceeded")`. `deadline` is a `time.monotonic()` value, not a duration.
- `ImageReader.read(path, tiles, *, max_side) -> list[Frame]` returns one RGB frame per tile, in order, with the longer side `<= max_side`.
- Audio format constants: `AUDIO_SAMPLE_RATE` (`16_000` Hz) and `AUDIO_CHANNELS` (`1`, mono). The ffmpeg adapter passes them to `-ar` and `-ac`. The test fake `tests/fakes.py` (`FakeMediaTool`) writes its WAVs with the same constants.

### Domain values: `src/scenewise/domain/media.py`
- `MediaInfo` holds `duration: Seconds`, `has_audio`, `has_video`, `width`, `height`. Its `__post_init__` rejects a negative duration and rejects a width without a height (or the reverse): both are known or both are `None`.
- `Frame` holds `timestamp`, `width`, `height`, `rgb: bytes`. The pixels are packed RGB24, row-major. `__post_init__` enforces `len(rgb) == width * height * RGB24_BYTES_PER_PIXEL` (3).
- `Tile` holds `timestamp` and `rect: Rect | None`. `rect=None` means the whole image.
- `Rect` holds `x, y, width, height`. The origin is top-left, the origin may not be negative, and the size must be positive.
- `FrameRef` and `SpriteGrid` live in the same module. They describe image inputs (a URI plus a timestamp, and a sprite-sheet layout). No adapter in this concept reads them.

### Start-up: `find_binaries` (`src/scenewise/adapters/media/ffmpeg.py`)
1. `build_dependencies` calls `find_binaries(ffmpeg=..., ffprobe=..., min_major=...)` with the three fields of `src/scenewise/service/config.py` (`MediaSettings`):
   - `ffmpeg`, default `"ffmpeg"`
   - `ffprobe`, default `"ffprobe"`
   - `min_major`, default `6` (commented "Ubuntu 24.04 ships 6.1")

   They are set through `SCENEWISE_MEDIA__FFMPEG`, `SCENEWISE_MEDIA__FFPROBE` and `SCENEWISE_MEDIA__MIN_MAJOR` (`Settings`: `env_prefix="SCENEWISE_"`, `env_nested_delimiter="__"`).
2. Both names are resolved with `shutil.which`. If either is missing, `find_binaries` raises `ConfigurationError(code="ffmpeg_unavailable")`, with the install hint `_INSTALL_HINT` as its detail.
3. It runs `ffmpeg -hide_banner -version` and reads the major version with the regex `_VERSION` (`version n?(\d+)\.`). A non-zero exit or no match raises `ffmpeg_unavailable` ("cannot read ffmpeg's version"). A major version below `min_major` raises `ConfigurationError(code="ffmpeg_too_old")`. **Only ffmpeg's version is checked, not ffprobe's.**
4. It returns the two absolute paths, which are passed to `FfmpegMediaTool(ffmpeg=..., ffprobe=...)`.
- Where the error surfaces: the CLI turns a `ConfigurationError` into exit code `EXIT_CONFIGURATION` (`2`) (`src/scenewise/service/cli.py`). The HTTP service calls `build_dependencies` inside the FastAPI lifespan (`src/scenewise/service/http/app.py` (`create_app`)), so a missing ffmpeg stops start-up.

### Running a process: `_run` and `_media`
- `_run(argv, *, timeout)` is "the one place scenewise starts a process". It calls `subprocess.run` with an argv list (never a shell), `capture_output=True`, `check=False` and the given timeout. ruff bans `subprocess.call` (`pyproject.toml` `"subprocess.call".msg`), and the S603 suppression on `_run` is one of the two in the suppression budget (`docs/skeleton-notes.md` G13).
- If the timeout is `<= 0` **before** the process starts, or `subprocess.TimeoutExpired` is raised, `_run` raises `InternalError(code="deadline_exceeded")`. In the second case the detail is the binary's basename.
- `FfmpegMediaTool._media` wraps `_run`. A non-zero exit becomes `InputError(code="corrupt_media")` whose detail is the last `_STDERR_TAIL` (500) characters of stderr. On success it returns stdout.
- Every input is passed as `file:<absolute path>` (`_file`), preceded by `_PROTOCOLS`: `-protocol_whitelist file,pipe -format_whitelist` followed by `DEMUXERS` (`mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mpegts,wav,mp3,aac,flac,ogg`). This excludes `hls`, `concat` and image sequences, so a local file whose content is a playlist cannot open other files (`ARCHITECTURE.md` §11).

### `probe`
- Runs `ffprobe -v error <_PROTOCOLS> -print_format json -show_format -show_streams file:<path>` with the fixed timeout `PROBE_TIMEOUT_S` (60 s). This timeout does **not** come from the job deadline.
- `_media_info` builds the `MediaInfo`:
  - `duration` comes from `format.duration`. If it is missing, the result is `corrupt_media` ("no duration").
  - `has_audio` is true when any stream has `codec_type == "audio"`.
  - Video streams are those with `codec_type == "video"`, **excluding** streams with `disposition.attached_pic` (cover art). `width` and `height` come from the first remaining video stream.
- Unparsable JSON, or a missing or malformed field (`KeyError`, `TypeError`, `AttributeError`, `ValueError`), becomes `corrupt_media` ("unreadable probe").

### `audio_track`
- Creates a `tempfile.TemporaryDirectory` (prefix `scenewise-audio-`). When there is more than one part, the parts are joined **byte-wise** into `joined`. This is not ffmpeg's `concat`.
- Runs `ffmpeg -nostdin -hide_banner -loglevel error <_PROTOCOLS> -i file:<source> -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le -map_metadata -1 -fflags +bitexact -f wav -y file:<track.wav>`. Only the **first** audio stream is mapped, and metadata is stripped.
- The timeout is `deadline - time.monotonic()`. The method yields the WAV path, and the directory is deleted when the context exits.
- On a file with no audio stream, ffmpeg fails and the result is `corrupt_media`. The only caller avoids this by probing first (see `## Where it's used`).

### `video_frames` and `scaled_size`
- First calls `probe`. If `width` or `height` is `None`, it raises `corrupt_media` ("no video stream"). `scaled_size(width, height, max_side)` scales by `min(1.0, max_side / max(width, height))`. It never upscales, and each side is clamped to at least 1 px (`_MIN_SIDE_PX`).
- For **each** time it starts a separate ffmpeg process: `-ss <t:.3f>` before `-i` (an input seek), then `-frames:v 1 -vf scale=W:H -f rawvideo -pix_fmt rgb24 pipe:1`. Each process gets the remaining time until `deadline` as its timeout.
- If stdout is not exactly `W*H*3` bytes (for example, a time past the end), it raises `corrupt_media` ("no frame at <t> s"). Otherwise it yields a `Frame`.

### `PillowImageReader.read` (`src/scenewise/adapters/media/images.py`)
- Opens the image and converts it to `"RGB"`. `UnidentifiedImageError`, `Image.DecompressionBombError` or `OSError` becomes `corrupt_media` ("unreadable image").
- For each tile:
  - A tile with a `rect` is cropped. A rect that extends past the image raises `InputError(code="invalid_sprite_grid")` ("tile outside the image").
  - A whole-image tile is copied first, so the converted image is not modified in place.
  - Each part is shrunk with `thumbnail((max_side, max_side))` and returned as `Frame(rgb=part.tobytes())`.
- It needs no timeout and no subprocess. Pillow is a base dependency (`pyproject.toml` `"pillow>=12.3.0"`, comment "ImageReader is always needed (D3)").

## Where it's used

- **[[audio-stage]]**: `src/scenewise/app/audio.py` (`acquire_audio`) materialises an `AudioFile` input through `deps.inputs`, calls `media.probe`, and yields `AcquiredAudio(media=info, track=None)` when `has_audio` is false. Otherwise it opens `media.audio_track([path], deadline=deadline)`. It always passes a **single** part: `AudioSegments` and `AudioManifest` raise `UnsupportedMediaError(code="unsupported_media")`. `src/scenewise/app/stages.py` (`audio`) returns the WAV bytes.
- **[[job-results-and-artifacts]]**: the probed `MediaInfo` becomes `Analysis.media` in `src/scenewise/app/runner.py` (`run_job`), and the result reports `duration_s`, `has_audio` and `has_video` from it (`src/scenewise/app/contract/mapping.py` (`_media`) → `ProbedMediaV1`). Width and height are not reported.
- **[[job-submission]]** and **[[cli-analyse]]**: both entry points reach media processing through `run_job`, which wraps the whole stage loop in `acquire_audio`. Both call `build_dependencies`, so both are subject to the start-up check. See also [[layering-and-ports]] for where the adapters are built.
- **Not yet reached from `src`:** `MediaTool.video_frames` and `ImageReader.read` have no caller under any layer path outside `tests/`. `vulture_whitelist.py` lists `_.video_frames` as an unused method. `PillowImageReader` exists because `Dependencies.images` is required, and "no stage reads images yet" (`docs/skeleton-notes.md` A10). Both are exercised only by the contract tests.

## Gotchas / constraints

- `probe` always uses the fixed 60 s `PROBE_TIMEOUT_S`, including the probe inside `video_frames`. Only the extraction and decode calls are bound to the job `deadline`. A probe can therefore run past a nearly expired deadline. `run_job` checks the deadline only between stages (`remaining`).
- A `deadline` already in the past makes `_run` raise `deadline_exceeded` without starting ffmpeg (`tests/contract/mediatool_contract.py` (`test_audio_track_after_the_deadline`)). A budget that runs out during the run is killed by the subprocess timeout and surfaces as the same code (`tests/contract/test_mediatool_ffmpeg.py` (`test_timeout_is_deadline_exceeded`)).
- Byte-wise joining of several parts works only for formats that can be concatenated as bytes (for example, MPEG-TS segments). No `src` caller passes more than one part today.
- `has_audio` counts every audio stream, but `audio_track` maps only `0:a:0`.
- Cover-art streams (`attached_pic`) do not count as video, so an audio file with embedded art probes as `has_video=False`.
- The test fixtures in `tests/fixtures/` (`clip.mp4`, `silent.mp4`, `tone.m4a`, made by `tests/fixtures/generate.sh`) differ byte-for-byte between ffmpeg builds. Tests therefore assert decoded properties only (`docs/skeleton-notes.md` G19).
- The ffmpeg used by published images (apt GPL build or an LGPL-only build) is still open (`ARCHITECTURE.md` §11 "Which ffmpeg (U17)"; `docs/research/q10-pyav-ffmpeg-licence.md`).
- Tests: `tests/contract/mediatool_contract.py` (`MediaToolContract`) runs against both `FfmpegMediaTool` (`tests/contract/test_mediatool_ffmpeg.py`) and `FakeMediaTool` (`tests/contract/test_mediatool_fake.py`). `tests/contract/imagereader_contract.py` (`ImageReaderContract`) runs against `PillowImageReader` and `FakeImageReader`. `test_a_playlist_cannot_reach_other_files` checks the demuxer whitelist with a playlist named both `.m3u8` and `.mp4`.

## Anchor files

- `src/scenewise/ports.py` (`MediaTool`, `ImageReader`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`): the port contracts and the audio format
- `src/scenewise/domain/media.py` (`MediaInfo`, `Frame`, `Tile`, `Rect`, `RGB24_BYTES_PER_PIXEL`): the domain values
- `src/scenewise/adapters/media/ffmpeg.py` (`FfmpegMediaTool`, `find_binaries`, `scaled_size`, `_run`, `DEMUXERS`, `PROBE_TIMEOUT_S`): the ffmpeg/ffprobe adapter
- `src/scenewise/adapters/media/images.py` (`PillowImageReader`): the Pillow adapter
- `src/scenewise/service/config.py` (`MediaSettings`): binary names and the minimum major version
- `src/scenewise/service/bootstrap.py` (`build_dependencies`): the start-up check and adapter construction
- `src/scenewise/app/deps.py` (`Dependencies`): the `media` and `images` fields
- `src/scenewise/app/audio.py` (`acquire_audio`): the only `src` caller of `probe` and `audio_track`
- `tests/contract/mediatool_contract.py` (`MediaToolContract`), `tests/contract/test_mediatool_ffmpeg.py`, `tests/contract/imagereader_contract.py` (`ImageReaderContract`), `tests/contract/test_imagereader_pillow.py`: the contract suites
- `tests/fakes.py` (`FakeMediaTool`, `FakeImageReader`): the in-memory doubles
- `ARCHITECTURE.md` §11: the design rationale

## Related

- [[audio-stage]] · [[layering-and-ports]] · [[error-model]] · [[configuration]] · [[storage-and-uri-policy]] · [[job-lifecycle-and-timing]] · [[cli-analyse]]
