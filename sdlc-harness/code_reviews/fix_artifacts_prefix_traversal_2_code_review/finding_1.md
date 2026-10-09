### 1. The attempt folder `{job folder}/a{n}` can still land exactly on the state directory, because only the job folder is compared

**File:** `src/scenewise/app/delivery.py` (`artifacts_prefix`): "path.is_relative_to(state_path)"

**Problem.** The branch's own reasoning (story plan `## Context` item 1) is that one safe segment does not make every composition safe: appended to an ancestor of the state directory, it can land exactly on that directory. So `artifacts_prefix` now compares the job folder `{uri_prefix}/{job_id}`, not the raw prefix. But artifacts are not written to the job folder. They go one more safe segment down, to `{job folder}/a{attempt}` (`src/scenewise/app/publish.py` (`attempt_prefix`): `f"{prefix.rstrip('/')}/a{attempt}"`). That segment is never compared with the state prefix. The same class of composition gap is still open, one level lower.

Concrete case: an operator sets `SCENEWISE_SERVICE__STATE_PREFIX=file:///srv/a1`. A request then posts `delivery.artifacts.uri_prefix = "file:///"` with job id `srv`:

- `_shape_refusal("file:///")` returns `None`: no query or fragment, and the path `/` is absolute.
- `folder = job_prefix("file:", "srv")` gives `file:/srv`. `_location` turns it into path `/srv`. `/srv` is not relative to `/srv/a1`, so the check passes and `artifacts_prefix` returns `file:/srv`.
- `publish` writes to `attempt_prefix("file:/srv", 1)`, which is `file:/srv/a1`, so `result.json` and `audio.wav` land at `/srv/a1/result.json` and `/srv/a1/audio.wav`. That is the root of the state directory.
- The output store does not catch it. `/srv/a1/result.json` is under the allowed state root. The fence's spelling check in `LocalBlobStore._path` also passes, because the path is spelt inside the fenced root (`_spelt` gives `/srv/a1/result.json`, which is under `/srv/a1`).

A second attempt does the same thing with a state directory named `a2`, and so on up to `max_attempts`. The case needs a state directory whose basename is `a<digits>`, which is an operator choice and not a default. That is why this is graded Should Fix and not Must Fix. When it does apply, though, a hostile request writes files directly under the state prefix. The branch's documentation now says that cannot happen: `docs/concepts/storage-and-uri-policy.md` gotcha "**A `uri_prefix` cannot reach the state tree by another spelling, except by case.**".

**Fix.** Also refuse a job folder that **contains** the state prefix, not only one that lies at or under it. Every `a{n}` subfolder then stays outside the state directory, whatever the attempt number. Here is the exact change in `artifacts_prefix`:

```python
    folder = job_prefix(job.artifacts_prefix.rstrip("/"), job.id)
    scheme, host, path = _location(folder)
    state_scheme, state_host, state_path = _location(state_prefix)
    same_authority = (scheme, host) == (state_scheme, state_host)
    if same_authority and (
        path.is_relative_to(state_path) or state_path.is_relative_to(path)
    ):
        detail = "artifacts may not be written under the state prefix"
        raise InputError(code="uri_not_allowed", detail=detail)
    return folder
```

This keeps `test_a_parent_prefix_with_another_job_id_is_accepted` passing (`/srv/other` neither contains nor lies under `/srv/state`). It also keeps every row of `test_a_prefix_outside_the_state_prefix_keeps_its_own_spelling` and the e2e `test_artifacts_under_an_artifact_root_are_job_scoped` passing, because none of those job folders is an ancestor of the state directory.

Sub-steps:

- [ ] Apply the change above in `src/scenewise/app/delivery.py` (`artifacts_prefix`).
- [ ] In the `artifacts_prefix` docstring, replace "and may not lie at or under it, so a parent of the state directory plus a job id equal to its basename is refused too." with "and may not lie at or under it, nor contain it, so a parent of the state directory plus a job id equal to its basename is refused, and so is a job folder whose `a{attempt}` subfolder would be the state directory."
- [ ] In `tests/unit/test_delivery.py`, add this test next to `test_a_prefix_whose_job_folder_is_the_state_prefix_is_refused`:

  ```python
  @pytest.mark.parametrize(
      ("state", "prefix", "job"),
      [
          ("file:///srv/a1", "file:///", "srv"),
          ("file:///srv/a1", "file:///srv/..", "srv"),
          (STATE, "file:///", "srv"),
          ("mem://bucket/x/a1", "mem://bucket", "x"),
      ],
  )
  def test_a_job_folder_that_contains_the_state_prefix_is_refused(
      state: str, prefix: str, job: str
  ) -> None:
      with pytest.raises(InputError) as caught:
          artifacts_prefix(_job_with(prefix, job), state)
      assert caught.value.code == "uri_not_allowed"
  ```

- [ ] Add "or contains it" to the sentences that state the rule. In each site below, the quoted text is the anchor and the words to insert are given:
  - `ARCHITECTURE.md` §7: "whose job folder normalises to the state prefix or below it" becomes "whose job folder normalises to the state prefix, below it, or to a folder containing it".
  - `docs/concepts/storage-and-uri-policy.md` (the `artifacts_prefix` sub-bullet): "If the folder is the state prefix or lies below it, the call raises" becomes "If the folder is the state prefix, lies below it, or contains it (so no `a{attempt}` subfolder can be the state directory), the call raises".
  - `docs/features/job-results-and-artifacts.md` (`**Gating:**`): "A `uri_prefix` whose job folder equals the state prefix, or lies under it once both are normalised" becomes "A `uri_prefix` whose job folder equals the state prefix, lies under it, or contains it once both are normalised".
  - `docs/concepts/configuration.md` (the "**`artifact_roots` is enforced by the store, not the use case.**" bullet): "normalises to the state prefix or under it" becomes "normalises to the state prefix, under it, or to a folder containing it".
  - `docs/concepts/error-model.md` (the `uri_not_allowed` bullet): "whose job folder normalises to the state prefix or under it" becomes "whose job folder normalises to the state prefix, under it, or to a folder containing it".
- [ ] Run only `bash harness-scripts/test.sh tests/unit/test_delivery.py`, the one test file this fix edits. The full suite runs later, in the Run gates phase.
