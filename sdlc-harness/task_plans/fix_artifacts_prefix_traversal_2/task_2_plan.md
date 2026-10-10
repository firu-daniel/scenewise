### Task 2 — Give `LocalBlobStore` `fenced` roots that a path may enter only by being spelt inside them

**Goal:** Close the gap a URI-level check cannot see. Add a keyword-only constructor argument `fenced: Sequence[Path] = ()` to `LocalBlobStore`. A URI whose **resolved** path lies inside a fenced root is allowed only when its **spelt** path (absolute, lexically normalised, no symlinks followed) also lies inside that root's configured spelling. Otherwise `_path` raises `InputError(code="uri_not_allowed", detail="path is not allowed")`, the same code and detail the existing root and `excluded` refusals use (`.claude/context/adapters.md` § Errors at the boundary: "a URI outside the allow-list → `InputError(code="uri_not_allowed")`"). This refuses three things:
- a symlink inside an artifact root that points into the state directory;
- a second spelling of a parent directory (for example `/private/var/…/state` when the state root is configured as `/var/…/state`);
- `link/..` through such a symlink.

A fenced root stays fully reachable through its own spelling, which is how every record and every default artifact is addressed.

**Where this layer stops.** This task builds the capability and changes no caller. Passing `fenced=(state path,)` to the output store is **Task 3's** (`src/scenewise/service/bootstrap.py` `_stores`). The URI-level comparison in `artifacts_prefix` is **Task 1's**. The tests for this argument are **Task 5's** (`tests/contract/test_blobstore_local.py`), because `tests` is its own layer. This task edits no test file. The adapter imports only the stdlib, `scenewise.domain` and `scenewise.ports` (`.claude/context/adapters.md` § What an adapter is), and nothing else changes in that respect.

**Interface this task produces (restated verbatim in Tasks 3 and 5):**

```python
LocalBlobStore(*, roots: Sequence[Path], excluded: Sequence[Path] = (), fenced: Sequence[Path] = ())
```

Contract: for each fenced root `F`, a URI whose resolved path `is_relative_to(F.resolve())` is refused with `uri_not_allowed` unless its spelt path `is_relative_to(spelt(F))`. Here `spelt(p)` means `p` made absolute against the working directory, any leading run of slashes collapsed to one, and `os.path.normpath` applied, with no symlink resolution. The check applies to every method that goes through `_path` (`read`, `write`, `materialise`), before any filesystem access.

### Targets

- `src/scenewise/adapters/storage/local.py`: `LocalBlobStore.__init__`, `LocalBlobStore._path`, the class and module docstrings, and one new private module function.

**Source:** `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.__init__`, `_path`). Today `_path` builds `path = Path(url2pathname(parts.path)).resolve()` and checks `roots` and `excluded` against the resolved path only.

**Work:**

- [ ] Add a private module function `_spelt(path: Path) -> Path`. It takes `path.absolute()`, collapses a leading run of slashes to one, and applies `os.path.normpath`. That is lexical normalisation with no filesystem access and no symlink resolution. `os` is already imported.
- [ ] `__init__`: add `fenced: Sequence[Path] = ()` after `excluded`, keyword-only like the others. Store `self._fenced = tuple((root.resolve(), _spelt(root)) for root in fenced)`, a tuple set once with no per-job state (`.claude/context/adapters.md` § What an adapter is). Extend the `__init__` docstring with one sentence: a path may enter a `fenced` root only by being spelt inside it, so a symlink or another spelling of a parent directory cannot reach it.
- [ ] `_path`: keep `requested = Path(url2pathname(parts.path))` before resolving, then `path = requested.resolve()`. After the existing roots and `excluded` check, raise `InputError(code="uri_not_allowed", detail="path is not allowed")` when, for any `(real, spelt) in self._fenced`, `path.is_relative_to(real)` and not `_spelt(requested).is_relative_to(spelt)`. Return `path` unchanged otherwise. The detail must not include the path (D8).
- [ ] Update the module docstring (or the class docstring) to say the store also supports `fenced` roots, and why: the output store fences the state directory so artifacts cannot reach it through a symlink or alias (D14 stays cited). Keep the module within 500 lines and `_path` within the complexity limits of `.claude/context/conventions.md` § Code shape. Add no `noqa` (adapters may carry one only with `# why:` and a budget change, and none is needed here).

**Verification:**

- Run `bash harness-scripts/typecheck.sh`: mypy strict, ruff `ALL`, import-linter and vulture must pass. vulture sees `fenced` read in `_path` and passed by Task 3, so no whitelist entry is needed.
- With `fenced=()` (the default), `_path` behaves exactly as before. The existing `BlobStoreContract` suite and the module-level tests in `tests/contract/test_blobstore_local.py` are unaffected. Phase G runs them, so this task does not run them.
- Read through the cases Task 5 asserts and check each against the new code, with `roots=[tmp/out]`, `fenced=[tmp/out/state]`:
  - `…/out/state/j/status.json` is allowed.
  - `…/out/state/x/../j/a.json` is allowed (spelt inside).
  - `…/out/artifacts/link/victim/a.json` with `link → out/state` is refused.
  - `…/alias/state/x` with `alias → out` is refused.
  - `…/alias/artifacts/x` is allowed (not fenced).
