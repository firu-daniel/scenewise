# Adapters layer

> **Read this when:** you are implementing, reviewing or planning a change under `src/scenewise/adapters/` — a new back end for a port, a change to how a back end talks to ffmpeg, Pillow, the file system, a model runtime or a remote service. **Skip when:** the change is to a port's signature (`src/scenewise/ports.py`, the `package` layer), to a use case (`app`), or to how a back end is selected and configured (`src/scenewise/service/bootstrap.py`, `service`) — read this file too only if that change also edits an adapter.

**Purpose.** What a driven implementation of a port looks like in scenewise, and what it must do at the boundary with the outside world. Read `.claude/context/conventions.md` first: the layer contract, the error vocabulary, logging, code shape and the testing bar are owned there and only their consequences for adapters are stated here.

## Stack in this layer

- Python, synchronous, below the async HTTP edge (owned by `.claude/context/conventions.md` `## Stack`). Ports are called from one worker thread per job; an adapter exposes no `async` API (`ARCHITECTURE.md` §4 "All ports live in `scenewise.ports` and are synchronous on purpose"; §8 "everything below `service/http` is synchronous").
- Media through the system `ffmpeg` / `ffprobe` binaries via `subprocess`; images through Pillow, a base dependency (`src/scenewise/adapters/media/__init__.py` module docstring; `docs/research/user-decisions.md` D3). PyAV and ffmpeg-python are rejected (`ARCHITECTURE.md` §11, attributed).
- Every other SDK — onnxruntime, sherpa-onnx, onnx-asr, faster-whisper, open_clip, anthropic, google-cloud-storage, httpx — is an optional extra and is imported only inside `src/scenewise/adapters/` (`ARCHITECTURE.md` §12; `pyproject.toml` contract "Driving side imports no ML or cloud SDK").

## What an adapter is

- One class implementing one port `Protocol` from `src/scenewise/ports.py` **structurally** — it does not inherit from the Protocol or from an ABC (`src/scenewise/adapters/storage/local.py` `class LocalBlobStore:`; `src/scenewise/adapters/media/ffmpeg.py` `class FfmpegMediaTool:`; `ARCHITECTURE.md` §14 "ABCs for ports" left out). A wrapper that composes two implementations of the same port is itself an implementation of that port (`ARCHITECTURE.md` §2 `FallbackTextGenerator`, attributed).
- Module path `src/scenewise/adapters/<kind>/<technology>.py`; class name `<Technology><Port>` — `LocalBlobStore`, `FfmpegMediaTool`, `PillowImageReader`. The module docstring opens with the class name and what it runs over, citing the decision or `ARCHITECTURE.md` section it implements (`src/scenewise/adapters/media/ffmpeg.py` "``FfmpegMediaTool``: ffprobe and ffmpeg through ``subprocess`` (ARCHITECTURE.md §11)"; `src/scenewise/adapters/storage/local.py` "(D14)"; `src/scenewise/adapters/media/images.py` "(D3)").
- Kinds are the adapter groups of `ARCHITECTURE.md` §2: `media`, `asr`, `llm`, `vision`, `storage`, `notify`. A new kind is a design decision stated there first. Kind independence and "a shared helper stays inside its kind" are owned by `.claude/context/conventions.md` `## Dependency direction`.
- An adapter imports the standard library, the one SDK it wraps, `scenewise.domain` and `scenewise.ports` — never `scenewise.app`, never `scenewise.service` (owned by `.claude/context/conventions.md` `## Dependency direction`; `pyproject.toml` layers contract). It returns domain values (`Blob`, `MediaInfo`, `Frame`) and never a wire model.
- Constructors are keyword-only and take resolved plain values — paths, binary paths, roots — that `src/scenewise/service/bootstrap.py` reads off `Settings`; an adapter never receives `Settings` (owned by `.claude/context/conventions.md` `## Dependency direction`; `src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool.__init__`; `src/scenewise/adapters/storage/local.py` `LocalBlobStore.__init__`).
- An adapter instance is long-lived and shared across jobs: `__init__` sets every attribute, and per-call state lives in locals or in the context manager the call yields — nothing per job is stored on the instance (`ARCHITECTURE.md` §4 "nothing per job is stored in them"; `src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool`).
- A start-up check a back end needs — binary resolution, version floor — is a module-level function in the adapter module that `bootstrap` calls once, raising `ConfigurationError` with an install hint; its result is passed to the constructor (`src/scenewise/adapters/media/ffmpeg.py` `find_binaries`, `_INSTALL_HINT`; `ARCHITECTURE.md` §11 "Checked at start-up").
- An adapter loads, runs and returns raw output; interpretation — thresholds, language rules, parsing model text into results — is pure `domain` code (`ARCHITECTURE.md` §13 "Functional core", attributed).
- Every optional SDK import sits at module top in the one adapter module that wraps it; adapters contain no function-local imports — the lazy import that makes a missing extra a `ConfigurationError` lives in `bootstrap` (`ARCHITECTURE.md` §2 "Naming rules"; `pyproject.toml` `PLC0415` per-file ignore scoped to `src/scenewise/service/bootstrap.py`).

