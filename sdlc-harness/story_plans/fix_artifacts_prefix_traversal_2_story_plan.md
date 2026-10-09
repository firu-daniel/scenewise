# Story: Refuse an artifact `uri_prefix` that resolves into the state prefix, however it is spelt

## Context

A job's `delivery.artifacts.uri_prefix` must never land artifacts under the state prefix. Today `artifacts_prefix` (`src/scenewise/app/delivery.py`) refuses the prefix only when the **raw string** equals the state prefix or starts with `{state}/`. The output store (`src/scenewise/adapters/storage/local.py` `LocalBlobStore._path`) resolves `..`, percent-escapes, repeated slashes and symlinks only later, and its roots include the state directory (`src/scenewise/service/bootstrap.py` `_stores`). So `{root}/artifacts/../state/victim` passes the check, and the write lands at `state/victim/attacker/a1/result.json`. This branch closes that gap with two checks that complement each other, one per layer, and keeps the layering of `.claude/context/conventions.md` § Dependency direction intact.

1. **`app`, scheme-agnostic and pure (Task 1).** `artifacts_prefix` compares the job folder the artifacts actually go to — `{uri_prefix}/{job_id}`, not just the requested prefix — with the state prefix after both are normalised the same way. Checking the folder also refuses a parent of the state directory posted with a job id equal to the state directory's basename (`file:///srv` + job `state` against `file:///srv/state`), which would otherwise write into job `a1`'s record folder. Normalising means: scheme and host lowercased, the RFC 8089 `localhost` host treated as empty for `file`, percent-escapes decoded, and the path collapsed with `posixpath.normpath` (dot segments, repeated slashes, a leading `//`). The check refuses a prefix that is equal to the state prefix or under it. It also refuses three spellings that would make "the string checked" and "the path written" disagree: a query, a fragment, and a relative path. This is string work only, from the stdlib, so `app` gains no adapter concern. **It cannot see symlinks.**
2. **`adapters`, filesystem-aware (Task 2), wired by `service` (Task 3).** `LocalBlobStore` gains a `fenced` roots list. A path whose **resolved** form lies in a fenced root must also be **spelt** inside it, compared lexically against the root's configured spelling. Otherwise the store raises `uri_not_allowed`. The output store fences the state directory. That catches the cases `app` cannot see: a symlink inside an artifact root that points into the state directory, and a second spelling of a parent directory (for example `/private/var/…` for a state prefix configured as `/var/…`). Records and default artifacts are always written through the configured state prefix, so they are spelt inside the fence and are unaffected. A plain write-scoped `excluded` on the output store would not work, because default artifacts (no `uri_prefix`) live under the state prefix by design.

