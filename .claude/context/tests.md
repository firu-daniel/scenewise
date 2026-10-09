# Tests

> **Read this when:** the change adds, moves or rewrites anything under `tests/` — a unit, contract or end-to-end test, a fake in `tests/fakes.py`, a fixture in a `conftest.py`, or the media under `tests/fixtures/` — or changes behaviour a test there protects. **Skip when:** the change touches only the machinery around testing — `[tool.pytest]` / `[tool.coverage]` in `pyproject.toml`, the CI workflows, the gate scripts — which the shared document (`.claude/context/conventions.md`, `## The general layer`) governs.

**Purpose.** How scenewise's tests are organised, named and bounded, so a test lands where its subject's reader would look for it and a failure says what broke. The cross-layer testing bar — coverage targets, no skips in CI, warnings as errors, timeout, random order, the `model` marker, no downloads — is owned by `.claude/context/conventions.md` (`## Testing bar`); this document states the tests layer's consequences of it.

## Tree and tiers

- Tests are organised by tier, not mirrored on `src/`: unit tests in `tests/unit/`, contract tests in `tests/contract/`, end-to-end tests in `tests/e2e/`; property tests live in `tests/unit/`, and model-loading tests live in `tests/contract/` under the `model` marker (`ARCHITECTURE.md` §15 "Testing strategy" table).
- Every directory of test code is a package with an `__init__.py` whose docstring states what the tier holds (`tests/__init__.py` "every directory is a package"; `tests/unit/__init__.py`, `tests/contract/__init__.py`, `tests/e2e/__init__.py`). Tests import shared test code absolutely, `from tests.fakes import …`, `from tests.contract.blobstore_contract import …` (`pyproject.toml` `[tool.pytest]` `pythonpath`; `tests/unit/test_runner.py`, `tests/contract/test_blobstore_fake.py`).
- **Unit** (`tests/unit/`): pure `domain` and the use cases over fakes, plus pure `service` helpers (`ARCHITECTURE.md` §15 "Unit" "Pure `domain` and the use cases with fakes"). Storage is `InMemoryBlobStore` and media is `FakeMediaTool` (`tests/unit/test_runner.py` `_store`; `tests/fakes.py` `fake_dependencies`). A fake may write scratch files that a unit test reads back (`tests/fakes.py` `FakeMediaTool` `tempfile.TemporaryDirectory()`; `tests/unit/test_audio.py` `test_file_with_audio_yields_one_track` `wave.open`). Because the unit tier alone must reach 100% branch coverage of `domain`, `app` and `ports` (`.claude/context/conventions.md` `## Testing bar`), a new branch there gets a unit test; an e2e test does not count toward that bar.
- **Contract** (`tests/contract/`): one mixin per port, subclassed per implementation — the fake and every adapter (`tests/contract/__init__.py`; `ARCHITECTURE.md` §15 "Contract tests"). Behaviour specific to one implementation is a module-level test function in that implementation's contract test file (`tests/contract/test_blobstore_local.py` `test_dot_dot_cannot_escape_a_root`; `tests/contract/test_mediatool_ffmpeg.py` `test_scaled_size`).
- **End to end** (`tests/e2e/`): the CLI and the HTTP service over the committed media, through the real app and adapters. Every module declares `pytestmark = pytest.mark.e2e` (`tests/e2e/test_cli.py`, `tests/e2e/test_http.py`, `tests/e2e/test_isolation.py`, `tests/e2e/test_bootstrap.py`). HTTP goes through FastAPI's `TestClient(create_app(settings))` in-process (`tests/e2e/test_http.py` `client`); the CLI is run as `subprocess.run([sys.executable, "-m", "scenewise", …], timeout=60)` (`tests/e2e/test_cli.py` `_cli`).

## Naming

- File names follow the table in `.claude/CLAUDE.md` `## File naming conventions`, which owns the pattern list.
- Each implementation's contract test lives in its own file, `tests/contract/test_<port>_<impl>.py`; one file never holds several implementations (maintainer decision, 2026-10-09). The tree follows it for every port: `tests/contract/test_blobstore_local.py` / `tests/contract/test_blobstore_fake.py`, `tests/contract/test_mediatool_ffmpeg.py` / `tests/contract/test_mediatool_fake.py`, `tests/contract/test_imagereader_pillow.py` / `tests/contract/test_imagereader_fake.py`.
- A unit file's `<subject>` is the source module's basename (`tests/unit/test_jobs.py` for `src/scenewise/domain/jobs.py`, `tests/unit/test_mapping.py` for `src/scenewise/app/contract/mapping.py`).
- A test function is `test_<behaviour as a snake_case sentence>` — `test_no_audio_stream_skips_the_stage`, `test_stale_generation_is_fenced`, `test_cross_job_read_is_refused` (`tests/unit/test_runner.py`, `tests/contract/blobstore_contract.py`, `tests/e2e/test_isolation.py`).
- Test cases are module-level functions. A class appears as a contract mixin `<Port>Contract`, which carries no `Test` prefix so it is collected only through a subclass, or as a subclass `Test<Implementation>(<Port>Contract)` (`tests/contract/blobstore_contract.py` `BlobStoreContract`; `tests/contract/test_blobstore_local.py` `TestLocalBlobStore`), or as a test double.
- Module-local helpers are private functions — `_job`, `_store`, `_deadline` (`tests/unit/test_runner.py`); module-local fixed values are `UPPER_CASE` constants — `NOW`, `INFO` (`tests/unit/test_jobs.py`).
- A test module carries no docstring unless it records why it exists (`tests/e2e/test_isolation.py` "Review r1, finding 1"); ruff's `D1` is off for `tests/**` (`pyproject.toml` `[tool.ruff.lint.per-file-ignores]`).

