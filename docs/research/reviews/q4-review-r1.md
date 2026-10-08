# Review r1: q4-moderation.md

Reviewer: fresh review agent (did not write the file). Every source below was re-opened on 2026-10-08 unless noted. The reviewed file was not edited. Desk research only: no dataset, image or weights were downloaded or viewed, and nothing that could be CSAM was encountered.

Severity counts: wrong 0 · unsupported 3 · missing option 4 · minor 11 (18 findings in total).

**Headline:** the Video Intelligence deprecation is **confirmed** on Google's own pages (https://docs.cloud.google.com/video-intelligence/docs/deprecations, "Last updated 2026-10-07 UTC"; the same banner appears on the `videos.annotate`, `Likelihood` and `analyze-safesearch` pages). The cost arithmetic re-checks correctly. The main gaps are missed hosted options (above all Google Cloud Vision SafeSearch) and one unsupported "calibrated" claim.

## Findings

1. **Missed option: Google Cloud Vision SafeSearch.** The doc does not mention it.
   → https://docs.cloud.google.com/vision/docs/detecting-safe-search (read 2026-10-08, "Last updated 2026-10-07 UTC") says "This feature uses five categories (`adult`, `spoof`, `medical`, `violence`, and `racy`)", each returned as a likelihood with the same VERY_UNLIKELY…VERY_LIKELY buckets (plus UNKNOWN). That page carries no deprecation banner. Pricing (https://cloud.google.com/vision/pricing, read 2026-10-08): first 1,000 units/month free, then $1.50 per 1,000 (1,001–5M) and $0.60 per 1,000 above 5M, and it is "Free with Label Detection".
   → **missing option** (high relevance)
   → Fix: add it to the survey and the open questions. It is a per-frame image API in the same Likelihood vocabulary, it covers **violence** and **racy** (which Video Intelligence does not), it is not part of the Video Intelligence deprecation, and Expause already runs on Google Cloud. It matters both as a cheap hosted second opinion and as a candidate primary signal after 2027-09-14 (open question 1). Note that it would be a Google model seconding a Google model, so errors may be correlated.

2. **Missed option: OpenAI `omni-moderation-latest` (free, accepts images).** Open question 13 lists free hosted endpoints as "not checked".
   → https://developers.openai.com/api/docs/guides/moderation (read 2026-10-08): "The moderation endpoint is free to use, and image files can be up to 20 MB". `omni-moderation-latest` "accepts text and image inputs". The image-capable categories are `sexual`, `violence`, `violence/graphic`, `self-harm`, `self-harm/intent` and `self-harm/instructions`. `sexual/minors` is **text only**. The page says: "Do not send known or suspected child sexual abuse material (CSAM) to the Moderation API." It does not restrict use to moderating OpenAI model I/O.
   → **missing option**
   → Fix: add it as a zero-cost hosted tier-2 or third opinion. It returns per-category scores, which fit the bucketing table. Flag that it sends frames to a third party (same CSAM pre-routing constraint as Claude), and that it does not cover weapons.

3. **Missed option: Gemini, which is Google's own named migration path.** The doc quotes "Google recommends migrating to Gemini" but does not evaluate Gemini as a moderation option or compare its cost with Haiku.
   → Deprecation banner (URL in the headline): "We recommend migrating to Gemini family of models."
   → **missing option**
   → Fix: add a short note to open question 1. Expause's likely post-2027 path is whatever Google recommends, so scenewise's bucketing and combination rules should be designed to work against a Gemini-based or SafeSearch-based primary signal too, not only `pornographyLikelihood`.

4. **Missed options: paid commercial APIs (AWS Rekognition `DetectModerationLabels`, Azure AI Content Safety, Hive, Sightengine).** These are not mentioned, even as rejected.
   → https://docs.aws.amazon.com/rekognition/latest/dg/moderation.html (read 2026-10-08) documents image and stored-video moderation with a downloadable label taxonomy and custom adapters. Azure Content Safety has an F0 free tier and image analysis with severity levels (https://learn.microsoft.com/azure/ai-services/content-safety/overview; I did not verify the F0 image quotas).
   → **missing option** (low priority, given the "local free or cheap hosted" brief)
   → Fix: add one line saying these were considered and set aside, with the reason (cost, another vendor, data leaves the infrastructure).

5. **"Calibrated" score for Shieldstral.** Summary item 2 says "a promptable guard model that returns a calibrated yes/no probability". The table says "softmax over yes/no logits, giving a calibrated score [S12][S13]".
   → https://huggingface.co/mistralai/Shieldstral-1.0-3B (read 2026-10-08) says it emits a single yes/no token, and a continuous score comes from renormalising the yes and no probabilities, with a default threshold of 0.5. The card does **not** say the score is calibrated. The announcement (https://mistral.ai/news/shieldstral/) does not say so either.
   → **unsupported**
   → Fix: change "calibrated" to "continuous (renormalised P(yes))". Note that calibration has to be measured on the eval set. The same applies to ShieldGemma 2's P(Yes).