**Decisions the task prompt asked planning to make:**
- **Where the resolution goes:** both places, split as above.
- **Symlinks:** they matter, because a symlinked or aliased state directory is an ordinary operator configuration. The store fence covers them. The API itself cannot create a symlink (the store writes regular files through `tempfile.mkstemp` + `Path.replace`).
- **Other callers:** `job_prefix` and `record_uri` are not changed. Every caller passes a `JobId` built by `scenewise.domain.jobs.job_id` (`envelope.parse`, `job_status`, `mapping.to_domain`, the CLI's fixed `cli`). `JOB_ID_PATTERN` `^[A-Za-z0-9._:-]{1,200}$` admits no `/` or `%`, and `job_id` refuses `.` and `..`, so a job id is always exactly one segment that cannot climb or smuggle a separator, which keeps a record inside its own folder under the configured state prefix. One safe segment does **not** make every composition safe — appended to an ancestor of the state directory it can land exactly on it — so Task 1 checks the composed job folder, and Tasks 4 and 6 test that case. Task 4 pins the percent-escape and backslash spellings in `tests/unit/test_jobs.py`.
- **The input store:** it already resolves before checking its `excluded` roots, so it is unchanged.

Tests and docs are separate single-layer tasks:
- Task 4: the `app` unit tests.
- Task 5: the store's contract-file tests.
- Task 6: the end-to-end test. It must fail against the current code, which the prompt requires.
- Tasks 7–8: docs. Task 7 covers the prompt-named sites: `ARCHITECTURE.md` §7, review-r1 row 1 of `docs/skeleton-notes.md`, and the gotchas in `docs/concepts/storage-and-uri-policy.md` and `docs/features/job-results-and-artifacts.md`. Task 8 covers the other concept docs that describe the output store or the check.

**Top risks:**
- **A spelling the store resolves but the `app` normaliser misses**, such as a percent-escaped `..`, a `localhost` host, a leading `//`, or a parent prefix that reaches the state directory only once the job id is appended. Task 1 specifies each transformation. Task 4 tests each spelling as a table. Task 6 sends the bypass spellings end to end and asserts the refusal itself, not just that the victim's files are unchanged (that weaker check is how the original gap got past the existing test).
- **The new store fence blocking legitimate writes** (records, default artifacts, prefixes inside an artifact root). The fence compares against the configured spelling that every record URI uses. Task 5 proves a fenced root stays reachable through its own spelling, and Task 6 keeps `test_artifacts_under_an_artifact_root_are_job_scoped` succeeding next to the new symlink refusal.
- **Docs still describing the lexical check as current behaviour.** Tasks 7 and 8 own every site the `## Scope register` derivations reach.

## Phase 2 Readiness — Ordered Fix List

**This section is the single source of truth for the implementation loop.** The orchestrator walks the `[ ]` entries below top-to-bottom. Only the committing role flips a marker to `[x]`: the `committer` agent in every flow that dispatches one, or the orchestrator itself in the supervised flow, which dispatches none. An implementer never changes a marker here, and never edits any other line of this section, in an index a run is iterating. `[ ]` markers anywhere else (sub-step bullets inside the per-task files) are informational only, and the committer never touches them.

Each entry resolves 1:1 to `sdlc-harness/task_plans/fix_artifacts_prefix_traversal_2/task_<K>_plan.md`. The order is bottom-up in the configured layer order (`app` → `adapters` → `service` → `tests` → `general`), with the catch-all layer last.

1. [x] **Task 1** — Compare the normalised artifact `uri_prefix` with the normalised state prefix in `artifacts_prefix` _(layer: app)_ _(points: 15)_
2. [x] **Task 2** — Give `LocalBlobStore` `fenced` roots that a path may enter only by being spelt inside them _(layer: adapters)_ _(points: 10)_
3. [x] **Task 3** — Fence the state directory on the output store in `bootstrap._stores` _(layer: service)_ _(points: 5)_
4. [x] **Task 4** — Unit-test every refused and accepted `uri_prefix` spelling, and pin the job-id segment spellings _(layer: tests)_ _(points: 10)_
5. [x] **Task 5** — Contract-file tests for the `LocalBlobStore` fence: own spelling allowed, symlink and parent alias refused _(layer: tests)_ _(points: 10)_
6. [ ] **Task 6** — Make `test_cross_job_overwrite_is_refused` assert the refusal and add the symlink spelling end to end _(layer: tests)_ _(points: 15)_
7. [ ] **Task 7** — Correct `ARCHITECTURE.md` §7, review-r1 row 1 of the skeleton notes, and the two `..` gotchas _(layer: general)_ _(points: 15)_
8. [ ] **Task 8** — Update the configuration, layering and error-model concept docs for the normalised check and the store fence _(layer: general)_ _(points: 10)_

## Scope register

**Scope predicate**, quoted verbatim from the task prompt: *"The review-r1 row in `docs/skeleton-notes.md`, the gotchas in the two docs above, and `ARCHITECTURE.md` §7 (which says a prefix under the state prefix is refused) are updated to match."* This plan widens the predicate to every durable doc that describes the `uri_prefix` check or the output store's arguments, because both change on this branch.

**Derivation entry A — docs that describe the prefix check (command).** Re-run verbatim from the repository root:
`git grep -nE 'uri_prefix|artifacts_prefix|state-prefix check|lexical' -- docs ARCHITECTURE.md README.md ':!docs/research'`

**Derivation entry B — docs that describe the stores' allow-lists (command).** Re-run verbatim from the repository root:
`git grep -nE 'LocalBlobStore\(|excluded' -- docs ARCHITECTURE.md README.md ':!docs/research'`

**Derivation entry C — conventions documents (command).** Re-run verbatim from the repository root:
`git grep -nE 'artifacts_prefix|uri_prefix|excluded' -- .claude/context`

**Derivation entry D — standing-artifact rows (procedure).**
- **First step, runnable:** `grep -nE '^## |^- ' sdlc-harness/lessons.md`.
- **Artifact:** the lessons ledger.
- **Traversal:** its topic headings in file order, then the one-line rules under each.
- **Decision rule:** a rule is reached when it names artifact prefixes, the state prefix, URI normalisation or `LocalBlobStore`.
- **Result:** it reaches no rule. The ledger's only rule is the template's worked layering example.

**Derivation entry E — docs that describe the output store's arguments and allow-list, by any wording (command).** Strictly wider than A and B together (it carries every alternative of both, plus prose that names the output store or `artifact_roots` without naming the constructor or `excluded`). Re-run verbatim from the repository root:
`git grep -nE 'uri_prefix|artifacts_prefix|state-prefix check|lexical|LocalBlobStore\(|excluded|output store|artifact_roots|ARTIFACT_ROOTS|symlink' -- docs ARCHITECTURE.md README.md ':!docs/research'`

`docs/research/` is excluded from A, B and E on purpose. It is the dated research and review record (`.claude/context/conventions.md` § The general layer), and is never rewritten to match later code.

**Closure invariant:** every file-and-anchor that entries A–C and E print appears in a row below, and every rule entry D reaches would appear as a row.

| # | Site | Copy | Evidence | Disposition | Owning task or reason |
|---|---|---|---|---|---|
| 1 | `ARCHITECTURE.md` §7 "**Storage.**" ("a `uri_prefix` under the state prefix is refused with `uri_not_allowed` (A6)") | — | A, `uri_prefix` | `change` | Task 7 |
| 2 | `ARCHITECTURE.md` §10 ("each `LocalBlobStore` enforces its own roots and excluded roots") | — | B, `excluded` | `change` | Task 7, which owns `ARCHITECTURE.md` |
| 3 | `ARCHITECTURE.md` §5 `Job(…, artifacts_prefix)` and §10 "`delivery` (… `artifacts.uri_prefix`) — not built yet" | — | A, `artifacts_prefix` / `uri_prefix` | `no-change` | a field list and a settings roadmap line. Neither states the check. |
| 4 | `README.md` "Run the audio stage" ("A request's `delivery.artifacts.uri_prefix` must lie below `SCENEWISE_SERVICE__ARTIFACT_ROOTS`") | — | A, `uri_prefix` | `no-change` | still accurate. It states where a prefix may point, not how the check compares. |
| 5 | `docs/concepts/configuration.md` step 5 "**Composition root.**" (output `LocalBlobStore(roots=[state dir, *artifact_roots])`) and "**`artifact_roots` is enforced by the store, not the use case.**" | — | A `artifacts_prefix`; B `LocalBlobStore(` | `change` | Task 8 |
| 6 | `docs/concepts/configuration.md` `DeliveryPolicy, artifacts_prefix` source line | — | A, `artifacts_prefix` | `no-change` | a pointer to the symbol, still accurate. |
| 7 | `docs/concepts/error-model.md` "`uri_not_allowed` comes from `LocalBlobStore._path` … outside the allowed roots or inside an excluded one" | — | B, `excluded` | `change` | Task 8 |
| 8 | `docs/concepts/error-model.md` "`uri_not_allowed` from `artifacts_prefix`" (the `_terminal` bullet) | — | A, `artifacts_prefix` | `no-change` | still accurate. The code and its source are unchanged. |
| 9 | `docs/concepts/job-lifecycle-and-timing.md` step 4 "**Run**" (`{artifacts_prefix}/a{n}/`) | — | A, `artifacts_prefix` | `no-change` | describes the attempt folder, which is unchanged. |
| 10 | `docs/concepts/layering-and-ports.md` `case "file"` bullet ("The output store gets `roots=[state path, *service.artifact_roots]`") and the `LocalBlobStore` source line ("root and excluded allow-lists") | — | B, `LocalBlobStore(` / `excluded` | `change` | Task 8 |
| 11 | `docs/concepts/storage-and-uri-policy.md`, `artifacts_prefix` rule (the "decides the artifact folder" bullet and its "first stripped of a trailing `/`" sub-bullet), the `_stores` composition bullets (the `case "file"` bullet "builds `outputs = [state path, *artifact_roots]`", its sub-bullets `LocalBlobStore(roots=outputs)` and `LocalBlobStore(roots=inputs.local_roots, excluded=outputs)`) incl. "The output store has no `excluded` list … lexical state-prefix check", the "**URI check** (`_path`)" bullet, and the gotcha "**A `uri_prefix` with `..` can land artifacts inside the state tree.**" | — | A `lexical` / `uri_prefix`; B `LocalBlobStore(` / `excluded`; E `artifact_roots` / `symlink` | `change` | Task 7 |
| 12 | `docs/concepts/storage-and-uri-policy.md` layout block `{uri_prefix}/{job_id}/a{n}/`, `artifact_roots` bullet, source lines (`record_uri`, `ArtifactSinkV1`) | — | A, `uri_prefix` / `artifacts_prefix` | `no-change` | layout and pointers, unchanged by this branch. Task 7 owns the file and leaves these lines alone. |
| 13 | `docs/concepts/wire-contract.md` `ArtifactSinkV1{uri_prefix?}` and the `to_domain` bullet | — | A, `uri_prefix` | `no-change` | the wire shape is unchanged. |
| 14 | `docs/features/audio-stage.md` "`{prefix}` … may not point into the state prefix (`uri_not_allowed`)", the `_run, artifacts_prefix` source line, and the input-store bullet `LocalBlobStore(roots=settings.inputs.local_roots, excluded=outputs)` | — | A `artifacts_prefix`; B `excluded` | `no-change` | still accurate. The input store is unchanged. |
| 15 | `docs/features/cli-analyse.md` ("no `artifacts_prefix`") | — | A, `artifacts_prefix` | `no-change` | the CLI path is unaffected. |
| 16 | `docs/features/job-results-and-artifacts.md` "A `uri_prefix` equal to the state prefix, or lexically under it, fails the job" and the edge case "**The state-prefix check is lexical.**", plus the `### adapters` `LocalBlobStore` bullet ("It resolves each path and checks it against its `roots`") | — | A, `lexical` / `uri_prefix` | `change` | Task 7 |
| 17 | `docs/features/job-results-and-artifacts.md` remaining `uri_prefix` / `artifacts_prefix` lines (layout bullets, `Job`, request side, `artifact_roots` default, related docs, the `POST /v1/jobs` line, source lines) | — | A, `uri_prefix` / `artifacts_prefix` | `no-change` | layout, wire and pointers, unchanged. Task 7 owns the file and leaves them alone. |
| 18 | `docs/features/job-submission.md` "A `uri_prefix` at or under the state prefix is `InputError(code="uri_not_allowed")`", the request-shape block (`artifacts?: {uri_prefix?: str}`), the stored-data line, and the test pointers | — | A, `uri_prefix` / `artifacts_prefix` | `no-change` | still accurate. "At or under" is now enforced after normalisation, and the sentence does not say how. |
| 19 | `docs/skeleton-notes.md` `## Review r1 fixes` row 1 ("two `..` spellings) now end `failed` / `uri_not_allowed`") | — | A, `uri_prefix`; B, `excluded` | `change` | Task 7 |
| 20 | `docs/skeleton-notes.md` A6 ("A requested `artifacts.uri_prefix` may not lie under the state prefix") | — | A, `uri_prefix` | `no-change` | the departure it records is unchanged and still true. |
| 21 | `docs/skeleton-notes.md` G3 ("`docs/**` excluded from typos") and review row 10 ("`^\s*\.\.\.$` exclusion is loose") | — | B, `excluded` | `no-change` | unrelated sense of "excluded". |
| 22 | `docs/decisions/initial-research.md` (five lines using "excluded" about research scope, models and licences) | — | B, `excluded` | `no-change` | unrelated sense, and a decision record. |
| 23 | `.claude/context/adapters.md` `## Storage` ("resolved path inside an allowed root and outside every `excluded` path") | — | C, `excluded` | `no-change` | a conventions document is never a task target. The rule stays true (the fence adds a condition and contradicts nothing), so no staleness is raised. |
| 24 | `.claude/context/app.md` `## Job record, artifacts and storage paths` ("a requested `uri_prefix` … may not lie under the state prefix — `InputError(code="uri_not_allowed")`") | — | C, `uri_prefix` / `artifacts_prefix` | `no-change` | a conventions document. The rule stays true and is now enforced on the normalised form. |
| 25 | `.claude/context/app.md` `_Provenance:` paragraph ("a second corpus fix re-read … `src/scenewise/app/delivery.py` (`job_prefix`, `artifacts_prefix`)") | — | C, `artifacts_prefix` | `no-change` | a conventions document, never a task target, and a provenance record of what was read, not a rule. Nothing in it is falsified. |
| 26 | `ARCHITECTURE.md` §10 settings list, the `service` bullet (`… state_prefix`, `artifact_roots`, …) | — | E, `artifact_roots` | `no-change` | a settings inventory. The setting is unchanged. |
| 27 | `ARCHITECTURE.md` §10 "**URI policy.**" ("`Dependencies.store` writes only below the state prefix and `service.artifact_roots`") | — | E, `artifact_roots` | `no-change` | still true: the fence narrows writes inside those roots and widens nothing. Task 7 owns the file and edits only the following "each `LocalBlobStore` enforces …" sentence (row 2). |
| 28 | `docs/INDEX.md` storage entry ("the separate input and output stores with their own root allow-lists") | — | E, `output store` | `no-change` | a one-line catalogue summary that still holds. The fence is described in the linked doc (row 11). |
| 29 | `docs/concepts/configuration.md` settings-table row `artifact_roots` ("`_stores` (the output store's roots)") | — | E, `artifact_roots` / `output store` | `no-change` | still accurate: `artifact_roots` remain the output store's roots. Task 8 owns the file and leaves this row alone. |
| 30 | `docs/concepts/configuration.md` related-docs line `[[job-results-and-artifacts]]` ("`state_prefix` and `artifact_roots` decide where artifacts may be written") | — | E, `artifact_roots` | `no-change` | a pointer that still holds. |
| 31 | `docs/concepts/configuration.md` `LocalBlobStore` source line ("enforces `local_roots` / `artifact_roots` / state exclusion") | — | E, `artifact_roots` | `change` | Task 8. The line lists what the store enforces, so once the output store fences the state directory the list is incomplete. |
| 32 | `docs/concepts/layering-and-ports.md` **Tests** bullet ("the inputs store is the same object as the output store") and related-docs line `[[storage-and-uri-policy]]` ("the input/output store split") | — | E, `output store` | `no-change` | the fakes and the pointer are unchanged. |
| 33 | `docs/concepts/storage-and-uri-policy.md` related-docs line `[[job-status]]` ("reads `record_uri` through the output store") and the source lines `_stores` ("builds the input and output stores from settings") and `ServiceSettings` (`state_prefix`, `artifact_roots`) | — | E, `output store` / `artifact_roots` | `no-change` | pointers, still accurate. Task 7 owns the file and leaves these lines alone. |
| 34 | `docs/features/cli-analyse.md` "**Input gating.**" bullet ("still excludes the state prefix and every `service.artifact_roots` directory"), the `LocalBlobStore` source line ("the input store's allow-list and exclusion check. The output store is also built…") and the `Settings` source line (`service.artifact_roots`) | — | E, `artifact_roots` / `output store` | `no-change` | the input store is unchanged, and the CLI never writes through the output store. |
| 35 | `docs/features/job-results-and-artifacts.md` `**Gating:**` bullet "Any other prefix must resolve below the state prefix's directory or one of `service.artifact_roots`. Otherwise the output store refuses the first write with `uri_not_allowed`" | — | E, `artifact_roots` / `output store` | `change` | Task 7. Once the fence lands the rule is incomplete: a prefix that resolves below the state directory through a symlink or a parent alias is refused. |
| 36 | `docs/features/job-results-and-artifacts.md` `### service` `_stores` bullet ("the output store (`deps.store`) over the state directory plus `artifact_roots`") | — | E, `output store` / `artifact_roots` | `change` | Task 7. The output store's construction now includes the state fence. |
| 37 | `docs/features/job-submission.md` `_stores` source line ("builds the output store (records and artifacts) over the state prefix plus `artifact_roots`") and `ServiceSettings` source line (`… state_prefix`, `artifact_roots`) | — | E, `output store` / `artifact_roots` | `no-change` | still accurate: the roots are unchanged and the line does not claim to list every check. The fence is described in `storage-and-uri-policy.md` (row 11) and `job-results-and-artifacts.md` (row 36). |
