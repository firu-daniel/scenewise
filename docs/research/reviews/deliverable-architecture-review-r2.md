# Review r2 (final): `ARCHITECTURE.md` against the final findings

Reviewer: a fresh agent that did not write or previously review the document, reading the repository cold.
Date: 2026-10-08. Read in full: `ARCHITECTURE.md` (816 lines), review r1, q8c, `user-decisions.md`, q8a §0–§13 and
its follow-ups, q8b §0–§15, `open-decisions.md` §2 and §4, `ROADMAP.md` §3–§4. Spot-checked: q1 §4.0 (URI policy),
q2 §5.2 (weight mirror), q3 (structured output), q4 (tier 1), q5 §6.1 (uncalibrated labels), q7 §1. The document was
not edited.

Format: location → problem → evidence → severity → correction. Severities: wrong / unsupported / dropped /
inconsistent / clarity / minor.

## Summary

| Severity | Count |
|---|---|
| wrong | 1 |
| unsupported | 0 |
| dropped | 2 |
| inconsistent | 0 |
| clarity | 2 |
| minor | 4 |
| **total** | **9** |

- **Round-1 findings.** All 24 are resolved; the table below gives one line each. Two are only partly resolved (r1 18,
  and r1 9 at the level of wording), and findings 5 and 7 cover them.
- **The cut.** The layout tree, the dependency rule, every port signature, wire-model placement, the lifecycle and
  status codes, the error hierarchy, the settings groups, the extras (with a pointer to q8c §3 for floors), the
  ffmpeg and PyAV rules, the testing tiers and the gate table are all present and agree with q8a, q8b and q8c. They
  hold every threshold the brief lists: mypy strict, ruff 88 with C901 ≤ 8, returns ≤ 6, branches ≤ 10, args ≤ 5,
  positional ≤ 3 and statements ≤ 40, the import-linter contracts, the 500-line limit, core coverage at 100% from
  unit tests and overall ≥ 90%, the suppression ban and budget, the stray-config check, the skip/xfail check and the
  lock check.
- **What the cut lost.** It removed domain types that the port signatures and settings now reference without defining
  (finding 2), and a few lifecycle details a skeleton builder needs (finding 3).
- **Internal consistency.** All ten ports, plus `ImageGuard`, appear in `ports.py` and in `Dependencies` or `Speech`,
  and each has an adapter in the tree. Every module sits in a layer that the rule allows. The port count, the extras,
  `max_jobs`, the lease and the error codes agree across sections.
- **Sources and §17.** Every decision traces to a finding, a U-decision or a D-default, with one exception: the labels
  row in §6 states an Expause policy as scenewise behaviour (finding 1). Each item in §17 is still open in the sources
  (checked against `open-decisions.md` §2 and §4, q8b §8 and q8c §8).
- **Length.** About 7,200 words by `wc`, of which about 5,500 are prose and the rest is the tree and code. That is
  roughly 25–30 minutes of reading, not 20 (finding 6).

### Round-1 findings: status

| r1 | Status |
|---|---|
| 1 skeleton claim | Resolved (§16 intro) |
| 2 keyword-only claim | Resolved (§14: "ruff does not enforce that") |
| 3 CI on token-opened PRs | Resolved (§17, "To verify before the ruleset is set up") |
| 4 `LabelScores` location | Resolved (§5 `# domain/labels.py`) |
| 5 `ports.py` vs `ports/` | Resolved (one rule in §2; §4 says "`scenewise.ports`") |
| 6 step-1 over-broad sentence | Resolved |
| 7 `media` and `llm` groups | Resolved (§10) |
| 8 config edits to apply | Resolved (§16 last paragraph) |
| 9 item markers | Resolved as r1 option (b); the wording is still ambiguous (finding 5) |
| 10 "CPU/GPU mix" | Resolved (§12) |
| 11 notify on every terminal write | Resolved (§7 step 7) |
| 12 422 retried | Resolved (status table) |
| 13 queue preconditions | Resolved (§7 "Timing") |
| 14 "two questions open" | Resolved (§8 names both; D11 in §17) |
| 15 diagram arrow | Resolved |
| 16 length | Partly resolved: about 2,100 words cut, still over target (finding 6) |
| 17 principles table | Resolved (three rules kept; the rest points to q8a §3) |
| 18 decision numbers in the tree | Resolved for the tree; still in the §6 "What runs" column (finding 7) |
| 19 `"und"` note | Resolved (now on `LanguageReport`) |
| 20 style-reference sample | Resolved (all lines ≤ 88 columns; the refusal check is shown) |
| 21 "3 Pythons" | Resolved |
| 22 `fakes.py` split | Resolved |
| 23 README, ROADMAP, LICENSE | Resolved |
| 24 version floors | Resolved (pointer to q8c §3) |

