# Package layer: the `scenewise` distribution and its top-level modules

> **Read this when:** the change touches the files under `src/scenewise/` that sit outside `domain/`, `app/`, `adapters/` and `service/`, or changes what the distribution promises an installer: its entry points, its version, its base dependencies and extras, its supported runtimes. **Skip when:** the change stays inside one of the four layer directories and leaves the ports, entry points and dependency set alone; read that layer's document instead.

**Purpose.** What the `scenewise` distribution promises whoever installs it, the rules for the package root and for `scenewise.ports`, and what therefore may not change quietly. Read `.claude/context/conventions.md` first: the stack, dependency direction, code shape, testing bar and commit-message policy are owned there and only cited here.

## The public surface

- **Entry points.** The `scenewise` console script and `python -m scenewise` are one entry point: both call `scenewise.service.cli.main` (`pyproject.toml` `[project.scripts]`; `src/scenewise/__main__.py`). `src/scenewise/__main__.py` delegates and holds no logic of its own; a command or flag is added in `src/scenewise/service/cli.py`, which the `service` layer owns (`ARCHITECTURE.md` §2 "`python -m scenewise` → service.cli.main()").
- **What an installer reaches** — the surfaces an adopter calls without reading the code: the `scenewise` command and its subcommands, every route registered on the service's HTTP router (`src/scenewise/service/http/routes.py` `router`), every versioned `*V1` wire model in `src/scenewise/app/contract/`, the job-record and artifact layout a caller follows through `result_uri`, the `SCENEWISE_` settings names, and the extras names (`README.md` intro, "Run the audio stage", "Extras"). The wire models and the storage layout are owned by the shared cross-layer document (`.claude/context/conventions.md` "Shared state, storage paths and the wire contract"); this layer's consequence is that a change to any of them is a change to the distribution's promise.
- **The package root.** `src/scenewise/__init__.py` holds `__version__` and nothing else, read from the installed distribution's metadata with `importlib.metadata.version("scenewise")` (`ARCHITECTURE.md` §2 "`__version__` only"; `src/scenewise/__init__.py`). The version is written once, in `pyproject.toml` `[project] version`; code that needs the running version imports `__version__` from `scenewise` (`src/scenewise/app/delivery.py`, `src/scenewise/app/contract/mapping.py`, `src/scenewise/service/cli.py`, `src/scenewise/service/http/app.py`, `from scenewise import __version__`).
- **Typed.** The distribution ships `src/scenewise/py.typed` and declares `Typing :: Typed` (`pyproject.toml` `classifiers`); every name it ships is fully annotated under the mypy settings the shared document owns (`.claude/context/conventions.md` "Stack", "Code shape in every layer").
- **One import package.** `scenewise` is the only top-level package under `src/`; a core-library-plus-service split was rejected (`docs/decisions/initial-research.md` "Rejected, and why"; the rule itself is owned by `.claude/context/conventions.md` "Stack").
- **Every module belongs to a layer.** The layers contract is exhaustive, so a new module directly under `src/scenewise/` fails import-linter unless it joins a layer; `__main__` is exempt, and adding another exemption is a layers-contract change (`ARCHITECTURE.md` §2 "exempt from the layer check", §16 "exhaustive (`__main__` exempt)").

Every Python import name is internal; see `## Releases`.

## The ports module

`src/scenewise/ports.py` is the `ports` layer of the import-linter contract. Its import allow-list, synchronous signatures, coverage bar and suppression ban are owned by `.claude/context/conventions.md` ("Dependency direction", "Stack", "Testing bar", "Code shape in every layer"); this layer's consequences:

