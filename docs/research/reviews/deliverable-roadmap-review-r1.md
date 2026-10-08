# Review r1: `ROADMAP.md`

Reviewer: fresh review agent (did not write the document), 2026-10-08.
Checked against: `docs/research/q1…q8c`, `user-decisions.md` (U1–U15 and the orchestrator defaults),
`open-decisions.md`, `docs/decisions/initial-research.md`, and the brief's `### The roadmap this research serves` and
`## What to deliver` item 3.

Result: links all resolve (13 files plus `#cross-cutting-work`). No stale content found from the listed checks: no old
`~/scenewise` path, onnx-asr is "tested second", no Gemini 2.5 Flash-Lite, no separate bot account, extras list matches
q8c §6.5 items 32–34. Findings below.

Severity counts: wrong 3, unsupported 1, stale 0, broken-link 0, clarity 5, minor 8.

---

1. **Whole document (structure) → does not follow the brief's format.**
   - Problem: the brief asks for "the items in `### The roadmap this research serves` with one paragraph each". The
     roadmap adds an item 0 (repository skeleton) that is not a roadmap item, and items 0–5 each run to two or three
     paragraphs plus one or more bullet lists ("Open measurements", "Follow-up checks").
   - Evidence: brief `## What to deliver` item 3; brief roadmap list has items 1–7 only. ROADMAP.md §0 (two paragraphs
     + two lists), §1 (three paragraphs + list), §2–§4 (two to three paragraphs + list each).
   - Severity: **wrong** (violates the deliverable's stated rule).
   - Correction: one paragraph per item 1–7, in order. Move the skeleton into the introduction or into "Cross-cutting
     work" (it is Part 2 work, not a roadmap item), and replace the per-item measurement lists with one sentence each
     linking to `initial-research.md` §7.2–§7.4 (or `open-decisions.md` §2), where those lists already live.

2. **§1, first paragraph: "it has the best open English word error rate on the Open ASR Leaderboard (4.70%) of the
   models that run openly" → factually wrong.**
   - Problem: several openly runnable open-weight models score lower WER than Parakeet v2.
   - Evidence: q2 §2 table: Qwen3-ASR-1.7B 4.31 ("best open-weights"), Canary-Qwen-2.5B 4.43, ARK-ASR-0.6B 4.56,
     granite-speech-4.1-2b 4.62, MOSS-Transcribe-Diarize 4.64, cohere-transcribe 4.67, all ahead of 4.70. q2 §1 and
     `initial-research.md` §1.1 claim only that Parakeet beats every openly runnable *Whisper variant* (5.40–6.36%),
     and that "the few lower-WER models lack" native timestamps.
   - Severity: **wrong**.
   - Correction: "It was chosen because it beats every openly runnable Whisper variant on the Open ASR Leaderboard
     (4.70% average WER vs 5.40–6.36%), has native timestamps, which the few lower-WER open models lack, and runs about
     9× faster than Whisper large-v3-turbo on CPU in the same runtime ([q2](…))."

3. **Introduction: "Cost figures … every one of them depends on the Cloud Run benchmark" → overstated.**
   - Problem: several cost figures in the roadmap do not depend on Cloud Run CPU speed: Haiku translation
     ($0.015–0.034 per language per video-hour, §5), Haiku summaries' fee, Cloud Vision label detection ($0.018, §4).
   - Evidence: q6 Summary item 4 (pure token arithmetic); q5 §1 item 7 and §5 (Cloud Vision is a list price); q7 §1
     says the CPU-speed uncertainty drives the *local* stages and the grid totals.
   - Severity: **wrong**.
   - Correction: "…not measurements. Every local-compute figure, and so every monthly total, depends on the Cloud Run
     benchmark described under Cross-cutting work."

4. **§7: "and Parakeet's CC-BY-4.0 attribution duty would carry over" → no finding behind it.**
   - Problem: no findings file analyses licence duties for a hosted, billed scenewise. q2 OQ11 even leaves open
     whether caption *outputs* carry any attribution duty. Only the Gemma point (q3 §"Gemma 3 and earlier", Gemma Terms
     §1.1(b)) is sourced.
   - Evidence: grep of `docs/research/*.md` and `initial-research.md` for hosted-service licensing finds only the q3
     Gemma row; q2 §1 / OQ11; U4 covers NOTICE/README and Expause's credit, not a hosted service.
   - Severity: **unsupported**.
   - Correction: drop the Parakeet clause, or say "Parakeet's CC-BY-4.0 attribution (U4) and the open question of
     whether outputs carry a duty (q2 OQ11) would need re-checking". A better sourced example is ShieldGemma 2 (a
     tier-2 candidate, §3), which is under the same Gemma Terms that count a hosted API as distribution.

