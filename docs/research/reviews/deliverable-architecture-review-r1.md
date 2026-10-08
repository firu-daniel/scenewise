# Review r1: `ARCHITECTURE.md` against the final findings

Reviewer: a fresh agent that did not write the document, reading the repository cold. Date: 2026-10-08.
Read in full: `ARCHITECTURE.md` (879 lines), q8c, `user-decisions.md`, q8a §0–§13 and its follow-ups, q8b §0–§15,
`open-decisions.md` §1, §2 and §4, `ROADMAP.md` §0–§4. Spot-checked against q1 (§4.0, §8.5), q2 (§5.2), q3, q4, q5 and
q7 (§1, §2.5). The document was not edited.

Format: location → problem → evidence → severity → correction.

## Summary

- q8c §6.4's edit list (items 22.1–31) is applied. One exception: 22.12's "(item 4)" tag on `app/contract/taxonomy.py`
  is missing (finding 9).
- None of the stale terms the brief lists appears: onnx-asr as primary, PyAV "not a dependency", "tiny models only",
  `asr-whisper` / `ort-*`, a bare `WriteConflict`, 400 lines, 120 characters, or a bot account for U13. One stale
  phrase from the two-selector design remains (finding 10).
- No case was found where the document decides something the findings left open. Every decision traces to a finding, a
  U-decision or a D-default. The two `unsupported` findings are claims that go beyond what was verified.
- Every port in §4 appears in the tree, in `Dependencies` or `Speech`, and has an adapter. Every module in the tree has
  a stated purpose and sits in a layer that matches the rule. The signatures shown are within max-args 5 and
  max-positional 3.

| Severity | Count |
|---|---|
| wrong | 1 |
| unsupported | 2 |
| decided-but-open | 0 |
| inconsistent | 6 |
| stale | 1 |
| clarity | 8 |
| minor | 6 |
| **total** | **24** |

---

## Findings

### 1. §16 intro: "q8b ran each gate against a skeleton of this layout"

- **Problem.** q8b's skeleton was q8a's tree, not this one. It had `asr/{parakeet,faster_whisper}.py`, the
  `asr-whisper` and `ort-*` extras, `line-length = 120`, six untyped-library overrides and Pillow in `vision`. q8c's
  changes were never run through the gates. These include the speech ports and adapters, the single `asr` extra,
  `sherpa_onnx` in the mypy override and the service contract, the new `check_lock.sh` assertion, 88 columns and the
  coverage `omit` without `images.py`.
- **Evidence.** q8b header, lines 21–31 ("q8a §1.4's package tree", "q8a §9.4's exact `[project]` extras"). q8c §6.1
  items 5–8 are text edits, and item 7 is explicitly conditional ("if deptry attributes the import to the undeclared
  core package on the first sync").
- **Severity.** unsupported.
- **Correction.** "q8b ran each gate against a skeleton of q8a's layout (q8b §14). The q8c changes applied here (§16
  last paragraph) have not been run yet; the skeleton task is where they are first verified."

### 2. §14, last sentence before "Deliberately left out": "ruff's limit of three positional parameters holds them to it"

- **Problem.** PLR0917 with `max-positional-args = 3` allows up to three positional parameters, so it does not make
  anything keyword-only. Dataclass constructors are keyword-only because of `kw_only=True`, and ruff does not see
  generated `__init__`s at all. The document's own sketches also use positional parameters:
  `ScenewiseError.__init__(self, code, detail)`, called as `InternalError("model_output_invalid", detail=…)` (§9,
  §13), and `FallbackTextGenerator(primary, secondary)` (§2, §14).
- **Evidence.** q8b §2 "Limits" (`max-positional-args` 3, with keyword-only as the stated convention); q8a §8;
  q8a §1.4.
- **Severity.** wrong.
- **Correction.** "Adapter constructors and option parameters in `src` are keyword-only by convention (q8b §2); ruff's
  limit of three positional parameters caps how far that can slip, and `kw_only=True` enforces it for dataclasses."
  Alternatively, drop "constructors" and keep "options".

### 3. §16, "How the gate-file rule binds (U13)", and §17: does CI run on agent PRs at all?