- Every port `Protocol`, `Blob` and `WriteConflictError` live in `scenewise.ports`, and every consumer imports them from there (`ARCHITECTURE.md` §2 "Ports live in one `ports.py`", §4; `src/scenewise/ports.py`).
- A port is a `typing.Protocol` at an I/O or model boundary, never an ABC (`ARCHITECTURE.md` §1 "Style", §14; owned by `.claude/context/conventions.md` "Where a new responsibility goes"). It contains only what its consumer calls (`docs/decisions/initial-research.md`, "a Protocol contains only what the consumer calls").
- A port's signatures name only `domain` types, standard-library types, and the types `scenewise.ports` itself defines (such as `Blob`); a domain value a new port needs is added to `domain` first (`.claude/context/conventions.md` "Dependency direction"; `src/scenewise/ports.py` `Blob`, `BlobStore`, imports from `scenewise.domain.*`). Wire models never cross a port; the notifier receives pre-serialised bytes (`src/scenewise/ports.py` `Notifier.notify`).
- **The docstrings are the contract.** The class docstring names the back ends that implement the port; the class and method docstrings state the behaviour every implementation must keep — ordering, ranges, absent-object results, and which error category and code a failure raises (`src/scenewise/ports.py` module docstring "docstring is the port's behavioural contract"; `BlobStore`, `MediaTool`, "Contract:"). Changing that text changes what every implementation and its contract suite must satisfy.
- A protocol method's body is its docstring followed by `...`; coverage excludes that line shape, an accepted gap that also excludes a bare `...` body elsewhere in the core (`docs/skeleton-notes.md` "Review r1 fixes", "`^\s*\.\.\.$` exclusion is loose"; `src/scenewise/ports.py`).
- `ports` logs nothing: it imports the stdlib only, so structlog is outside its allow-list (`.claude/context/conventions.md` "Dependency direction").
- **When it splits**, it becomes a `ports/` package with one module per port kind, re-exported from `src/scenewise/ports/__init__.py` so `from scenewise.ports import …` keeps working (`ARCHITECTURE.md` §2 "it starts as `ports/`, one module per port kind re-exported from `__init__.py`"). The module-size ceiling is owned by `.claude/context/conventions.md` "Code shape in every layer".
- The set that accompanies a new port — the docstring contract, the contract mixin, the in-memory fake and the fake's contract test — is owned by `.claude/context/conventions.md` "The set that accompanies a new unit"; when a port declared ahead of its first use gets its contract mixin and fake is open there (`.claude/context/conventions.md` `## Not determined`).

## Dependency policy

Floors, pins and the lock checks are owned by `.claude/context/conventions.md` ("The general layer"); the third-party allow-lists per layer by its "Dependency direction". This layer's rules for what the distribution carries:

- The base install holds only what every install needs; model runtimes, torch and the HTTP server stack are extras (`ARCHITECTURE.md` §12 "Everything else is an extra"; `README.md` "Extras", "The base install has no model runtime and no torch"; `pyproject.toml` `dependencies`, `[project.optional-dependencies]`).
- torch and torchvision arrive only through the `torch-cpu` / `torch-cu130` selector pair, which is a uv `conflicts` entry (`pyproject.toml` `[tool.uv] conflicts`, `[tool.uv.sources]`; `ARCHITECTURE.md` §12).
- `asr` carries no PyAV; faster-whisper, and PyAV's GPL x264/x265 with it, stays in the opt-in `asr-whisper` extra and out of published images (`docs/research/user-decisions.md` U16; `pyproject.toml` `asr-whisper` comment; `scripts/check_lock.sh`).
- A declared dependency is imported somewhere in `src`, or it sits in deptry's `DEP002` list with a comment naming why and the item that removes it (`ARCHITECTURE.md` §16 "Declared = imported"; `docs/skeleton-notes.md` G8 "each entry commented with the item that removes it").

## Releases

- A release is cut by the maintainer running `bash harness-scripts/release.sh <version>` at a terminal. The script bumps `pyproject.toml` `[project] version` with `uv version` in a pull request onto `dev`, publishes `dev` onto `main`, tags the publication `v<version>` and creates its GitHub Release. The tag and the GitHub Release are the release; scenewise is not published to a package index (`harness-scripts/release.sh` header; maintainer statement, 2026-10-09). A change never bumps the version by hand.
- The Python import names (`scenewise.ports`, the domain types, every module under `src/scenewise/`) are internal. They are not a library API and not covered by the version number. Adopters reach scenewise only through the surfaces in `## The public surface`. Entry points exposed as APIs later will import these names, and only those entry points become public (maintainer decision, 2026-10-09).
- Versions follow Semantic Versioning, `MAJOR.MINOR.PATCH` (maintainer decision, 2026-10-09). A breaking change to a surface in `## The public surface` bumps MAJOR, a backwards-compatible addition bumps MINOR, and a fix bumps PATCH.

## Supported runtimes

