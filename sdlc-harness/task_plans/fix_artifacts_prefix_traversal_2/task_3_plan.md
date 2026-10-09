### Task 3 — Fence the state directory on the output store in `bootstrap._stores`

**Goal:** Wire Task 2's capability into the composition root. The output store is built with the state directory as a `fenced` root, so a request can no longer reach the state directory through a symlink or a second spelling of a parent directory. The input store and every other back-end choice stay as they are.

**Depends on:** Task 2, which adds `fenced` to the `LocalBlobStore` constructor:

```python
LocalBlobStore(*, roots: Sequence[Path], excluded: Sequence[Path] = (), fenced: Sequence[Path] = ())
```

A URI whose resolved path lies inside a fenced root is refused with `uri_not_allowed` unless its spelt (absolute, lexically normalised, no symlinks followed) path also lies inside that root as configured. This task passes the state path **as configured**, meaning the same `Path(url2pathname(state.path))` value the roots list already uses. Every record URI (`record_uri`) and every default artifact URI (`job_prefix`) is built from the same configured `state_prefix` string, so those writes are spelt inside the fence and stay allowed.

**Where this layer stops.** This task changes no adapter and no use case. The URI-level comparison in `artifacts_prefix` is Task 1's. The end-to-end proof that this wiring refuses a symlinked prefix over HTTP is **Task 6's** `test_a_symlink_into_the_state_prefix_is_refused` (`tests/e2e/test_isolation.py`). This task edits no test file.

### Targets

- `src/scenewise/service/bootstrap.py`: `_stores`.

**Source:** `src/scenewise/service/bootstrap.py` (`_stores`). Today the file case builds `outputs = [Path(url2pathname(state.path)), *settings.service.artifact_roots]` and returns `LocalBlobStore(roots=outputs)` together with `LocalBlobStore(roots=settings.inputs.local_roots, excluded=outputs)`.

**Work:**

- [ ] In the `case "file":` branch, bind `state_path = Path(url2pathname(state.path))` once and build `outputs = [state_path, *settings.service.artifact_roots]` from it. Construct the output store as `LocalBlobStore(roots=outputs, fenced=(state_path,))`, and leave the input store's construction (`roots=settings.inputs.local_roots, excluded=outputs`) as it is. Keep the adapter import function-local, as it is today (`.claude/context/conventions.md` § Dependency direction: only `bootstrap` imports adapters).
- [ ] Extend the `_stores` docstring by one clause: the output store fences the state directory, so artifacts cannot reach it through a symlink or another spelling. Leave `build_dependencies` and the `case scheme:` `ConfigurationError(code="store_unavailable")` branch unchanged.

**Verification:**

- Run `bash harness-scripts/typecheck.sh`: mypy strict, ruff and import-linter (the "Only the composition root imports adapters" contract) must pass.
- Task 6 exercises the wiring end to end: a request whose `uri_prefix` is a symlink inside the artifact root pointing at `state/victim` ends `failed` / `uri_not_allowed`, and `test_artifacts_under_an_artifact_root_are_job_scoped` still ends `succeeded` with `result_uri == f"{prefix}/job-2/a1/result.json"`. Phase G runs both, so this task does not run them.