## Errors at the boundary

The categories and the keyword construction form are owned by `.claude/context/conventions.md` `## Errors`. In this layer:

- Where an adapter handles a third-party or `OSError` exception, it catches it at the narrowest call that raises it and re-raises a `ScenewiseError` with `from e` (`src/scenewise/adapters/media/images.py` `PillowImageReader.read` catching `UnidentifiedImageError`, `Image.DecompressionBombError`, `OSError`; `src/scenewise/adapters/storage/local.py` `LocalBlobStore.read`, `LocalBlobStore.write`). Whether every such exception must be translated is in `## Not determined`.
- The mapping:
  - unreadable, corrupt or non-conforming input, including unparsable tool output → `InputError(code="corrupt_media")` (`src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool.probe`, `FfmpegMediaTool._media`);
  - a URI outside the allow-list → `InputError(code="uri_not_allowed")`; a missing input → `InputError(code="input_unavailable")` (`src/scenewise/adapters/storage/local.py` `_path`, `materialise`);
  - transient storage or network I/O → `RetryableError(code="storage_unavailable")` with `detail=type(e).__name__`, never the exception message (`src/scenewise/adapters/storage/local.py` `LocalBlobStore.read`);
  - a timeout or an exhausted deadline → `InternalError(code="deadline_exceeded")` (`src/scenewise/adapters/media/ffmpeg.py` `_run`);
  - a missing or unusable back end at start-up → `ConfigurationError` (`src/scenewise/adapters/media/ffmpeg.py` `find_binaries`);
  - a failed compare-and-swap precondition → `scenewise.ports.WriteConflictError`, raised as-is (`src/scenewise/adapters/storage/local.py` `LocalBlobStore.write`; `ARCHITECTURE.md` §4).
- Validate what a back end returns before building a domain value from it — e.g. a decoded frame's byte count equals `width * height * RGB24_BYTES_PER_PIXEL` (`src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool.video_frames`).

## Processes: ffmpeg and ffprobe

- `_run` in `src/scenewise/adapters/media/ffmpeg.py` is the one place scenewise starts a process; a new process call goes through it (`_run` docstring "The one place scenewise starts a process"). It takes an argv list, never a shell string, and always a timeout; a non-positive timeout is `deadline_exceeded` before anything starts (`ARCHITECTURE.md` §11; `pyproject.toml` banned API `subprocess.call`).
- Callers pass an absolute monotonic `deadline` and compute `timeout=deadline - time.monotonic()` at each call (`src/scenewise/adapters/media/ffmpeg.py` `audio_track`, `video_frames`).
- Every ffmpeg and ffprobe input is a local path spelled `file:<resolved path>` by `_file`, preceded by `_PROTOCOLS` (`-protocol_whitelist file,pipe` and `-format_whitelist` with `DEMUXERS`). ffmpeg is never handed a URL; inputs are materialised through `BlobStore` first (owned by `.claude/context/conventions.md` `## Code shape in every layer`; `src/scenewise/adapters/media/ffmpeg.py` comment above `DEMUXERS`).
- `DEMUXERS` lists container demuxers only — no `hls`, `concat` or image-sequence demuxer; adding one reopens the local-file-following hole and is a security decision (`src/scenewise/adapters/media/ffmpeg.py` comment above `DEMUXERS`; `ARCHITECTURE.md` §11; `docs/skeleton-notes.md` review r1 finding 2).
- ffmpeg argv starts `-nostdin -hide_banner -loglevel error`; ffprobe argv starts `-v error` and asks for `-print_format json` (`src/scenewise/adapters/media/ffmpeg.py` `audio_track`, `video_frames`, `probe`).
- A non-zero exit is `InputError(code="corrupt_media")` whose `detail` is the stderr tail capped at `_STDERR_TAIL` characters (`src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool._media`).
- Binaries are resolved to absolute paths with `shutil.which` at start-up, checked against `media.min_major`, and overridden by `SCENEWISE_MEDIA__FFMPEG` / `SCENEWISE_MEDIA__FFPROBE` (`src/scenewise/adapters/media/ffmpeg.py` `find_binaries`; `README.md` "ffmpeg and ffprobe").
- A file an adapter yields lives in a `tempfile.TemporaryDirectory` owned by the context manager that yields it, so it is removed when the caller's `with` exits (`src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool.audio_track`, prefix `scenewise-audio-`).
- Output formats are part of the port contract: audio is one 16 kHz mono `pcm_s16le` WAV (`AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS` from `src/scenewise/ports.py`), frames are `rawvideo rgb24` on `pipe:1` (`ARCHITECTURE.md` §4, §11; `src/scenewise/adapters/media/ffmpeg.py` `audio_track`, `video_frames`).

