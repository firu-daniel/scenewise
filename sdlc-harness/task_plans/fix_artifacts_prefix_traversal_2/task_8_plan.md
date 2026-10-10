### Task 8 — Update the configuration, layering and error-model concept docs for the normalised check and the store fence

**Goal:** Update the three concept docs that describe the output store's constructor arguments or the source of `uri_not_allowed`, so none of them still reads as if the output store had only roots and `artifacts_prefix` only a string-prefix check. These are register rows 5, 7, 10 and 31 in the story index's `## Scope register`. Rows 6, 8, 29, 30 and 32, in the same files, stay unchanged.

**Depends on:** Tasks 1–3, which change the behaviour these docs describe:
- **`artifacts_prefix`** (`src/scenewise/app/delivery.py`, Task 1) refuses, with `InputError(code="uri_not_allowed")`, a `uri_prefix` that normalises to the state prefix or under it. Normalisation covers dot segments, repeated slashes, percent-escapes, scheme and host case, and `file://localhost`. It also refuses a prefix with a query, a fragment or a relative path.
- **`LocalBlobStore`** (`src/scenewise/adapters/storage/local.py`, Task 2) takes `fenced: Sequence[Path] = ()`. In `_path`, a path whose resolved form lies inside a fenced root, but whose spelling does not, is refused with `uri_not_allowed`.
- **`bootstrap._stores`** (`src/scenewise/service/bootstrap.py`, Task 3) builds the output store as `LocalBlobStore(roots=[state path, *artifact_roots], fenced=(state path,))`. The input store is unchanged.

The gotcha-level description, including the remaining case-insensitive-filesystem limit, is Task 7's in `docs/concepts/storage-and-uri-policy.md`. This task links there rather than restating it.

**How this task's implementer reads the conventions.** This is a catch-all (`general`) task under `.claude/context/conventions.md` § The general layer: `docs/` is the research and reference record, outside ruff and typos. It touches no file Task 7 owns.

### Targets

- `docs/concepts/configuration.md`
- `docs/concepts/layering-and-ports.md`
- `docs/concepts/error-model.md`

**Work:**

- [ ] `docs/concepts/configuration.md`:
  - In step 5 "**Composition root.**", show the output store as `LocalBlobStore(roots=[state dir, *artifact_roots], fenced=(state dir,))`.
  - Rewrite the bullet "**`artifact_roots` is enforced by the store, not the use case.**" so it says three things: `artifacts_prefix` refuses a `uri_prefix` that normalises to or under the state prefix, and one with a query, fragment or relative path; the output store's roots refuse any other location; and its fence refuses a path that reaches the state directory through a symlink or another spelling.
  - In the `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`) source line, extend "enforces `local_roots` / `artifact_roots` / state exclusion" with the output store's state fence (register row 31).
  - Leave the `DeliveryPolicy, artifacts_prefix` source line, the settings-table row `artifact_roots` and the `[[job-results-and-artifacts]]` related-docs line as they are.
- [ ] `docs/concepts/layering-and-ports.md`: in the `case "file"` bullet, add `fenced=(state path,)` to the output store's arguments, with one clause on why. In the `src/scenewise/adapters/storage/local.py` (`LocalBlobStore`) source line, change "root and excluded allow-lists" to "root, excluded and fenced lists".
- [ ] `docs/concepts/error-model.md`: in the bullet "`uri_not_allowed` comes from `LocalBlobStore._path`…", add the fence case (a path that resolves into a fenced root without being spelt inside it). Note that `artifacts_prefix` also raises it for a prefix that normalises into the state prefix, or that has a query, fragment or relative path. Leave the `_terminal` bullet as it is.

**Verification:**

- Re-run the register's derivation entry E verbatim: `git grep -nE 'uri_prefix|artifacts_prefix|state-prefix check|lexical|LocalBlobStore\(|excluded|output store|artifact_roots|ARTIFACT_ROOTS|symlink' -- docs ARCHITECTURE.md README.md ':!docs/research'`. Every line it prints in this task's three files either mentions the fence or the normalised check, or is a line the register marks `no-change`.
- Re-read `src/scenewise/service/bootstrap.py` `_stores` and `src/scenewise/adapters/storage/local.py` `LocalBlobStore.__init__` / `_path` against each changed sentence. The constructor arguments and error codes in the docs must match the code as landed.

**Deviations from plan:** The plan words the check as "a `uri_prefix` that normalises to or under the state prefix". `artifacts_prefix` in `src/scenewise/app/delivery.py` compares the job folder `{uri_prefix}/{job_id}`, not the bare prefix, so `configuration.md` and `error-model.md` say "whose job folder normalises to the state prefix or under it". This matches `docs/concepts/storage-and-uri-policy.md` and `docs/features/job-results-and-artifacts.md`. Verification evidence: derivation E was re-run, and `_stores`, `LocalBlobStore.__init__` / `_path` and `artifacts_prefix` were re-read against each changed sentence. `bash harness-scripts/typecheck.sh` was run and failed only on typos findings ("unparseable") in `task_4_plan.md` line 58 and `task_7_plan.md` line 42, files this task did not touch.
