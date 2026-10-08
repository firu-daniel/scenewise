# Review r2 (final round): q5-labels.md

Reviewer: a fresh review agent that neither wrote nor previously reviewed the file. All sources were re-opened on 2026-10-08. Expause code was read only, under `/Users/daniel/Work/expause/cloud_functions/functions/src/functions`. I did not edit the reviewed file.

Severity counts: wrong 4 · unsupported 1 · missing option 0 · design concern 4 · minor 13 (22 findings in total).

**Headline:** the r1 fixes mostly hold, and the cost-table arithmetic re-checks. Three new factual errors came in with the fixes:
- The preview counts are off by one. Expause analyses `floor(D/I)` previews, not `floor(D/I)+1`.
- The Video Intelligence "$0.09 / $0.08 volume tiers" are savings-plan prices, not volume tiers.
- `gemini-2.5-flash-lite` retires on Vertex AI on 2026-10-20, 12 days from now, so it is not a usable alternative.

The minimal taxonomy schema is well scoped. Its weak point is the calibration story: thresholds go stale silently, partial calibration is undefined, the thresholds depend on clip length, and the uncalibrated top-k always returns k labels. No recommended item carries an EU territorial clause.

## Findings

1. **Claim (§5b inputs, §8 #3):** "about `floor(D/I) + 1` sprites [S49]. That gives K ≈ 8 for a 15 s clip, 13 for 60 s and 31 for 5 min". Round-1 #3 was resolved as "8–31 previews".
   → Expause code: `computeSpriteSheetPreviewsParams` sets `columnCount = Math.floor(durationToProcess / previewsIntervalSeconds)` and `rowCount = 1` (`transcoding/app_transcoding.ts:707-708`). The success handler recomputes `columnCount` from `media.duration` and crops exactly `columnCount` tiles from the first sheet (`:123-131`, `extractThumbnailsFromSpriteSheet`). The cited source [S49] says the same: q1 §3.2 line 71, "`columnCount = floor(duration / I)` and `rowCount = 1`". The analysed set is therefore **7 / 12 / 30**. Scenewise reads the raw sheets (q1), so it may see one more sprite on the overflow sheet when D is not a multiple of I (15 s → 8). It sees 12 and 30 at 60 s and 5 min.
   → **wrong** (also wrongly attributed to [S49])
   → Correction: K = `floor(D/I)` = 7 / 12 / 30 for what Expause analyses today, with a note that the raw sheets can add one sprite when D is not a multiple of I. Recompute the columns at K = 7/12/30: local ≈ $0.00007 / $0.00013 / $0.00032; Haiku 360×640 ≈ $0.00039 / $0.00053 / $0.0011; Gemini Embedding 2 $0.00084 / $0.0014 / $0.0036; Cloud Vision $0.0105 / $0.018 / $0.045. Also change `"frames": 13` in the response example to 12. No conclusion changes.

2. **Claim (§2 Price row):** "Label detection: … $0.10/min (lower tiers $0.09 and $0.08 at higher volume)".
   → https://cloud.google.com/video-intelligence/pricing (curl, 2026-10-08). The table columns are "Price (USD)", "Gemini Enterprise Flexible Savings Plan - 1 Year" and "… - 3 Year". The row "Label detection 0–1,001 min Free, 1,001 min and above $0.10 | $0.09 | $0.08" therefore gives one list price and two **commitment-plan** prices. It has no higher-volume tier.
   → **wrong**
   → Correction: "$0.10/min after 1,000 free min/month; $0.09 / $0.08 under 1-/3-year Gemini Enterprise Flexible Savings Plans".

3. **Claim (§2 bullet, §5b VI row, OQ2):** the synthetic-video length is open ("at least 5 s"; "$0.008 (if still 5 s; OQ2)"), as are the `labelDetectionMode`, `model` and thresholds.
   → Expause code: `createSyntheticVideo(…, minDuration = 5, desiredFrameRate = 30)` computes `videoDuration = Math.max(5, previewsCount / 30)` (`transcoding/app_transcoding.ts:955-976`). With K ≤ 150, which covers every clip up to 150 min given the 60 s interval cap, the video is **exactly 5.00 s**. The request is `{inputContent, features: ['LABEL_DETECTION', 'EXPLICIT_CONTENT_DETECTION']}` with no `videoContext` (`video_analysis/video_analysis.ts:36-40`). So the API defaults apply: `SHOT_MODE`, `builtin/stable`, video threshold 0.3 and frame threshold 0.4 [S4].
   → **minor** (answerable now)
   → Correction: close the length and config half of OQ2. The VI label cost is a flat 5/60 × $0.10 = **$0.0083** per video beyond the free tier, for every K. Drop "(if still 5 s; OQ2)".

4. **Claim (§1 context, §2, §5b):** the Video Intelligence cost is given for label detection only.
   → The same call also bills `EXPLICIT_CONTENT_DETECTION` (code above). The pricing page lists "Explicit content detection … 1,001 minute and above $0.10" (curl, 2026-10-08). Expause's actual Video Intelligence bill is therefore about **$0.0167** per video. The 2027-09-14 shutdown also removes Expause's explicit-content signal, not just its labels.
   → **minor** (context missing)
   → Correction: add one line to §1 or §2. The like-for-like label row stays at $0.0083. Note that explicit detection is the moderation question (q4), not this document's.

5. **Claim (§5b):** "Every option sees the same K thumbnails."
   → [S1] samples frame-level labels "at 1 fps". The synthetic video packs K previews into 5 s at K/5 fps (finding 3), so the frame-level pass sees only about 5 of the K previews. How the segment-level labels are derived from shots is not documented.
   → **minor** (inference)
   → Correction: add the caveat that Video Intelligence may not see every preview, so its row is a cost comparison and not an input-parity comparison.

6. **Claim (§4 table):** "What Expause consumes today: top-10 `description` + confidence as `contentTags`". §1 says it "keeps … `entity.description` and the confidence".
   → `processVideoAnalysisResults` (`transcoding/app_transcoding.ts:420-443`) uses the confidence only to sort, and it takes the **last** segment's confidence in the loop. It then stores `contentTags = videoLabels.slice(0, 10).map(label => label.name)`, which is a `string[]` of names only.
   → **wrong** (low impact, but it matters for design: Expause cannot filter by score downstream; see finding 16)
   → Correction: "`contentTags` = the top-10 label names (strings); confidence is used only for ordering and is not stored".

7. **Claim (§1.8, §5a, §8 #17):** "Gemini 2.5 Flash-Lite is a near-equal-price alternative … (no shutdown date announced [S38])".
   → Gemini API deprecations (https://ai.google.dev/gemini-api/docs/deprecations, 2026-10-08): `gemini-2.5-flash-lite` released 2025-07-22, "No shutdown date announced". That is accurate for the Gemini Developer API. But Vertex AI "Model versions and lifecycle" (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, curl 2026-10-08) lists `gemini-2.5-flash-lite`, released July 22, 2025, with a **retirement date of October 20, 2026** and replacements "gemini-3.8-flash or gemini-3.1-flash-lite or Gemma 4". Vertex is the route with EU regional endpoints, which is what an EU operator would use (OQ9). On that route the model is gone in 12 days.
   → **wrong** (as a recommended alternative). The r1 #17 price correction is right for the Gemini API, but its conclusion fails on lifecycle.
   → Correction: name `gemini-3.1-flash-lite` as the Google alternative: $0.25 / $1.50 per MTok [S37], with Vertex retirement "May 7, 2027 or later". Haiku 5.5 is then cheaper (2.5× on input, 3× on output), which is the r1 reviewer's original conclusion. Drop 2.5 Flash-Lite, or mark it "retires on Vertex 2026-10-20".

8. **Claim (§3 "Considered and set aside", §5a):** `multimodalembedding@001` "is superseded by `gemini-embedding-2`, which the same Vertex page lists alongside it".
   → The Vertex page (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-multimodal-embeddings, curl 2026-10-08) lists both under "Supported models" and never says "superseded". The lifecycle page (URL in finding 7) gives `multimodalembedding@001` a **retirement date of April 1, 2027**. The embeddings page also caps its text at "32 tokens (~32 words)".
   → **unsupported** (the conclusion is right, but the stated reason has no source)
   → Correction: "retires on Vertex 2027-04-01 [lifecycle page]; text input capped at 32 tokens; set aside in favour of `gemini-embedding-2`".

9. **Claim (§1.3, §3 table):** OpenAI CLIP is excluded because "their terms … exclude deployment".
   → The model card (https://huggingface.co/openai/clip-vit-large-patch14) does say "**Any** deployed use case of the model - whether commercial or not - is currently out of scope". But this is an intended-use statement on the card, not a licence term. The weights have no HF licence tag, and the `openai/CLIP` GitHub repository is MIT (GitHub API, 2026-10-08).
   → **minor**
   → Correction: keep the exclusion as a policy choice, worded "the model card places any deployed use out of scope (no licence on the weights; repo code MIT)".

10. **Claim (§3 table, OQ8):** EVA02-L-14-336 "MIT (… L card not opened)", "Yes (presumed)"; OQ8 stays open for it.
    → HF API `timm/eva02_large_patch14_clip_336.merged2b` returns `license:mit`, not gated (2026-10-08).
    → **minor**
    → Correction: mark it "MIT, Yes" and close OQ8.

11. **Claim (§3 set-aside):** VideoPrism and InternVideo2 are set aside because the previews are "taken 2–10 s apart"; InternVideo2 is "gated".
    → The interval table goes up to 20 / 40 / 60 s for clips over 5 / 10 / 30 min (`app_transcoding.ts:699-704`). HF API: InternVideo2-CLIP is `gated: "auto"`, meaning automatic approval on accepting terms. The reasoning itself is sound; wider spacing only strengthens it. VideoPrism LvT is Apache-2.0 (verified).
    → **minor**
    → Correction: "2–60 s apart"; "gated (auto-approval)".

12. **Design concern: calibrations go stale silently** (§6.1 principles 3–4, §6.2).
    → No source applies; this is my own judgement. Calibrations are keyed only by `model_id`, and `taxonomy_hash` deliberately excludes `calibrations`. If an adopter edits a label's `prompts`, or edits the global `templates`, the hash changes and the text-embedding cache is correctly invalidated. The old threshold under `calibrations[model_id]` still applies to the new prompts, with `calibrated: true`. A threshold fitted on different prompts is meaningless.
    → **design concern**
    → Correction: give each calibration entry the `taxonomy_hash` it was fitted against (or a per-label prompt hash), plus the preprocessing and pooling id. On mismatch, ignore the entry, fall back to uncalibrated and log a warning.

13. **Design concern: partial calibration is undefined.** The example calibrates 2 of 5 labels, but the rule says "With one, it returns the labels at or above their threshold … with `calibrated: true`".
    → No source; this is my own judgement. Nothing says what happens to `sport`, `food` and `asmr`. They might always be dropped, always kept, or ranked by raw score. A response-level `calibrated: true` cannot express a mixed state.
    → **design concern**
    → Correction: add a per-label `calibrated` flag in the output. State the rule explicitly, for example "uncalibrated labels in a partly calibrated taxonomy are returned only through top-k fill, flagged". Alternatively, make `calibrate` cover every label or fail validation.

14. **Design concern: a per-label threshold on `score_max` depends on clip length** (§6.2 scoring 3–4).
    → This is an inference from the code above. K ranges from 7 to 30 for typical clips (finding 1). The maximum over 30 frames is stochastically higher than the maximum over 7, so one threshold is too strict for short clips and too lenient for long ones. It also depends on squash versus pad (OQ10).
    → **design concern**
    → Correction: fit thresholds on a K-stratified sample and record the K range in the calibration, or threshold a K-robust statistic (mean of the top 3 frames). At minimum, list this in §6.3 and OQ10.

15. **Design concern: uncalibrated top-k always returns exactly k labels** (§1.6, §6.1 principle 5).
    → No source; this is my judgement, informed by finding 6. Today Video Intelligence only returns labels above its 0.3 video-level default (finding 3), so sparse videos get fewer than 10 tags. Scenewise without calibration returns 10 tags for every video, including ones where nothing in the taxonomy applies. Expause stores only names, so it cannot filter them later. r1 #24 suggested "top-k plus a margin"; the resolution kept only top-k.
    → **design concern**
    → Correction: either add a model-agnostic relative cut (drop labels below `best − δ`, or below the per-video median plus a margin), or state that adopters should not write uncalibrated labels into production tags. Make one `scenewise calibrate` run part of the Expause integration (labels can be bootstrapped with Haiku, as §5 already suggests).

16. **Claim (§6.2 scoring 4):** "`scenewise calibrate` takes a CSV of `(video_id, label_id, is_positive)` and fits one threshold per label for a target precision."
    → No source; this is my judgement. The CSV does not say where the frames for `video_id` come from. The target precision is not recorded in the output (`fitted_at` only). It has no rule for labels with few positives.
    → **minor**
    → Correction: give the input as a frames manifest (or cached per-frame scores). Record `target_precision`, `n_pos`, `n_neg`, `taxonomy_hash` and the scenewise version. Leave labels with fewer than N positives uncalibrated.

17. **Claim (§6.1 principle 4):** thresholds "are written only by `scenewise calibrate`" into the taxonomy file.
    → No source; this is my judgement. A tool that rewrites an adopter's hand-edited YAML loses comments and ordering, and it mixes generated and authored content under version control.
    → **minor**
    → Correction: write calibrations to a sidecar file (`<taxonomy>.calibrations.json`) that the loader merges, keyed as in finding 12.

18. **Claim (§6.1 principle 2 vs §6.2 request and response):** the principles say "selected per request by `taxonomy_id`" and "echoes … `taxonomy_hash`". The JSON uses `"taxonomy": {"id": …}` and `taxonomy.hash`.
    → This is internal to the document.
    → **minor**
    → Correction: use one naming convention throughout.

19. **Claim (§1.7):** "All are below 2 cents per video."
    → §5b shows Cloud Vision at $0.020 (K = 13) and $0.047 (K = 31). §5b's own reading says "under 5 cents".
    → **minor**
    → Correction: "All are below 5 cents per video; all but Cloud Vision are below 2 cents".

20. **Claim (§5b reading, Haiku 4.5 line):** Haiku 4.5 is costed on a 1600×900 sheet.
    → This is a leftover from r0 and contradicts "Every option sees the same K thumbnails". The arithmetic itself (≈ $0.0031) re-checks.
    → **minor**
    → Correction: recost it at K × 360×640, or drop it.

21. **Claim (§5b compute assumption):** the local cost assumes 4 vCPU billed for the full per-image time at 4 threads.
    → This is the document's own measurement (§3). The figures are 37 ms per image on 4 threads against 54 ms on 1 thread, a 1.46× speed-up for 4× the vCPU. Per image that is about 148 vCPU-ms on 4 threads against 54 vCPU-ms on 1 thread.
    → **minor** (inference; cost does not decide anyway)
    → Correction: note that single-thread workers would cut local compute cost by about 2.7×. That means 1 vCPU instances, or concurrency 4 with one thread each. This matters only for the q7 sizing.

22. **Claim (§1.2 alternative, U3 check):** PE-Core is Apache-2.0.
    → Verified: the HF API `timm/PE-Core-B-16` and `facebook/PE-Core-B16-224` carry `license:apache-2.0`, and the README badge says "Model License-Apache 2.0". But the same `perception_models` repo hosts Perception-LM under the "FAIR Research License", built on Llama 3.x. Llama multimodal is excluded by U3.
    → **minor**
    → Correction: one line saying only PE-Core weights are recommended, never PLM.

## Round-1 resolutions judged

- #1, #4–#6, #8–#15, #18–#20 and #22–#28 are resolved correctly. I spot-checked the figures and quotes below.
- #2 is resolved correctly (the prorated example is verbatim on the live page), but it introduced the savings-plan misreading in finding 2.
- #3 is accepted with the correction "8–31", but the correction is off by one (finding 1). The conclusion stands.
- #7 is resolved correctly. EVA02-L can now be closed too (finding 10).
- #16: the correction is **right**. The Gemini API page gives "128 - 3072, Recommended: 768, 1536, 3072". Vertex gives "128 to 3072 … 128, 768 or 1536". The Gemini API page also says the model "auto-normalizes truncated dimensions".
- #17: the price correction is right for the Gemini API, but the recommendation fails on the Vertex retirement of 2026-10-20 (finding 7).
- #21: the conclusion is right, but the reason has no source (finding 8).

## Verified correct (re-opened 2026-10-08)

- **Video Intelligence pricing (curl):** the rounding sentence and the 82 s × 1000 = 1366.66 min → $36.67 example are verbatim. 5 s = $0.00833.
- **Cloud Vision pricing:** label detection free for the first 1,000 units, then $1.50 per 1,000 up to 5 M and $1.00 above. "Each feature applied to an image is a billable unit." No deprecation notice.
- **Gemini Embedding 2 (Gemini API):**
  - Stable, default 3072-d, at most 6 images per request, video ≤120 s and ≤32 frames, 8,192 tokens.
  - Prices: image $0.00012 ($0.00006 batch), video $0.00079 per frame, text $0.20/MTok.
  - Released 2026-04-22, no shutdown date. The Vertex lifecycle page also gives no retirement date.
- **Flash-Lite prices:** `gemini-3.1-flash-lite` $0.25 / $1.50 and `gemini-3.5-flash-lite` $0.30 / $2.50 per MTok.
- **Firestore:**
  - Vector values are "8 bytes per dimension".
  - "The index type must be flat"; at most 2048 dimensions.
  - "1000 (Standard edition limitation only)"; "Only the Python, Node.js, Go, and Java client libraries support vector search".
  - kNN billing is one read per ≤100 index entries, and the 1550 → 16 + 5 example matches.
  - us-central1 reads cost $0.03 per 100k and stored data $0.000205479 per GiB in the hourly view (≈ $0.15/GiB-month).
  - The storage table (3.8 / 5.7 / 7.6 / 8.6 GiB), $0.86/month, 10,000 reads ≈ $0.003, and $3,000 per 1 M queries all re-check.
- **Cloud Run:** request-based Tier 1 (europe-west1) active CPU $0.000024/vCPU-s and memory $0.0000025/GiB-s, so 4 vCPU / 8 GiB = $0.000116/s. The local column re-checks: 91.8 ms × K × $0.000116. One cold start, 12 s ≈ $0.0014 ≈ 10 warm videos.
- **Haiku 5.5:** 360×640 = 13 × 23 = 299 tokens and 720×1280 = 26 × 46 = 1196 tokens. Every Haiku cell re-checks at K = 8/13/31.
- **Licences (HF API):**
  - EVA02-B merged2b: MIT.
  - SigLIP v1 so400m: Apache-2.0.
  - SigLIP 2 NaFlex B and `timm` SigLIP 2 B-16 / B-32-256: Apache-2.0.
  - PE-Core B and S: Apache-2.0.
  - DataComp B-32: MIT.
  - VideoPrism LvT: Apache-2.0.
  - OpenAI CLIP-L: no tag; the card quote is verbatim.
- **open_clip v3.3.0 tag:** contains `ViT-B-16-SigLIP2`, `ViT-B-32-SigLIP2-256`, `ViT-B-16-SigLIP2-384`, `ViT-SO400M-16-SigLIP2-256`, `PE-Core-B-16`, `PE-Core-S-16-384` and `ViT-SO400M-14-SigLIP2-378`. It has no NaFlex config; `main` has `ViT-B-16-SigLIP2-naflex.json`.
- **transformers:** tag `v4.49.0-SigLIP-2` exists. v4.50.0 was published 2025-03-21 and its notes mention SigLIP-2. PyPI's latest is 5.19.0 (2026-10-06).
- **SigLIP 2 paper §3.1.1:** "On benchmarks predominantly based on natural images, the standard B-sized variant outperforms NaFlex", while for So400m the two are "on par". Table 1: B/32-256 74.0, B/16-384 80.6, So400m/16-256 83.4.
- **Taxonomy example:** it validates against its own rule table. Ids match the pattern, both `parent`s resolve, each template has one `{}`, both calibrated labels exist, and 0.31 ≥ 0.21 in the response example. No over-engineered feature remains; everything from r1 #22 sits in §6.3.
- **Timing method:** it is adequate for indicative numbers (warm-up, 7 repeats, median, two rounds, load stated, decode, preprocessing and cold start separated). The r0 single-run rows (B-32, L-16) are labelled as such.
- **U3:** nothing recommended carries an EU territorial clause. SigLIP 2, PE-Core, EVA02 and DataComp weights are Apache or MIT; e5 and bge-m3 are MIT. Hosted options: Haiku, Gemini API / Vertex, Cloud Vision. The Llama-based items (PLM) are not recommended (finding 22).