## Frames and images

- Every `Frame` an adapter returns is raw RGB24 bytes, downscaled so its longer side is at most `max_side` and never upscaled — at decode for video (`src/scenewise/adapters/media/ffmpeg.py` `scaled_size`, `-vf scale=`), with `Image.thumbnail` for images (`src/scenewise/adapters/media/images.py` `PillowImageReader.read`; `ARCHITECTURE.md` §4 "A frame is raw RGB24 bytes").
- A sprite tile outside the image is `InputError(code="invalid_sprite_grid")`; the full image is copied only for a whole-image tile (`src/scenewise/adapters/media/images.py` `PillowImageReader.read`; `docs/skeleton-notes.md` review r1 finding 15).

## Storage

The record and artifact paths, and the job record as source of truth, are owned by `.claude/context/conventions.md` `## Shared state, storage paths and the wire contract`. A `BlobStore` adapter:

- Resolves and checks every URI before any file-system access: scheme, host, resolved path inside an allowed root and outside every `excluded` path, so `..` and symlinks cannot escape (`src/scenewise/adapters/storage/local.py` `LocalBlobStore._path`; `docs/skeleton-notes.md` A6 and review r1 finding 1).
- Keeps the input/output split: the input store never reaches the state prefix or an artifact root; a new store or a scheme router keeps the same split (`docs/skeleton-notes.md` A6 "`by_scheme` and the GCS store must keep the same input/output split", attributed).
- Implements `if_generation` compare-and-swap with the port's token semantics: an absent object is generation `0`, a successful write returns the new generation (`src/scenewise/ports.py` `BlobStore`; `src/scenewise/adapters/storage/local.py` `LocalBlobStore._generation`).
- A `read` or `materialise` of an absent object creates nothing: the absence check comes before the lock (`src/scenewise/adapters/storage/local.py` `LocalBlobStore.read` comment "reads never create directories or lock files" on the absent-object return, `LocalBlobStore.materialise`; `docs/skeleton-notes.md` review r1 finding 5 "returns `None` for an absent object before taking the lock").
- Local store specifics: per-object exclusive `fcntl.flock` on the hidden sibling `.<name>.lock`; generation and content type in `.<name>.meta.json`, written before the data so a crash leaves a stale token unusable; data replaced atomically through a fsynced temporary `.<name>.*` in the same directory (`src/scenewise/adapters/storage/local.py` `_locked`, `_meta`, `_replace`, comment "Generation first"). It is a single-host development and self-hosting store; network file systems are unsupported (`src/scenewise/adapters/storage/local.py` module docstring; D14).

## Model and remote back ends

Carried over from the adopter's architecture, attributed:

- Model weights are loaded from files pinned by sha256; nothing downloads at run time; weights load with safetensors, never `torch.load` or `pickle` (`ARCHITECTURE.md` §12, §15; `pyproject.toml` banned API messages).
- Model locks wrap inference only, never ffmpeg, storage, hosted calls or the whole job (`ARCHITECTURE.md` §8).
- Speech adapters read only the spans they are given; recognisers and language ID are handed decoded arrays (`ARCHITECTURE.md` §4).
- A `Notifier` receives pre-serialised bytes and sends them unchanged; it raises `RetryableError`, which delivery logs and swallows (`ARCHITECTURE.md` §4; owned by `.claude/context/conventions.md` `## Shared state, storage paths and the wire contract`).
- A heavy-extra adapter's coverage `omit`, deptry `DEP002` and `pytest.importorskip` obligations are owned by `.claude/context/conventions.md` "The set that accompanies a new unit".

## Constants

- A value a deployment tunes arrives as a constructor or call argument from `Settings` via `bootstrap` (`min_major`, `max_side`, `deadline`) (`src/scenewise/adapters/media/ffmpeg.py`). A constant shared with another layer is imported from `domain` (`RGB24_BYTES_PER_PIXEL` from `src/scenewise/domain/media.py`) — the placement rule is owned by `.claude/context/conventions.md` `## Constants and configuration`.