- **Problem.** U13 has agent PRs opened by GitHub Actions as `github-actions[bot]`. The document presents this as
  binding and working. No finding checks the CI side:
  - GitHub does not start new workflow runs for events caused by the repository's `GITHUB_TOKEN`, apart from
    `workflow_dispatch` and `repository_dispatch`. A PR opened with that token would therefore not trigger `ci.yml`'s
    `pull_request` run, and the required `static` / `test` checks would never report.
  - Actions may create PRs only after the repository setting "Allow GitHub Actions to create and approve pull
    requests" is turned on.
  - To be verified: whether `GITHUB_TOKEN` may push changes under `.github/workflows/` at all. Agent edits to gate
    workflows would then be impossible, not merely reviewed.

  These points come from the reviewer's knowledge of GitHub's documentation. No research file contains them, so they
  must be verified before the ruleset is set up.
- **Evidence.** U13; q8c §8 (A′ assumed a bot collaborator account or an App, not `GITHUB_TOKEN`); q8b §13 (`ci.yml`
  triggers on `pull_request`). No finding covers workflow triggering for token-created PRs.
- **Severity.** unsupported. U13 is the user's decision, but the claim that the setup works as described has no
  finding behind it.
- **Correction.** Keep U13 as decided. Add to §17 "Tooling": "Verify before the ruleset is created: (a) that CI runs on
  PRs opened by `github-actions[bot]` (`GITHUB_TOKEN`-triggered events start no workflow runs, so the agent workflow
  may need to dispatch CI explicitly or use another token); (b) the 'Allow GitHub Actions to create … pull requests'
  setting; (c) whether `GITHUB_TOKEN` can change `.github/workflows/`." Do not choose a fix here; it is open.

### 4. §5 code block: `LabelScores` listed under `# domain/results.py`

- **Problem.** q8c places `LabelScores` in `domain/labels.py`. §2's tree is vague about it ("moderation and label
  results").
- **Evidence.** q8c §4.1: "`# scenewise/domain/labels.py` … `class LabelScores`".
- **Severity.** inconsistent.
- **Correction.** Move `LabelScores(...)` under a `# domain/labels.py` heading in §5. Optionally say in the
  `domain/labels.py` tree comment that it defines `LabelScores`.

### 5. §2 tree (`ports.py … becomes ports/ at ≈200 lines`) vs §2 naming paragraph and §4 opening

- **Problem.** The tree and §4 ("All ports live in `scenewise/ports.py`") describe one module. The naming paragraph
  says that with ten ports "it will reach that early; it then starts as `ports/`". A reader cannot tell which shape the
  skeleton starts with.
- **Evidence.** q8c §6.3 item 14: "Start it as `ports/` … if the first draft exceeds 200 lines."
- **Severity.** inconsistent.
- **Correction.** Use one rule in all three places: "`ports.py`; if the first draft exceeds about 200 lines, it starts
  as `ports/` (one module per port kind, re-exported from `__init__.py`)." In §4, say "in `scenewise.ports`".

### 6. §7 step 1: "From here on, every path ends in a terminal record or a retryable 429/503"

- **Problem.** The status table two screens later has "Same `job_id`, different body → 200 … no record written". That
  path is neither a terminal record nor a 429/503.
- **Evidence.** q8a §6.2 step 8 (`Conflict` → 200, "No record is written"). q8a step 0 has the same over-broad
  sentence, so the error is inherited.
- **Severity.** inconsistent.
- **Correction.** "… ends in a terminal record, a `job_id_conflict` rejection (200, no record), or a retryable
  429/503."

### 7. §10 settings groups vs §11

- **Problem.** §11 says `SCENEWISE_MEDIA__FFMPEG` overrides the ffmpeg path, which implies a `media` group. §10's group
  list has none. §10 also omits the `llm` back-end selector (`anthropic | openai-compat | none`), although it lists the
  analogous `asr.backend`.
- **Evidence.** q8a §9.1 (`SCENEWISE_MEDIA__FFMPEG`); q8a §7.1 (`llm` discriminated on its back end). q8a §7.1 also
  lacks `media`, so the gap is inherited.
- **Severity.** inconsistent.
- **Correction.** Add "`media` (`ffmpeg`/`ffprobe` paths, minimum version)" and "`llm` (`backend`: `anthropic` |
  `openai-compat` | `none`; provider and region for Anthropic, U5; the U7 thresholds)" to §10's list.

### 8. §16 last paragraph: the list of decisions to apply to q8b's config is incomplete

