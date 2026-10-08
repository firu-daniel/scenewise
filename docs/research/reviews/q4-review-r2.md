# Review r2 (final round): q4-moderation.md

Reviewer: a fresh review agent that did not write or previously review the file. All sources were re-opened on 2026-10-08. The reviewed file was not edited. This was desk research only: no dataset, image or weights were downloaded or viewed, and nothing that could be CSAM came up.

Settled user decision used as the yardstick: **scenewise stays a complement / second opinion. Expause moves its primary signal to Gemini or Cloud Vision, and scenewise does not become primary.**

Severity counts: wrong 4 · unsupported 1 · missing option 1 · minor 5 (11 findings in total).

## Findings

1. **The file still leaves the stance open.**
   - Claims:
     - L37: "Whether scenewise's 'complement, never replace' stance changes is the user's decision. It is not decided here."
     - L53: "If the stance stays 'complement, never replace' …"
     - L245 (open question 1): "Does the 'complement, never replace' stance stay?"
     - L285: "The stance itself is left to the user."
     - L264–266 (resolution of r1 items 2 and 3) describe OpenAI as "a case-(b) option".
   - Source: the user decision (settled). scenewise stays a complement, and the primary moves to Gemini or Cloud Vision.
   - **Severity: wrong** (contradicts the settled decision).
   - Correction:
     - Replace L37 with "Decided: scenewise stays a second opinion in both cases; only the primary it is compared against changes."
     - Make L53 unconditional.
     - Reduce open question 1 to "Which primary: Cloud Vision SafeSearch or Gemini?"
     - Change L285 to record the decision.

2. **The file still offers a route for scenewise to become primary.**
   - Claims:
     - L49: the case-(b) table has a candidate row "scenewise local tiers as primary".
     - L54: "If the user allows scenewise to become primary: only after shadow-mode evaluation …".
     - L202: a primary mode "is not offered unless the user changes the decided stance (case b)".
     - L241: "(or any primary role, if the user ever allows one)".
     - L50 / L87: OpenAI omni-moderation is listed as a candidate *primary*, but the decision names only Gemini or Cloud Vision.
   - Source: the user decision (settled).
   - **Severity: wrong.**
   - Correction:
     - Delete the L49 row and the L54 bullet.
     - At L202, say "a primary mode is not offered".
     - Drop the parenthesis at L241.
     - Move OpenAI out of the case-(b) primary table. It may stay as an optional scenewise tier-2 / third opinion.