## Suppressions and types

- Adapters sit outside the no-suppression zone: a line-level `noqa` here carries `# why: …` and counts against `suppression_budget` (`src/scenewise/adapters/media/ffmpeg.py` `_run` `# noqa: S603  # why:`; owned by `.claude/context/conventions.md` `## Code shape in every layer`).
- Explicit `Any` is permitted here: mypy's `disallow_any_explicit` covers only `domain`, `app` and `ports` (`pyproject.toml` mypy override); `src/scenewise/adapters/media/ffmpeg.py` `_media_info` types ffprobe's parsed JSON with it before building `MediaInfo`.

## Tests for an adapter

- Every implementation passes its port's contract suite, a mixin class per port subclassed per implementation; a heavy adapter is imported inside the fixture (`ARCHITECTURE.md` §15 "Contract tests are a mixin class per port, subclassed per implementation", attributed). How a contract test is written is owned by `.claude/context/tests.md`; the required set and the testing bar by `.claude/context/conventions.md` "The set that accompanies a new unit" and `## Testing bar`.

## Surfaces owned elsewhere

The logger, the commit-message policy, the wire models and serialized field names, the stack names, and the absence of any UI, localization, theming, navigation or interactive-test surface are owned by `.claude/context/conventions.md`. Adapters see no wire model and no `Settings`.

## Example

`src/scenewise/adapters/media/ffmpeg.py` (`_run`) — the single process entry point: argv list, mandatory timeout, timeout mapped to a scenewise error code, the one budgeted suppression with its reason:

```python
def _run(argv: list[str], *, timeout: float) -> subprocess.CompletedProcess[bytes]:
    """The one place scenewise starts a process."""
    if timeout <= 0:
        raise InternalError(code="deadline_exceeded")
    try:
        return subprocess.run(  # noqa: S603  # why: argv list; binaries resolved by which()
            argv, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as e:
        detail = Path(argv[0]).name
        raise InternalError(code="deadline_exceeded", detail=detail) from e
```

_Provenance: existing mode. Read every Python module under `src/scenewise/adapters/`; `src/scenewise/ports.py` (`BlobStore`) and `src/scenewise/service/bootstrap.py` for how adapters are built; `pyproject.toml` (ruff, coverage, deptry, import-linter); `ARCHITECTURE.md` §2–§4, §8–§16; `docs/skeleton-notes.md`; `README.md`; `docs/research/user-decisions.md`; `.claude/context/conventions.md` as the vocabulary anchor._

## Not determined

- Whether `MediaTool.probe` takes a deadline: `probe` runs under the fixed `PROBE_TIMEOUT_S` rather than the caller's deadline (`src/scenewise/adapters/media/ffmpeg.py` `FfmpegMediaTool.probe`; `docs/skeleton-notes.md` review r1 finding 14 "Decide with item 1"). A port-signature decision settles it.
- Whether every third-party or `OSError` exception must be translated before it leaves an adapter: `LocalBlobStore` and `PillowImageReader` translate theirs, while `src/scenewise/adapters/media/ffmpeg.py` `_run` catches only `subprocess.TimeoutExpired` (an `OSError` from exec escapes) and `FfmpegMediaTool.audio_track` calls `part.read_bytes()`, `source.open("wb")` and `tempfile.TemporaryDirectory` with no handler; `ARCHITECTURE.md` §9 says only that before the stages "Any non-scenewise exception becomes `InternalError("unexpected")`". A layer-wide rule recorded in `ARCHITECTURE.md` §9, or handlers added in `ffmpeg.py`, settles it.
- Whether a read of an existing object may create the lock sibling: `LocalBlobStore.read` takes `_locked`, which runs `path.parent.mkdir` and opens `.<name>.lock` with `"a"`, so a read creates the lock file for an object that lacks one (a file placed by hand, with no sidecar, is `_HAND_PLACED_GENERATION`); `docs/skeleton-notes.md` review r1 finding 5 says "only writes create directories and lock files". A storage decision recorded in `ARCHITECTURE.md` §4 or a change to `LocalBlobStore.read` settles it.
- Which HTTP client the HTTP-based adapters (OpenAI-compatible LLM, notifier, `https` store) use: `ARCHITECTURE.md` §12 names `httpx` as the base dependency, `docs/skeleton-notes.md` G7 says "consider httpx2 for the adapters". A maintainer decision recorded in `ARCHITECTURE.md` settles it.
- Whether adapters log: no source states whether a back end may log or must leave logging to `app`. A logging rule in `ARCHITECTURE.md` §10 settles it.
