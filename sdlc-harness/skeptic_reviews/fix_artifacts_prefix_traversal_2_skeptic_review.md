# Skeptic Review: fix_artifacts_prefix_traversal_2

## Context

**Branch:** `fix_artifacts_prefix_traversal_2`
**Date:** 2026-10-09
**Reviewed:** the whole branch diff against `dev` (`origin/dev`; this checkout has no local `dev`), reviewed adversarially:
- `artifacts_prefix`, `_location` and `_shape_refusal` in `src/scenewise/app/delivery.py`;
- the `fenced` roots and `_spelt` in `src/scenewise/adapters/storage/local.py`;
- the state fence in `src/scenewise/service/bootstrap.py` `_stores`;
- the unit, contract-file and end-to-end tests;
- the doc corrections.

16 run-artifact files excluded from the reviewed diff.

**De-duplicated against:** `sdlc-harness/code_reviews/fix_artifacts_prefix_traversal_2_code_review.md` and its `finding_1.md` (the attempt-folder containment gap, now fixed at `716a5cd`). No parity review exists, because `phases.parity` is `false`. No architecture branch review exists. The lessons ledger holds only the template example.

**Checks run:**
- **Check 1 (wiring).** `fenced` has its one caller, `bootstrap._stores`. `artifacts_prefix` is reached from the delivery path as before.
- **Check 2.** The parity leg is inert. For the runtime-address leg, the state prefix, `job_prefix` and `attempt_prefix` were composed by hand. The app-side containment test now covers the job folder and every `a{n}` beneath it.
- **Check 3.** Every justification was opened. The branch documents one exception to the prompt's "however it is spelt": the case-insensitive file-system limit. Its only justification, "Linux as the deployment target (D14)" in task 7's plan, is miscited, and the same plan says so.
- **Check 4.** It found no other divergences.

**Headline conclusion:** the issue's bypass and its `..`, `.`, `//`, `%2E`, `localhost`, symlink and parent-alias variants are closed. One spelling remains open under an unauthorised exception: Finding 1.

---

## Phase 2 Readiness — Ordered Fix List

**This section is the single source of truth for the per-item fix loop.** The orchestrator walks the `[ ]` entries below top-to-bottom. Only the committing role flips each one to `[x]` as that fix's commit lands: the `committer` agent in every flow that dispatches one, or the orchestrator itself in the supervised fix flow. `[ ]` markers anywhere else are informational only.

Each entry resolves to `sdlc-harness/skeptic_reviews/fix_artifacts_prefix_traversal_2_skeptic_review/finding_<K>.md` through its `**Finding K**` reference.

1. [x] **Finding 1** — Make the output store's fence recognise the state directory by identity, so a case-changed spelling is refused, and drop the "except by case" limit from the docs _(layer: adapters, tests, general)_

---

## Must Fix

### 1. The "except by case" limit is an unauthorised exception to "however it is spelt", and its justification cites a source that does not support it
→ [finding_1.md](fix_artifacts_prefix_traversal_2_skeptic_review/finding_1.md)

---

## Should Fix

_None._

---

## Nice to Have

_None._

---

## Out of scope / verified-OK (intentional divergences / call-outs)

`phases.parity` is `false`, so this section has no parity divergences.

- **Verified-OK — `job_prefix` / `record_uri` left unchanged.** The story plan says every caller passes a `JobId` from `scenewise.domain.jobs.job_id`. That claim was checked: `JOB_ID_PATTERN` admits no `/` or `%`, and `.` and `..` are refused, so a job id is always one segment.
- **Verified-OK — the composition is fully covered.** `artifacts_prefix` now refuses a job folder that lies at, under or above the state prefix. One safe `a{n}` segment below a folder that is none of those cannot lie at or under the state prefix.
