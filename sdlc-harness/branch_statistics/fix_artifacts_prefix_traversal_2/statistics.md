# Branch statistics: fix_artifacts_prefix_traversal_2

## Summary

- `success_rate`: **`100%`** — headline metric.
- `story_points_total`: `90` — denominator (sum of every task's `_(points: <N>)_` story-point estimate in the story index's `## Phase 2 Readiness — Ordered Fix List`).
- `issue_cost_total`: `0` — subtraction (sum of each user-review observation's severity weight, in story-point units).
- `story_plan_tasks`: `8` — retained raw count of `## Phase 2 Readiness — Ordered Fix List` task entries.
- `user_review_issues`: `0` — retained raw count of observations across all `fix_artifacts_prefix_traversal_2_review*.md` user-review files.

Formula:

```
success_rate = round(clamp((story_points_total - issue_cost_total) / story_points_total, 0, 1) * 100, 1) percent
```

Worked example: `round(clamp((90 - 0) / 90, 0, 1) * 100, 1)` = `round(100.0, 1)` = `100%`.

Edge cases (the rate is always computed via the formula, then adjusted by these rules):

- **No issues** — when `issue_cost_total` is `0` (no user review yet, or a fully clean review) the rate is `100%`.
- **Clamped at zero** — when `issue_cost_total > story_points_total` (weighted defect load exceeds the planned story points), the raw value goes negative; the rate is **clamped to `0%`** rather than recorded as a negative number. The rate never exceeds `100%`.
- **No points** — when `story_points_total` is `0` the rate is recorded as `n/a` (cannot divide by zero). This is only reachable when the story index has **zero** task entries; a story index that has tasks but no `_(points: …)_` tags falls back to the legacy task-count denominator (see below), so it still produces a number.
- **No points tags (back-compat fallback)** — when the story index has task entries but **none** carry a `_(points: …)_` tag, `story_points_total` falls back to `story_plan_tasks` (the legacy task-count denominator) and `## Notes` records that points were unavailable.

## Counts breakdown

Per-source raw numbers and per-issue costs are retained so the metric can be refined later without re-deriving them.

- **Story-index source** — `story_points_total`: `90`, `story_plan_tasks`: `8`
  - counted from `sdlc-harness/story_plans/fix_artifacts_prefix_traversal_2_story_plan.md` (the `N. [x] **Task K** — … _(layer: …)_ _(points: <N>)_` entries under its `## Phase 2 Readiness — Ordered Fix List`, counting `[ ]` and `[x]` alike; all eight are `[x]`).
  - per-task points (`_(points: <N>)_` tag on each entry), summed:
    - Task 1 (app): `15`
    - Task 2 (adapters): `10`
    - Task 3 (service): `5`
    - Task 4 (tests): `10`
    - Task 5 (tests): `10`
    - Task 6 (tests): `15`
    - Task 7 (general): `15`
    - Task 8 (general): `10`
    - **sum (`story_points_total`)**: `90`
  - `dispositioned_points`: `0` — no commit in `dev..HEAD` (read as `origin/dev..HEAD`; no local `dev` branch exists in this checkout) carries the `record disposition of ` record, so no unit was closed without a fix and no unpointed token was matched.
  - Every entry carries a `_(points: …)_` tag, so the back-compat task-count fallback did not fire.
- **User-review source** — `user_review_issues`: `0`, `issue_cost_total`: `0`
  - glob `sdlc-harness/user_reviews/fix_artifacts_prefix_traversal_2_review*.md` matched no files (the directory holds only `README.md`); no `_fix_plan` file was matched or dropped. This is the pre-user-review write, so no file was counted.
  - **total**: `0` observations → `issue_cost_total` `0`
  - Each file's observation count is the count of whatever top-level enumeration that file uses, taken from the first of four arms to return non-zero and never summed across arms: (1) numbered `##`–`####` headings with required trailing punctuation, `grep -cE '^#{2,4} +[0-9]+[.):]'`; (2) top-level numbered/bulleted list items, `grep -cE '^[0-9]+\.|^[-*][[:space:]]'`; (3) an explicit per-observation marker the file itself uses, with the matching grep recorded beside the count; (4) `1`, reserved for a file with no enumeration of any kind. With no files matched, no arm was evaluated.
  - Each observation is weighted in story-point units: **Major** `15` (explicit `[major]` marker, or the observation describes a broken/incorrect user-facing flow, a missing/client-only authorization gate, data loss/corruption/unprotected data, or an absent whole ported behaviour — the deciding phrase is quoted beside the observation), **Trivial** `2` (explicit `[trivial]` marker), **Minor** `5` (the default for every observation without a Major/Trivial classification).

## Status

- status: `pre-user-review` — written after the branch (code) review with no user review yet (`issue_cost_total` `0` → `100%`); a post-user-review update will re-count from scratch and overwrite this file.
- last_updated: `2026-10-09`

## Notes

This is a deliberately basic but points-weighted estimate of the agentic-workflow success rate. The headline rate is `(story_points_total - issue_cost_total) / story_points_total`: the denominator is the sum of the story-plan tasks' story-point complexity estimates (the scope the agent committed to, weighted by effort rather than raw task count), and the subtraction is the severity-weighted cost of user-review observations (defects found after the workflow finished, each costing Minor `5` by default, Major `15` on an explicit marker or a documented broken-flow / security / data-integrity / missing-behaviour classification, and Trivial `2` only on an explicit marker). The retained raw counts (`story_plan_tasks`, `user_review_issues`) and per-issue costs under `## Counts breakdown` let the metric be refined later without losing the raw data. No unit on this branch was closed via the dispositioned outcome, so no story points are counted as delivered without a fix.