- **Problem.** The paragraph lists U11, D3, D2 and q8c §6.1–§6.2. It omits three changes that touch q8b §11–§13:
  - D5 and U13 for `.github/CODEOWNERS`. q8b's file has `@<maintainers>` and a header that says "Do not allow
    bypassing" and "agents push from a separate identity", both superseded.
  - q8c §7.7, which rewrites q8b §6's contract-test example to the new `transcribe` signature and
    `adapters.asr.sherpa_parakeet`, and adds the VAD and LID contract suites.
  - The `models` job's `fetch_models.py` comment (`snapshot_download`), superseded by q8c item 11a. It is inside
    §6.2's range, but easy to miss.
- **Evidence.** q8b §13 (CODEOWNERS block); q8c §7.7; q8c §6.2 item 11a.
- **Severity.** inconsistent.
- **Correction.** "… `WriteConflictError` (D2), `@firu-daniel` and the U13 ruleset wording in CODEOWNERS (D5, U13),
  the contract-test example of q8c §7.7, and q8c §6.1–§6.2."

### 9. §2 tree: roadmap-item markers

- **Problem.**
  - (a) `app/contract/taxonomy.py` has no "item 4" marker, although q8c 22.12 adds it as an item-4 line. Its
    sibling `app/calibrate.py` has one.
  - (b) Only the item-specific extras are marked. ROADMAP makes all of moderation item 3 and all of labels item 4.
    Unmarked lines such as `domain/moderation.py`, `domain/labels.py`, `adapters/vision/*` and `domain/sampling.py`
    therefore read as part of the skeleton or item 1.
- **Evidence.** q8c §6.4 22.12; `ROADMAP.md` §3, §4; q8c §5 ("labels come from roadmap item 4, which ships after
  summaries").
- **Severity.** inconsistent.
- **Correction.** Mark `taxonomy.py` "item 4". Then either mark every module by the item that adds it (0–4), or change
  the sentence above the tree to "The tree is the v1 target; lines marked item 3/4 exist only to serve those items'
  extensions. Which item builds which module is in ROADMAP.md."

### 10. §12 bullet "cu130 is the GPU target … A CPU/GPU mix is caught at start-up"

- **Problem.** "A CPU/GPU mix" comes from q8a's two independent selector pairs (ORT CPU with torch GPU, or the
  reverse). There is now one pair. What the start-up check actually catches is `device=cuda` configured on a
  `torch-cpu` install.
- **Evidence.** q8a §9.4 ("Mixing CPU and GPU across the pairs"); q8c §3 and §6.4 item 26.
- **Severity.** stale.
- **Correction.** "A `torch-cpu` install configured with `device=cuda` is caught at start-up: `bootstrap` checks
  `torch.version.cuda`."

### 11. §7 step 7: "On success, notify once, best-effort, then answer 200"

- **Problem.** This reads as "notify only when the job succeeded". q8a notifies after every terminal write, FAILED
  included (input and internal errors, `GiveUp`), and never on `AlreadyDone`. "Success" in q8a step 6 means a
  successful CAS.
- **Evidence.** q8a §6.2 step 6 ("Success → notify"), step 7 ("finish as `FAILED` … → notify → 200"), step 9, and
  step 10 ("No re-notify").
- **Severity.** clarity.
- **Correction.** "If the terminal write succeeds, whatever the job's state, notify once (best-effort) and answer 200.
  Duplicates of a terminal job (`AlreadyDone`) are not re-notified."

### 12. §7 step 1 and the status table: 422 for a body without a usable `job_id`

- **Problem.** A reader will assume 422 is final. Cloud Tasks retries every non-2xx, 422 included, until
  `maxRetryDuration`. q8a chose that on purpose, as the signal for a broken producer.
- **Evidence.** q8a §6.1 ("This includes 409 and 422"); q8a §8 table ("Cloud Tasks retries until `maxRetryDuration`,
  the signal for a broken producer").
- **Severity.** clarity.
- **Correction.** Append to the table row: "(Cloud Tasks retries it until `maxRetryDuration`; deliberate, since no
  record can be keyed)".

### 13. §7: the caller-side queue settings the lease depends on are missing

- **Problem.** The static lease's correctness and the "scenewise's counter is authoritative" rule rely on three
  queue settings: every task's `dispatchDeadline` ≤ `dispatch_deadline_s` (1800 s), `maxAttempts: -1`, and
  `maxRetryDuration` above `max_attempts × (lease + maxBackoff)` (about 12 h). §7 states the lease but not these
  preconditions, so a cold reader cannot see why 1920 s is safe.