3. **ShieldGemma 2 is said to be "best among the models in its own Table 2" (L15, L73; this was the r1 #6 fix).**
   - Source: SG2 report, arXiv 2504.01081 Table 2 (https://arxiv.org/html/2504.01081, read 2026-10-08). Danger 1−FPR is SG2 **88.7**, GPT-4o mini **92.3** and Gemma 3 **93.8**. SG2 is best only on Sexual F1 (64.2 vs 57.1, 50.4, 42.1, 37.8) and on Violence 1−FPR (95.9 vs 62.5, 57.3, 40.1, 13.0).
   - **Severity: wrong.**
   - Correction: "best on sexual F1 and violence 1−FPR in its own Table 2; on danger 1−FPR, GPT-4o mini (92.3) and Gemma 3 (93.8) are ahead". Also note that 1−FPR measures only false positives, not recall.

4. **Gemini 2.5 Flash-Lite is presented as the cheap Gemini option (L48, L86: "≈ $0.00004–0.00017 per frame on Gemini 2.5 Flash-Lite"; "recommends Gemini 2.5 Flash-Lite for low-cost filtering").**
   - Sources:
     - Vertex AI model versions page (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, updated 2026-10-07): `gemini-2.5-flash-lite` has a **retirement date of October 20, 2026**. The recommended replacements are gemini-3.8-flash, gemini-3.1-flash-lite or Gemma 4.
     - Gemini API deprecations page (https://ai.google.dev/gemini-api/docs/deprecations, updated 2026-10-07): no shutdown date is set, but "access is limited to users who have used them before. New projects are directed to newer models."
     - The S42 quote ("Gemini 2.5 Flash-Lite is recommended…") is verbatim but stale against these pages.
   - **Severity: wrong** (the low end of the Gemini cost range rests on a model that Expause, a Google Cloud user, cannot adopt for a 2027 migration).
   - Correction: drop 2.5 Flash-Lite as a candidate. Base the low end on Gemini 3.1 Flash-Lite ($0.25 / $1.50 per MTok, Gemini API pricing page, updated 2026-10-07). Note that 2.5 Flash-Lite retires on Vertex on 2026-10-20.

5. **Gemini 3.5 Flash-Lite per-frame cost uses the 258-token tiling rule (L48: "≈ $0.00018–0.00056 … tile count for 432×768 is uncertain (2–6 tiles)").**
   - Sources:
     - Gemini media resolution page (https://ai.google.dev/gemini-api/docs/media-resolution, updated 2026-09-23). Its table is headed "Gemini 3 models": `low` 280, `medium` 560, `high` 1120, default (`unspecified`) **1120 tokens per image**, `ultra_high` 2240. The page notes that counts "vary significantly between Gemini 3 and earlier Gemini models".
     - The tiling rule (https://ai.google.dev/gemini-api/docs/image-understanding) is the older scheme. Under it, 432×768 gives crop unit 288 → 2×3 = 6 tiles = 1,548 tokens.
   - Recomputed, with 40 output tokens:
     - Gemini 3.5 Flash-Lite ($0.30 / $2.50): low 280 tokens ≈ **$0.00018**; default 1120 tokens ≈ **$0.00044**.
     - Gemini 3.1 Flash-Lite ($0.25 / $1.50): ≈ **$0.00013** (low) to **$0.00034** (default).
     - Google search snippets (secondary) say 3.5 Flash-Lite defaults to `MINIMAL` thinking. Any thinking tokens bill as output.
   - **Severity: unsupported** (the range happens to bracket the right numbers, but the method does not apply to Gemini 3.x).
   - Correction: cost Gemini 3.x by `media_resolution` (≈ $0.00013–0.00044 per frame across 3.1 and 3.5 Flash-Lite at low to default). Recommend `media_resolution: low` for evaluation. Note the thinking level.

6. **Arithmetic: the Gemini 2.5 Flash-Lite range "$0.00004–0.00017" is inconsistent with the stated "2–6 tiles".**
   - 2 tiles = 516 tokens → $0.0000516 + 40 × $0.40/MTok ($0.000016) = **$0.000068**. 6 tiles = 1,548 → **$0.000171**. The $0.00004 lower bound corresponds to a single 258-token image, which applies only if both sides are ≤ 384 px. 432×768 is not.
   - The same inconsistency affects the 3.5 lower bound under the old rule: 1 tile gives $0.000177, 2 tiles give $0.000255.
   - **Severity: minor** (largely superseded by findings 4 and 5).
   - Correction: $0.00007–0.00017 if 2.5 is kept at all.

7. **Missing option: NVIDIA Nemotron 3.5 Content Safety (4B), a multimodal guard with custom policies.**
   - Sources:
     - The Shieldstral card the file cites as [S12] (https://huggingface.co/mistralai/Shieldstral-1.0-3B, read 2026-10-08) benchmarks "Nemotron-3.5-Safety-4B" (VLGuard 84.2, UnsafeBench 67.7, LlavaGuard 70.0) and "OmniGuard-7B" (88.5 / 72.6 / 71.7). Both score above ShieldGemma 2 (61.3 / 54.9 / 56.2) in that table.
     - HF card nvidia/nemotron-3.5-content-safety (found via search, 2026-10-08): Gemma-3-4B LoRA fine-tune, SigLIP encoder, a single image plus custom policies, "ready for commercial use". The licence is named inconsistently: OpenMDW 1.1 + Gemma Terms on HF, "NVIDIA Nemotron Open Model License" + Gemma on NGC.
   - **Severity: missing option.**
   - Correction: add a survey row as a tier-2 candidate alongside SG2 and Shieldstral, flagging that the licence name is unresolved. Add OmniGuard-7B to the "other leads" line. The Shieldstral table also gives LlavaGuard-7B UnsafeBench 63.9 in Mistral's setup, which could sit next to the SG2-report 42.1.

8. **Server-side fallbacks "silently" re-run a refused request (L110).**
   - Source: Refusals and fallback (https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback, read 2026-10-08): "Fallbacks are visible either way: the response names the model that served it, and the `fallback` content block marks the handoff." In `"default"` mode, "For categories with no recommended fallback, the refusal stands."
   - **Severity: minor.** The recommendation not to enable `fallbacks` still holds, because a client that reads only the verdict loses the refusal signal. The other parts of the r1 #14 fix check out verbatim:
     - pre-output billing applies only to `bio` / `frontier_llm` / `reasoning_extraction`;
     - the mid-stream billing sentence;
     - batch refusals come back as `succeeded` + `stop_reason`;
     - `fallbacks` in a batch gives an errored item;
     - "A Claude Haiku 5.5 refusal carries no fallback credit".
   - Correction: replace "silently" with "re-runs on another model; the swap is marked in the response but easily missed by a verdict-only parser".

9. **"Free with Label Detection" (L47, L85).**
   - Source: Vision pricing (https://cloud.google.com/vision/pricing, read 2026-10-08). The table shows "Free with Label Detection, or $1.50" for 1,001–5M and "…or $0.60" above 5M; the first 1,000 are free. The page does not define the note and shows no date. The deprecations page (updated 2026-10-07) lists only Celebrity Recognition and OCR On-Prem. The SafeSearch page (updated 2026-10-07) lists the five categories, has no banner, and its sample uses UNKNOWN…VERY_LIKELY. All of this is consistent with the file.
   - **Severity: minor.** The file's reading of the note is an inference, not stated by Google.
   - Correction: add "(meaning not defined on the page; confirm on the SKU page)".

10. **EU / EEA terms for Gemini are not mentioned.**
    - Source: Gemini API Additional Terms (https://ai.google.dev/gemini-api/terms, read 2026-10-08): "You may use only Paid Services when making API Clients available to users in the European Economic Area" (Switzerland and the UK likewise). Paid-service data terms say prompts are not used for training and "Google logs prompts and responses for a limited period of time" for abuse monitoring.
    - **Severity: minor.** This is not a territorial ban: the file already uses paid prices, and no recommended item carries an EU restriction. Llama Guard 4, the only item with an EU clause, remains rejected, and the L75 quote of the Llama 4 AUP is verbatim (USE_POLICY.md, read 2026-10-08).
    - Correction: note in open question 5 that EEA use must be paid tier, and that prompts are logged for a limited period. This partly answers the retention question for Gemini (Gemini API; Vertex terms are separate).

11. **Haiku 4.5 cost rows include 200 thinking tokens.**
    - Source: Haiku 5.5 overview (https://platform.claude.com/docs/en/models/haiku-5-5/overview, read 2026-10-08): adaptive thinking on by default, effort `medium`. That applies to Haiku 5.5. Haiku 4.5 uses manual extended thinking, which is off unless requested.
    - **Severity: minor.** The effect is about +$0.001 per video on Haiku 4.5 rows.
    - Correction: state that the 4.5 rows assume thinking enabled, or drop the 200 tokens for 4.5.

## Round-1 resolutions: verification

- **#1 SafeSearch:** correct, apart from the minor note in finding 9.
- **#2 OpenAI:** quotes verbatim. Free; 20 MB; six image categories; `sexual/minors` text-only; both CSAM sentences; no restriction to OpenAI I/O; no retention statement on the page. Correct, but its placement as a candidate primary conflicts with the decision (finding 2).
- **#3 Gemini:** S42 quotes verbatim (safety filters off; "shouldn't be used for detecting … CSAM"; `PROHIBITED_CONTENT`; page updated 2026-10-07). Cost basis and model choice are flawed (findings 4–6).
- **#4:** acceptable.
- **#5:** correct. The card says "continuous confidence score", threshold 0.5, and never uses the word "calibrated".
- **#6:** the fix introduced an error (finding 3). The Mistral-setup SG2 UnsafeBench 54.9 is confirmed.
- **#7:** correct ("curate their own bespoke policy" is verbatim).
- **#8:** correct. LlavaGuard-7B scores 81.4 vs Shieldstral 72.0, and the note on unavailable images is confirmed.
- **#9:** correct. The quote is verbatim, including the end-user exception.
- **#10:** correct. The API shows `gated: "auto"`, lastModified 2026-03-05T04:15:56Z, and no licence tag; the gating prompt reads "Data Use Agreement (DUA)".
- **#11:** correct. Table 3 gives NudeNet Sexual F1 0.624 / 0.650 / 0.596.
- **#12:** correct.
  - Haiku 5.5 costs $0.10 / $0.50 for prompts ≤ 100,000 tokens and $0.50 / $2.50 above. The tier also applies to cache and batch prices.
  - Image limits: 100 per request for 200k-context models and 600 for all others; the 2000 px rule applies above 20 images.
  - About 220 frames at 448 tokens fit under 100k.
- **#13:** correct (post-4.7 tokenizer statement verified).
- **#14:** correct apart from finding 8.
- **#15:** correct (≈30% more text tokens; image tokens follow the patch formula).
- **#16:** arithmetic re-done and correct:
  - 3 frames: (1,050 + 1,344) × $0.10/MTok + 320 × $0.50/MTok = $0.00040.
  - 10 frames: $0.00085.
  - Haiku 4.5: 3 frames $0.0037, 10 frames $0.0083.
  - 60 frames on Haiku 5.5: $0.0041.
- **#17:** correct.
- **#18:** correct.

LlavaGuard figures re-checked in SG2 Table 2: sexual F1 42.1 and violence 1−FPR 40.1 (with "Our Policy"; it scores 37.8 / 13.0 with its original policy). They are correct as cited.