---

## Findings

### 1. §6 Labels row: "Uncalibrated labels are stored for shadow comparison only (U10)"

- **Problem.** The "What runs" column describes what scenewise does. Here it states an Expause integration policy as if
  it were scenewise behaviour. In scenewise, uncalibrated labels are emitted with `calibrated: false` whenever they
  pass the per-video relative cut `z ≥ z_min`. It is Expause that keeps them out of `contentTags` until one
  `scenewise calibrate` run has been done. A builder who reads the row literally would drop uncalibrated labels. That
  would contradict the document itself: §2 (`select()`), §5 (`Label.calibrated`) and §10 (`labels.z_min`, which
  exists only for uncalibrated emission).
- **Evidence.** U10 ("Uncalibrated labels into Expause `contentTags` … stored for shadow comparison only; one
  `scenewise calibrate` run is part of the Expause integration"). q5 §1 principle 6 and §6.1 principle 5 (an
  uncalibrated label "is emitted only when it stands out … Each carries `calibrated: true|false`"). q8c §4.1
  (`select()`: "calibrated threshold or z ≥ z_min"). `ROADMAP.md` §4 says the same as U10, in the context of
  `contentTags`.
- **Severity.** wrong.
- **Correction.** "… calibrated thresholds from `scenewise calibrate`. Labels without a fitted threshold are emitted
  only above a per-video relative cut (`z_min`) and carry `calibrated: false`. Expause stores them for shadow
  comparison only until it has run `calibrate` (U10)."

### 2. §5 (and §2 `domain/`): types used by the ports and settings are no longer defined