- **Evidence.** q8a §6.2 "Contract statements for callers"; §6.3 timing table.
- **Severity.** clarity. The omitted assumption is load-bearing.
- **Correction.** Add one sentence after "Timing": "This holds only if the caller's queue sets each task's
  `dispatchDeadline` ≤ `dispatch_deadline_s`, `maxAttempts: -1` and `maxRetryDuration` of about 12 h (q8a §6.2)."

### 14. §8 last line: "Two questions here are still open (§17)"

- **Problem.** §17 does not say which two. The probe-slot question (Q-19) is listed there. The GIL measurement (D11)
  is not.
- **Evidence.** §17 "Runtime and measurement"; q8a Q-5 and Q-19; D11.
- **Severity.** clarity.
- **Correction.** "Open: whether probes take a request slot (q8a Q-19), and GIL contention from torch inference,
  measured per D11 (§17)." Add the GIL measurement to §17.

### 15. §3 diagram: `adapters ✗ app` drawn with `◄──►`

- **Problem.** A double-headed arrow normally means "imports each other". The ✗ is easy to miss.
- **Evidence.** The sentence above the diagram says the opposite of what the arrow suggests.
- **Severity.** clarity.
- **Correction.** Draw `adapters   ✗ no imports either way ✗   app`, or leave the edge out and keep the bold rule.

### 16. Length and reading time (whole document)

- **Problem.** 9,300 words. Dense technical prose reads at roughly 200–250 words per minute, so the document takes
  about 40 minutes, about twice the 20-minute target. Much of the excess is provenance and history, not architecture.
- **Evidence.** Section word counts:

  | Section | Words |
  |---|---|
  | §2 | 1,426 |
  | §4 | 908 |
  | §16 | 857 |
  | §5 | 812 |
  | §7 | 658 |
  | §13 | 565 |
  | §15 | 551 |
  | §14 | 420 |

- **Severity.** clarity.
- **Correction.** Cut or tighten, in this order (about 2,500 words saved):
  1. §2 paragraph "Two errata changed q8a's adapters …" (history). Keep only "The only lazy imports in `src` are in
     `bootstrap.py`." Shorten the tree comments to purpose only, without decision numbers (see finding 18).
  2. §3 paragraph "q8a §1.5 wrote the layers as a five-step list …" (history). Keep one clause: "the pipe makes
     `adapters` and `app` independent siblings".
  3. §13 principles table: see finding 17.
  4. §14 "Deliberately left out": drop the items already stated in §11 (PyAV), §12 (llama-cpp-python, GPU ASR) and
     §17 (music tagger, visual-only summaries). Keep the patterns list (Stage class, Clock, Repository/UoW, bus, DI).
  5. §16: reduce the U13 paragraph to two sentences (who opens agent PRs; who may bypass, and that the bypass widens
     if the repository moves to an organisation). The gate table already says the rest.
  6. §17 first paragraph (what earlier documents settled): delete; it is history.
  7. §15: shorten the fixtures bullet to one line and point to q8b §6.
  8. Inline "(q8a §x; q8c §y)" citations: keep them in §1's Evidence column and in tables; drop most from running
     prose. The opening paragraph already says everything is sourced.

### 17. §13 "How the design principles apply"

- **Problem.** About 80% of the table restates §2–§4 and §14: module purposes, ports, the fallback wrapper and the
  bootstrap factory. For a cold reader it is ceremony. The one part that teaches something new is the stage code
  sample plus the ownership sentence.
- **Evidence.** For example, Single responsibility repeats the §2 tree comments; Interface segregation repeats the §4
  bullets; Dependency inversion repeats §3.