- Python versions are owned by `.claude/context/conventions.md` "Stack"; `requires-python`, the classifiers and the CI matrix state them (`pyproject.toml` `requires-python`, `classifiers`; `.github/workflows/ci.yml` `matrix`).
- ffmpeg and ffprobe are a runtime requirement of the distribution, not a Python dependency: found on `PATH` or through `SCENEWISE_MEDIA__FFMPEG` / `SCENEWISE_MEDIA__FFPROBE`, with a minimum major version that is a setting checked at start-up (`src/scenewise/service/config.py` `min_major`; `src/scenewise/adapters/media/ffmpeg.py` `find_binaries`; `README.md` "Requirements").

## The public surface is the contract

The public surface *is* the contract, so changing it is a versioning decision rather than a refactor. Renaming the `scenewise` command or one of its flags, a settings name, an extra, a route or a wire field, narrowing an accepted input, or altering a returned shape breaks callers who will never read the change — they will read the version number. An internal rearrangement that leaves every surface above behaving as documented is free; anything else is a release note.

**What each surface carries** — the documented behaviour and the test that pins it:

- A port: its docstring contract and its contract suite under `tests/contract/` (`.claude/context/conventions.md` "The set that accompanies a new unit").
- The command line, `python -m scenewise` and the HTTP routes: the end-to-end tier under `tests/e2e/` (`ARCHITECTURE.md` §15 "CLI and HTTP over media that ffmpeg generates").
- A wire field: its model, its mapping and a test in `tests/unit/test_mapping.py` (`.claude/context/conventions.md` "The set that accompanies a new unit").

## Questions answered elsewhere

The stack's names, the logger, settings, the wire types and their field naming, the source of truth for shared state, storage paths, shared constants, the test runner and doubles, and the commit-message policy are owned by `.claude/context/conventions.md`. scenewise has no UI framework, client-side state container, localization, theming or sizing accessor, shared UI components, test attributes or navigation registries (`.claude/context/conventions.md` "Surfaces this project does not have").

## Example

```python
# src/scenewise/__init__.py — the package root carries the version and nothing else.
from importlib.metadata import version

__version__ = version("scenewise")


# src/scenewise/ports.py — a port: a Protocol over domain types, its docstrings the
# contract that tests/contract/imagereader_contract.py checks every implementation against.
class ImageReader(Protocol):
    """Still images (Pillow).

    Contract: one RGB frame per tile, in order, longer side <= ``max_side``.
    """

    def read(self, path: Path, tiles: Sequence[Tile], *, max_side: int) -> list[Frame]:
        """Cut ``tiles`` out of the image in ``path``."""
        ...
```

_Provenance: existing mode. Read `src/scenewise/__init__.py`, `src/scenewise/__main__.py`, `src/scenewise/ports.py`, `src/scenewise/py.typed`, the `__version__` importers in `src`, `src/scenewise/service/http/routes.py`, the model classes in `src/scenewise/app/contract/`, `src/scenewise/service/config.py` and `src/scenewise/adapters/media/ffmpeg.py` for the ffmpeg check, `pyproject.toml`, `.github/workflows/ci.yml`, `README.md`, `ARCHITECTURE.md` §1–§4, §12, §14–§16, `docs/skeleton-notes.md`, `docs/research/user-decisions.md`, `docs/decisions/initial-research.md` ("Rejected, and why"), `ROADMAP.md`, and `.claude/context/conventions.md`. Revised once on review findings, and once on a corpus finding (C3)._

## Not determined

- Who decides a dependency addition: no source names who decides whether a new base dependency or extra is admitted. A maintainer statement in `ARCHITECTURE.md` §12 or `README.md` "Extras" settles it.
- When `src/scenewise/ports.py` splits into `ports/`: `ARCHITECTURE.md` §2 sets the trigger at a first draft of about 200 lines, and says nothing about the module after its first draft; only the module-size gate binds it now. An `ARCHITECTURE.md` §2 update stating the trigger for the existing module settles it.
- Rules read only off files outside this layer's scope (`src`): whether the mypy override for `ports` already covers a split `scenewise.ports.*` package, and which end-to-end test pins the composition at start-up. Both are stated only in `pyproject.toml` and `tests/`, which this layer's scope excludes; widening the `package` layer's `layers[].path`, or a harvested source stating them, settles it.