- **Problem.** The cut removed domain types that the document still uses:
  - `SpeechProbabilities`, the return type of `VoiceActivityDetector` in §4;
  - `SpeechPolicy`, the whole `captions` settings group in §10;
  - `LanguagePlan`, which carries `stretches`, `skip` and `report` (the language rule's output);
  - `Word` and `TranscriptSegment(span, words)`. §5 shows `Transcript(language, segments)` with no segment type, so a
    builder who falls back on q8a §5 gets the superseded text-only `TranscriptSegment(span, text, confidence)`;
  - `Failed(error_code, detail)`, the fields that feed `ErrorInfo` (D8 applies to `detail`);
  - `FrameModeration`, the return type of `ImageModerator` in §4;
  - `Callback`, a parameter of `Notifier`;
  - `AttemptInfo`, a parameter of `decide_attempt`;
  - `Job`, `JobSpec`, `StageOptions` (including `labels_taxonomy` and `labels_max`) and `FrameRef`.

  q8c §6.4 items 23.2 and 23.7 asked for the speech and transcript types in §5, and r1 confirmed they had been
  applied. Nothing tells a builder that q8a §5, *as amended by q8c §1, §2, §5 and §7.5*, is the full sketch. "Sources:
  q8a §5" points at the unamended version.
- **Evidence.** §4 lines 239, 255 and 267; §5 lines 324–356; §10 "`captions` (the `SpeechPolicy` fields)". q8c §1
  (`Word`, `TranscriptSegment`), §2 (`SpeechProbabilities`, `SpeechPolicy`, `LanguagePlan`), §5 (`Failed`), §7.5
  (`StageOptions` fields), §9 (q8a §5 `Transcript`/`TranscriptSegment` superseded). q8a §5 (`Callback`,
  `AttemptInfo`, `Job`, `JobSpec`, `FrameRef`, `FrameModeration`).
- **Severity.** dropped.
- **Correction.** Add one condensed line per type to the §5 block (about eight lines):
  `SpeechProbabilities(hop, values)`, `SpeechPolicy(…)  # 16 fields, q8c §2`,
  `LanguagePlan(stretches, skip, report)`, `Word(text, span, log_prob)`, `TranscriptSegment(span, words)`,
  `Failed(error_code, detail)`, `FrameModeration(timestamp, scores)`, `AttemptInfo(now, lease, max_attempts)`. Then
  replace "Condensed:" with "Condensed; the full sketch is q8a §5 as amended by q8c §1, §2, §5 and §7.5
  (`Job`, `JobSpec`, `StageOptions`, `Callback`, `FrameRef` and the moderation values are unchanged from q8a)."

### 3. §7 and §9: lifecycle details the skeleton needs were cut

- **Problem.** Five items that `delivery.py`, `publish.py`, `config.py` and `routes.py` need are missing:
  - **`GiveUp`.** It appears in the decision list, but its handling does not: write `FAILED("attempts_exhausted")`
    with `if_generation=g0`, notify, answer 200; on a `WriteConflictError`, answer 503.
  - **"Released".** §9 says "the record is released" but never says how: `RUNNING{attempt=n, lease_until=now}` with
    `if_generation=<token>`. That write is also what makes `GET` report `retry_wait`.
  - **`artifacts_prefix`.** It is used without its default: `delivery.artifacts.uri_prefix`, or
    `{state_prefix}/{job_id}`.
  - **Timing invariant.** `watchdog_grace_s` (120 s) and the start-up check
    `budget + grace + probe window < dispatch_deadline_s` are missing. §10 lists "grace" only as a field name.
  - **`/readyz`.** The start-up probe that reports model loading is not mentioned anywhere.

  §9 also leaves out that a `required_stages` entry with no back end is a `ConfigurationError`, which is what stops a
  bad revision from becoming ready.
- **Evidence.** q8a §6.2 steps 7 and 9, and "Storage layout"; q8a §6.3 timing table and "Liveness watchdog"; q8a §1.4
  `routes.py`; q8a §8 "Stage not offered".
- **Severity.** dropped.
- **Correction.**
  - §7: add a step "**8. Give up.** `GiveUp` → `FAILED("attempts_exhausted")` with `if_generation=g0`, notify, 200; on
    a conflict, 503."
  - §7 "Storage": add "(`artifacts_prefix` = `delivery.artifacts.uri_prefix`, else `{state_prefix}/{job_id}`)".
  - §7 "Timing": add "`watchdog_grace_s` = 120 s; `config.py` rejects settings unless budget + grace + probe window <
    `dispatch_deadline_s`".
  - §9: "released (`RUNNING`, `lease_until = now`)"; and "`required_stages` without a back end is a
    `ConfigurationError`".
  - §2: add `/readyz` to the `routes.py` comment.

### 4. §16 gate table: settings that pin the gates are not named

- **Problem.**
  - The Layers row omits `exhaustive = true` with `exhaustive_ignores = ["__main__"]`. That setting is what makes a
    stray top-level module such as `scenewise.utils` fail; the tree only says `__main__.py` is "exempt from the layer
    check".
  - The allow-list row says "Pydantic", but the contract lists `pydantic` and `pydantic_core` separately.
  - The table does not mention the tool-version pins, `ruff required-version = "==0.16.10"` and
    `[tool.uv] required-version = "==0.12.23"`, or `ban-relative-imports = "all"`.

  All of these are in q8b §11–§12, which the section points to. They are listed here because the brief treats the
  gate table as the skeleton's checklist.
- **Evidence.** q8b §12 (layers contract; app `allowed`), §11 (`required-version`, `flake8-tidy-imports`), §3 row 1
  (the seeded `scenewise.utils`).
- **Severity.** minor.
- **Correction.**
  - Layers row: "… `> domain`, exhaustive (`__main__` exempt)".
  - Allow-list row: "`app`: + `pydantic`, `pydantic_core`, `structlog`".
  - Format/Lint rows: append "; exact `required-version` pins for ruff and uv".

### 5. §2 sentence above the tree: "Lines marked 'item 3' or 'item 4' exist only to serve those items' extensions"

- **Problem.** "Extensions" is undefined, and the markers do not follow one rule:
  - `app/contract/taxonomy.py` is marked "item 4", but `domain/labels.py`, `adapters/vision/open_clip.py` and the
    `labels` settings group are not, although all of labels is item 4.
  - §6 says moderation's "Tier 2 … comes with item 3", which implies tier 1 comes earlier. `ROADMAP.md` §3 makes the
    whole moderation stage item 3.

  A cold reader cannot tell which unmarked modules belong to the skeleton and items 1–2, and which belong to items 3–4.
- **Evidence.** `ROADMAP.md` §3, §4; q8c §4.1 ("port changed now; implemented with roadmap item 4"), §4.2, §4.3;
  r1 finding 9.
- **Severity.** clarity.
- **Correction.** "Moderation is item 3 and labels are item 4 (`ROADMAP.md`). Their ports and modules are in the v1
  tree so that the skeleton's seams are complete. Lines marked 'item 3' or 'item 4' are additional modules that exist
  only for those items: the guard, `calibrate` and the taxonomy loader." Alternatively, mark every module with the item
  that builds it.

### 6. Whole document: reading time

- **Problem.** About 7,200 words by `wc`: about 5,500 words of prose plus the tree and the code blocks. At 200–250
  words per minute for dense prose, plus scanning the code, that is about 25–30 minutes, against the 20-minute target.
  The largest prose sections are §16 (670 words), §7 (610), §17 (360), §15 (360), §6 (350) and §14 (340).
- **Evidence.** Word counts per section, with code blocks removed.
- **Severity.** clarity.
- **Correction.** The following cuts save about 700–900 words without losing content a builder needs, which leaves
  room for findings 2 and 3:
  - §16: cut the "Apply to them" paragraph to one sentence that points to q8c §6.1–§6.2 and §7.7 and names only U11,
    D2, D3 and D5.
  - §17 "Tooling and licences": replace the OQ list with "q8b OQ3, OQ4, OQ5, OQ8 and OQ9
    (`open-decisions.md` §2, Tooling)".
  - §14 "Deliberately left out": keep the pattern list and point to q8a §12 for the rest.
  - §1: drop the Evidence column, because every section ends with its sources.

### 7. §6 "What runs" column: decision numbers as shorthand

- **Problem.** (D20), (D23), (D21), (D19), (U7…U14), (D18), (U1) and (U10) sit in running text in the "What runs"
  cells. r1 finding 18 asked for them to move to the Findings column.
- **Evidence.** §6 table; r1 finding 18's correction.
- **Severity.** minor.
- **Correction.** Move the numbers to the Findings column, next to q2, q3, q4 and q5.

### 8. §17 last bullet: an open item with no source

- **Problem.** "Whether `tests/models.lock` and `Dockerfile` belong in the CODEOWNERS gate-file list" comes from a
  note outside the counted findings in review r1. No research file raises it. Every other §17 item cites its source.
- **Evidence.** r1 "Note outside the findings"; q8b §4.2 layer 11 and §13 CODEOWNERS, which list neither file.
- **Severity.** minor.
- **Correction.** Append "(raised in `reviews/deliverable-architecture-review-r1.md`; no finding covers it)".

### 9. §15 "A step after each pytest run fails on any skipped or xfailed test in the JUnit XML"

- **Problem.** In q8b §13 the unit-only coverage run writes no JUnit report. Only the all-tiers run and the models run
  are checked. The effect is the same, because the unit tests run again in the all-tiers step, but "each" overstates
  what the workflow does, and a builder copying the sentence might add a JUnit step that is not needed.
- **Evidence.** q8b §13 `ci.yml` `test` job (the "core coverage from unit tests only" step has no `--junitxml`) and
  `extended.yml` `models`.
- **Severity.** minor.
- **Correction.** "A step after the all-tiers run in `test`, and after the model run, fails on any skipped or xfailed
  test in the JUnit XML."