- **Severity.** clarity.
- **Correction.** Keep the stage sample, the "captions use case is the longer example" sentence and the ownership
  paragraph. Replace the table with three sentences, or move it to q8a by reference ("Each SOLID principle mapped to a
  stage, a back end and an input source: q8a §3"). If the showcase purpose argues for keeping it, cut it to the
  Liskov, Open/closed and Functional-core rows, which carry rules not stated elsewhere.

### 18. Decision numbers as shorthand in the tree and the tables

- **Problem.** Tree comments and table cells use "(D20)", "(U5)", "(D23)" and similar. A cold reader has to open
  `user-decisions.md` to understand a line. That makes the tree a decision log instead of a map of the code.
- **Evidence.** §2 lines 64–167; §6 table.
- **Severity.** clarity.
- **Correction.** In the tree, state the purpose only ("sherpa-onnx Parakeet: primary runtime"). Keep the D/U numbers
  in §1, the §6 Findings column and §17, where provenance belongs.

### 19. §5 `LanguageGuess` comment: `"und" below lid_p_min`

- **Problem.** The comment implies the adapter returns `"und"`. Per q8c the adapter returns the argmax and p, and
  `"und"` is the domain's key for a window below `lid_p_min`. It is assigned in `domain/speech.py` and appears in
  `LanguageReport.detected`.
- **Evidence.** q8c §2: `LanguageGuess.language: str  # Whisper language code`; "`"und"` … is the key for windows
  below `lid_p_min`, in the domain and on the wire".
- **Severity.** minor.
- **Correction.** Move the `"und"` note to `LanguageReport` ("detected includes `"und"` for windows below
  `lid_p_min`").

### 20. §13 stage sample: line length and the omitted refusal check

- **Problem.** The sample is called "the style reference", but it is not ruff-formatted at 88 columns (its `def` line
  is about 105 characters). It also leaves out the refusal check, which the stage must have. The code blocks in §4 and
  §5 also exceed 88 columns, which is fine for sketches. A style reference, though, is what agents will copy.
- **Evidence.** U11; q8c §7.1 ("The stage checks `refused` before any JSON parse").
- **Severity.** minor.
- **Correction.** Format the sample at 88 columns, and add the two-line refusal check
  (`if generation.refused: raise InternalError("model_refused")`) inside or above `generate_valid`, instead of
  saying it is "left out for brevity".

### 21. §15 tier table: the "Runs" column

- **Problem.** "every PR, 3 Pythons" appears only on Unit. The `test` job runs unit, contract and e2e on all three
  Pythons, so Contract and e2e look single-version.
- **Evidence.** q8b §13 `test` job (matrix 3.12/3.13/3.14, "all PR tiers").
- **Severity.** minor.
- **Correction.** Write "every PR, 3 Pythons" on Contract and e2e too, or put it in a note under the table.

### 22. §2 tree: `tests/fakes.py` as one module for every fake

- **Problem.** Ten or eleven port fakes, some with real behaviour (BlobStore generations and preconditions, the
  scripted VAD/LID/recogniser), together with their docstrings, are likely to approach the 500-line gate. §2 already
  plans such splits for `ports.py` and `ffmpeg.py`.
- **Evidence.** q8b §4.1 (500 lines; docstrings count); q8c §6.3 item 14 (ports reach their split point early for the
  same reason).
- **Severity.** minor.
- **Correction.** Write "`fakes.py` (becomes `fakes/`, one module per port kind, if it nears the limit)", as for
  `ports.py`.

### 23. §2 tree omits files the text relies on

- **Problem.** §11 and §12 point to "the README" (ffmpeg declaration, pip users' torch index). The opening paragraph
  cites `ROADMAP.md`. Neither file appears in the tree, and neither does `LICENSE`.
- **Evidence.** §11 "Declared in the README"; §12 "The README tells them …"; q8a §9.2.
- **Severity.** minor.
- **Correction.** Add `README.md` (install, ffmpeg requirement, the pip torch-index note, attribution), `ROADMAP.md`
  and `LICENSE` at the top of the tree, one line each.

### 24. §12 extras table: version floors

- **Problem.** The lead-in says "floors are the locked versions", but only the `asr` row gives versions. `service`,
  `llm-anthropic`, `vision`, `gcs` and `torch-*` have floors in q8c §3 that the table drops.
- **Evidence.** q8c §3 table (`fastapi>=0.142`, `uvicorn>=0.54`, `anthropic[vertex]>=1.12`, `open-clip-torch>=3.3`,
  `timm>=1.0.17`, `google-cloud-storage>=3.16`, `torch>=2.14`, `torchvision>=0.29`).
- **Severity.** minor.
- **Correction.** Either add the floors to every row, or reword the lead-in to "floors are in q8c §3; `uv.lock` pins
  exactly" and drop the versions from the `asr` row too.

---

### Note outside the findings (not counted; for the orchestrator)

`tests/models.lock` (sha256 pins for the models the model tier loads) and `Dockerfile` (image extras and weight
verification) are not in the CODEOWNERS gate-file list. No finding discusses whether they should be. This is not a
correction to the document; it could be raised as an open question. It is not decided here.
