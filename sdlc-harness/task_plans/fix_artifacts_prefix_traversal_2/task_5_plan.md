### Task 5 — Contract-file tests for the `LocalBlobStore` fence: own spelling allowed, symlink and parent alias refused

**Goal:** Pin the behaviour of Task 2's `fenced` argument against a real filesystem. A fenced root is reachable through its own spelling, including a `..` that stays lexically inside it. It is not reachable through a symlink placed in another root, through `link/..`, or through a symlinked alias of a parent directory. A refused write creates nothing inside the fenced root. Behaviour specific to one implementation is a module-level test function in that implementation's contract file (`.claude/context/tests.md` § Tree and tiers, which gives `test_dot_dot_cannot_escape_a_root` as the example).

**Depends on:** Task 2, which produces:

```python
LocalBlobStore(*, roots: Sequence[Path], excluded: Sequence[Path] = (), fenced: Sequence[Path] = ())
```

For each fenced root `F`, a URI whose resolved path lies inside `F.resolve()` is refused with `InputError(code="uri_not_allowed")` unless its spelt path (absolute, leading slashes collapsed, `os.path.normpath`, no symlinks followed) lies inside `F` as spelt. The check runs in `_path`, so it covers `read`, `write` and `materialise`, before any filesystem access.

**Where this layer stops.** These tests use only `LocalBlobStore` and `tmp_path` (`.claude/context/tests.md` § What a test may reach for: the filesystem is `tmp_path` in the contract tier). They do not touch the shared `BlobStoreContract` mixin, which `fenced` does not change, and they do not test the HTTP path, which is Task 6's.

### Targets

- `tests/contract/test_blobstore_local.py`: new module-level test functions.

**Work:**

- [ ] Add `test_a_fenced_root_is_reachable_by_its_own_spelling(tmp_path)`. Build `store = LocalBlobStore(roots=[tmp_path / "out"], fenced=[tmp_path / "out" / "state"])`. A `write` then `read` of `(tmp_path / "out" / "state" / "j" / "status.json").as_uri()` round-trips. A write to `(tmp_path / "out" / "state").as_uri() + "/x/../j/a.json"` succeeds and lands at `out/state/j/a.json`.
- [ ] Add `test_a_symlink_into_a_fenced_root_is_refused(tmp_path)`. Create `out/state/victim/` and `out/artifacts/`, and `(tmp_path / "out" / "artifacts" / "link").symlink_to(tmp_path / "out" / "state" / "victim")`. With the same store, `write` to `…/artifacts/link/attacker/a1/result.json` raises `InputError` with `code == "uri_not_allowed"`. So do `read` and `materialise` of `…/artifacts/link/x`. Afterwards `list((tmp_path / "out" / "state" / "victim").iterdir()) == []`: nothing was created behind the fence.
- [ ] Add `test_dot_dot_through_a_symlink_into_a_fenced_root_is_refused(tmp_path)`. With `link → out/state/victim/sub` (create `sub` first), a write to `(…/artifacts/link).as_uri() + "/../x"` raises `uri_not_allowed`. `Path.resolve` follows the link before applying `..`, so the target is `out/state/victim/x`, while the spelling says `out/artifacts/x`.
- [ ] Add `test_a_second_spelling_of_a_parent_cannot_enter_a_fenced_root(tmp_path)`. Create `out/` and `(tmp_path / "alias").symlink_to(tmp_path / "out")`, and use the same store (roots and fence spelt through `out`). A write to `(tmp_path / "alias" / "state" / "x").as_uri()` raises `uri_not_allowed`. A write to `(tmp_path / "alias" / "artifacts" / "x").as_uri()` succeeds, because only the fenced root is guarded and the root check is on resolved paths.

**Verification:**

- `bash harness-scripts/test.sh tests/contract/test_blobstore_local.py` passes: the new functions plus the file's existing `TestLocalBlobStore` subclass and module-level tests (the file this task edits).
- Each test name reads as a sentence about the store's behaviour (`.claude/context/tests.md` § Naming), and each refusal is asserted by its `code`, not its message (`.claude/context/tests.md` § Assertions).
- Run `bash harness-scripts/typecheck.sh`: mypy and ruff must pass over the edited file.
