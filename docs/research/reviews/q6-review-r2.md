# Review r2 (final round): q6-translation.md

Reviewer: fresh review agent. I did not write the file and did not review it in round 1. Every source below was re-opened on 2026-10-08. The reviewed file was not edited.

Severity counts: wrong 1 · unsupported 0 · missing option 1 · minor 9 (11 findings in total).

## Round-1 resolution check

All 18 round-1 findings are resolved correctly. I checked each fix against its source:

- **#1:** The Papi et al. attribution and the "could be a sub-optimal solution" quote are correct.
- **#2–#7:** The Haiku 5.5 facts in S27/S28/S29 match the pages (ID, dates, tiers, tokenizer, thinking and sampling). The arithmetic is re-derived below and is correct.
- **#8:** The Gemma Terms point is correct: last modified 2026-04-01, no non-commercial clause, §3.1/§3.2, TranslateGemma in the Appendix, Gemma 4 excluded.
- **#9–#10:** The Gemma 4 sizes, audio limits, CoVoST figure and context lengths are correct.
- **#11:** The Canary-1b-v2 facts are correct.
- **#12:** The Hunyuan-MT-7B territory and MAU facts are correct.
- **#13:** The Seed-X card facts are correct.
- **#14:** The DeepL and Google figures are correct, though the sourcing can now be improved (findings 5 and 6).
- **#15–#18:** Correct.

The resolution note on #16 (Opus-MT *links* separate OPUS-100 models) is consistent with round 1's own wording.

## Arithmetic re-done

| Step | Doc | Re-computed |
|---|---|---|
| Haiku 5.5 tokens/h | 16,200 | 9,000 / 0.555 = 16,216 ✓ |
| Haiku 5.5 input | 48,600 → $0.0049 | 16,200 × 3 = 48,600; × $0.10/M = $0.00486 ✓ |
| Haiku 5.5 output | 19,400–58,300 → $0.0097–0.0292 | 19,440–58,320; × $0.50/M = $0.00972–0.02916 ✓ |
| Haiku 5.5 total | $0.015–0.034 | $0.01458–0.03402 ✓ |
| Haiku 4.5 total | $0.11–0.25 | $0.036 + $0.072–0.216 = $0.108–0.252 ✓ |
| Thinking ×2 upper | $0.063 | 0.00486 + 2 × 0.02916 = $0.0632 ✓ |
| 100k tier | ~2 h; 5× | 100,000 / 48,600 = 2.06 h; $0.50/$0.10 = $2.50/$0.50 = 5× ✓ |
| Google NMT / LLM / DeepL | $1.08 / $1.08 / $1.49 | 54k × $20/M = $1.08; 54k × ($10 + $10)/M = $1.08; 54k × $27.50/M = $1.485 ✓ |
| Per 3-min video | $0.0017 / $0.013 | 0.034 / 20 = $0.0017; 0.252 / 20 = $0.0126 ✓ |
| API vs Haiku 5.5 multiple | "about 30–70×" | **32–99×** (see finding 1) |

## Findings

1. **The "30–70×" multiple is understated.** The DeepL/Google row says "**Deferred:** about 30–70× Haiku 5.5's cost".
   → Recomputed from the doc's own figures. Character APIs cost $1.08–1.49 per hour and Haiku 5.5 costs $0.015–0.034 per hour. The extremes are 1.08 / 0.034 = 32× and 1.49 / 0.015 = 99×. The "70×" appears to be Google only (1.08 / 0.015 = 72×). DeepL alone is 44–99×.
   → **wrong** (low impact; the conclusion stands)
   → Correction: "about 30–100× Haiku 5.5's cost".

2. **The OpenMDW licence text is readable, so open question 3 and the "once its licence is checked" hedge can be closed.** The doc says "Licence text not read (open question)" (Seed-X row). Open question 3 says "openmdw.ai/license, not read". The summary says "Seed-X once its licence is checked".
   → The Seed-X repo's own LICENSE (https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B/raw/main/LICENSE, read 2026-10-08) is **OpenMDW-1.0**. The openmdw.ai/license index lists 1.0 and 1.1 (1.1 updated 2026-05-27). The 1.0 text contains:
   - "permission is hereby granted, free of charge, to deal in the Model Materials without restriction, including under all copyright, patent, database, and trade secret rights".
   - A redistribution condition: "retain in your distribution (1) a copy of this agreement, and (2) all copyright notices and other notices of origin". So the agreement must be shipped too, not only the notices.
   - Patent termination on bringing a patent suit.
   - "does not impose any restrictions or obligations with respect to any use, modification, or sharing of any outputs".
   - An AS-IS disclaimer, and "YOU ARE SOLELY RESPONSIBLE FOR (1) CLEARING RIGHTS OF OTHER PERSONS…".
   - No AUP and no field-of-use limit.
   → **minor** (an open question that can now be answered)
   → Correction: state that Seed-X ships under OpenMDW-1.0, which is MIT-like: commercial use is allowed, and the obligations are to keep the licence copy and notices on redistribution, plus patent termination. The user carries the rights-clearance burden. Close open question 3 and drop "once its licence is checked" from the recommendation.

