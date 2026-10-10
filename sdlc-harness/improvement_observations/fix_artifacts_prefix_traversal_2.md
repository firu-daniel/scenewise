## The configured type check fails on wording inside run artifacts under `sdlc-harness/`
- **category:** tooling-gap
- **evidence:** `bash harness-scripts/typecheck.sh` runs the `typos` spell checker over `sdlc-harness/` (`pyproject.toml` `[tool.typos.files]` excludes only `uv.lock`, `tests/fixtures/**`, `docs/**`). Task 4's implementer wrote the spelling typos rejects in favour of `unparsable` into its deviation note in `sdlc-harness/task_plans/fix_artifacts_prefix_traversal_2/task_4_plan.md`; later run artifacts quoted it (`task_7_plan.md`, `task_8_plan.md`, and `sdlc-harness/dispatch_additions/fix_artifacts_prefix_traversal_2.md`, whose `verbatim:` field must quote the addition exactly). Every implementer from Task 5 through Phase C (Tasks 5, 6, 7, 8 and the three layers of code-review Finding 1) reported `typecheck.sh` exit 2 on that one spell-check hit, and each one had to tell the hit apart from its own work.
- **cost this run:** 7 implementer dispatches reported a failing type check unrelated to their unit, and none of them could fix it, since the files sit outside their layer.
- **hypothesis:** (guess) run artifacts are not covered by the spell-check exclusion list.

## Whole-tree `ruff format --check .` fails on a Python code block inside a committed review finding
- **category:** tooling-gap
- **evidence:** all three Phase C2 implementers (adapters, tests, general) for skeptic Finding 1 reported `bash harness-scripts/typecheck.sh` exit 1 at its first gate, `ruff format --check .`. That gate flags the Python snippet in `sdlc-harness/skeptic_reviews/fix_artifacts_prefix_traversal_2_skeptic_review/finding_1.md` (line 66), so ruff check, whole-tree mypy and lint-imports did not run in those dispatches. The adapters and tests implementers fell back to `typecheck.sh <file>` (mypy only).
- **cost this run:** 3 dispatches ran without whole-tree lint or import-contract verification.

## Run gates printed `pass` right after implementers reported `typecheck.sh` red
- **category:** silent-failure
- **evidence:** `bash harness-scripts/run-test-suite.sh task_round_1` printed `pass` (Phase G round 1). The last three implementer returns before it (Phase C2, skeptic Finding 1) each reported `bash harness-scripts/typecheck.sh` failing, exit 1 at `ruff format --check .`. The orchestrator does not read gate logs, so it is unknown here whether the gate suite includes the same static checks.
- **cost this run:** the branch reached Phase D with `commands.typecheck` last observed failing, and no gate round to fix it.
- **hypothesis:** (guess) the Run gates wrapper does not run the same checks as `commands.typecheck`, or it excludes `sdlc-harness/`.

## `defaultBranch` `dev` has no local ref in the run's checkout
- **category:** tooling-gap
- **evidence:** `git rev-parse --verify -q dev` printed nothing. The `branch-reviewer` (Phase B) and the `statistics-plan-writer` (Phase D) each reported diffing against `origin/dev` instead. The architecture reviewer was dispatched with `diff_base: dev` as the core prescribes, and the docs survey needed a `context_notes:` line (recorded in `sdlc-harness/dispatch_additions/fix_artifacts_prefix_traversal_2.md`) to name the substitute base.
- **cost this run:** three agents each worked out the base for themselves, and one dispatch carried an extra note.

## The statistics writer's section-scoped extraction command was refused
- **category:** tooling-gap
- **evidence:** the `statistics-plan-writer` return (Phase D): "The section-scoped `awk`/`grep` extraction commands did not run because the permission layer turned down the combined Bash call". It counted the 8 tasks and 90 points by reading the story index instead.
- **cost this run:** the statistics figures were counted by eye, not by the agent's prescribed command.
