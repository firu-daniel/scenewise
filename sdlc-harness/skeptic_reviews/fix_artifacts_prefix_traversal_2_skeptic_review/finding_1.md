### 1. The "except by case" limit is an unauthorised exception to "however it is spelt", and its justification cites a source that does not support it

**File:** `src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`): "path.is_relative_to(real) and not spelling.is_relative_to(spelt)"

**Problem.** The task prompt's `## What done looks like` requires: *"Any artifact `uri_prefix` that **resolves** to the state prefix or anywhere under it ends the job `failed` / `uri_not_allowed`, however it is spelt (`..`, `.`, repeated slashes, and so on). No file is written anywhere under the state prefix for that job."* The branch leaves one spelling open, and the docs record that as a known limit: `docs/concepts/storage-and-uri-policy.md` gotcha "**A `uri_prefix` cannot reach the state tree by another spelling, except by case.**", repeated by `docs/features/job-results-and-artifacts.md` "**Other spellings of the state prefix are refused.**".

Here is how the gap opens. On a case-insensitive file system (the macOS default, a vfat mount, an ext4 casefold directory), `/srv/STATE` and `/srv/state` are the same directory. `Path.resolve()` (`os.path.realpath`) follows symlinks but does not fold case, so the resolved path keeps the caller's case. Take a state prefix `file:///srv/state`, an artifact root `/srv` (one that contains the state directory, which nothing forbids), and a request `uri_prefix = "file:///srv/STATE/victim"` with job `attacker`:

- `artifacts_prefix` compares `/srv/STATE/victim/attacker` with `/srv/state` as case-sensitive `PurePosixPath`s. Neither lies under the other, so the prefix is accepted.
- `LocalBlobStore._path("file:///srv/STATE/victim/attacker/a1/result.json")`: `path` resolves to `/srv/STATE/victim/attacker/a1/result.json`. That is under the allowed root `/srv`. The fence test `path.is_relative_to(real)`, with `real = /srv/state`, is `False`, so the spelling check never runs and the write is accepted.
- The file lands in the victim job's folder inside the state directory. This is the exact harm the issue describes.

**The justification does not hold up (check 3).** No authorisation for this exception exists:
- The task prompt names no exception.
- The story plan's `## Context` and "Decisions the task prompt asked planning to make" never mention case.
- The only justification is in `sdlc-harness/task_plans/fix_artifacts_prefix_traversal_2/task_7_plan.md`: "**Remaining limit:** … with Linux as the deployment target (D14)." The same task plan then admits the citation is wrong: "D14 (`docs/decisions/initial-research.md`) states only single-host compare-and-swap, and no tracked doc names Linux as the target."
- So the exception rests on a miscited source and is recorded only in a docs gotcha. Neither waives the prompt's requirement.

**Fix.** Make the store fence recognise the fenced directory by identity as well as by resolved name. A case-changed (or otherwise unfolded) spelling then counts as entering the fence. Because it is not spelt inside the configured spelling, it is refused. Records and default artifacts are spelt through the configured state prefix, so they are unaffected, as now.

- [ ] In `src/scenewise/adapters/storage/local.py`, change the import `from contextlib import contextmanager` to `from contextlib import contextmanager, suppress`.
- [ ] In the same file, add this module-level function directly above `_spelt`:

  ```python
  def _enters(path: Path, real: Path) -> bool:
      """Whether the resolved ``path`` lies in directory ``real``, by name or identity.

      ``resolve()`` does not fold case, so on a case-insensitive file system a
      case-changed spelling of ``real`` is the same directory under another name.
      """
      if path.is_relative_to(real):
          return True
      for parent in (path, *path.parents):
          with suppress(OSError):
              if parent.samefile(real):
                  return True
      return False
  ```

- [ ] In `LocalBlobStore._path`, replace

  ```python
              path.is_relative_to(real) and not spelling.is_relative_to(spelt)
  ```

  with

  ```python
              _enters(path, real) and not spelling.is_relative_to(spelt)
  ```

- [ ] In `tests/contract/test_blobstore_local.py`, add this test after `test_a_second_spelling_of_a_parent_cannot_enter_a_fenced_root`. It simulates a case-insensitive file system by making `Path.samefile` compare case-folded strings, so it runs and is not skipped on a case-sensitive CI host (`.claude/context/conventions.md` `## Testing bar`: no skips):

  ```python
  def test_a_case_changed_spelling_cannot_enter_a_fenced_root(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      (tmp_path / "out" / "state").mkdir(parents=True)

      def case_insensitive(self: Path, other: Path) -> bool:
          return str(self).lower() == str(other).lower()

      monkeypatch.setattr(Path, "samefile", case_insensitive)
      store = _fenced_store(tmp_path)
      with pytest.raises(InputError) as caught:
          store.write(
              (tmp_path / "out" / "STATE" / "x").as_uri(), b"x", content_type="x"
          )
      assert caught.value.code == "uri_not_allowed"
      assert not (tmp_path / "out" / "STATE").exists()
      store.write((tmp_path / "out" / "artifacts" / "x").as_uri(), b"x", content_type="x")
      assert (tmp_path / "out" / "artifacts" / "x").read_bytes() == b"x"
  ```

- [ ] In `docs/concepts/storage-and-uri-policy.md`, replace the whole gotcha bullet that begins "**A `uri_prefix` cannot reach the state tree by another spelling, except by case.**" with:

  `- **A `uri_prefix` cannot reach the state tree by another spelling.** `artifacts_prefix` refuses `..` and `.` segments, repeated slashes, percent-escapes and `file://localhost` spellings that normalise to the state prefix or below it. The output store's fence refuses a symlink, a parent alias or a case-changed spelling (on a case-insensitive file system) into the state directory: it recognises the directory by identity (`Path.samefile`), not only by its resolved name. Each ends the job `failed` / `uri_not_allowed` (`tests/e2e/test_isolation.py` (`test_cross_job_overwrite_is_refused`, `test_a_symlink_into_the_state_prefix_is_refused`); `tests/contract/test_blobstore_local.py` (`test_a_case_changed_spelling_cannot_enter_a_fenced_root`)).`

- [ ] In `docs/features/job-results-and-artifacts.md`, replace the bullet "**Other spellings of the state prefix are refused.** … the remaining case-insensitive-file-system limit is in `docs/concepts/storage-and-uri-policy.md` (Gotchas)." with:

  `  - **Other spellings of the state prefix are refused.** `artifacts_prefix` refuses `..` and similar spellings on the normalised URI. The output store's fence refuses symlinks, parent aliases and case-changed spellings into the state directory (`docs/concepts/storage-and-uri-policy.md` (Gotchas)).`

- [ ] Run only the contract-file test this fix edits: `bash harness-scripts/test.sh tests/contract/test_blobstore_local.py`. The full suite runs later, in the Run gates phase.
