# Q4: Moderation second opinion (roadmap item 3)

Desk research only. I downloaded no dataset, image or model weights; I read only model cards, docs, papers, pricing pages and API metadata. All sources were read on 2026-10-08. I found nothing that could be CSAM. Source IDs `[S#]` are listed at the end. Revised after review rounds 1 and 2 (see "Review round 1 — resolution" and "Review round 2 — resolution").

## Summary and recommendation

**Recommendation: a two-tier local pipeline, with Claude Haiku as an optional third opinion. scenewise may only escalate a video. It never clears one.** scenewise stays a complement / second opinion permanently; this is a settled user decision (U1, `user-decisions.md`, 2026-10-08). Before and after the Video Intelligence shutdown the recommendation is the same. Only the primary that scenewise is compared against changes: Video Intelligence now, then Gemini or Cloud Vision SafeSearch.

1. **Tier 1 runs locally on every sampled frame, on CPU.**
   - **Explicit content:** `Freepik/nsfw_image_detector`, MIT, EVA-02 base at 448 px, about 86M params [S9][S10]. It outputs four graded levels (neutral/low/medium/high), which map almost directly onto Google's Likelihood buckets. It has the best self-reported numbers of the small classifiers, but on Freepik's own internal benchmark [S10].
   - **Small fallback model:** `Marqo/nsfw-image-detection-384`, Apache-2.0, about 5.6M params [S5][S9].
   - **Violence, gore and weapons:** SigLIP 2 zero-shot prompts, Apache-2.0 [S9]. No dedicated open, commercially licensed classifier for these turned up. The zero-shot approach has **no accuracy evidence** until we evaluate it.
2. **Tier 2 runs only on ambiguous or flagged frames.** Use a promptable guard model that returns a continuous yes/no score (renormalised P(yes)). Neither vendor claims the score is calibrated; calibration must be measured on our eval set [S12][S15].
   - **Mistral Shieldstral-1.0-3B** (Apache-2.0, released 2026-08-04; policies are free text) [S11][S12][S13].
   - **Google ShieldGemma 2 4B** (Gemma Terms of Use; three trained policies: sexual, dangerous, violence/gore; custom policy text is accepted but untrained). On a relabelled UnsafeBench subset in its own report (Table 2), it is best on sexual F1 and on violence 1−FPR. On danger 1−FPR, GPT-4o mini (92.3) and Gemma 3 (93.8) are ahead of it (88.7). 1−FPR measures only false positives, not recall [S6][S14][S15]. Its UnsafeBench figures and Shieldstral's are **not comparable** (different labels, metrics and setups; see table).
   - **NVIDIA Nemotron 3.5 Content Safety (4B)** (Gemma-3-4B LoRA fine-tune; one image plus custom policies; "ready for commercial use"). In Mistral's table it scores above ShieldGemma 2 [S12][S45]. **Its licence name is inconsistent across NVIDIA's own pages** (OpenMDW 1.1 vs "NVIDIA Nemotron Open Model License", plus the Gemma terms on both), so it is a candidate only once that is resolved (Open question 15). Unlike the other two, it has no documented continuous score: it outputs safe/unsafe labels.
   - All three are 4B-class models. CPU latency is unknown (open question).
3. **Claude Haiku 5.5 is optional, as a third opinion or tie-breaker.**
   - **Policy:** Anthropic documents content moderation, including images, as a supported use case [S20]. The Usage Policy prohibits *generating* sexual content, not classifying it [S19].
   - **Caveats:**
     - Claude "does not process inappropriate or explicit images that violate the Acceptable Use Policy" [S21].
     - Its built-in safety behaviour may flag explicit content whatever the prompt says [S20].
     - Haiku 5.5 can return `stop_reason: "refusal"` [S23].
     - Anthropic hash-matches images against NCMEC on first-party services and reports matches [S24].
   - **Consequence:** use Claude for the non-sexual categories and for context. Treat a refusal as a signal to escalate, never as a verdict. **Do not enable server-side `fallbacks`** (details below).
   - **Cost:** about **$0.0004–0.0009 per video** for 3–10 preview thumbnails on Haiku 5.5 ($0.003–0.007 on Haiku 4.5). The 5-minute, every-10-s figure (about $0.002) is an upper bound. Batch is half price (calculation below).
4. **Not recommended.**
   - **NudeNet:** the licence conflicts. The GitHub repo is AGPL-3.0, PyPI says MIT, and the detectors are Ultralytics YOLOv8 models [S2][S3][S4].
   - **Llama Guard 4:** single-image F1 is only 38% on Meta's own test set. Llama 4 multimodal rights are withheld from any company with "a principal place of business in" the EU, though end users of a product that incorporates the model are exempt [S7][S8][S16].
   - **LlavaGuard:** the weights licence is not stated, and it scores weakly on UnsafeBench per the ShieldGemma 2 report [S15][S17].
   - **OpenNSFW2:** MIT code; weights are a conversion of Yahoo's 2016 Open-NSFW release, whose (archived) repo is BSD-2 [S1][S4]. Use it only as a baseline.
   - **AWS Rekognition, Azure AI Content Safety (and Hive, Sightengine):** set aside. They are paid or quota-capped, add another vendor, and send frames out of Expause's infrastructure, without covering anything the options above do not (see Hosted options).

### Video Intelligence deprecation: before and after shutdown

**Confirmed fact.** Google: "Starting on September 14, 2026, Video Intelligence API is officially deprecated and will no longer be supported. … You can continue using Video Intelligence API until September 14, 2027, when it will be shut down." Google recommends "migrating to Gemini family of models" [S26]. Google's explicit detection covers only adult content (nudity, sexual activity, pornography), not violence [S27], so scenewise's violence, gore and weapons outputs are *additional* signals in either case.

**Decided (U1, 2026-10-08): scenewise stays a second opinion in both periods. Only the primary it is compared against changes.** Expause moves its primary moderation signal to Gemini or Cloud Vision SafeSearch. scenewise does not become primary, and no part of this document offers it as one.

**(a) Until shutdown (now to 2027-09-14): second opinion against Video Intelligence.**
- scenewise runs alongside Video Intelligence `pornographyLikelihood`, exactly as in the combination rule below. Nothing in the recommendation changes.
- Design change: make the combination rule **primary-signal-agnostic** (it takes "primary likelihood per category" as input, not `pornographyLikelihood` specifically), so that it survives Expause's migration without a rewrite.

**(b) After shutdown: second opinion against Expause's new primary.** Per U1 the primary is one of the two Google options below. Which one is the remaining decision (Open question 1).