3. **Open question 6 (can thinking be disabled?) is answered in the docs.** The doc says: "Does it accept `thinking: {type: "disabled"}`? Not checked [S29]."
   → The Thinking page (https://platform.claude.com/docs/en/build-with-claude/thinking, read 2026-10-08) says: "Claude Haiku 5.5 also has thinking on by default and accepts `thinking: {type: "disabled"}` at effort `high` or below. At `xhigh` or `max` effort, that combination returns a 400 error." It also gives a caveat relevant to cue-ID JSON: "With thinking off, the model can skip a tool call it needs when you also request JSON output."
   → **minor**
   → Correction: answer that half of open question 6 and cite the Thinking page. Keep the half about real token counts per script. Note that the "without thinking" cost figures are directly achievable. Add the JSON-with-thinking-off caveat to the Notes.

4. **"Thinking is billed as output" is uncited.** Cost step 6 says "Thinking is billed as output", and the only citation in that step, [S27], is for Batch.
   → The pricing page (S27) does not say this. The Thinking page (same URL as finding 3) does: "the tokens Claude spends reasoning are billed as output tokens, even when the thinking text isn't returned to you, and they count toward `max_tokens`".
   → **minor**
   → Correction: add the Thinking page as a source and cite it in step 6.

5. **The Google pricing page can be read first-hand, so the S30 caveat is out of date.** S30 says "The page did not render via fetch… comes from a search excerpt". Open question 9 says the prices "need re-checking from first-party pages".
   → A plain HTTP GET of https://cloud.google.com/translate/pricing (2026-10-08) returns the full page. It shows:
   - NMT: "First 500,000 characters per month Free (applied as $10 credit every month)", then "$20.00" per million for 500k to 1B characters. The credit applies collectively to Basic and Advanced.
   - Translation LLM: "charged $10 per million characters input and $10 per million characters output, making it cost equivalent with NMT".
   - Adaptive translation (LLM): $25 + $25 per million characters.

   The pricing examples on the page confirm these figures. All of the doc's Google figures are correct. The $10 credit is listed under NMT only, so the LLM mode has no free tier.
   → **minor**
   → Correction: replace the S30 caveat with "read first-hand 2026-10-08". Add "no free tier on Translation LLM", and optionally the Adaptive $25 + $25 rate. Drop the Google part of open question 9's re-check.

6. **DeepL's figures are still secondary-only.** The doc says "DeepL Growth costs $32.50 a month for 1M characters, plus $27.50 per extra M [S31]".
   → I tried https://www.deepl.com/en/pro-api, /en/pricing and /en/pricing#api on 2026-10-08. They return only the Translator plans (€7.49 / €24.99 / €49.99). The API tab is rendered client-side, and the HTML holds only the plan names "Developer" and "Growth" with no prices. So I could not confirm the figure first-party. S31 (2026-06-03) matches the doc exactly. It adds a 50M-character monthly cap, €29.75 a month in Europe, a free "Developer" plan with a one-time 1M characters, and "API Free and API Pro plans have been discontinued for new signups as of mid-2026". A second secondary source, the flexprice.io pricing index (search excerpt, dated 2026-09-22), agrees: $32.50 monthly or $26.00 annual, $27.50 per extra M, and €22.00 per extra M in EUR.
   → Two side notes. The $32.50 includes 1M characters, which is about 18 video-hours at 54k characters per hour. Below that volume the marginal DeepL cost is $0 and the cost is the fixed fee. The $1.49 per hour is the overage rate.
   → **minor**
   → Correction: keep the secondary-source caveat. Add the second corroborating source, the Free/Pro discontinuation and the 1M-included note. Keep the DeepL half of open question 9 open.

7. **Hunyuan licence details are incomplete.** The doc says "Separate licence needed above 100M MAU [S24]".
   → The licence (https://huggingface.co/tencent/Hunyuan-MT-7B/raw/main/License.txt, read 2026-10-08) has two further points:
   - §4 counts MAU "on the … version release date" ("greater than 100 million monthly active users in the preceding calendar month"). It is a snapshot at release, not an ongoing threshold.
   - §5(b) forbids using "any Output or results of the Tencent Hunyuan Works to improve any other AI model".
   - The Exhibit A AUP (2024-11-05) can be updated by Tencent at will.

   None of this changes the verdict.
   → **minor**
   → Correction: add "MAU measured at release date. Outputs may not be used to improve other models. AUP updatable".

8. **Missing option, to be ruled out: Tencent HY-MT1.5 (1.8B and 7B, 2025-12-30).** The doc lists only Hunyuan-MT-7B.
   → https://huggingface.co/tencent/HY-MT1.5-1.8B/raw/main/License.txt (read 2026-10-08) is the "TENCENT HY COMMUNITY LICENSE AGREEMENT, Tencent HY-MT1.5 Release Date: December 30, 2025". It also says "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA", with the same 100M MAU clause. The search results and the HY-MT1.5 tech report (arXiv 2512.24092) describe 33 languages and a 1.8B model meant for edge deployment. It is newer and smaller than Hunyuan-MT-7B, and readers will ask about it.
   → **missing option**
   → Correction: add HY-MT1.5 1.8B/7B to the Hunyuan row as "same Tencent HY licence: EU/UK/KR excluded, not usable".

9. **The TranslateGemma terms include a remote-restriction right that open question 1 should name.** Open question 1 asks only whether the §3.1 pass-through and the Prohibited Use Policy are acceptable.
   → The Gemma Terms (https://ai.google.dev/gemma/terms, last modified 2026-04-01, read 2026-10-08) say in §3.2 that Google "reserves the right to restrict (remotely or otherwise) usage" of Gemma Services that it reasonably believes violate the Agreement. §4.5 allows termination for breach. §3.1 also requires giving recipients a copy of the Agreement and marking modified files, as well as the Notice text.
   → **minor**
   → Correction: add the remote-restriction clause and the copy/marking duties to open question 1.

10. **"Likely the strongest clean local candidate" (Seed-X) rests only on self-reported claims with no numbers.**
    → The Seed-X card (https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B, read 2026-10-08) gives no scores on the card. The numbers are in the tech report (arXiv 2507.13618). It claims "on par with or outperforming ultra-large models like Gemini-2.5, Claude-3.5, and GPT-4". The card also says:
    - the model "has no chat template";
    - it needs a target-language tag (e.g. `<de>`) at the end of the prompt;
    - it is not meant for other tasks;
    - the authors advise against unofficial quantised versions.

    That matters for the doc's cue-ID JSON plan ("Handles cue-ID JSON" is claimed for Qwen3, but Seed-X is a translation-only, single-turn model). The HF metadata also shows 8B params against the 7B in the name.
    → **minor**
    → Correction: soften "likely the strongest" to "strongest self-reported claims among clean candidates (unverified)". Add the usage constraints: no chat template, sentence or segment prompts, so cue-ID JSON is unlikely to round-trip.

11. **Characters and tokens are slightly inconsistent between the two cost methods.** The Haiku 4.5 path uses 12,000 tokens per hour, which at the pricing page's "1 token is approximately 4 characters" (S27 FAQ) is about 48k characters. The MT-API path assumes 54k characters per hour.
    → **minor** (about 12% gap, no effect on conclusions)
    → Correction: either state that the two conversions are independent rough assumptions, or use 54k / 4 = 13.5k tokens for Haiku 4.5.

## Verified as correct (new or changed claims)

- **Haiku 5.5 (S27, S28, S29):**
  - ID `claude-haiku-5-5`, released October 7, 2026.
  - $0.10 / $0.50 per MTok for prompts of 100k tokens or fewer, $0.50 / $2.50 over 100k, and Batch at 50% off.
  - "approximately 30% more tokens than on Claude Haiku 4.5", and "1M tokens is roughly 555k words" against 750k before.
  - Adaptive thinking is on by default, with default effort `medium`.
  - "Omit `temperature`, `top_p`, and `top_k`, since a non-default value for any of them returns a 400 error".
  - The pricing page says Haiku 5.5 is the exception to flat 1M pricing.
- **Haiku 4.5:** $1 / $5, and listed under "Legacy models (still available)".
- **Canary-1b-v2 (S23):** CC-BY-4.0, commercial and non-commercial use, about 978M parameters, released 2025-08-14. It covers 25 languages, En→24 and 24→En, with no X↔Y pairs. It "only supports segment level timestamps for translation". En→X FLEURS COMET is 84.56 and BLEU 29.4. Long audio is chunked automatically.
- **Gemma 4 E4B card (S19):**
  - Apache-2.0, with the sizes E2B, E4B, 12B, 26B A4B and 31B.
  - Audio on E2B, E4B and 12B only, with a "maximum length of 30 seconds" and "speech-to-translated-text translation across multiple languages".
  - CoVoST: E4B 35.54 (E2B 33.47, 12B 38.5). E4B is 4.5B effective, 8B with embeddings.
  - 128K context on E2B and E4B. 140+ pretrained and 35+ supported languages. No timestamps mentioned.
- **Seed-X (S25):** OpenMDW, 28 languages, paper dated 2025-07-18, and the FLORES-200 / WMT-25 claims as quoted.
- **OpenMDW (S26):** The LF post dated 2025-07-02 says "for any purpose", royalty-free, and notices on redistribution of the Model Materials only.
- **Hunyuan-MT-7B (S24):** The territory wording is exact. The release date is 2025-09-01 and the 100M MAU figure is correct.
- **Determinism note:** `temperature: 0` is non-default, so it returns a 400 error. The Thinking page also says this applies "regardless of whether thinking is used".
- **TranslateGemma (S15, S16):** Gemma licence, 5B badge on the 4B model, 55 languages, "Total input context of 2K tokens", and WMT24++ MetricX/COMET exact. The tech report is dated 2026-01-13.
- **Omnilingual MT:** Still no weights or licence found (search 2026-10-08). arXiv is at v3, 2026-05-07, and the abstract does not name the LLaMA 3 base, so "unverified" remains the right label.
