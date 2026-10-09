# Code Review: fix_artifacts_prefix_traversal_2

## Context

**Branch:** `fix_artifacts_prefix_traversal_2`
**Date:** 2026-10-09
**Reviewed:** the whole branch diff against `dev` (`origin/dev`; no local `dev` branch exists in this checkout). That covers:
- the normalised job-folder check in `artifacts_prefix`, with `_location` and `_shape_refusal` (Task 1);
- the `fenced` roots on `LocalBlobStore` and `_spelt` (Task 2);
- the state fence wired into `bootstrap._stores` (Task 3);
- the unit, contract-file and end-to-end tests (Tasks 4–6);
- the corrections to `ARCHITECTURE.md`, `docs/skeleton-notes.md` and the concept and feature docs (Tasks 7–8).

14 run-artifact files excluded from the reviewed diff.

**Headline conclusions:**
- **The issue's bypass is closed.** `{root}/artifacts/../state/victim` is now refused, and so are its `.`, `//`, `%2E%2E`, `%2F` and `file://localhost` variants. `app` compares normalised URIs, and `adapters` fences the state directory against symlinks and parent aliases. That split keeps `.claude/context/conventions.md` § Dependency direction intact: `app` gains only stdlib imports (`posixpath`, `pathlib`, `urllib.parse`), and only `bootstrap` imports the adapter.
- **The test the prompt named now asserts the refusal.** `test_cross_job_overwrite_is_refused` checks `failed` / `uri_not_allowed` and that no attacker files exist for every spelling, so it fails against the pre-branch code as the prompt requires.
- **Tests and code shape.** Each new `app` branch has a unit test, for the 100% unit-tier coverage bar. This review runs no suite: whether the tests pass is the Run gates phase's to establish. Pass 0 found no new suppression, `print`, explicit `Any` or `cast` in the added lines. Every touched module is under the 500-line cap. The one new keyword argument, `fenced`, has its caller in `bootstrap._stores`.
- **Parity.** `phases.parity` is off, so no parity check applies.
- **Pass 2.** `per_task_findings_root` holds no per-unit review folders (per-unit review was off), so Pass 2 had nothing to reconcile.

One finding is left. The job folder is compared with the state prefix, but the attempt folder one safe segment below it is not.

---

## Phase 2 Readiness — Ordered Fix List

**This section is the single source of truth for the per-item fix loop.** The orchestrator walks the `[ ]` entries below top-to-bottom. The committing role flips each one to `[x]` as that fix's commit lands: the `committer` agent in every flow that dispatches one, or the orchestrator itself in the supervised fix flow, which dispatches none. `[ ]` markers anywhere else, such as sub-step bullets inside a per-finding file, are informational only. They are never the iteration source, and the committer does not touch them.

Each entry resolves to `sdlc-harness/code_reviews/fix_artifacts_prefix_traversal_2_code_review/finding_<K>.md` through its `**Finding K**` reference.

1. [ ] **Finding 1** — Refuse a job folder that contains the state prefix, so no `a{attempt}` folder can be the state directory _(layer: app, tests, general)_

---

## Must Fix

_None._

---

## Should Fix

### 1. The attempt folder `{job folder}/a{n}` can still land exactly on the state directory, because only the job folder is compared
→ [finding_1.md](fix_artifacts_prefix_traversal_2_code_review/finding_1.md)

---

## Nice to Have

_None._

---

## Out of scope / verified-OK (intentional divergences / call-outs)

`phases.parity` is `false`, so there is no reference implementation to diverge from and this section has no parity call-outs.