## What a test may reach for

- **Fakes, not mocks.** A port's test double is its in-memory fake in `tests/fakes.py`, and every fake there passes its port's contract suite; use-case tests build their port bundle with `fake_dependencies` (owned by `.claude/context/conventions.md` `## Testing bar`; `tests/fakes.py` module docstring). A variant one test module needs subclasses the shared fake in that module (`tests/unit/test_delivery.py` `ConflictingStore(InMemoryBlobStore)`). A port the code under test only checks for presence is passed as `cast("<Port>", object())` (`tests/unit/test_deps.py` `TEXT`). `unittest.mock` is allowed for what no fake covers (`.claude/context/conventions.md` `## Testing bar`).
- **`monkeypatch`** replaces a module or class attribute to inject a failure (`tests/unit/test_runner.py` `monkeypatch.setattr(stages, "audio", broken)`; `tests/contract/test_mediatool_ffmpeg.py` `test_unreadable_probe_output`) and sets `SCENEWISE_` environment variables (`tests/unit/test_service.py` `test_settings_from_the_environment`).
- **Shared fixtures** go in `tests/conftest.py` (`ffmpeg_binaries`, `fixtures_dir`); tier-only fixtures go in that tier's `conftest.py` (`tests/e2e/conftest.py` `inputs`); a fixture a contract mixin needs is named in the mixin's docstring and provided by each subclass (`tests/contract/blobstore_contract.py` "Subclass and provide the ``store``, ``base`` and ``outside`` fixtures"), or, when every implementation's file needs the same one, by `tests/contract/conftest.py` (`image`, named in `tests/contract/imagereader_contract.py` "from ``tests/contract/conftest.py``").
- **The clock.** Time is passed in as a value, not read and patched: a fixed `NOW` into `AttemptInfo(now=NOW, …)` (`tests/unit/test_jobs.py`), and deadlines as `time.monotonic() + 60` (`tests/unit/test_runner.py` `_deadline`). There is no `Clock` port (`.claude/context/conventions.md` `## Where a new responsibility goes`).
- **The filesystem** is `tmp_path`, in the contract and e2e tiers (`tests/contract/test_blobstore_local.py`, `tests/e2e/test_http.py` `state`).
- **ffmpeg** is reached only through the `ffmpeg_binaries` fixture, directly, through `@pytest.mark.usefixtures("ffmpeg_binaries")`, or through `inputs`; it skips when the binaries are missing, and CI fails on any skip (`tests/conftest.py` `ffmpeg_binaries` docstring "a skip fails CI"; `tests/e2e/test_bootstrap.py`). A test function never calls `pytest.skip` or marks itself `xfail` (`.claude/context/conventions.md` `## Testing bar`).
- **Media** comes from the committed files under `tests/fixtures/`, regenerated by `tests/fixtures/generate.sh` from ffmpeg's lavfi sources and never downloaded; tests reach them through `fixtures_dir` and assert decoded properties — duration, streams, sample rate, frame size — never fixture bytes (`tests/fixtures/generate.sh` header; `docs/skeleton-notes.md` G19; `tests/contract/mediatool_contract.py` `test_audio_track_is_16k_mono_s16`). A fixture file the fake must know is added to `FIXTURE_INFOS` in `tests/fakes.py`, because `FakeMediaTool` knows media by file name (`tests/fakes.py` `FakeMediaTool` docstring).
- **HTTP** is exercised in-process through `TestClient`, not over a socket (`tests/e2e/test_http.py` `client`).
- **Heavy-extra adapters** are imported inside their test fixture after `pytest.importorskip`, so collection works without the extra (`.claude/context/conventions.md` `**The set that accompanies a new unit**`, **Adapter:**; `pyproject.toml` per-file ignore `PLC0415` for `tests/**`; `ARCHITECTURE.md` §15 "Contract tests").
- **Lint relaxations** for `tests/**` — `assert`, literal expectations, private-attribute access, fixtures as positional parameters — are the per-file ignores in `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`. Any other suppression follows the shared rule: line-level, with `# why: …` (`.claude/context/conventions.md` `## Code shape in every layer`; `tests/e2e/test_cli.py` `# noqa: S603  # why: this interpreter, fixed argv`).