5. **Introduction: "Decisions the maintainer took during that research are in `user-decisions.md`" → incomplete.**
   - Problem: the roadmap cites many D-numbers (D19–D24, D26, D28, D30, D31) as settled, but those are orchestrator
     defaults the user may override, not maintainer decisions. A cold reader cannot tell U from D.
   - Evidence: `user-decisions.md` "Orchestrator defaults (the research's recommended option; the user may override)".
   - Severity: **clarity**.
   - Correction: "Decisions the maintainer took (U1–U15) and the defaults adopted from the research (D-numbers) are
     in…", and say once that U/D/T/E codes refer to those files.

6. **Introduction: "the questions still open are in `open-decisions.md`" → points readers at a list that is partly
   settled.**
   - Problem: `open-decisions.md` was compiled before U5–U15 and the defaults; most of its D1–D33 are now settled. The
     current open list is `initial-research.md` §7 ("with the decisions in section 4 applied").
   - Evidence: `open-decisions.md` line 3 ("Compiled 2026-10-08 from … q1–q8b"; only U1–U4 excluded);
     `initial-research.md` §7 intro and §7.5.
   - Severity: **clarity**.
   - Correction: link `docs/decisions/initial-research.md#7-open-measurements-and-expause-facts-still-needed` as the
     current open list, and `open-decisions.md` as the full record.

7. **Status of items 0/1 vs "Cloud Run CPU benchmark (the first engineering task)" → ambiguous order.**
   - Problem: item 0 is "next", item 1 is "next (first feature after the skeleton)", and the benchmark is "the first
     engineering task". A reader cannot tell which comes first.
   - Evidence: `initial-research.md` §1.2 and §7.1 call the benchmark the first engineering task; the brief puts the
     skeleton in Part 2 before any feature.
   - Severity: **clarity**.
   - Correction: state the order once, e.g. "skeleton → Cloud Run benchmark → captions", or give the benchmark the
     status "next" explicitly.

8. **§1, risks: "at half the assumed speed, local captions ($0.0026 per 5-minute video, estimated) cost more than a
   gated hosted Gemini option" → the figure in brackets is the ×1 figure.**
   - Problem: read naturally, $0.0026 is the half-speed cost. At ×0.5 local is $0.0051 vs $0.0040–0.0043 for gated
     Gemini 3.x.
   - Evidence: q7 §1 "What the grid says per stage", Captions row.
   - Severity: **clarity**.
   - Correction: "Local captions are estimated at $0.0026 per 5-minute video; at half the assumed CPU speed that
     becomes $0.0051, dearer than gated Gemini 3.x Flash-Lite on Vertex EU ($0.0040–0.0043)."

9. **Readability for a public repository → unexplained codes and internal jargon.**
   - Problem: U11, D1–D8, D19, T1–T4, E1–E13, "LID", "tier-2 guard", "Freepik" (used in Cross-cutting before or
     without context) appear without a key; "D1–D8 … settled in `user-decisions.md`" means nothing to a cold reader.
   - Evidence: §0 ("(U11)", "(D1–D8)"), §1 ("T1"…"T4"), Cross-cutting ("Freepik and the tier-2 guard").
   - Severity: **clarity**.
   - Correction: one sentence in the introduction defining the code families, and spell out "language ID (LID)" on
     first use.