6. **ShieldGemma 2 "best published numbers on a relabelled UnsafeBench subset".**
   → The SG2 report (https://arxiv.org/html/2504.01081, Table 2) does show SG2 ahead of LlavaGuard, GPT-4o mini and Gemma 3 on its relabelled UnsafeBench (sexual F1 64.2; violence 1−FPR 95.9). But the Shieldstral card reports **UnsafeBench F1 81.8**, which the doc also cites. The two setups differ (a relabelled subset with per-policy metrics, against Mistral's own overall F1), so "best published" is ambiguous and reads as contradicting the Shieldstral row.
   → **unsupported** (as worded)
   → Fix: say "best among the models compared in its own report". Add that the SG2 and Shieldstral UnsafeBench figures are not comparable.

7. **ShieldGemma 2 policy wording is inconsistent.** The summary says "three fixed policies". The table says "Custom policies supported [S15]".
   → The SG2 report says users can "curate their own bespoke policy", but the model is "not specifically fine-tuned for policies other than sexual, danger and violence". The HF card (https://huggingface.co/google/shieldgemma-2-4b-it) lists only the three.
   → **minor**
   → Fix: "three trained policies; custom policy text accepted but untrained."

8. **Shieldstral benchmark row omits a result in which it loses.** The doc gives "LlavaGuard 72.0" as a Shieldstral score.
   → The card's multimodal table shows LlavaGuard-7B at **81.4** on the LlavaGuard benchmark, ahead of Shieldstral's 72.0. VLGuard 97.7 and UnsafeBench 81.8 are correct.
   → **minor**
   → Fix: add "(LlavaGuard-7B scores 81.4 on its own benchmark)", so the vendor table is not read as a clean sweep.

9. **The Llama 4 EU clause is paraphrased too broadly.** The doc says "Llama 4 multimodal rights are not granted to EU-domiciled companies".
   → https://raw.githubusercontent.com/meta-llama/llama-models/main/models/llama4/USE_POLICY.md (read 2026-10-08): rights are withheld from "an individual domiciled in, or a company with a principal place of business in, the European Union", and "This restriction does not apply to end users of a product or service that incorporates any such multimodal models."
   → **minor**
   → Fix: quote "principal place of business in the EU" and the end-user exception. The test is where the operator of scenewise (Expause, or a self-hoster) has its principal place of business.

10. **UnsafeBench gating is described as "manual approval of 1–2 days".**
    → The card (https://huggingface.co/datasets/yiting/UnsafeBench) says "Our team may take 1-2 days to process your request", but the HF API (https://huggingface.co/api/datasets/yiting/UnsafeBench) reports `gated: "auto"`. Neither the API nor the card metadata has a licence tag; the gating prompt calls the terms a "Data Use Agreement". The card text "research/education purposes and responsible commercial use" is confirmed. A secondary search summary described the dataset as "research purposes only", which may reflect an older card version (lastModified 2026-03-05).
    → **minor**
    → Fix: say "gated (HF flag: auto; card says 1–2 days)". Record the card's lastModified date so a later change of terms can be detected.

11. **NudeNet "None published" omits UnsafeBench's number.**
    → The UnsafeBench paper (https://arxiv.org/html/2405.03486v3) evaluates NudeNet as one of five conventional classifiers, with an overall **Sexual F1 of 0.624**.
    → **minor**
    → Fix: add the figure. It is useful context next to SG2's 64.2, with the caveat that the two use different label sets.

12. **The cost table does not warn about the 100k-token price tier or image-count limits.**
    → Pricing (https://platform.claude.com/docs/en/about-claude/pricing, read 2026-10-08): Haiku 5.5 costs $0.10/$0.50 for prompts up to 100,000 tokens and **$0.50/$2.50 above**. Vision (https://platform.claude.com/docs/en/build-with-claude/vision): 600 images per request for models other than 200k-context ones, and **100 per request for 200k-context models**. Haiku 4.5 is a 200k-context model.
    → At 448 tokens per frame, the 5× tier starts at about 220 frames in one request. That is not reached in the doc's scenarios, but it would be by a "one request per video" design on longer videos.
    → **minor**
    → Fix: add "keep each request under 100k tokens (about 200 frames at 432×768); Haiku 4.5 is capped at 100 images per request". Replace "on 1M-context models" with the docs' wording.

13. **Haiku 5.5 resolution tier is marked as not stated.**
    → The vision docs put "Claude 4.7 and later models" in the high-resolution tier. The Haiku 5.5 overview (https://platform.claude.com/docs/en/models/haiku-5-5/overview) says it "uses the same newer tokenizer as Claude 4.7 and later models", and the pricing page groups models the same way. The tier is not stated for Haiku 5.5 by name, so the open question is fair, but the likely reading is high-res.
    → **minor**
    → Fix: say "probably high-res (it is a post-4.7 model); irrelevant at ≤1568 px".

14. **The refusal billing summary is incomplete.**
    → https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback (read 2026-10-08) confirms that a pre-output refusal is unbilled unless its category is `bio`, `frontier_llm` or `reasoning_extraction`. It also says: "A mid-stream refusal bills the input tokens and the output already streamed". Server-side `fallbacks` (beta) can re-run a refused request on **another model**. Batch refusals come back as `succeeded` with `stop_reason: "refusal"`. "A Claude Haiku 5.5 refusal carries no fallback credit." The categories are `cyber`, `bio`, `frontier_llm`, `reasoning_extraction`, `general_harms` or `null`.
    → **minor**
    → Fix: add mid-stream billing. Say scenewise must **not** enable `fallbacks`, or must record which model answered, so that a refusal is not silently replaced by a different model's verdict. For batch, detect refusals by `stop_reason`, not by `result.type`.

15. **The 800-token prompt estimate ignores Haiku 5.5's tokenizer.**
    → The Haiku 5.5 overview says text counts as about 30% more tokens than on Haiku 4.5. Image tokens follow the patch formula and are unaffected.
    → **minor** (negligible cost impact: about 240 extra tokens per request, under $0.00003)
    → Fix: note "~800 tokens on Haiku 4.5, ~1,050 on Haiku 5.5".

16. **The cost framing assumes 5-minute videos, but the consumer is a short-video app scanning preview thumbnails.**
    → The doc's own open question 11 asks whether Expause sends thumbnails or whole videos. The brief says Video Intelligence runs on preview thumbnails.
    → **minor**
    → Fix: add a row for "N preview thumbnails per video" (for example 3–10 frames, about $0.0003–0.0008 on Haiku 5.5), and restate the 5-minute figures as an upper bound.

17. **ShieldGemma 2 access is described as a "click-through".**
    → The HF API (https://huggingface.co/api/models/google/shieldgemma-2-4b-it) reports `gated: "manual"`. Llama Guard 4 is also `gated: "manual"`.
    → **minor**
    → Fix: say "gated (manual)". Add Llama Guard 4's gating for completeness.

18. **Yahoo weights licence for OpenNSFW2 is inferred, not stated.**
    → The `yahoo/open_nsfw` repo is BSD-2-Clause and **archived** (https://api.github.com/repos/yahoo/open_nsfw). The opennsfw2 README (https://github.com/bhky/opennsfw2) shows an MIT link and says the weights come from Yahoo. It does not say which licence covers the converted weights file it downloads.
    → **unsupported** (low impact)
    → Fix: say "weights are a conversion of Yahoo's BSD-2 release (inferred; the opennsfw2 README does not state it); the upstream repo is archived".

## Verified correct (brief)

- **Video Intelligence deprecation:** the quote is verbatim. Deprecated 2026-09-14, shutdown 2027-09-14, Gemini recommended. The deprecations page is dated 2026-10-07, and the banner also appears on the annotate, Likelihood and analyze-safesearch pages.
- **Explicit content scope:** the feature covers adult content only (nudity, sexual activity, pornography), visual only, per-frame; violence is not covered (analyze-safesearch, updated 2026-10-07).
- **`Likelihood` enum:** six values with one-word descriptions (page updated 2025-07-09).
- **`ExplicitContentAnnotation` and `ExplicitContentFrame`:** `{frames[], version}` and `{timeOffset, pornographyLikelihood}`.
- **`ExplicitContentDetectionConfig.model`:** `builtin/stable` (default) or `builtin/latest`.
- **Freepik:** MIT, 86,351,620 params, EVA-02 base 448, lastModified 2025-05-09, four levels. All benchmark numbers match, including the Falconsai and AdamCodd rows. 28 ms at batch 1 with PIL on an RTX 3090.
- **Marqo:** Apache-2.0, 5,597,762 params, ViT-tiny 384, 98.56% on a 20k test set, chart-only comparison, training data includes drawings and AI-generated images, lastModified 2024-11-27.
- **Falconsai:** Apache-2.0, 85.8M params, lastModified 2026-09-07, eval_accuracy 0.980375, about 80k proprietary images.
- **AdamCodd:** Apache-2.0, 86.1M params, 2024-12-03.
- **SigLIP 2:** Apache-2.0. Base is 375.2M params and so400m is 1.136B.
- **Shieldstral-1.0-3B:** exists, Apache-2.0, released 2026-08-04 (Mistral post), 3,849,090,048 params, Ministral-3-3B base with a Pixtral encoder, 16 GB VRAM, GGUF Q4_K_M/Q5_K_M/Q8_0, no CPU numbers, arXiv 2607.25857. The AI Weekly dates (2026-08-04, updated 2026-08-10) also match.
- **ShieldGemma 2:** Gemma licence, 4.30B params, lastModified 2025-04-04. Internal P/R/F1 matches (88.6 / 93.7 / 85.0). UnsafeBench sexual F1 64.2 and violence 1−FPR 95.9. LlavaGuard 42.1 / 40.1. Single image only; text-overlay harms out of scope.
- **Gemma Terms of Use:** last modified 2026-04-01; the use restrictions must be passed downstream (§3.1).
- **NudeNet:** PyPI 3.4.2 (2024-07-03, MIT classifier). GitHub reports AGPL-3.0. 18 classes, YOLOv8n 320 (default) and YOLOv8m 640, `{class, score, box}` output.
- **OpenNSFW2:** MIT, tag v0.19.0, pushed 2026-09-13, video frame interval and aggregation built in, no accuracy figures.
- **LAION CLIP-based-NSFW-Detector:** README says MIT, GitHub API says NOASSERTION, pushed 2023-05-30, score 0–1, test set linked, no figures.
- **Q16:** MIT badge only, FAccT 2022, CLIP ViT-L/14, UnsafeBench Hate F1 0.533.
- **Image-Guard-2.0:** Apache-2.0 tag, 92.9M params, 14 downloads, 2025-10-14.
- **GuardReasoner-VL-3B:** Apache-2.0, 4.07B params, 2025-06-09.
- **Llama Guard 4:** 12.0B params, lastModified 2025-04-29, S1–S14 list. Single-image R 41% / FPR 9% / F1 38%, multi-image F1 52%. Licence effective 2025-04-05, with the 700M MAU clause and "Built with Llama" attribution.
- **LlavaGuard v1.2:** no weights licence on either card. 0.89B and 8.03B params. O1–O9 categories and `{rating, category, rationale}` output. Repo Apache-2.0.
- **Anthropic AUP:** effective 2025-09-15. The sexual-content bullets are quoted correctly (all generation-type). The under-18 definition and CSAM reporting sentence are correct, as is the government-censorship bullet. The high-risk list does not include moderation.
- **Content moderation guide:** the multimodal sentence, the Haiku 5.5 cost suggestion and the "adult website … still flags explicit content" note are all correct.
- **Vision docs:** the "does not process inappropriate or explicit images" line is correct. So are the `⌈w/28⌉×⌈h/28⌉` formula, the tiers (2576 px/4784 tokens; 1568 px/1568 tokens), 1000×1000 = 1296 tokens at about $1.30 per thousand on Haiku 4.5, and the 2000 px limit above 20 images.
- **Image tokens:** 432×768 is 16×28 = 448 (old formula 442.4). 288×512 is 11×19 = 209 (old formula 196.6).
- **Pricing:** Haiku 5.5 costs $0.10/$0.50 at 100k tokens or less, with cache reads at $0.01 (0.1×). Haiku 4.5 costs $1/$5. Batch is 50% off. Haiku 5.5 was released 2026-10-07 as `claude-haiku-5-5`, with adaptive thinking on by default (default effort `medium`).
- **Cost arithmetic:** re-done and correct.
  - 60 frames: 27,680 input tokens. Haiku 5.5 costs $0.0028 in + about $0.0012–0.0015 out ≈ $0.004. Haiku 4.5 costs $0.0277 + $0.012–0.015 ≈ $0.040–0.043.
  - 30 frames: 14,240 input tokens. About $0.002 on Haiku 5.5 and $0.020–0.022 on Haiku 4.5.
  - 10 frames: 5,280 input tokens. About $0.0008 on Haiku 5.5 and $0.0073–0.008 on Haiku 4.5.
- **Refusals:** HTTP 200 with `stop_reason: "refusal"`; `stop_details.category` may be null; billing exceptions are `bio`, `frontier_llm` and `reasoning_extraction`; Haiku 5.5 is listed among the classifier models.
- **CSAM help article:** dated 2026-03-16. Perceptual hash against NCMEC, report, notice to the user or organisation, "first-party services", API not named.
- **UnsafeBench:** 10,146 images (6,098 safe, 4,048 unsafe), 11 categories, LAION-5B and Lexica sources, GPT-4V best overall, ethics statement says no CSAM. Published at CCS 2025 (DOI 10.1145/3719027.3765088, via CISPA and search).
- **Re-LAION-5B:** 2024-08-30, 2,236 suspected-CSAM links removed.
- **Other datasets:** LlavaGuard dataset is Apache-2.0, gated auto, 1k–10k items. VLGuard is MIT, gated auto, 1k–10k items.
