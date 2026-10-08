# Review r1: docs/decisions/initial-research.md

Reviewer: a fresh review agent that did not write the document. Date: 2026-10-08.
Checked against: q1–q8c, `q7_cost_grid.py` (run with `python3 -I`), `user-decisions.md` (modified 15:16, after the document's 15:13), and `open-decisions.md`. No web sources were used. Citations were spot-checked against each findings file's own source list.

## Summary

| Severity | Count |
|---|---|
| wrong | 0 |
| unsupported | 4 |
| decided-but-open | 2 |
| stale | 4 |
| clarity | 10 |
| minor | 22 |
| **total** | **42** |

What passed:
- **Cost grid.** All 18 grid figures in §1.3 match the script output exactly, as do the ranges ($1.28–$420.62), the 8 GiB note (−14 to −15%, $1.62 to $187.43), the free-tier note, the 61% guess share (Freepik 44% + guard 17%), every crossover in Q7 and every §2 constant.
- **Pins.** Every version and Hugging Face revision pin in Part 2 matches q8a §9.4, q8b, q8c §3/X1 and q2 §5.2.
- **Expause issues.** E1–E13 match q1 §10 in numbering, issue, effect and fix, except for the omission in finding 16.
- **Stale terms.** The old path `/Users/daniel/scenewise` does not appear. Gemini 2.5 Flash-Lite, line length 120 and the 400-line limit appear only as superseded, and onnx-asr appears only as the second runtime.
- **Citations.** More than five per question were checked, and all that are not listed below are correct.

---

## Unsupported

**1. Line 34 (§1.1 Summaries row), line 304 (Q3 rejected, "A local LLM"), line 496 (Q7 crossover row)**
- **Problem.** "A local model cannot win on cost and loses on chaptering quality" and "Haiku is cheaper at every volume" overstate the findings.
  - On cost, q7 compares Haiku only with a *single-stream* local LLM; a batched vLLM server on L4 is unmeasured.
  - On quality, no benchmark compares chaptering quality with Haiku 5.5.
- **Evidence.**
  - q7 §7, "Local LLM vs Haiku" row: cheaper "than a single-stream local LLM … A batched vLLM server inside the L4 job could break even … Unmeasured". q7 §9 r1 item 9 already fixed this overstatement inside q7.
  - q3 §Summary item 2: "No published summarisation or chaptering benchmark for Haiku 5.5 was found". The F1 figures cover Llama, GPT-4o-mini, GPT-4o and Gemini.
- **Severity.** unsupported.
- **Correction.** "Haiku is about 17× cheaper than a single-stream Qwen3.5-4B on Cloud Run CPU. A batched vLLM on L4 is unmeasured, with at most about $10/month at stake. Small local models score lower on zero-shot chaptering than larger hosted models, and Haiku 5.5 itself has no published chaptering benchmark [q3 §Summary 2; q7 §7]."

**2. Line 35 (§1.1 Moderation row), line 363 (Q4 evidence, "But it refuses explicit images"), line 382 (Q4 rejected, "Refuses explicit frames")**
- **Problem.** The document states as fact that Haiku refuses explicit frames. The findings have only Anthropic's documentation sentence, and they explicitly leave open whether Haiku refuses to classify or only declines to describe. The document's own §7.4 lists this as q4 OQ3.
- **Evidence.** q4 S21 ("does not process inappropriate or explicit images …"). q4 Open question 3: "will [Haiku] reliably refuse to classify explicit frames, or only refuse to describe them? This needs an empirical test".
- **Severity.** unsupported.
- **Correction.** "Anthropic documents that Claude does not process explicit images that violate the AUP, so Haiku cannot be relied on for the sexual category. Whether it refuses or only declines to describe is untested (q4 OQ3)."

**3. Line 36 (§1.1 Labels row, deciding sentence)**
- **Problem.** The sentence says "only a local open-weight model … yields labels and an embedding in one pass, and lets the adopter define the vocabulary". q5 shows Gemini Embedding 2 also gives zero-shot labels from adopter text plus an embedding in one pass. Only data residency and vendor independence are exclusive to the local model. q5 rests the case on four points combined.
- **Evidence.**
  - q5 §5a, Gemini Embedding 2 row: "Zero-shot labels still work by text-image dot product … Data leaves the operator's infrastructure, and stored vectors are locked to the vendor".
  - q5 §5b: "The case for the local default rests on four points".
- **Severity.** unsupported.
- **Correction.** "… only a local open-weight model *combines* keeping data in the operator's infrastructure, no vendor lock-in on stored vectors, labels plus an embedding in one pass, and an adopter-defined vocabulary [q5 §5a, §5b]."

**4. Line 972 (Part 2 step 1, "licence Apache-2.0")**
- **Problem.** No findings file or user decision sets scenewise's own licence. It presumably comes from the brief, but the document cites nothing.
- **Evidence.** A grep of q8a, q8b, q8c, open-decisions and user-decisions finds no scenewise licence decision.
- **Severity.** unsupported (low impact).
- **Correction.** Cite the brief as the source, or record it as a user decision.

## Decided-but-open

**5. Line 253 (Q2 rejected, "Hosted captions (Gemini 3.x Flash-Lite, Speech-to-Text V2)"); also §1.1 Captions row and §7.1**
- **Problem.**
  - Gemini 3.x Flash-Lite captions sit in the *Rejected* table, but q7 leaves local vs Gemini for the benchmark to decide.
  - §7.2 (line 875) lists Gemini only as "Optional".
  - The §7.1 benchmark item never says it settles local vs hosted captions.
- **Evidence.** q7 §1 table: "Local, but close: at CPU speed ×0.5 local is $0.0051, dearer than gated Gemini 3.x ($0.0040–0.0043). Decide after the benchmark". The q7 crossover discussion says: "Close call that the benchmark decides".
- **Severity.** decided-but-open.
- **Correction.**
  - Keep only STT V2 standard in Rejected.
  - Move Gemini 3.1/3.5 Flash-Lite to a "decided by the benchmark" note in Q2 and in the §1.1 Captions row.
  - Add to §7.1 that the benchmark settles local vs Gemini captions (and q7 OQ9, whether Gemini 3.x is on the `eu` endpoint).

**6. Line 979 (Part 2 step 1, "the optional AudioSet tagger Apache-2.0 (D22). None is non-commercial.")**
- **Problem.** This states as settled a licence that D22 and q2 OQ16 leave open. The document's own §7.2 (line 878) lists the tagger's AudioSet provenance as an open legal check.
- **Evidence.** D22: "Music handling waits for test T1 (and a licence check on the AudioSet tagger)". q2 gives the licence as "Apache-2.0 (card)" only. q2 OQ16 is the provenance question.
- **Severity.** decided-but-open.
- **Correction.** "the optional AudioSet tagger: Apache-2.0 per its card, provenance check pending (D22, q2 OQ16)".

## Stale

**7. Lines 138–141 (Q1 input table, summary/chapters row: "the transcript and/or visual input")**
- **Problem.** The row copies q1 §4.1, which U14 overrides for v1. Q3 (lines 277–279) applies U14, so Q1 and Q3 contradict each other.
- **Evidence.** q1 §4.1 ("summary | transcript … and/or `visual`"). q8c §9 row narrowing q1 §9. U14.
- **Severity.** stale.
- **Correction.** "the transcript (v1 speech-only, U14; visual input with roadmap item 4), plus optional title/description/tags".

**8. Line 212 (Q2 decision table, Fallback row: `vad_filter=True`)**
- **Problem.** The table states q2's original value. The paragraph directly below says q8c replaced it with `vad_filter=False`, so the table contradicts the text and §4.3 (line 766).
- **Evidence.** q8c §2, adapters table, `adapters/asr/faster_whisper.py`: "`vad_filter=False` because the spans are already VAD-cut and merged".
- **Severity.** stale.
- **Correction.** Write `vad_filter=False` in the table cell (spans already VAD-cut, q8c §2).

**9. Line 946 (§7.5 Settled, CODEOWNERS row: "option A′ (bot or App for agents, …)")**
- **Problem.** This is q8c §8's pre-U13 setup. U13's corrected wording says agent PRs are opened by GitHub Actions, so no extra bot account or App is needed. Lines 631 and 718 already use the corrected wording.
- **Evidence.** user-decisions U13: "Agent PRs are opened by GitHub Actions (author `github-actions[bot]`), so no extra bot account is needed". q8c §8 A′ Setup ("a bot collaborator account … or a GitHub App") is superseded.
- **Severity.** stale.
- **Correction.** "U13: option A′ (agent PRs opened by GitHub Actions as `github-actions[bot]`; code-owner review binds; Repository-admin bypass, pull requests only)".

**10. Line 15, §4.1 (lines 702–720), line 631, Part 2 step 1 (line 974)**
- **Problem.** U13a is missing. It was added to user-decisions.md at 15:16, after the document was written at 15:13. Line 631's parenthetical hints at it ("any agent path that opens PRs with the maintainer's own token would make them maintainer-authored") but does not state the decision: local-run PRs are maintainer-authored, so gate changes from them need the logged admin bypass, *on purpose*.
- **Evidence.** user-decisions U13a: "PRs from **local** harness runs are opened manually by the maintainer … needs the logged admin bypass. That is intended: the forced bypass is the signal that an agent changed a gate."
- **Severity.** stale.
- **Correction.**
  - Add U13a to §4.1.
  - Change line 15 to "U1–U15 and U13a".
  - Replace line 631's parenthetical with U13a's wording.
  - Mention it in step 1 next to the ruleset.

## Clarity

**11. §1.3 grid and §2.2 summary tokens (line 101)**
- **Problem.** The grid charges a Haiku summary (1,160/150 tokens plus a 3 s billed wait) on the 40% of videos without speech. Under U14 and U7's 40-word minimum those videos get no summary in v1. The grid predates U14 and overstates cost slightly: about $0.00025 per video, or about $5/month at 100k × 5%. The document does not say so.
- **Evidence.** q7 §5 step 6 (`0.6 × speech + 0.4 × no-speech`); U14.
- **Severity.** clarity.
- **Correction.** Add one sentence under §1.3 saying the grid is conservative by up to about $5/month because it predates U14, or set the no-speech summary share to 0 at the next re-run.

**12. Line 393 (Q5 transcript text embedding), with lines 116 and 479**
- **Problem.** The transcript embedding is presented as an available opt-in vector and is costed in q7. However, q8c gives it no port in v1, and the Q8 list of ten ports has no embedder.
- **Evidence.** q8c §7.5: "The transcript embedding (q5 point 4) gets no port until Expause's recommender consumes vectors (q5 OQ11)."
- **Severity.** clarity.
- **Correction.** Add "not built in v1; no port until Expause's recommender consumes vectors (q8c §7.5); q7 still costs its 0.5 s guess, which is conservative".

**13. Line 380 (Q4 rejected, OpenAI `omni-moderation-latest`)**
- **Problem.** The row is in *Rejected*, but its text says the model is kept as an optional tier.
- **Evidence.** q4 §Hosted options gives the verdict "Optional zero-cost hosted tier-2 / third opinion", off by default because frames leave the operator.
- **Severity.** clarity.
- **Correction.** Move it to the Decision bullets as an optional, off-by-default tier, or reword the row to "Rejected as a primary only".

**14. Lines 333–334 (Q4 optional Haiku third opinion)**
- **Problem.** The document does not say how frames reach Haiku. q8c adds `images` to `TextRequest`, with no new port.
- **Evidence.** q8c §4.2.
- **Severity.** clarity.
- **Correction.** Add "(frames through `TextRequest.images`, q8c §4.2)".

**15. Line 631 (gate ownership) vs U13**
- **Problem.**
  - (a) The document says "a ruleset requires code-owner review on the default branch", while U13 says "on gate files". Both describe one setup, but the document does not connect them.
  - (b) The statement that GitHub Actions authorship makes the maintainer's approval count is a user decision. No finding verified it: q8c X5 and §8 evaluated only a bot collaborator or an App.
- **Evidence.** q8c §8 A′ Setup; q8b §13 CODEOWNERS file list; U13.
- **Severity.** clarity.
- **Correction.** Write "a ruleset on the default branch requires code-owner review; CODEOWNERS lists only the gate files". Mark the Actions-authorship mechanism as U13, to be confirmed in Part 2 step 1 when the ruleset is set up.

**16. Line 837 (E13) and line 889 (§7.3)**
- **Problem.** q1's E13 covers raw uploads in the default bucket as well. The document drops "raw upload" from the effect, which hides what U9 accepts: a 7-day restore window for raw uploads of paywalled media.
- **Evidence.** q1 §10 E13: "… (and the default bucket for raw uploads) … Every 'deleted' plaintext segment, playlist, sprite sheet and raw upload of paywalled or early-access media (C8) can be restored for 7 days". q1 OQ12.
- **Severity.** clarity.
- **Correction.** Keep "raw upload" in the effect and add "(accepted for the upload bucket by U9)".

**17. Line 886 (§7.3: "sizes the 120 s skip threshold")**
- **Problem.** The 120 s skip threshold is never introduced. Q1 (line 161) mentions only the 15 s budget.
- **Evidence.** q1 §8.3 step 2: "the hook is skipped entirely if the handler has already used more than 120 s".
- **Severity.** clarity.
- **Correction.** In Q1 line 161, add "and is skipped once the handler has used more than 120 s".

**18. Line 210 (Q2 VAD row)**
- **Problem.** The row describes only q2's cut ("segments capped at about 30 s"). The q8c merge into recognition segments appears only in the paragraph below, so the table alone misdescribes the v1 pipeline.
- **Evidence.** q8c §2, "Segmentation: cut, then merge".
- **Severity.** clarity.
- **Correction.** Add to the row: "then merged into ≤ 30 s recognition segments across gaps < 2 s (q8c §2)".

**19. Whole document: readability for someone who has not seen the research**
- **Problem.** The structure works: a decisions-at-a-glance section first, then one section per question with Decision / Key evidence / Rejected, then user decisions, open items and the checklist. Three things make it hard going for a newcomer:
  - **Abbreviations and codes used before or without definition.**
    - VAD, LID, ASR, WER and RTFx first appear in the §1.1 table.
    - "C1, C2" (line 190) are q1-internal codes that are never defined here.
    - "E7" (line 192) and "E1" (line 198) appear before §6 defines them.
    - T1–T4 (line 224 onward) and "OQ" and "S" numbers are not explained anywhere.
    - "Likelihood buckets", "GVI" and "CAS" also appear.
  - **Density.** The §1.1 cells hold three to five facts each, and the "deciding sentence" column often holds two or three sentences' worth of claims.
  - **Mixed altitude.** Q8 mixes architecture decisions with implementation detail (method signatures, chunk sizes) that belongs in q8c §6.
- **Evidence.** Lines 33–37, 190, 192, 198, 224, 864–869.
- **Severity.** clarity.
- **Correction.**
  - Add a short glossary after the header bullets: VAD, LID, ASR, WER, RTFx, GVI, CAS, Likelihood, E/C/T/OQ/S/L codes.
  - Replace "(C1, C2)" with its meaning: "the handler has a 180 s timeout with no retry, and anything that fails before encryption leaves media unpublished".
  - Forward-reference §6 at the first E-number.

**20. Line 15 and §4.2 (D-number range "D2–D31")**
- **Problem.** The range has gaps: D1, D15–D17, D25 and D29 are missing from §4.2, and D32 and D33 are outside the range. A reader cannot tell why. They became U11, U6, U5, U7, U10, U8, U12 and U9.
- **Evidence.** user-decisions.md; open-decisions §1.
- **Severity.** clarity.
- **Correction.** Add one line to §4.2: "D1, D15–D17, D25, D29, D32 and D33 were put to the user and became U11, U6, U5, U7, U10, U8, U12 and U9."

## Minor

**21. Line 33 (§1.1 Captions: "about 9× faster than … large-v3-turbo")**
- **Problem.** 9× is the default-precision ratio. At int8, which is what scenewise ships, the ratio is about 5.6×. Line 242 says "5.6–9×".
- **Evidence.** q2 §1: "about 9× faster … at default precision (36.8 vs 3.9) and about 5.6× faster at int8 (30.5 vs 5.4)".
- **Severity.** minor.
- **Correction.** "about 5.6–9× faster".

**22. Line 232 (Q2 evidence, "about 32 RTFx … [q2 §6.2, L1]")**
- **Problem.** The figure is in §6.1 and §10. §6.2 holds only the memory figure.
- **Evidence.** q2 §6.1; q2 §10 table ("32.3 (4 threads)").
- **Severity.** minor.
- **Correction.** Cite [q2 §6.1, §6.2, §10 L1].

**23. Lines 453–454 (Q6: Parakeet English-only, so multilingual ASR is needed; Canary-1b-v2) [q6 §Summary, D28]**
- **Problem.** q6 does not say this. The constraint comes from q2, and q6 names Canary only as a speech-translation option (OQ5).
- **Evidence.** q2 §1 (English only); q2 §2 (Canary-1b-v2: "source language must be given"); q6 OQ5.
- **Severity.** minor.
- **Correction.** Cite [q2 §1, §2; q6 §Summary, OQ5].

**24. Line 463 (Q6 "Clean options": Opus-MT CC-BY-4.0)**
- **Problem.** The Source cell gives no source for Opus-MT.
- **Evidence.** q6 options table [S11].
- **Severity.** minor.
- **Correction.** Add https://github.com/Helsinki-NLP/Opus-MT [q6 S11].

**25. Line 469 ("Meta Omnilingual MT: no weights or licence published")**
- **Problem.** q6 found only that Meta's page *links* none.
- **Evidence.** q6 Omnilingual row: "The Meta page (2026-03-17) links no weights, code or licence [S21]".
- **Severity.** minor.
- **Correction.** "Meta's page linked no weights or licence as of 2026-10-08 [q6 S21]".

**26. §7.2 (lines 861–878)**
- **Problem.** q2 OQ6 is not carried. It is the product question of whether lyric captions or SDH event cues ([music], [laughter]) are wanted at all.
- **Evidence.** q2 §7 OQ6.
- **Severity.** minor.
- **Correction.** Add "product call: lyric captions / SDH event cues (q2 OQ6)" next to T1.

**27. Line 297 (Q3 evidence, Licences)**
- **Problem.**
  - "Qwen3/3.5/3.6/3.8 Apache-2.0 per checkpoint" is cited to S10, which is only the Qwen3.5-4B card. The per-checkpoint check is S38.
  - The Llama 4 AUP is S21, not S19.
  - q3 marks Qwen3.8-Flash-Next as not permissive.
- **Evidence.** q3 Sources S10, S19, S21, S38.
- **Severity.** minor.
- **Correction.** Cite S38 and S21. Write "per checkpoint; some excluded".

**28. Line 293 (Q3 evidence, Vertex EU)**
- **Problem.** The claim "Haiku 5.5 served on global, US and EU multi-region" comes from q7 S26 (the Vertex Haiku 5.5 page), not from S25 or S27.
- **Evidence.** q7 §2.3 "[S25][S26]".
- **Severity.** minor.
- **Correction.** Add https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-5-5 [q7 S26].

**29. Line 265 (Q3 local server: "llama.cpp, Ollama or vLLM")**
- **Problem.** q3 names Ollama or llama.cpp for the CPU default. vLLM belongs to the GPU escalation tier.
- **Evidence.** q3 §Summary.
- **Severity.** minor.
- **Correction.** "llama.cpp or Ollama (vLLM for the GPU escalation tier)".

**30. Line 35 and line 326 (tier 2 on "flagged frames only")**
- **Problem.** The findings say "ambiguous or flagged".
- **Evidence.** q4 §Summary item 2; q8c §4.2 (`ambiguous(frames, scores, band)`).
- **Severity.** minor.
- **Correction.** "ambiguous or flagged frames only".

**31. Line 379 (Q4 rejected: AWS Rekognition, Azure, Hive, Sightengine)**
- **Problem.** Hive and Sightengine read as evaluated, but they were not.
- **Evidence.** q4 §Hosted options: "Not researched; same objections (paid, third party)".
- **Severity.** minor.
- **Correction.** Append "(Hive and Sightengine not researched)".

**32. Line 101 (§2.2: "q3 scenario A ÷ 12 videos per hour" for both token rows)**
- **Problem.** Only the speech row comes from q3. The no-speech row is a guess.
- **Evidence.** q7 §5 Content: "no-speech is a guess". Script: `SUM_IN_TOK_NOSPEECH = 1_160 # … (GUESS)`.
- **Severity.** minor.
- **Correction.** "speech: q3 scenario A ÷ 12; no-speech: guess".

**33. Line 43 (§1.2: "$54–106/month … [q7 §1, §2.4]")**
- **Problem.** The figures are right (218.46 − 164.67 and 218.46 − 112.10), but the $106 Delayed Job figure is in q7 open question 3, not §1 or §2.4.
- **Evidence.** q7 §1 ("$54 … $98"); q7 OQ3 ("about $106/month").
- **Severity.** minor.
- **Correction.** Cite [q7 §1, open question 3].

**34. Line 424 (Q5 evidence, "768-d")**
- **Problem.** The dimension is sourced to S45 (the open_clip configs), not to S6 or S8.
- **Evidence.** q5 §3 table: "768 [S45]".
- **Severity.** minor.
- **Correction.** Add [q5 S45].

**35. Lines 518–521 (Q7 rejected, all cited to [q7 §1])**
- **Problem.** The reasons for rejecting worker pools, one service per stage, and Hub downloads come from q7 §2.1, §2.2 and §3.
- **Evidence.** q7 §2.1 worker-pool row; q7 §2.2 "Why one service rather than one per stage"; q7 §3 model-loading table.
- **Severity.** minor.
- **Correction.** Cite [q7 §1–§3].

**36. Line 125 (§2.3: "set … the cold start")**
- **Problem.** `COLD_START_S_CPU` is derived, so editing it directly is not how the script works.
- **Evidence.** `q7_cost_grid.py`: `COLD_START_S_CPU = round(CPU_IMAGE_START_S + (SIGLIP_LOAD_S_M4 + OTHER_MODELS_LOAD_S_M4) * CLOUD_SLOWDOWN_VS_M4)`.
- **Severity.** minor.
- **Correction.** Name `CPU_IMAGE_START_S` and `OTHER_MODELS_LOAD_S_M4`.

**37. Line 960 (§7.5 tooling follow-ups) / Part 2 step 1**
- **Problem.** The nightly `codeowners/errors` check is missing.
- **Evidence.** q8c §8: "Either way add the nightly `codeowners/errors` check (q8b OQ7) once the repo exists."
- **Severity.** minor.
- **Correction.** Add it to step 1 next to the ruleset.

**38. Lines 985–986 ("`uv.lock` pins exactly the versions read on 2026-10-08 [q8c §3]")**
- **Problem.** The lock pins whatever resolves at lock time. q8c says floors equal the versions read and the lock pins exactly, so the read versions are a target to check, not a guarantee.
- **Evidence.** q8c §3.
- **Severity.** minor.
- **Correction.** "floors equal the versions read on 2026-10-08; check after `uv lock` that the lock resolves to them".

**39. Line 625 (import-linter row)**
- **Problem.** The row omits q8c §6.1 item 8: add `sherpa_onnx` to the service forbidden list and drop the `bootstrap -> onnxruntime` ignore. Only the torch probe stays exempt; q8b said "two start-up probes".
- **Evidence.** q8c §6.1 item 8; q8b §0.
- **Severity.** minor.
- **Correction.** Append "(sherpa_onnx added; only bootstrap's torch probe exempt, q8c §6.1 item 8)".

**40. §4.2 heading "the research's recommendation"**
- **Problem.** For D5, D6, D7 and D8, open-decisions records "Research's choice: none". These are orchestrator choices, not research recommendations. The heading copies user-decisions.md, whose intro says "where the research gave a recommendation *or the choice is technical and reversible*".
- **Evidence.** open-decisions §1, D5–D8.
- **Severity.** minor.
- **Correction.** "Orchestrator defaults (the research's recommendation where it gave one, otherwise a technical, reversible choice; the user may override)".

**41. Line 708 (U3) and line 744 (D23)**
- **Problem.**
  - U3 is shortened to "excluded from every default"; the source says "from every default and recommendation".
  - The D23 row drops "the caption stage reports `skipped / no_speech`" (it is stated elsewhere).
- **Evidence.** user-decisions U3, D23.
- **Severity.** minor.
- **Correction.** Restore the full wording.

**42. Line 1019 (§9: local measurement scripts "live in the session scratchpad, not the repo")**
- **Problem.** The session scratchpad is not durable, so the L1 measurements behind §1.3's measured constants cannot be reproduced. q1 says the scripts should be committed under `bench/` when the repo gets code. Part 2 has no step for this.
- **Evidence.** q1 §6.2 caveats: "They should be committed under `bench/` when the scenewise repo gets code"; q2 L1; q5 §3 ("scratchpad `q5/bench.py`").
- **Severity.** minor.
- **Correction.** Add to Part 2 step 2: "commit the q1/q2/q5 measurement scripts under `bench/`, if they still exist; otherwise note they are lost and that the Cloud Run benchmark replaces them".
