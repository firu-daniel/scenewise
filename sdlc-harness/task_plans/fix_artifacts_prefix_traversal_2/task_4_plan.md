### Task 4 — Unit-test every refused and accepted `uri_prefix` spelling, and pin the job-id segment spellings

**Goal:** Give Task 1's normalised check the unit tests the `app` layer requires: 100% branch coverage of `app` from `tests/unit` alone (`.claude/context/conventions.md` § Testing bar; `.claude/context/tests.md` § Tree and tiers: "a new branch there gets a unit test; an e2e test does not count toward that bar"). Each spelling the store would resolve is a row in a parametrized table, so a regression names the spelling that broke. Also pin the two `job_id` spellings that make `job_prefix` and `record_uri` safe without a change: a percent-escape and a backslash.

**Depends on:** Task 1, which changes `scenewise.app.delivery.artifacts_prefix(job: Job, state_prefix: str) -> str` (the signature is unchanged) as follows:
- `InputError(code="uri_not_allowed")` when the requested prefix contains a `?` or a `#` (an empty query or fragment included — the check is on the raw string, not on `urlsplit`'s `query` / `fragment`), or has a non-empty path that does not start with `/`.
- The same error when, after both sides are normalised (scheme and host lowercased, `file://localhost` read as `file://`, percent-escapes decoded, a leading run of slashes collapsed, `posixpath.normpath`), the **job folder** `{requested.rstrip("/")}/{job_id}` — not only the requested prefix — has the state prefix's scheme and host and its path is the state path or under it. So `file:///srv` with job id `state` is refused against state `file:///srv/state`, while `file:///srv` with job id `other` is accepted and returns `file:///srv/other`.
- Otherwise it returns `job_prefix(requested.rstrip("/"), job.id)`, which is the caller's own spelling with `/{job_id}` appended.

This task tests exactly that contract and imports no private helper. It tests through the public `artifacts_prefix`, and through `handle_delivery` where the existing tests already do.

**Where this layer stops.** Unit tests only, over pure functions and `fake_dependencies`. No `tmp_path`, no adapter import, no symlink. The store fence is tested in Task 5's contract file and the HTTP path in Task 6's e2e file.

### Targets

- `tests/unit/test_delivery.py`: new parametrized tests for `artifacts_prefix`.
- `tests/unit/test_jobs.py`: two more rows in `test_job_id_rejects`.

**Work:**

- [ ] `tests/unit/test_delivery.py`: import `artifacts_prefix` from `scenewise.app.delivery`, and `InputError` alongside the existing error imports. Add a private helper `_job_with(prefix: str | None, job: str = "j") -> Job` that builds `Job(id=job_id(job), spec=JobSpec(stages=frozenset({StageName.AUDIO})), audio=None, artifacts_prefix=prefix)`, the construction `tests/unit/test_runner.py` `_job` uses, with imports from `scenewise.domain.jobs`. Add module constants `STATE = "file:///srv/state"` and `BUCKET_STATE = "mem://bucket/state"`.
- [ ] Add `test_a_prefix_that_normalises_into_the_state_prefix_is_refused`, parametrized over `(state, prefix)`, asserting `caught.value.code == "uri_not_allowed"` (`.claude/context/tests.md` § Assertions). The rows, each against `STATE` unless marked:
  - `file:///srv/artifacts/../state/victim`
  - `file:///srv/state/../state/victim`
  - `file:///srv/./state/victim`
  - `file:///srv//state/victim`
  - `file:////srv/state/victim`
  - `file:///srv/artifacts/%2E%2E/state/victim`
  - `file:///srv/artifacts%2F..%2Fstate/victim`
  - `file://localhost/srv/state/victim`
  - `FILE:///srv/state/victim`
  - `file:///srv/state`
  - `file:///srv/state/`
  - `file:///srv/artifacts/x/../../state`
  - `mem://bucket/out/../state/x` against `BUCKET_STATE`

  Beside it, add `test_a_prefix_whose_job_folder_is_the_state_prefix_is_refused`, parametrized over `(state, prefix, job)` and calling `artifacts_prefix(_job_with(prefix, job), state)`, asserting `uri_not_allowed`: `(STATE, "file:///srv", "state")`, `(STATE, "file:///srv/", "state")`, `(STATE, "file:///srv/artifacts/..", "state")`, `(BUCKET_STATE, "mem://bucket", "state")`. Add `test_a_parent_prefix_with_another_job_id_is_accepted`: `artifacts_prefix(_job_with("file:///srv", "other"), STATE) == "file:///srv/other"`, pinning that the check keys on the composed folder, not on the parent prefix as such.
- [ ] Add `test_a_prefix_with_a_query_fragment_or_relative_path_is_refused`, parametrized over `file:///srv/artifacts/x?a=b`, `file:///srv/artifacts/x#f`, `file:///srv/artifacts/x?`, `file:///srv/artifacts/x#`, `file:state/victim` and `file:./state`, each against `STATE`, asserting `uri_not_allowed`. The empty-`?` and empty-`#` rows pin that the refusal tests the raw string: a regression to `urlsplit(...).query` / `.fragment` passes the `?a=b` and `#f` rows but fails these two. Add `test_a_prefix_outside_the_state_prefix_keeps_its_own_spelling`, parametrized over `(state, prefix, expected)`:
  - `(STATE, "file:///srv/statefoo/x", "file:///srv/statefoo/x/j")`: the boundary is a whole segment.
  - `(STATE, "file:///srv/artifacts/media-1/", "file:///srv/artifacts/media-1/j")`
  - `(STATE, "file://otherhost/srv/state/x", "file://otherhost/srv/state/x/j")`: another host is another location, and the store refuses it.
  - `(BUCKET_STATE, "mem://out/x", "mem://out/x/j")`
  - `(BUCKET_STATE, "gs://bucket", "gs://bucket/j")`: an empty path reads as `/`.
  - Also add one row that pins the `None` fallback: `artifacts_prefix(_job_with(None), STATE) == "file:///srv/state/j"`.
- [ ] Keep `test_artifacts_go_to_the_requested_prefix` and `test_artifacts_never_go_under_the_state_prefix` (they run through `handle_delivery`) as they are. Extend the latter's parametrization with `mem://state/../state/other-job`, so the delivery path also shows a normalised spelling ending `failed` / `uri_not_allowed`. Under `POLICY` (`mem://state`), `mem://state/../state/other-job` normalises to host `state`, path `/state/other-job`, which is under the state location (host `state`, path `/`), so it is refused.
- [ ] `tests/unit/test_jobs.py`: add `"%2e%2e"` and `"a\\b"` to the `test_job_id_rejects` parametrization. This pins that a job id can never carry a percent-escape or a separator-like character into `job_prefix` / `record_uri`, which is why those two functions are unchanged on this branch. (A single safe segment can still land on the state directory when appended to its parent; that composition is the job-folder rows above, not these.)

**Verification:**

- Run the two edited files on their own, as `.claude/context/conventions.md` § Testing bar states: `bash harness-scripts/test.sh tests/unit/test_delivery.py` and `bash harness-scripts/test.sh tests/unit/test_jobs.py`. Every new row passes against Task 1's code.
- Every branch Task 1 added (query/fragment, relative path, the `file` + `localhost` host rewrite and its false side, the empty-path-as-`/` case, same versus different scheme or host, a job folder contained versus not — including a folder that reaches the state path only through the appended job id) is reached by at least one row above. That keeps the unit-tier 100% branch-coverage bar for `app`, which Phase G measures.
- Run `bash harness-scripts/typecheck.sh`: mypy and ruff must pass over the edited test files.

**Deviations from plan:**

- Three tests added for the two branches Task 1 recorded under its own **Deviations from plan:** note, which this plan does not list. Without them `app` misses the unit-tier 100% branch bar. `test_a_prefix_that_is_not_a_valid_uri_is_refused` covers `file://[/srv` → `uri_not_allowed` with detail "artifacts uri_prefix is not a valid URI". With an unparsable state prefix `file://[/srv`, `test_an_unparsable_state_prefix_refuses_a_scheme_less_prefix` covers `/srv/x` refused (it fails closed), and `test_an_unparsable_state_prefix_accepts_a_prefix_with_a_scheme` covers `file:///srv/x` accepted.
- The `None` fallback row is its own test, `test_no_requested_prefix_puts_artifacts_in_the_job_folder`, rather than a row in the `(state, prefix, expected)` table. Its call shape is the plan's.
- The test names say "unparsable", not "unparseable", because the typecheck gate's spell checker rejects "unparseable".
