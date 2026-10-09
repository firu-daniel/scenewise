## [A · Task 4 · tests · iter 0] → layer-implementer  (#7)
- **added:** `context_notes:`
- **verbatim:** `context_notes: Task 1 added two branches its plan did not list — an unparseable requested prefix refused with detail "artifacts uri_prefix is not a valid URI", and `_location` returning a root path instead of raising on an unparseable state prefix — recorded in the **Deviations from plan:** note of sdlc-harness/task_plans/fix_artifacts_prefix_traversal_2/task_1_plan.md (commit 2ab7e56).`
- **why the agent could not derive it:** `sdlc-harness/task_plans/fix_artifacts_prefix_traversal_2/task_4_plan.md` (written before Task 1 ran) does not list those two branches; they exist only in Task 1's deviation note, outside Task 4's read set.

## [D · docs · survey] → docs-writer  (#32) (iter 0)
- **added:** `context_notes:`
- **verbatim:** `context_notes: the local branch `dev` does not exist in this checkout (`git rev-parse --verify -q dev` printed nothing); `origin/dev` is the diff base used above.`
- **why the agent could not derive it:** `harness.config.json` names `defaultBranch: dev`; the absence of a local `dev` ref in this checkout is recorded in no file the agent reads.

## [D · docs · configuration · review · iter 1] → docs-reviewer  (#34)
- **added:** `outside the sanctioned form`
- **verbatim:** `(plus the uncommitted working-tree edit to docs/concepts/configuration.md, which is the update under review)` appended to the `diff_ref:` line, and the trailing line `Open the findings file (if you write one) with a one-line note: branch fix_artifacts_prefix_traversal_2, follows review_0.md.`
- **why the agent could not derive it:** the update under review was uncommitted at dispatch time, so the `origin/dev...HEAD` diff did not contain it; the findings-file note is the docs phase's own next-free-index rule (`docs_phase_instructions.md` → `## Loop` step 2), not in the reviewer's read set.

## [D · docs · job-submission · review · iter 3] → docs-reviewer  (#36)
- **added:** `outside the sanctioned form`
- **verbatim:** `(plus the uncommitted working-tree edit to docs/features/job-submission.md, which is the update under review)` appended to the `diff_ref:` line, and the trailing line `Open the findings file (if you write one) with a one-line note: branch fix_artifacts_prefix_traversal_2, follows review_2.md.`
- **why the agent could not derive it:** same as #34 — the edit under review was uncommitted, and the note comes from the docs phase's next-free-index rule.

## [D · docs · audio-stage · review · iter 3] → docs-reviewer  (#38)
- **added:** `outside the sanctioned form`
- **verbatim:** `(plus the uncommitted working-tree edit to docs/features/audio-stage.md, which is the update under review)` appended to the `diff_ref:` line, the `target:` line's reason text `missed-doc ripple: its `artifacts_prefix` / `job_prefix` bullet described only the old rule ("may not point into the state prefix"), leaving out the rule against a job folder that contains the state prefix, and the query, fragment and relative-path refusals.` with its entry-hints, and the trailing line `Open the findings file (if you write one) with a one-line note: branch fix_artifacts_prefix_traversal_2, follows review_2.md.`
- **why the agent could not derive it:** the edit under review was uncommitted; the target reason is the previous reviewer's `missed_docs:` return, which the docs phase passes as the target; the note comes from the docs phase's next-free-index rule.
- **reported back by the agent:**
  ## Unsolicited dispatch guidance
  - `missed-doc ripple: its `artifacts_prefix` / `job_prefix` bullet described only the old rule ("may not point into the state prefix"), leaving out the rule against a job folder that contains the state prefix, and the query, fragment and relative-path refusals.` (disregarded for verdict purposes)
  - `entry-hints: `src/scenewise/app/delivery.py` (`artifacts_prefix`, `_shape_refusal`, `_location`); `src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`, `_enters`); `src/scenewise/service/bootstrap.py` (`_stores`)` (disregarded for verdict purposes)
  - `Open the findings file (if you write one) with a one-line note: branch fix_artifacts_prefix_traversal_2, follows review_2.md.` (disregarded for verdict purposes)