10. **§2: "about $0.0047 per video-hour" → price basis mixed with the Vertex deployment.**
    - Problem: $0.0047 is the first-party list price, synchronous (q3; `initial-research.md` Q3 "first-party list
      price"), while the same sentence says Expause calls Haiku on Vertex EU (×1.10, q7 `HAIKU_PRICE_MULT`). The 17×
      figure that follows is per video, Vertex EU, wait included (q7 §1).
    - Severity: **minor**.
    - Correction: "about $0.00075 per 5-minute video on Vertex EU including the billed wait, about 17× less than…"
      (both figures from q7 §1), or label $0.0047 "first-party list price".

11. **§1: "runs several times faster than Whisper on CPU" → missing caveat.**
    - Problem: the 9× (5.6× at int8) comparison is inside onnx-asr's own Whisper path, not against the actual fallback
      (faster-whisper/CTranslate2), which is unmeasured; the roadmap's own open-measurement list includes it.
    - Evidence: q2 §1 "That comparison uses onnx-asr's own Whisper ONNX path…".
    - Severity: **minor**.
    - Correction: "about 9× faster than Whisper large-v3-turbo on CPU in the same runtime".

12. **Cross-cutting benchmark list → order and scope differ from the source.**
    - Problem: "It measures, in order" puts cold start before peak memory; the source order is peak RSS (with guard)
      then cold start (with and without lazy guard loading). "This decides 8 or 16 GiB" drops "or a separate guard
      service".
    - Evidence: `initial-research.md` §7.1; `open-decisions.md` §2 "Runtime / deployment task".
    - Severity: **minor**.
    - Correction: split into "peak memory with the guard loaded (decides 8 vs 16 GiB, or a separate guard service)"
      then "cold start, with and without lazy guard loading".

13. **Cross-cutting: "one Cloud Run CPU service in europe-west1" → region stated as settled.**
    - Problem: the region is an open Expause fact; the decision says "an EU Tier-1 region (europe-west1, or wherever
      Expause's buckets are)".
    - Evidence: `initial-research.md` §1.2 Runtime row; `open-decisions.md` §3 "GCP region".
    - Severity: **minor**.
    - Correction: "in an EU region (europe-west1 assumed; Expause's bucket region decides)".

14. **§3, open measurements: licence checks → list is partial.**
    - Problem: lists only LlavaGuard weights and dataset terms; omits Nemotron (D24) and NudeNet, and the still-open
      check that the guard server returns `top_logprobs` for image + text requests. LlavaGuard is "not recommended"
      (q4 §Summary 4), so on its own it is the least relevant item.
    - Evidence: `initial-research.md` §7.4 "Moderation"; q4 OQ6, OQ7, OQ12; q8c §4.2.
    - Severity: **minor**.
    - Correction: "Licence checks (Nemotron, NudeNet, LlavaGuard, evaluation datasets), and that the guard server
      returns `top_logprobs`." Also say that the tier-2 model itself is still open (`initial-research.md` §7.5).

15. **§1: the language rule omits the outcome for too little English.**
    - Problem: the roadmap says when English is captioned but not what happens below ~2 s of English (no track,
      `language_unsupported` / `language_unknown`), which is part of the v1 contract.
    - Evidence: q2 §1 LID bullets; q8c §5 `SkipReason`; q8c §6.4 item 23.9.
    - Severity: **minor**.
    - Correction: add "below that, no track is emitted and the stage is skipped with `language_unsupported` or
      `language_unknown`."

16. **§0: does not mention `ARCHITECTURE.md` or the open PyAV/FFmpeg licence check.**
    - Problem: `ARCHITECTURE.md` exists at the root and is the skeleton's spec, but §0 links only q8a/q8b. The
      still-open licence check of the FFmpeg libraries bundled in PyAV wheels belongs to Part 2 step 1.
    - Evidence: repository root listing; `initial-research.md` §7.5 "Still open", PyAV row.
    - Severity: **minor**.
    - Correction: link `ARCHITECTURE.md` from §0, and add the PyAV licence check to the follow-up checks.

17. **Headings §3/§4 → drift from the brief's wording.**
    - Problem: §4 "Labels for recommendations" drops "feed" and "alongside Google Video Intelligence". §3's change to
      "alongside Google's primary signal" is justified (U8); §4 could say the same for consistency.
    - Evidence: brief roadmap items 3–4; U8.
    - Severity: **minor**.
    - Correction: "## 4. Labels for feed recommendations, alongside Google's primary signal".

18. **Line wrapping → inconsistent in the source.**
    - Problem: most lines wrap at about 120 characters, but lines 37 (136), 57 (153) and 186 (133) are longer, which
      looks like unreflowed edits. It does not affect rendering.
    - Severity: **minor**.
    - Correction: reflow those paragraphs.
