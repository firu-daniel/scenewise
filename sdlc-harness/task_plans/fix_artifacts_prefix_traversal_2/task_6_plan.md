### Task 6 — Make `test_cross_job_overwrite_is_refused` assert the refusal and add the symlink spelling end to end

**Goal:** Turn the isolation test into one that **fails against the current code**, as the task prompt requires. For every spelling, it asserts:
- the refusal itself: the status is `failed` and `error_code` is `uri_not_allowed`;
- that the post created nothing anywhere under the state prefix apart from the posting job's own record files — checked as a before/after snapshot of the whole state tree, never filtered on the posting job's name.

Today the test only checks that the victim's `a1/result.json` is unchanged and that `victim/a1/attacker` is absent. That is why `{root}/artifacts/../state/victim` passed while the write landed at `state/victim/attacker/a1/result.json`. Also add the symlink case end to end, which proves the composition root wires Task 3's fence into the running service.

**Depends on:** Tasks 1, 2 and 3:
- Task 1 makes `artifacts_prefix` refuse, with `InputError(code="uri_not_allowed")`, any `uri_prefix` whose job folder `{uri_prefix}/{job_id}` normalises to the state prefix or under it — including a parent of the state directory posted with a job id equal to the state directory's basename. Normalisation covers `..`, `.`, repeated or leading slashes, percent-escapes, and `file://localhost`. It also refuses queries, fragments and relative paths.
- Task 2 adds `LocalBlobStore(…, fenced=…)`, which refuses a path that resolves into a fenced root without being spelt inside it.
- Task 3 builds the output store with `fenced=(state path,)` in `bootstrap._stores`.

Over HTTP, each refusal surfaces as a terminal `failed` record with `error_code == "uri_not_allowed"`, returned in the 200 status body of `POST /v1/jobs` (`src/scenewise/app/delivery.py` `_run` → `_terminal`).

**Where this layer stops.** This file drives the real app and adapters through `TestClient(create_app(settings))` over the committed media (`.claude/context/tests.md` § Tree and tiers, End to end). It keeps `pytestmark = pytest.mark.e2e`, reaches ffmpeg only through the `inputs` fixture, and adds no skip or xfail.

### Targets

- `tests/e2e/test_isolation.py`: `test_cross_job_overwrite_is_refused`, and one new test.

**Work:**

- [ ] Change the parametrization of `test_cross_job_overwrite_is_refused` from `"prefix"` to `("prefix", "job")` and post `_job(job, (inputs / "tone.m4a").as_uri(), uri)`. Keep the four existing rows with job `"attacker"` (`{state}/victim`, `{state}`, `{state}/../state/victim`, `{root}/artifacts/../state/victim`) and add, with job `"attacker"`:
  - `{root}/./state/victim`
  - `{root}//state/victim`
  - `{root}/artifacts/%2E%2E/state/victim`
  - `file://localhost{state_path}/victim`

  and, with job `"state"` (the `victim` fixture's state directory is `tmp_path / "state"`, so `{root}` + `state` is the state prefix itself):
  - `{root}`
  - `{root}/artifacts/..`

  Format each row with `prefix.format(state=victim.as_uri(), root=victim.parent.as_uri(), state_path=victim.as_posix())`.
- [ ] In that test, take `before_tree = set(victim.rglob("*"))` before the post, keep the response (`status = client.post("/v1/jobs", json=body).json()`) and assert `(status["status"], status["error_code"]) == ("failed", "uri_not_allowed")`. This is the assertion the current code fails for `{root}/artifacts/../state/victim` and for each new row. Keep the existing assertions: the victim's `result.json` bytes are unchanged, its `job_id` is `victim`, and `victim/a1/attacker` does not exist; add `assert not (victim / "a1").exists()`.
- [ ] Add the "nothing under the state prefix except the posting job's record" assertion, keyed on the parametrized `job`, never on a literal name: `{p.relative_to(victim).as_posix() for p in set(victim.rglob("*")) - before_tree}` must be a subset of `{job, f"{job}/status.json", f"{job}/.status.json.meta.json", f"{job}/.status.json.lock"}`. These are the names `LocalBlobStore` gives a record folder, the record, its sidecar and its lock (`src/scenewise/adapters/storage/local.py` `_meta`, `_locked`). For the `"state"` rows the pre-branch code writes `a1/audio.wav` and `a1/result.json` (the artifacts land in `state/a1/`, a different job's record folder), which this set excludes.
- [ ] Add `test_a_symlink_into_the_state_prefix_is_refused(victim: Path, inputs: Path) -> None`:
  - Create the artifact root `victim.parent / "artifacts"` (`mkdir(exist_ok=True)`) and `(victim.parent / "artifacts" / "link").symlink_to(victim / "victim")`.
  - Post `_job("attacker", (inputs / "tone.m4a").as_uri(), (victim.parent / "artifacts" / "link").as_uri())` through `_client(victim, local_roots=(inputs,))`.
  - Assert the status is `failed` / `uri_not_allowed` and that `victim / "victim" / "attacker"` does not exist.
  - This spelling is lexically outside the state prefix, so Task 1 passes it. Only Task 3's wiring of Task 2's fence refuses it, which makes this test the end-to-end check of that wiring.
- [ ] Leave `test_artifacts_under_an_artifact_root_are_job_scoped` (expects `succeeded` and `result_uri == f"{prefix}/job-2/a1/result.json"`) and `test_artifacts_outside_every_root_are_refused` unchanged. They are the regression guard that the normalised check and the fence still let a legitimate artifact-root prefix through with its spelling intact. Update the module docstring only if it no longer describes the file (it names review r1 finding 1, which still holds).

**Verification:**

- `bash harness-scripts/test.sh tests/e2e/test_isolation.py` passes with Tasks 1–3 in place (this is the file this task edits).
- Against the pre-branch code, the strengthened `test_cross_job_overwrite_is_refused` fails for `{root}/artifacts/../state/victim`, for the four new `"attacker"` rows and for the two new `"state"` rows (`{root}` and `{root}/artifacts/..` with job id `state`: the raw prefix is not under `{state}/`, the output store allows the write because the state directory is one of its roots, and `victim/a1/audio.wav` and `victim/a1/result.json` appear — failing the status assertion, the `victim / "a1"` assertion and the snapshot assertion), and the symlink test fails. State this in the task's return, reasoned from the code (the old check is `requested.startswith(f"{state}/")` on the raw string, and the old output store has no fence). Do not check out other code to run it.
- Run `bash harness-scripts/typecheck.sh`: mypy and ruff must pass over the edited file.