| Candidate primary (U1) | Fit | Cost per frame (list, 2026-10-08) | Main risks |
|---|---|---|---|
| **Cloud Vision SafeSearch** [S36][S37][S38] | Closest like-for-like. Per-image, same `VERY_UNLIKELY…VERY_LIKELY` enum (plus `UNKNOWN`), five categories `adult`, `spoof`, `medical`, `violence`, `racy`. Expause already runs on Google Cloud. Not deprecated (no banner on the feature page; the Vision deprecations page lists only Celebrity Recognition and OCR On-Prem). | First 1,000 units/month free, then $1.50 per 1,000 (to 5M) and $0.60 per 1,000 above. The pricing table also shows "Free with Label Detection"; the page does not define what that means (my reading: free only if Expause already pays for label detection on the same image; confirm on the SKU page). So **about $0.0015 per frame**, i.e. $0.0045–0.015 per video at 3–10 thumbnails. | `adult` is not defined the same way as VI's `pornography`, so thresholds must be re-set. A Google model may share failure modes with the old Google model, but it is no longer what scenewise seconds. |
| **Gemini** (Google's named replacement) [S26][S40][S41][S42][S46][S47] | Google documents Gemini for content moderation with custom policies and image input [S42]. That guide still recommends Gemini 2.5 Flash-Lite, but **2.5 Flash-Lite retires on Vertex AI on 2026-10-20** (replacements named: gemini-3.8-flash, gemini-3.1-flash-lite, Gemma 4), and the Gemini API limits 2.5 models to existing users [S46][S47]. So the candidates are **Gemini 3.1 Flash-Lite** (cheapest) and **Gemini 3.5 Flash-Lite**. Output is whatever we prompt for (we would ask for the ordinal scale in the mapping table), so it is not a native Likelihood. | Gemini 3 bills an image by `media_resolution`: low 280, medium 560, high 1120 tokens, default (unspecified) 1120 [S41]. My arithmetic, with about 40 output tokens per frame and the prompt left out: **≈ $0.00013–0.00044 per frame** (table below). Comparable to Haiku 5.5 (≈ $0.00007 per 432×768 frame). | Generative model: prompt-dependent, needs its own evaluation. Google says to "Turn off Gemini's safety filters, so as not to interfere with content moderation", and that Gemini "shouldn't be used for detecting Child Sexual Abuse Material (CSAM) imagery"; CSAM inputs are flagged as `PROHIBITED_CONTENT` [S42]. Thinking tokens bill as output; set the lowest thinking level. EEA use requires paid tier [S48]. Prices are from the Gemini API page; Vertex AI prices may differ (not checked). |

**Gemini 3.x per-frame cost (my arithmetic; Gemini API paid prices [S40], image tokens by `media_resolution` [S41]; 40 output tokens; policy prompt excluded).**

| Model ($ input / $ output per MTok) | `low` (280 tokens) | `medium` (560) | default / `high` (1120) |
|---|---|---|---|
| Gemini 3.1 Flash-Lite ($0.25 / $1.50) | 280 × 0.25 + 40 × 1.50 = 70 + 60 = 130 µ$ → **$0.00013** | 140 + 60 → **$0.00020** | 280 + 60 → **$0.00034** |
| Gemini 3.5 Flash-Lite ($0.30 / $2.50) | 280 × 0.30 + 40 × 2.50 = 84 + 100 = 184 µ$ → **$0.00018** | 168 + 100 → **$0.00027** | 336 + 100 → **$0.00044** |

(µ$ = millionths of a dollar: tokens × $/MTok.) A policy prompt of about 800 tokens adds 200 µ$ (3.1) or 240 µ$ (3.5) per request, so send several frames per request or use caching. Use `media_resolution: low` for evaluation first and only raise it if recall suffers. Per video at 3–10 thumbnails on 3.1 Flash-Lite at `low`: about $0.0004–0.0013 plus the prompt.

**OpenAI `omni-moderation-latest`** is **not** a candidate primary (U1 names only Gemini or Cloud Vision). It stays available as an optional, off-by-default scenewise tier-2 / third opinion (see Hosted options) [S39].

**Recommendation for case (b) (stance decided by U1; the choice of primary is the user's, Open question 1):**
- Expause migrates its primary to **Cloud Vision SafeSearch** (cheapest migration: same enum, per-frame, same vendor, adds `violence` and `racy`), or to **Gemini 3.1/3.5 Flash-Lite** if Expause prefers Google's named path and accepts building and evaluating a prompt. scenewise keeps exactly the same second-opinion role against whichever is chosen, and is built so that either works.
- **Before 2027-09-14:** run the candidate primary in shadow mode next to Video Intelligence and scenewise, so that Expause can compare SafeSearch/Gemini with Video Intelligence on the same frames while both still exist.

## Classifier survey table (local models)

Parameter counts come from the Hugging Face API safetensors totals [S9] unless stated otherwise. **No source gives CPU latency for any of these models.** CPU speed must be benchmarked (Open questions); the only measured speed is Freepik's GPU figure.

| Model (version read) | Categories | Output | Size | Licence (commercial?) | Reported accuracy |
|---|---|---|---|---|---|
| **Falconsai/nsfw_image_detection** (HF lastModified 2026-09-07) | `normal`, `nsfw` | Softmax probabilities, 2 classes | 85.8M (ViT-B/16 224, from `google/vit-base-patch16-224-in21k`) | **Apache-2.0**, yes [S0][S9] | Accuracy 0.980 on its own eval split of a proprietary set of about 80k images [S0]. Freepik's benchmark puts it at 31% on the "low" level and 78.5% on "medium" [S10]. |
| **Marqo/nsfw-image-detection-384** (2024-11-27) | NSFW / SFW | 2-class probabilities (timm) | 5.6M (ViT-tiny at 384) | **Apache-2.0**, yes [S5][S9] | 98.56% on a proprietary 20k test set. Card claims it beats Falconsai and AdamCodd, but the scores are only in a chart [S5]. Training data includes drawings and AI-generated images [S5]. |
| **Freepik/nsfw_image_detector** (2025-05-09) | `neutral`, `low`, `medium`, `high` (graded) | Probabilities. Custom code gives cumulative low/medium/high scores and `is_nsfw(img, level)` | 86.4M (EVA-02 base at 448) | **MIT**, yes [S9][S10] | Internal benchmark: high 99.5%, medium 97.0%, low 98.3%, neutral 99.9%. On the same set: Falconsai 97.9 / 78.5 / 31.3 / 99.3, AdamCodd 98.6 / 91.7 / 89.7 / 98.4 [S10]. GPU only: 28 ms per image at batch 1 on an RTX 3090 (PIL input) [S10]. |
| AdamCodd/vit-base-nsfw-detector (2024-12-03) | nsfw / sfw | Probabilities | 86.1M | Apache-2.0 [S9] | Comparison numbers only, from [S10]. |
| **NudeNet** (PyPI 3.4.2, 2024-07-03; weights v3.4, 2024-06-30) | 18 body-part detector classes (`*_EXPOSED` / `*_COVERED`, faces, feet, armpits, belly) | Boxes: `{class, score, box}` | YOLOv8n at 320 (default) or YOLOv8m at 640 [S3] | **Conflict: GitHub repo AGPL-3.0, PyPI says MIT** [S2][S4]. Ultralytics YOLOv8 derivative. Treat as **not cleared** for commercial use. | None published by the project [S3]. UnsafeBench: Sexual F1 0.624 overall (0.650 real, 0.596 AI-generated), on UnsafeBench's own labels, so not comparable with SG2's relabelled 64.2 [S29]. |
| **OpenNSFW2** (latest tag v0.19.0; repo pushed 2026-09-13) | SFW / NSFW (pornography) | NSFW probability. Has built-in video frame sampling and aggregation | Not stated (Keras port of Yahoo's 2016 Open-NSFW) | Code **MIT** [S1][S4]. Weights: a conversion of Yahoo's release; the upstream `yahoo/open_nsfw` repo is BSD-2-Clause and **archived** [S4]. The opennsfw2 README does not state the converted weights' licence, so BSD-2 is inferred [S1]. | None [S1]. |
| **LAION CLIP-based-NSFW-Detector** (repo last pushed 2023-05-30) | NSFW score | Value from 0 to 1 (1 = NSFW), from an MLP on CLIP ViT-L/14 (768-d) or B/32 embeddings | Small MLP plus a CLIP backbone (ViT-L/14 is about 428M [S9]) | README: **MIT**. GitHub API: NOASSERTION [S4][S18] | No figures. A manually annotated test set is linked [S18]. Trained on LAION embeddings. |
| **Q16** (ml-research, FAccT 2022) | "Inappropriate" (single concept) | Binary, CLIP prompt-tuned | CLIP ViT-L/14 | MIT badge [S30] | UnsafeBench: best only on Hate (F1 0.533) [S29]. |
| **CLIP / SigLIP 2 zero-shot** | Anything you can write as a prompt (violence, gore, weapon, blood, …) | Cosine similarity, then softmax over prompts | SigLIP2-base 375M; so400m 1.14B [S9] | SigLIP 2 **Apache-2.0** [S9]. OpenAI CLIP **MIT** [S4]. Yes. | None for our categories. **Must be evaluated.** |
| prithivMLmods/Image-Guard-2.0-Post0.1 (2025-10-14) | Anime-SFW, Normal-SFW, Hentai, Enticing/Sensual, Pornography, plus a synthetic-image class | Multi-label probabilities | 92.9M (SigLIP2-base) | Apache-2.0 on HF tags [S9]. The blog states none [S31]. | None in text. Author calls it "an experimental start" [S31]. 14 downloads [S9]. |
| **ShieldGemma 2 4B IT** (HF 2025-04-04; paper arXiv 2504.01081) | Three trained policies: Sexually explicit, Dangerous, Violence/Gore. Users may "curate their own bespoke policy", but it is "not specifically fine-tuned for policies other than sexual, danger and violence" [S15]. | P(Yes) / P(No) token probabilities, so a continuous (not documented as calibrated) score | 4.3B (Gemma 3 4B) | **Gemma Terms of Use**: use, modify and distribute allowed. Gemma Prohibited Use Policy applies and must be passed downstream. **Gated (HF: manual approval)** [S6][S9][S14] | Internal P/R/F1: sexual 87.6 / 89.7 / 88.6, dangerous 95.6 / 91.9 / 93.7, violence 80.3 / 90.4 / 85.0 [S6]. UnsafeBench relabelled with Google's policies: sexual F1 64.2, danger 1-FPR 88.7, violence 1-FPR 95.9. In its own Table 2 (vs LlavaGuard, GPT-4o mini, Gemma 3) it is best on sexual F1 (64.2 vs 57.1 / 50.4 / 42.1 / 37.8) and violence 1-FPR (95.9 vs 62.5 / 57.3 / 40.1 / 13.0); on danger 1-FPR GPT-4o mini (92.3) and Gemma 3 (93.8) are ahead. 1-FPR counts false positives only, not recall [S15]. In Mistral's setup it scores UnsafeBench F1 54.9 [S12]. Single images only; text-overlay harms out of scope [S15]. |
| **Mistral Shieldstral-1.0-3B** (released 2026-08-04; HF 2026-08-05) | No fixed categories. Policies are natural-language yes/no questions | One yes/no token. Continuous score = renormalised P(yes) (softmax over the yes/no logits); default threshold 0.5. The card does not call it calibrated [S12][S13] | Described as 3B; HF lists 3.85B (Ministral-3-3B plus Pixtral encoder) [S9][S12] | **Apache-2.0**, yes [S9][S12] | Vendor multimodal F1: VLGuard 97.7, UnsafeBench 81.8, LlavaGuard benchmark 72.0. On the LlavaGuard benchmark, **LlavaGuard-7B scores higher (81.4)**; some of its test images were unavailable [S12]. Mistral's UnsafeBench F1 is an overall score on Mistral's setup, not comparable with SG2's relabelled per-policy figures. Vendor claims, not independent. Fits 16 GB VRAM. GGUF Q4/Q5/Q8 documented, but no CPU numbers [S12]. Not tested on video frames. |
| **NVIDIA Nemotron 3.5 Content Safety** (HF card, released 2026-06-02) | Default safety taxonomy, or a custom policy supplied in the chat template; optional reasoning mode (`enable_thinking`) | Text lines: `User Safety` (safe/unsafe), optional `Response Safety` and `Safety Categories`. No documented continuous score [S45] | About 4B (Gemma-3-4B-it LoRA fine-tune, merged; SigLIP encoder). Single image per input [S45] | **Unresolved licence name.** HF card: OpenMDW 1.1 + Gemma Terms of Use + Gemma Prohibited Use Policy; NGC model page: "NVIDIA Nemotron Open Model License" + Gemma terms; NGC governing-terms page and NVIDIA API docs: OpenMDW 1.1. All say "ready for commercial use" [S45]. Gemma terms apply in every version. | Vendor: VLGuard prompt harmful F1 0.90, MM-SafetyBench 0.71 [S45]. In Mistral's setup: VLGuard 84.2, UnsafeBench 67.7, LlavaGuard 70.0 F1, i.e. above ShieldGemma 2 (61.3 / 54.9 / 56.2) and below Shieldstral (97.7 / 81.8 / 72.0) [S12]. Different setups; not independent. |
| **Llama Guard 4 12B** (HF 2025-04-29) | MLCommons S1–S14, including S12 Sexual Content, S1 Violent Crimes, S9 Indiscriminate Weapons, S4 Child Sexual Exploitation | Text: `safe` / `unsafe` + category codes | 12.0B | Llama 4 Community Licence (effective 2025-04-05). 700M MAU clause; "Built with Llama" attribution [S7][S16]. AUP: multimodal rights "are not being granted to you if you are an individual domiciled in, or a company with a principal place of business in, the European Union. This restriction does not apply to end users of a product or service that incorporates any such multimodal models." [S8]. **Gated (HF: manual approval)** [S9]. | In-house single-image: R 41%, FPR 9%, F1 38%. Multi-image F1 52% [S7]. Image-only classification not documented [S7]. |
| **LlavaGuard v1.2** (0.5B and 7B OV, HF 2025-01-17) | O1–O9: hate, violence, sexual, nudity, criminal planning, weapons/substance abuse, self-harm, animal cruelty, disasters | JSON `{rating, category, rationale}` | 0.89B / 8.0B (LLaVA-OneVision / Qwen2) [S9][S17] | Code Apache-2.0 [S4]. **Weights licence not stated** [S17]. | UnsafeBench (relabelled) per the ShieldGemma 2 report: sexual F1 42.1, violence 1-FPR 40.1 [S15]. In Mistral's setup (Shieldstral card): LlavaGuard benchmark F1 81.4, UnsafeBench F1 63.9 (vs the SG2 report's relabelled sexual F1 42.1; different setups) [S12]. |
| **GuardReasoner-VL 3B / 7B** (NeurIPS 2025; HF 2025-06-09) | General VLM-safety harm (prompt and response) | Reasoning trace, then a label | 4.07B (Qwen2.5-VL-3B) [S9] | Weights Apache-2.0 on HF; repo MIT [S4][S9] | 7B: 70.84% on HarmImageTest, from a third-party summary [S32]. Aimed at VLM I/O, not UGC frames. |

Other leads seen but not researched further: OmniGuard-7B (in Mistral's table: VLGuard 88.5, UnsafeBench 72.6, LlavaGuard 71.7 F1, above ShieldGemma 2 and Nemotron; licence and card not checked) [S12], ProGuard (arXiv 2512.23573), GuardReasoner-Omni (arXiv 2602.03328, text, image, video and audio), SafeGuard-VL (CVPR 2026), and the SafeAtlas-VL guard (arXiv 2608.29098) [S32].

## Hosted options

| Service | Categories relevant to Expause | Output | Price (2026-10-08) | Status / terms | Verdict |
|---|---|---|---|---|---|
| **Google Cloud Vision SafeSearch** [S36][S37][S38] | `adult`, `spoof`, `medical`, `violence`, `racy` | Likelihood per category (`UNKNOWN`, `VERY_UNLIKELY` … `VERY_LIKELY`) | 1,000 units/month free; $1.50 / 1,000 (1,001–5M); $0.60 / 1,000 above 5M; "Free with Label Detection" (meaning not defined on the page; confirm on the SKU page) | Not deprecated (feature page has no banner; Vision deprecations page lists only Celebrity Recognition and OCR On-Prem). | **Candidate primary after 2027-09-14** (U1). Not used as a scenewise second opinion: it would add a Google signal next to a Google signal, so errors may correlate. |
| **Gemini** (3.1 / 3.5 Flash-Lite; 2.5 Flash-Lite retires on Vertex 2026-10-20) [S40][S41][S42][S46][S47] | Any prompted policy; Google documents moderation use | Whatever is prompted (use the ordinal scale) | ≈ $0.00013–0.00044 per frame at `media_resolution` low to default (table above) | Google's named VI replacement. Turn its safety filters off for moderation; not for CSAM detection [S42]. EEA: paid tier only; prompts and responses logged for a limited period for abuse monitoring (Gemini API terms; Vertex terms separate) [S48]. | **Candidate primary** (U1). If Expause picks Gemini as primary, do not also use it as a scenewise tier; otherwise usable as a hosted tier-2 alternative to Claude, with the same evaluation. |
| **OpenAI `omni-moderation-latest`** [S39] | `sexual`, `violence`, `violence/graphic`, self-harm ×3 on images; no weapons; `sexual/minors` text-only | `flagged`, booleans, `category_scores` 0–1 (fits the probability row of the mapping table) | Free | Images ≤ 20 MB. "Do not send known or suspected child sexual abuse material (CSAM)"; "not designed for CSAM detection or handling". Not restricted to OpenAI model I/O. | **Optional zero-cost hosted tier-2 / third opinion.** Same CSAM pre-routing constraint as Claude. Off by default because frames leave Expause's infrastructure. |
| **Claude Haiku 5.5** | Any prompted policy | Ordinal JSON (prompted) | ≈ $0.00007 per 432×768 frame | See next section | **Optional third opinion** (as recommended). |
| AWS Rekognition `DetectModerationLabels` [S43] | Image and stored-video moderation, downloadable label taxonomy, custom adapters | Labels with confidence | $0.0010 per image (first tier, us-east-1); 1,000 images/month free for 12 months | Another vendor and cloud | **Rejected:** paid per image, frames leave Google Cloud, nothing the free/local options lack. |
| Azure AI Content Safety [S44] | Image analysis with severity levels | Severity per category | F0 free tier: 5,000 images/month, no overage; Standard image price not visible on the page | Another vendor and cloud | **Rejected:** same reasons; F0 quota too small for production. |
| Hive, Sightengine | Not researched | — | — | — | **Not researched**; same objections (paid, third party). |

## Claude vision: policy and cost

**Policy (Anthropic Usage Policy, "Effective September 15, 2025", the current version on 2026-10-08) [S19]**

- The **"Do Not Generate Sexually Explicit Content"** section prohibits using Claude to "Depict or request sexual intercourse or sex acts", "Generate content related to sexual fetishes or fantasies", "Facilitate, promote, or depict incest or bestiality", and "Engage in erotic chats". These are all *generation* prohibitions. The AUP does not mention classification or moderation as either permitted or prohibited.
- **"Do Not Compromise Children's Safety"** prohibits using Claude to "Create, distribute, or promote child sexual abuse material ("CSAM"), including AI-generated CSAM". It also says: "We define a minor or child to be any individual under the age of 18 years old, regardless of jurisdiction." and "When we detect CSAM (including AI-generated CSAM), or coercion or enticement of a minor to engage in sexual activities, we will report to relevant authorities."
- **High-risk requirement:** human review applies only to the listed high-risk domains. Automated moderation is not on that list [S19].
- **Government censorship:** "Analyze or identify specific content to censor on behalf of a government organization" is prohibited [S19]. This does not apply to Expause.

**Content moderation is an explicitly documented use case.** The "Content moderation" guide [S20] says that "Claude's multimodal capabilities allow it to analyze and interpret content across both text and images". It suggests Claude Haiku 5.5 when cost matters. It also warns that Claude may flag explicit content "regardless of the prompt used … an adult website … may find that Claude still flags explicit content as requiring moderation". For Expause this behaviour is harmless, because we want explicit content flagged.

**Caveats for sexual images**

- The vision docs say Claude "does not process inappropriate or explicit images that violate the Acceptable Use Policy" [S21]. I could not establish whether *classifying* an explicit frame counts as "processing" in that sense; it is an open question. In practice expect refusals or degraded answers on explicit frames.
- Haiku 5.5 has safety classifiers that return `stop_reason: "refusal"` as a normal response, with `stop_details.category` set to `cyber`, `bio`, `frontier_llm`, `reasoning_extraction`, `general_harms` or `null` [S22][S23].
  - **Billing:** a refusal *before any output* is **not billed** unless its category is `bio`, `frontier_llm` or `reasoning_extraction`. "A mid-stream refusal bills the input tokens and the output already streamed at normal rates." Partial output from a mid-stream refusal must be discarded [S23].
  - **Batch:** a refused batch item comes back as `result.type: "succeeded"` with `stop_reason: "refusal"`. **Detect refusals by `stop_reason` (or `stop_details`), never by `result.type`** [S23].
  - **Do not use server-side `fallbacks`** (beta, header `server-side-fallback-2026-07-01`). It re-runs a refused request on another model. The swap is marked in the response (the response names the serving model and a `fallback` content block marks the handoff), but a verdict-only parser easily misses it, so a "refusal → escalate" signal would be replaced by a different model's verdict. In `"default"` mode, categories with no recommended fallback keep the refusal. It is not supported on the Batch API anyway (the item errors), and "A Claude Haiku 5.5 refusal carries no fallback credit" [S23]. If a retry on another model is ever wanted, do it client-side and record which model answered.
  - **scenewise should treat a refusal as "escalate to a human", never as SAFE or UNSAFE.**
- **CSAM:** Anthropic "strictly prohibits CSAM on our services". On first-party services it compares a perceptual hash of each input image against NCMEC's known-CSAM hashes, reports matches to NCMEC, and notifies the organization (article dated 2026-03-16) [S24]. The article does not say whether this covers the API. **Expause needs its own legally reviewed CSAM pipeline**, such as hash matching and mandatory reporting, *before* any frame reaches any third party (Anthropic, Google Gemini, OpenAI). Google and OpenAI both say their moderation tools are not for CSAM detection [S39][S42]. That is out of scope for scenewise (open question).

**Image token cost: the `w*h/750` formula is out of date.** The current docs give `⌈width/28⌉ × ⌈height/28⌉` visual tokens [S21].

- **Resolution tiers:**
  - "Claude 4.7 and later models": long edge up to 2576 px, up to 4784 tokens.
  - All other models: long edge up to 1568 px, up to 1568 tokens.
  - Haiku 5.5 is not named in the tier table, but it is a post-4.7 model that "uses the same newer tokenizer as Claude 4.7 and later models", so it is **probably high-res** [S21][S28]. This is irrelevant for frames ≤ 1568 px, such as those below.
- **Example from the docs:** 1000×1000 = 1296 tokens, so "about $1.30 per thousand images" on Haiku 4.5 [S21].
- **Old formula vs. current formula:**
  - 432×768: current 16 × 28 = **448 tokens**; old formula 442.
  - 288×512: current 11 × 19 = **209 tokens**; old formula 197.
  - So the old formula is a close approximation at these sizes.

**Pricing (2026-10-08) [S25][S28]**

| Model | Input $/MTok | Output $/MTok | Batch |
|---|---|---|---|
| Claude Haiku 5.5 (`claude-haiku-5-5`, released 2026-10-07, 1M context), prompts ≤ 100,000 tokens | $0.10 | $0.50 | 50% off |
| Claude Haiku 5.5, **prompts > 100,000 tokens** | **$0.50** | **$2.50** | 50% off |
| Claude Haiku 4.5 (200k context) | $1.00 | $5.00 | 50% off |

- Cache reads cost 0.1× input [S25].
- **Keep each Haiku 5.5 request under 100k tokens** (about 200 frames at 432×768, including the prompt); above that every token costs 5× [S25][S28].
- Image limits per API request: "100 per request on the API, for models with a 200k-token context window" (this includes Haiku 4.5) and "600 per request on the API, for all other models" (Haiku 5.5). Above 20 images per request, each image must be 2000 px or less per side [S21].
- Haiku 5.5's tokenizer counts the same text as about 30% more tokens than Haiku 4.5; image tokens are unaffected [S28].

**Per video (my estimate, not sourced)**

- **Assumptions:**
  - Portrait 432×768 frames (448 tokens each).
  - One request per video with all frames.
  - Prompt (policy and schema; cacheable): about 800 tokens on Haiku 4.5, about 1,050 on Haiku 5.5 (tokenizer +30%).
  - About 40 output tokens per frame (JSON).
  - Haiku 5.5 only: about 200 thinking tokens. Haiku 5.5 thinking is adaptive and on by default (default effort `medium`), and thinking tokens bill as output; set effort to low [S28]. Haiku 4.5 uses manual extended thinking, which is off unless requested, so its column assumes no thinking.

| Sampling | Frames | Haiku 5.5 | Haiku 4.5 |
|---|---|---|---|
| **Preview thumbnails (Expause's actual input)** | 3 | ≈ **$0.0004** | ≈ **$0.0027** |
| **Preview thumbnails** | 10 | ≈ **$0.0009** | ≈ **$0.0073** |
| Upper bound: 5-min video, 1 per 5 s | 60 | ≈ **$0.004** | ≈ **$0.040** |
| Upper bound: 5-min video, 1 per 10 s | 30 | ≈ **$0.002** | ≈ **$0.020** |
| Upper bound: 5-min video, 1 per 30 s | 10 | ≈ **$0.0009** | ≈ **$0.0073** |

- Haiku 4.5 arithmetic, 3 frames: (800 + 3 × 448) × $1.00/MTok + 120 × $5.00/MTok = $0.0021 + $0.0006 = $0.0027. Haiku 5.5, 3 frames: (1,050 + 1,344) × $0.10/MTok + 320 × $0.50/MTok = $0.00040.
- The Batch API halves all of these.
- **Cheapest design:** send Claude only frames that tier 1 or the primary signal rates POSSIBLE or higher. Most videos would then cost $0.
- At 288×512 the image token count roughly halves.
- **Fit:** cost is not a blocker. The blockers are refusal behaviour on sexual frames and the CSAM-routing question.

## Likelihood mapping

Google's enum is `LIKELIHOOD_UNSPECIFIED`, `VERY_UNLIKELY`, `UNLIKELY`, `POSSIBLE`, `LIKELY`, `VERY_LIKELY`; the descriptions are just those words [S26a]. Cloud Vision SafeSearch uses the same five buckets plus `UNKNOWN` [S36].

- **Where it appears (Video Intelligence):** `ExplicitContentAnnotation.frames[]` holds `ExplicitContentFrame { timeOffset, pornographyLikelihood }`, plus a `version` [S26b].
- **Model choice:** `ExplicitContentDetectionConfig.model` is `builtin/stable` (the default) or `builtin/latest` [S26].
- **Thresholds:** Google publishes no numeric thresholds behind the buckets. That means **no mapping can be "equivalent"**. It can only be calibrated empirically against the primary signal's output and against moderator decisions.

**Proposed bucketing.** These are starting points only. Each model is re-calibrated on the eval set (next sections) so that each bucket hits a target precision, not fixed score cut-offs. None of the continuous scores below is documented as calibrated.

| scenewise source | VERY_UNLIKELY | UNLIKELY | POSSIBLE | LIKELY | VERY_LIKELY |
|---|---|---|---|---|---|
| Any probability model (Falconsai, Marqo, OpenNSFW2, LAION, SigLIP zero-shot softmax, ShieldGemma 2 P(Yes), Shieldstral score, OpenAI `category_scores`) | p < 0.15 | 0.15–0.35 | 0.35–0.60 | 0.60–0.85 | ≥ 0.85 |
| Freepik graded (argmax level, with cumulative score ≥ 0.5) | neutral | low | medium | high, cumulative 0.5–0.85 | high, cumulative ≥ 0.85 |
| NudeNet (if ever cleared) | no detections | only `*_COVERED` classes | exposed breast or buttocks ≥ 0.5 | exposed genitalia or anus ≥ 0.5 | exposed genitalia or anus ≥ 0.8 |
| Claude / Gemini / LLM with ordinal output (ask for `none / low / medium / high / certain`) | none | low | medium | high | certain |
| Llama Guard / Nemotron style `safe` / `unsafe:Sx` | safe | n/a | n/a | unsafe | n/a (no confidence) |
| Claude `stop_reason: refusal` | not mapped: emit `LIKELIHOOD_UNSPECIFIED` + `escalate=true` | | | | |

Rules:

- **Separate categories.** scenewise emits `sexual`, `violence_gore`, `weapons` and `dangerous` separately. **Only categories the primary signal also covers are combined with it.** With Video Intelligence that is `sexual` vs `pornographyLikelihood` only [S27]. With SafeSearch it would be `sexual` vs `adult` (and possibly `racy`) and `violence_gore` vs `violence` [S36]. The others remain new signals.
- **Frame to video:** a video's likelihood for a category is the max over frames, with a persistence guard. A single-frame LIKELY becomes POSSIBLE unless an adjacent sampled frame is also POSSIBLE or higher. VERY_LIKELY is never downgraded.
- **Keep everything.** Always store the raw score, model ID and version, the threshold set version, and (for any hosted LLM) the model that actually answered, alongside the bucket.

## Combination rule

scenewise is framed as a second opinion. **It can add an escalation. It can never remove or lower the primary verdict.** "Primary" is Video Intelligence `pornographyLikelihood` today and Gemini or Cloud Vision SafeSearch after migration (U1). The rule takes the primary likelihood per category as an input, so it applies unchanged to whatever primary Expause uses.

| Primary likelihood (video max, per covered category) | scenewise, same category | Action |
|---|---|---|
| Any | Within ±1 bucket of primary | Agreement. Expause's existing rule decides, unchanged. |
| ≤ UNLIKELY | ≥ LIKELY | **Escalate to human review** (possible primary miss). No auto-action from scenewise alone. |
| ≥ LIKELY | ≤ UNLIKELY | The primary's rule still applies. Log it as disagreement for calibration. Optionally put it in a low-priority "possible false positive" queue. scenewise never auto-restores. |
| POSSIBLE | ≥ LIKELY | Escalate, priority high. |
| Any | Claude refusal, or tier-2 guard VERY_LIKELY | Escalate. |
| n/a (primary does not cover the category) | `violence_gore` / `weapons` / `dangerous` ≥ LIKELY | Escalate to human. Expause decides later whether VERY_LIKELY auto-actions. |

Mode options for Expause:

- **`advisory`** (default): scenewise only emits flags and escalations.
- **`max`**: effective likelihood = max(primary, scenewise). Expause can opt in after the evaluation shows scenewise's precision at LIKELY or higher is acceptable.
- A mode in which scenewise is itself primary (can clear content) is **not offered** (U1).

**Any content suspected to involve a minor must leave the scenewise path and go to Expause's CSAM procedure. scenewise does not try to classify age.**

## Evaluation plan

**Principle: the repo and CI never hold explicit material.** The repo contains:

- eval harness code;
- dataset *identifiers* and access instructions;
- prediction and score CSVs keyed by opaque IDs or hashes;
- aggregate metrics.

CI plumbing tests use only benign synthetic fixtures, such as solid colours and generated shapes.

1. **Offline benchmarks, run by an authorised operator outside the repo.**
   - The operator accepts each dataset's terms personally and streams or fetches it into ephemeral, access-controlled storage.
   - The operator runs `scenewise eval --dataset-dir <external>` and deletes the data afterwards.
   - Only metrics and per-ID scores are committed.
   - Candidate datasets (none downloaded for this research):
     - **UnsafeBench** (`yiting/UnsafeBench`): 10,146 images (6,098 safe, 4,048 unsafe), 11 categories (Hate, Harassment, Violence, Self-Harm, Sexual, Shocking, Illegal Activity, Deception, Political, Public and Personal Health, Spam). Half real images from LAION-5B, half AI-generated from Lexica. **Gated: the HF API flag is `auto`, but the card says "Our team may take 1-2 days to process your request"**. Terms are a Data Use Agreement with no licence tag; the card allows "research/education purposes and responsible commercial use". Card lastModified 2026-03-05; re-check the terms before use, since a secondary summary described it as research-only [S9][S29][S33]. It allows comparison against published numbers for ShieldGemma 2, Shieldstral, NudeNet and GPT-4V, keeping in mind the setups differ [S12][S15][S29]. Its ethics statement says it contains no CSAM [S29]. Its real images come from LAION-5B, where suspected CSAM links were found and later removed in Re-LAION-5B [S34], so access should still follow a CSAM-aware handling procedure.
     - **LlavaGuard dataset** (`AIML-TUDA/LlavaGuard`): Apache-2.0 tag, gated (auto), 1k–10k items [S9].
     - **VLGuard** (`ys-zong/VLGuard`): MIT tag, gated (auto), 1k–10k items [S9]. It is VLM-safety oriented.
     - **Violence:** RWF-2000 (Duke Kunshan; a release agreement exists, but its official terms were not verified) and XD-Violence (terms not found) [S35]. Both are video, which suits frame sampling.
     - **Pornography:** NPDI (800 videos, UFMG) and LSPD (about 50k images). Both are by request, for research [S35]. Terms not verified.
   - Commercial-use eligibility of each dataset for an evaluation that serves a commercial consumer is an **open question**.
2. **Shadow mode on Expause: the primary evaluation.**
   - scenewise runs next to the primary signal on Expause's existing preview-frame pipeline, inside Expause's infrastructure. Frames are processed in memory and never persisted by scenewise.
   - **Before 2027-09-14**, also run the candidate replacement primary (SafeSearch and/or Gemini) in shadow, so that Expause can compare it with Video Intelligence on the same frames while both exist.
   - Logged per video: primary likelihoods, scenewise scores and buckets, model versions, and **the human moderator's final decision** (ground truth from Expause's existing process).
   - Metrics:
     - 5×5 confusion matrix of primary vs. scenewise;
     - escalation rate;
     - precision of escalations against moderator outcome;
     - "primary missed, scenewise caught" count;
     - Claude refusal rate;
     - per-category PR curves and calibration curves, used to recalibrate thresholds.
   - Explicit material stays in Expause's moderated store under Expause's policies, never in scenewise.
3. **Benign proxy tests for zero-shot categories.** Weapons and violence classifiers can be partly regression-tested on non-explicit public images, for example ordinary photos of kitchen knives, toy guns or sports, to measure *false positives* without any harmful material. This does not measure recall.
4. **Release gate:** before `max` mode is offered, precision at LIKELY or higher must reach Expause's agreed target in shadow mode, measured on at least N moderator-reviewed escalations (target and N to be set by Expause).

## Open questions

1. **Decision for the user: which primary, Cloud Vision SafeSearch or Gemini?** (The stance is settled by U1: scenewise stays a second opinion.)
   - *For SafeSearch:* same Likelihood enum and per-image model as today, no prompt to build or maintain, deterministic, not deprecated, adds `violence` and `racy`. About $0.0015 per frame, roughly 10× Gemini 3.1 Flash-Lite at `low`.
   - *For Gemini:* Google's named VI replacement, custom policies (could cover weapons and dangerous content), cheaper per frame (≈ $0.00013–0.00044). But it is a generative model that needs a prompt, its own evaluation and its safety filters turned off, it is not a native Likelihood, and Flash-Lite models turn over fast (2.5 Flash-Lite retires on Vertex 2026-10-20).
   - Either way, scenewise's combination rule works unchanged. The pre-shutdown shadow run can settle it on Expause's own frames.
2. **SafeSearch vs. VI equivalence.** Is SafeSearch `adult` close enough to VI `pornographyLikelihood` that Expause's thresholds carry over? Does SafeSearch share a model with VI (correlated errors)? Not documented [S36][S27]. Answer with the pre-shutdown shadow run.
3. **Claude on explicit frames.** Does "does not process inappropriate or explicit images" [S21] mean Haiku will reliably refuse to classify explicit frames, or only refuse to describe them? This needs an empirical test, run by Expause in their environment on their moderated content, or clarification from Anthropic. Does the hash-match/NCMEC process [S24] apply to API traffic?
4. **CSAM legal process.** What is Expause's legally required CSAM detection and reporting process (hash matching, NCMEC/IWF reporting), and must it run before frames reach scenewise or any third-party API (Anthropic, Google Gemini, OpenAI)? Google and OpenAI both say their moderation tools are not for CSAM [S39][S42]. This needs legal input and is outside scenewise.
5. **Third-party hosted terms.** Gemini API (paid tier, required for EEA users): prompts are not used for training, and "Google logs prompts and responses for a limited period of time" for abuse monitoring [S48]. Vertex AI Gemini terms and OpenAI moderation data-retention terms were not checked. Vertex AI Gemini prices (vs. the Gemini API prices used here) were not checked. Can Expause get Gemini's safety filters turned off as Google's moderation guide advises [S42]?
6. **NudeNet licence.** Which governs: the repo's AGPL-3.0 or PyPI's MIT? What about the Ultralytics-derived weights [S2][S3][S4]?
7. **LlavaGuard weights licence** is not stated [S17].
8. **Llama 4 EU restriction.** Expause is EU-based (U3), so Llama Guard 4 stays excluded [S8]. Other self-hosters of scenewise must check their own principal place of business before enabling it.
9. **CPU latency.** None of the model cards publish CPU numbers. Benchmark Freepik, Marqo, Falconsai, SigLIP2-base and so400m, Shieldstral GGUF Q4/Q8 and (if its licence clears) Nemotron 3.5 Content Safety on the target host.
10. **Haiku 5.5 resolution tier** is probably high-res but not stated by name [S21][S28]. It only matters if frames over 1568 px are sent.
11. **Shieldstral claims** are vendor-reported, from a two-month-old release [S12][S13]. The paper (arXiv 2607.25857) was not read. ShieldGemma 2 has no published input resolution [S15]. Neither score is documented as calibrated.
12. **Dataset terms** for evaluating a commercial product: UnsafeBench's DUA allows "responsible commercial use" (card version 2026-03-05); RWF-2000, XD-Violence, NPDI and LSPD terms are unverified.
13. **Google's frame sampling** for explicit detection is undocumented [S27]. How many preview thumbnails does Expause send per video, and should scenewise score the same frames?
14. **Volumes.** What target escalation rate and human-review capacity does Expause have? These set the thresholds and decide whether SafeSearch's per-image price matters.
15. **Decision for the user: keep NVIDIA Nemotron 3.5 Content Safety as a tier-2 candidate while its licence name is unresolved?**
   - *Keep it:* it scores above ShieldGemma 2 in Mistral's table, takes custom policies, and every NVIDIA page says "ready for commercial use"; both licence names sit on top of the Gemma terms SG2 already carries.
   - *Drop it until clarified:* NVIDIA's pages name two different licences (OpenMDW 1.1 vs Nemotron Open Model License), it has no documented continuous score, and Shieldstral (Apache-2.0) already scores higher.

## Review round 1 — resolution

Each finding was re-checked against its source on 2026-10-08.

1. **Cloud Vision SafeSearch missing:** fixed. Re-verified five categories, Likelihood buckets, no banner, page updated 2026-10-07 [S36]; pricing [S37]; Vision deprecations page lists no SafeSearch or API deprecation [S38]. Added to Hosted options and as the case-(b) like-for-like candidate.
2. **OpenAI omni-moderation missing:** fixed. Re-verified free, images ≤ 20 MB, six image-capable categories, `sexual/minors` text-only, CSAM warning plus "not designed for CSAM detection" [S39]. Added as optional zero-cost tier-2 / third opinion and a case-(b) option (the case-(b) primary role was withdrawn in round 2 under U1).
3. **Gemini not evaluated:** fixed. Added with per-frame cost estimate [S40][S41] (model choice and cost method corrected in round 2), Google's moderation guidance incl. safety-filters-off and CSAM caveat [S42]; combination rule made primary-agnostic.
4. **AWS / Azure / Hive / Sightengine not mentioned:** fixed. Rekognition and Azure priced and rejected with reasons [S43][S44]; Hive and Sightengine listed as not researched.
5. **Shieldstral "calibrated" unsupported:** fixed. Card confirms renormalised P(yes), threshold 0.5, no calibration claim [S12]. Wording changed to "continuous"; calibration to be measured.
6. **SG2 "best published" ambiguous:** fixed (wording corrected again in round 2, item 3). Now "best among the models compared in its own report"; added non-comparability note and Mistral's own SG2 figure (UnsafeBench 54.9) [S12][S15].
7. **SG2 policy wording inconsistent:** fixed. "Three trained policies; custom policy text accepted but untrained", quoted [S15].
8. **Shieldstral LlavaGuard result omitted a loss:** fixed. LlavaGuard-7B 81.4 vs Shieldstral 72.0 added [S12].
9. **Llama 4 EU clause too broad:** fixed. Quoted "principal place of business" and the end-user exception [S8].
10. **UnsafeBench gating wording:** fixed. API reports `gated: "auto"`, card says 1–2 days, DUA with no licence tag, card lastModified 2026-03-05 [S9][S33].
11. **NudeNet UnsafeBench figure omitted:** fixed. Sexual F1 0.624 overall (0.650 / 0.596) added with comparability caveat [S29].
12. **100k-token tier / image-count limits:** fixed. Haiku 5.5 >100k-token pricing ($0.50 / $2.50) and the 100/600 image limits (by context window) added; Haiku 5.5 is 1M context, Haiku 4.5 200k [S21][S25][S28].
13. **Haiku 5.5 resolution tier:** fixed. "Probably high-res" with tokenizer reasoning; kept as a minor open question [S21][S28].
14. **Refusal billing incomplete:** fixed. Mid-stream billing, batch `succeeded` + `stop_reason`, full category list, no Haiku 5.5 fallback credit; scenewise advised **not** to enable server-side `fallbacks` [S23].
15. **Prompt tokens ignore Haiku 5.5 tokenizer:** fixed. ~800 tokens on Haiku 4.5, ~1,050 on Haiku 5.5 [S28].
16. **Cost framed on 5-minute videos:** fixed. Added 3- and 10-thumbnail rows; 5-minute rows relabelled as upper bound.
17. **SG2 "click-through":** fixed. HF API reports `gated: "manual"` for SG2 and Llama Guard 4 [S9].
18. **OpenNSFW2 weights licence inferred:** fixed. Marked as inferred; upstream `yahoo/open_nsfw` confirmed BSD-2-Clause and archived [S1][S4].

**Rejected: none.** All 18 findings held up on re-verification.

**Recommendation changed?** The core recommendation (local tier 1 + tier-2 guard + optional Haiku, escalate-only) is unchanged. Added: a before/after split for the Video Intelligence shutdown, with SafeSearch or Gemini as the post-shutdown primary; a primary-agnostic combination rule; OpenAI omni-moderation as an optional free hosted opinion; and an explicit "no server-side fallbacks" rule. The stance was later settled by the user (U1): scenewise stays a second opinion.

## Review round 2 — resolution

Final review round (`reviews/q4-review-r2.md`). Findings were re-checked on 2026-10-08 against their sources where marked; the others were checked against the file and the reviewer's quoted source text.

1. **Stance left open (wrong):** fixed. Every passage now states the decision: scenewise stays a second opinion (U1). Open question 1 is reduced to "SafeSearch or Gemini?", and the round-1 conclusion records the decision.
2. **Route to scenewise-as-primary (wrong):** fixed. Deleted the "scenewise local tiers as primary" row and the "if the user allows scenewise to become primary" bullet. The primary mode is "not offered (U1)", the release-gate parenthesis is gone, and OpenAI omni-moderation is out of the primary table (it stays an optional tier-2 / third opinion).
3. **SG2 "best in its Table 2" (wrong):** fixed. Re-read Table 2 [S15]: SG2 is best on sexual F1 and violence 1−FPR only. GPT-4o mini (92.3) and Gemma 3 (93.8) beat it on danger 1−FPR (88.7). Added the note that 1−FPR does not measure recall.
4. **Gemini 2.5 Flash-Lite (wrong):** fixed. Re-verified the Vertex retirement date of 2026-10-20 and its named replacements [S46], and the Gemini API restriction of 2.5 models to past users [S47]. Replaced with Gemini 3.1 Flash-Lite ($0.25 / $1.50) and 3.5 Flash-Lite ($0.30 / $2.50) [S40].
5. **Gemini cost by the 258-token tiling rule (unsupported):** fixed. Re-verified the Gemini 3 `media_resolution` counts (280 / 560 / 1120; default 1120) [S41]. Recomputed with the arithmetic shown: ≈ $0.00013–0.00044 per frame. `low` is recommended for evaluation, and thinking tokens are noted.
6. **2.5 range arithmetic (minor):** superseded by item 4, because 2.5 Flash-Lite is dropped.
7. **Nemotron 3.5 Content Safety missing (missing option):** fixed. Re-verified the HF card and the Shieldstral table [S12][S45]. Added a survey row and a tier-2 bullet, with the licence inconsistency (OpenMDW 1.1 vs Nemotron Open Model License) flagged. Added OmniGuard-7B to other leads and LlavaGuard-7B UnsafeBench 63.9 to the LlavaGuard row.
8. **"Silently" (minor):** fixed. The text now says the swap is marked in the response but easily missed by a verdict-only parser. The "do not enable fallbacks" advice stays.
9. **"Free with Label Detection" (minor):** fixed. The text now says the meaning is not defined on the page and should be confirmed on the SKU page.
10. **EEA terms for Gemini (minor):** fixed. Re-verified [S48]: EEA use requires the paid tier, and prompts are logged for a limited period. Added to the Gemini row and Open question 5.
11. **Haiku 4.5 thinking tokens (minor):** fixed. The 4.5 column now assumes thinking off, and its values are recomputed: $0.0027 / $0.0073 / $0.040 / $0.020 / $0.0073, with the arithmetic shown for 3 frames. The summary range is now $0.003–0.007.

**Rejected: none.** Two questions remain unsettled: the choice of primary and the Nemotron licence. Both are now Open questions 1 and 15, phrased as decisions for the user. Open question 8 is closed by U3 (Expause is EU-based).

**Recommendation changed?** The core recommendation is unchanged. scenewise's role is now stated as decided (U1). The Gemini option moves to 3.x Flash-Lite with recomputed costs, and Nemotron 3.5 Content Safety is added as a conditional tier-2 candidate.

## Sources (all read 2026-10-08)

- [S0] Falconsai/nsfw_image_detection model card (README). https://huggingface.co/Falconsai/nsfw_image_detection/raw/main/README.md
- [S1] bhky/opennsfw2 README. https://github.com/bhky/opennsfw2
- [S2] NudeNet on PyPI, version 3.4.2, 2024-07-03, MIT classifier. https://pypi.org/project/nudenet/
- [S3] NudeNet README (v3 branch). https://raw.githubusercontent.com/notAI-tech/NudeNet/v3/README.md
- [S4] GitHub API licence fields: notAI-tech/NudeNet = AGPL-3.0; bhky/opennsfw2 = MIT (tags v0.19.0); yahoo/open_nsfw = BSD-2-Clause, `archived: true`; openai/CLIP = MIT; LAION-AI/CLIP-based-NSFW-Detector = NOASSERTION; ml-research/LlavaGuard = Apache-2.0; yueliu1999/GuardReasoner-VL = MIT. NudeNet releases v3.4-weights 2024-06-30. https://api.github.com/repos/{owner}/{repo}
- [S5] Marqo/nsfw-image-detection-384 model card. https://huggingface.co/Marqo/nsfw-image-detection-384/raw/main/README.md
- [S6] google/shieldgemma-2-4b-it model card. https://huggingface.co/google/shieldgemma-2-4b-it
- [S7] meta-llama/Llama-Guard-4-12B model card. https://huggingface.co/meta-llama/Llama-Guard-4-12B and https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Guard4/12B/MODEL_CARD.md
- [S8] Llama 4 Acceptable Use Policy (EU multimodal clause and end-user exception). https://raw.githubusercontent.com/meta-llama/llama-models/main/models/llama4/USE_POLICY.md. Context: https://www.llama.com/faq/
- [S9] Hugging Face model and dataset API metadata (licence tags, safetensors param totals, lastModified, gating: SG2 `manual`, Llama Guard 4 `manual`, UnsafeBench `auto`). https://huggingface.co/api/models/{id}, https://huggingface.co/api/datasets/{id}
- [S10] Freepik/nsfw_image_detector model card. https://huggingface.co/Freepik/nsfw_image_detector/raw/main/README.md
- [S11] AI Weekly, "Mistral open-sources Shieldstral" (2026-08-04, updated 2026-08-10). https://aiweekly.co/alerts/mistral-open-sources-shieldstral-a-3b-multimodal-safety-guard
- [S12] mistralai/Shieldstral-1.0-3B model card (score computation, threshold, multimodal benchmark table). https://huggingface.co/mistralai/Shieldstral-1.0-3B
- [S13] Mistral, "Shieldstral" announcement (2026-08-04). https://mistral.ai/news/shieldstral/
- [S14] Gemma Terms of Use (last modified 2026-04-01). https://ai.google.dev/gemma/terms
- [S15] ShieldGemma 2 technical report, arXiv 2504.01081. https://arxiv.org/html/2504.01081
- [S16] Llama 4 Community License (effective 2025-04-05). https://raw.githubusercontent.com/meta-llama/llama-models/main/models/llama4/LICENSE
- [S17] AIML-TUDA/LlavaGuard-v1.2-7B-OV-hf model card. https://huggingface.co/AIML-TUDA/LlavaGuard-v1.2-7B-OV-hf. Repo: https://github.com/ml-research/LlavaGuard
- [S18] LAION-AI/CLIP-based-NSFW-Detector README. https://github.com/LAION-AI/CLIP-based-NSFW-Detector
- [S19] Anthropic Usage Policy, effective 2025-09-15. https://www.anthropic.com/legal/aup
- [S20] Claude docs, "Content moderation" use-case guide. https://platform.claude.com/docs/en/about-claude/use-case-guides/content-moderation
- [S21] Claude docs, "Vision" (token formula, tiers, image-count limits by context window, limitations). https://platform.claude.com/docs/en/build-with-claude/vision
- [S22] Claude docs, "Handling stop reasons". https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons
- [S23] Claude docs, "Refusals and fallback" (categories, pre-output and mid-stream billing, server-side fallbacks beta, batch refusals, Haiku 5.5 fallback credit). https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
- [S24] Claude Help Center, "CSAM detection and reporting" (2026-03-16). https://support.claude.com/en/articles/9020328-csam-detection-and-reporting
- [S25] Claude docs, "Pricing" (Haiku 5.5 ≤100k and >100k-token prices). https://platform.claude.com/docs/en/about-claude/pricing
- [S26] Google Video Intelligence REST `videos.annotate` (ExplicitContentDetectionConfig; deprecation banner; page updated 2025-07-09). https://docs.cloud.google.com/video-intelligence/docs/reference/rest/v1/videos/annotate and the deprecations page (updated 2026-10-07): https://docs.cloud.google.com/video-intelligence/docs/deprecations
- [S26a] Google Video Intelligence `Likelihood` enum (updated 2025-07-09). https://docs.cloud.google.com/video-intelligence/docs/reference/rest/v1/Likelihood
- [S26b] Google Video Intelligence `AnnotateVideoResponse` (ExplicitContentAnnotation / ExplicitContentFrame). https://docs.cloud.google.com/video-intelligence/docs/reference/rest/v1/AnnotateVideoResponse
- [S27] Google, "Analyze videos for explicit content" (updated 2026-10-07). https://docs.cloud.google.com/video-intelligence/docs/analyze-safesearch
- [S28] Claude docs, Claude Haiku 5.5 overview (released 2026-10-07; 1M context; tokenizer ~30% more tokens than Haiku 4.5; adaptive thinking default, effort `medium`; tiered pricing). https://platform.claude.com/docs/en/models/haiku-5-5/overview and the models overview https://platform.claude.com/docs/en/about-claude/models/overview
- [S29] Qu et al., "UnsafeBench", arXiv 2405.03486 v3 (ACM CCS 2025), incl. Table 3 NudeNet Sexual F1. https://arxiv.org/abs/2405.03486, https://arxiv.org/html/2405.03486v3
- [S30] ml-research/Q16 README. https://github.com/ml-research/Q16
- [S31] prithivMLmods, "Image-Guard-2.0" HF blog (2025-10-14). https://huggingface.co/blog/prithivMLmods/image-guard-models
- [S32] Web search leads (not primary): GuardReasoner-VL arXiv 2505.11049 https://arxiv.org/abs/2505.11049. Summary: https://liner.com/review/guardreasonervl-safeguarding-vlms-via-reinforced-reasoning. Curated list: https://github.com/ant-research/awesome-mllm-guardrails
- [S33] yiting/UnsafeBench dataset card (DUA, gating text; card text only, no data accessed). https://huggingface.co/datasets/yiting/UnsafeBench
- [S34] LAION, "Releasing Re-LAION-5B" (2024-08-30). https://laion.ai/blog/relaion-5b/
- [S35] Web search on RWF-2000 / XD-Violence / NPDI / LSPD access terms (not primary; terms unverified). https://arxiv.org/abs/1911.05913v1, https://roc-ng.github.io/XD-Violence/, https://arxiv.org/pdf/1511.08899, https://data.mendeley.com/datasets/jkrzbbbch7/1
- [S36] Google Cloud Vision, "Detect explicit content (SafeSearch)" (updated 2026-10-07; no deprecation banner). https://docs.cloud.google.com/vision/docs/detecting-safe-search
- [S37] Google Cloud Vision pricing (SafeSearch tiers; no deprecation notice; no page date shown). https://cloud.google.com/vision/pricing
- [S38] Google Cloud Vision deprecations page (updated 2026-10-07; lists only Celebrity Recognition and OCR On-Prem). https://docs.cloud.google.com/vision/docs/deprecations
- [S39] OpenAI, Moderation guide (`omni-moderation-latest`, free, image categories, CSAM statements). https://developers.openai.com/api/docs/guides/moderation
- [S40] Google, Gemini API pricing (updated 2026-10-07; Flash-Lite prices). https://ai.google.dev/gemini-api/docs/pricing
- [S41] Google, Gemini API image understanding (older 258-token tiling rule; updated 2026-09-23) https://ai.google.dev/gemini-api/docs/image-understanding, and Media resolution (Gemini 3 models: low 280, medium 560, high 1120, unspecified 1120, ultra_high 2240 tokens per image; updated 2026-09-23) https://ai.google.dev/gemini-api/docs/media-resolution
- [S42] Google Cloud, "Gemini for safety filtering and content moderation" (updated 2026-10-07; still recommends Gemini 2.5 Flash-Lite for filtering, stale against [S46][S47]; turn off safety filters; not for CSAM). https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-for-filtering-and-moderation
- [S43] AWS Rekognition pricing ($0.0010 per image first tier for Group 2 incl. DetectModerationLabels; 1,000 images/month free for 12 months) and moderation guide. https://aws.amazon.com/rekognition/pricing/, https://docs.aws.amazon.com/rekognition/latest/dg/moderation.html
- [S44] Azure AI Content Safety pricing (F0: 5,000 images/month, no overage; Standard image price not shown on page). https://azure.microsoft.com/en-us/pricing/details/content-safety/
- [S45] NVIDIA Nemotron 3.5 Content Safety: HF model card (Gemma-3-4B-it LoRA, single image, custom policies, OpenMDW 1.1 + Gemma terms, "ready for commercial use", released 2026-06-02) https://huggingface.co/nvidia/nemotron-3.5-content-safety; NGC model page (names "NVIDIA Nemotron Open Model License" + Gemma terms) https://catalog.ngc.nvidia.com/orgs/nim/nvidia/models/nemotron-3.5-content-safety/-; NGC governing terms (OpenMDW 1.1) https://catalog.ngc.nvidia.com/orgs/nim/nvidia/models/nemotron-3.5-content-safety/-/governing-terms. NGC wording seen via web search.
- [S46] Google Cloud Vertex AI, Model versions and lifecycle (gemini-2.5-flash-lite retires 2026-10-20; replacements gemini-3.8-flash, gemini-3.1-flash-lite, Gemma 4; updated 2026-10-07). https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
- [S47] Google, Gemini API deprecations (2.5 Flash-Lite: no shutdown date; access limited to past users; new projects directed to 3.5 Flash-Lite or 3.8 Flash; updated 2026-10-07). https://ai.google.dev/gemini-api/docs/deprecations
- [S48] Google, Gemini API Additional Terms of Service ("You may use only Paid Services when making API Clients available to users in the European Economic Area"; paid-service prompt logging for a limited period). https://ai.google.dev/gemini-api/terms