## Assertions

- A deliberate scenewise error is asserted by its `code`: `with pytest.raises(InputError) as caught:` then `assert caught.value.code == "corrupt_media"` (`tests/contract/blobstore_contract.py` `test_materialise_missing`; `tests/unit/test_runner.py` `test_stage_not_offered_fails_the_job`). A plain `ValueError` from a domain constructor is asserted with `match=` on its message (`tests/unit/test_jobs.py` `test_job_id_rejects`).
- Several related values are compared as one tuple: `assert (info.has_audio, info.has_video) == (True, True)` (`tests/contract/mediatool_contract.py` `test_probe_video_with_audio`).
- Input variations are `@pytest.mark.parametrize`; a property over a whole input space is a hypothesis `@given` test in `tests/unit/`, which runs with hypothesis's default profile wherever `tests/unit` runs and with the `nightly` profile in the nightly job (`tests/unit/test_jobs.py` `test_job_id_accepts_the_pattern`; `tests/conftest.py` `settings.register_profile(`; `.github/workflows/extended.yml` `property-nightly` `--hypothesis-profile=nightly`).

## What may not land without a test

The required set per new unit — port, adapter, input kind, domain module or use case, wire field — is owned by `.claude/context/conventions.md` (`**The set that accompanies a new unit**`). Its tests-layer consequences:

- A new port adds `tests/contract/<port>_contract.py`, an in-memory fake in `tests/fakes.py`, and a contract subclass running that fake, in its own file (`## Naming`).
- A new adapter adds a `Test<Adapter>(<Port>Contract)` subclass, in its own file (`## Naming`).
- A wire field adds a test in `tests/unit/test_mapping.py`.

**Rule that holds whatever the language is:** a test names the behaviour it protects, not the function it calls. A failing run is read by someone who did not write the test and may not know the code, so the name has to carry the claim — a failure should read as a sentence about the product, and a test whose name only repeats a file path leaves that reader with a search instead of an answer.

## Surfaces this project does not have

No interactive or browser test, so no test-attribute convention or helper that applies one (`.claude/context/conventions.md` `## Surfaces this project does not have`).

## Example

A port's contract is a mixin; the fake and each adapter subclass it and provide its fixtures (`tests/contract/blobstore_contract.py`, `tests/contract/test_blobstore_fake.py`):

```python
class BlobStoreContract:
    """Subclass and provide the ``store``, ``base`` and ``outside`` fixtures."""

    def test_stale_generation_is_fenced(self, store: BlobStore, base: str) -> None: ...


class TestInMemoryBlobStore(BlobStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryBlobStore:
        return InMemoryBlobStore()
```

_Provenance: existing mode. Read every tracked file under `tests/` (`git ls-files tests`), `ARCHITECTURE.md` §15, `docs/skeleton-notes.md` (A13, A14, G19, `## Review r1 fixes`), `README.md`, the `[tool.pytest]` and `[tool.ruff.lint.per-file-ignores]` tables of `pyproject.toml`, `.github/workflows/extended.yml` (`property-nightly`), and `.claude/context/conventions.md` as the vocabulary anchor. Corpus fix pass: re-read the class definitions in `tests/contract/test_*.py`, the `.claude/CLAUDE.md` `## File naming conventions` table and `.claude/context/conventions.md` **Port:**._

## Not determined

- Unit file subject for a layer rather than a module: `tests/unit/test_service.py` covers `service.config`, `service.http.health` and `service.http.problems` under the layer's name, while the other unit files are named after one module. Settled by a maintainer statement of which form a new `service` unit test follows.
- Model-tier conventions — the `tests/models.lock` format, how a model fixture loads offline, and the D8 log test — are stated only as plans (`ARCHITECTURE.md` §15 "Model"; `docs/skeleton-notes.md` A13, A14); the tree has nothing to read them off. Settled by the first model-tier test (`ROADMAP.md` item 1).
- Whether a defect fix must land with a test reproducing it: review fixes recorded in `docs/skeleton-notes.md` `## Review r1 fixes` name the test that reproduces them (findings 1, 2 and 5), and `tests/e2e/test_isolation.py` names its finding in the module docstring, but no source states it as a rule. Settled by a maintainer statement.
- Whether a unit test may import a `scenewise.adapters` module or take `tmp_path`: the unit tier observed does neither, but no source states it as a rule (`ARCHITECTURE.md` §15 "Unit" names only "the use cases with fakes"). Settled by a maintainer statement.
