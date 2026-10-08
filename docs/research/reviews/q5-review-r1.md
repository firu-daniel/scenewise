# Review r1: q5-labels.md

Reviewer: a fresh review agent that did not write the file. I re-opened every source below on 2026-10-08 unless noted. I did not edit the reviewed file. The Video Intelligence deprecation was confirmed by another review, so I did not re-verify it here.

Severity counts: wrong 2 · unsupported 1 · missing option 7 · design concern 6 · minor 12 (28 findings in total).

**Headline:** most of the numbers re-check correctly. That covers SigLIP 2, PE-Core, OpenCLIP CSV, MobileCLIP2 and DFN, the licences, the PyPI versions, the Haiku 5.5 prices and the image-token formula, the Firestore limits and pgvector. The doc has two factual errors. The ">10,000 entities" figure belongs to **Cloud Vision**, not Video Intelligence. The "≥ $0.10 per video" LABEL_DETECTION floor is contradicted by Google's own worked example on the pricing page. The biggest gaps are three options it does not consider: Cloud Vision label detection, Gemini Embedding 2 and SigLIP 2 NaFlex. The main design concerns:
- "Local = $0" ignores Cloud Run compute, which is about the same cost as Haiku 5.5 here.
- The YouTube paper is cited for something it does not show.
- The headline puts embeddings first, although Expause consumes labels today.
- The taxonomy schema is over-built for v1.

## Findings

1. **Claim (§2 Vocabulary, OQ4):** LABEL_DETECTION has "over 10,000 entities" per Google's 2017 blog [S5].
   → The source is https://cloud.google.com/blog/products/gcp/cloud-machine-learning-perception-services-updates-cloud-video-intelligence-enters-beta-and-cloud-vision-gets-new-features (2017-06-30). The sentence sits in the **Cloud Vision** section: "Updated label detection model that has over 2x increase in recall, and an increased overall vocabulary to over 10,000 entities". The post gives no entity count for Video Intelligence.
   → **wrong** (misattributed)
   → Correction: say that no public vocabulary size exists for Video Intelligence LABEL_DETECTION, and that the 10,000+ figure is Cloud Vision's (2017). Keep OQ4 open.

2. **Claim (§1.7, §5):** "LABEL_DETECTION costs $0.10/min … rounded up per minute, so at least $0.10 per video", and "≥ $0.10 per video beyond the free tier, because of per-minute rounding". OQ3 says the pricing page did not render.
   → https://cloud.google.com/video-intelligence/pricing (read 2026-10-08 with curl, which renders fine) does say "Prices are per minute. Partial minutes are rounded up to the next full minute. Volume is per month." But the page's own worked example is "1000 label detection requests, each containing a 1m22s long video … (82*1000)/60 = 1366.66 minutes … the additional 366.66 minutes cost $0.10 per minute, totaling $36.67". So Google prorates each 82 s request instead of billing it as 2 minutes, which suggests rounding applies to the monthly total. The rates are confirmed: label detection free for 0–1,000 min, then $0.10/min; shot detection $0.05/min, or "free with Label detection"; streaming label detection $0.12/min.
   → **wrong** (the "≥ $0.10 per video" floor is contradicted by the source's own example)
   → Correction: cost per video ≈ (synthetic-video seconds / 60) × $0.10 beyond 1,000 free min/month. For example, a 20 s synthetic video costs about $0.033 and a 100 s one about $0.167. Make it depend on OQ2 (the video length). Close OQ3, since the figures are confirmed on the live page.

3. **Claim (§1.7, §5):** "Local SigLIP is $0 in AI cost", which the doc sets against Haiku at about $0.0004 per video.
   → Cloud Run pricing (https://cloud.google.com/run/pricing, read 2026-10-08) for instance-based billing in us-central1 is $0.000018 per vCPU-second and $0.000002 per GiB-second. The doc's own figure of about 7 s for 100 thumbnails on 4 vCPU/4 GiB works out to 4×7×0.000018 + 4×7×0.000002 ≈ **$0.00056 per video**, before model-load cold starts and before slower x86 vCPUs. That is the same order as Haiku 5.5 ($0.00037) and as Gemini Embedding 2 for a single sprite ($0.00012 per image, finding 16).
   → **design concern**
   → Correction: replace "$0" with an estimated compute cost per video. Base the case for the local model on privacy, on getting embeddings and labels from one pass, and on vendor independence, not on cost. Cost alone does not separate the options at Expause's scale.

4. **Claim (§3):** the CPU latencies were "measured … single timed run after warm-up": SigLIP 2 B/16 66 ms, PE-Core-B 67, PE-Core-S-384 76 and So400m 707 ms per image.
   → I re-ran it on the same machine (Apple M4, 4 performance cores) with the author's environment (`torch` 2.14.1, `open_clip_torch` 3.3.0, `timm` 1.0.30, 4 threads, fp32, batch 16, random tensors, median of 5 runs). Results: SigLIP2-B/16 **36.5 ms** (min 36.1, max 38.1), PE-Core-B/16 **41.1 ms**, PE-Core-S-16-384 **51.5 ms**, So400m-14-378 **690 ms** (min 667, max 707). SigLIP 2 B/16 on one thread came out at 54 ms. The image-tower parameter counts match: 92.9 M, 93.7 M, 23.8 M and 428.2 M. The So400m figure reproduces. The B- and S-size figures are about 1.5–1.8× too slow, most likely because of contention from other processes during a single unrepeated run.
   → **minor** (plausible, conservative, but the method is weak)
   → Correction: report the median of at least 5 runs and say the machine was idle. State that image decode and resize, and the cold-start model load (relevant on Cloud Run), are excluded. The ranking and "~4–7 s per 100 thumbnails" still hold.

5. **Claim (§1.1, §4):** "Recommenders consume dense embeddings natively: YouTube's candidate generator averages embeddings …" [S20], offered as support for mean-pooled frame (content) embeddings.
   → Covington et al. 2016 (https://research.google/pubs/deep-neural-networks-for-youtube-recommendations/) averages **learned embeddings of watched video IDs** to represent the user ("a user's watch history is represented by a variable-length sequence of sparse video IDs which is mapped to a dense vector representation via the embeddings"). It does not use pixel or frame content embeddings, and it serves by nearest neighbour against learned item vectors. (I could not machine-extract the PDF this session. The quoted context is from the paper's §3.1 as published.)
   → **unsupported** (the citation does not show that content embeddings help a recommender)
   → Correction: cite S20 only for "averaging embeddings works well and is served with dot-product ANN". Say that content embeddings mainly help cold start and content-to-content similarity, and that the paper does not show their value for Expause's recommender. That value should be checked offline (OQ11).

6. **Claim (§3 table, OQ8):** OpenAI ViT-L-14 licence "not stated on HF card", Commercial "?".
   → https://huggingface.co/openai/clip-vit-large-patch14 (read 2026-10-08) has no licence tag, but its "Out-of-Scope Use Cases" section says: "Any deployed use case of the model - whether commercial or not - is currently out of scope."
   → **minor** (resolvable now)
   → Correction: mark OpenAI CLIP weights as **No (deployed use out of scope per model card)**.

7. **Claim (§3 table, OQ8):** the EVA02 and SigLIP v1 licences are "not verified" or "assumed".
   → HF API (read 2026-10-08): `timm/eva02_base_patch16_clip_224.merged2b` is `license:mit`, and `google/siglip-so400m-patch14-384` is `license:apache-2.0`.
   → **minor**
   → Correction: fill in MIT (EVA02 open_clip/timm weights) and Apache-2.0 (SigLIP v1), and shrink OQ8. Also confirmed: DFN5B's card carries the same `apple-amlr` tag as MobileCLIP2, though the card has no licence link.

8. **Claim (§3 table, "Image tower params" column):** jina-clip-v2 "0.9 B (EVA02-L image tower)", MetaCLIP 2 H/14 "~2 B".
   → https://huggingface.co/jinaai/jina-clip-v2 says 0.9 B is the total: "561M-parameter text encoder and a 304M-parameter image encoder". The MetaCLIP 2 card's "2B params" is also the full model.
   → **minor**
   → Correction: put 304 M (jina) in that column. Mark MetaCLIP 2 as "~2 B total". The non-commercial verdict does not change.

9. **Claim (§5):** Haiku 4.5 ≈ $0.0037 per video for the same 1600×900 sprite.
   → The Vision page (https://platform.claude.com/docs/en/build-with-claude/vision, read 2026-10-08) places Haiku 4.5 in the **Standard** tier: 1568 px long edge and 1568 visual tokens maximum. A 1600×900 image is downscaled to at most 1568 tokens, not 1914. The pricing page also says that models from 4.7 on use a tokenizer producing "approximately 30% more tokens", so the ~1000 prompt tokens are fewer on Haiku 4.5.
   → **minor**
   → Correction: ≈ (1568 + ~770) × $1/MTok + 150 × $5/MTok ≈ **$0.0031**. The Haiku 5.5 arithmetic re-checks: 58×33 = 1914; (1914+1000)×$0.10/MTok + 150×$0.50/MTok = $0.000366; Batch $0.000183.

10. **Claim (§5, OQ9):** "Adaptive thinking on Haiku 5.5 may add output tokens."
    → The models overview (https://platform.claude.com/docs/en/about-claude/models/overview, read 2026-10-08) lists Haiku 5.5 with adaptive thinking and default effort `medium`. Pricing says output is charged at $0.50/MTok, and thinking counts as output.
    → **minor**
    → Correction: say concretely that a few hundred thinking tokens would double the per-video cost. Prescribe `effort: low`, or thinking disabled (the Models API reports `capabilities.thinking.types.disabled.supported` to check this), plus a small `max_tokens` and structured output for tagging.

11. **Claim (§1.2, §5):** SigLIP latency is quoted for "100 thumbnails", while Haiku cost is quoted for one 1600×900 sprite sheet.
    → This is internal to the doc. If 100 thumbnails go on a 1600×900 sheet, each is about 160×90 px, and vertical 9:16 thumbnails become about 50×90. That is a very different input from 100 full thumbnails, and it is below the "very small images under 200 pixels" accuracy warning on the Vision page.
    → **design concern**
    → Correction: compare like with like, for example K thumbnails per video at a stated resolution for both tiers. State K, which depends on Expause's real thumbnail count per video (OQ2).

12. **Claim (§4 storage table, OQ5):** float32 sizes (768-d = 3 KB, so ~3 GB per 1 M videos), and "Firestore's on-disk accounting … not verified".
    → https://firebase.google.com/docs/firestore/storage-size (read 2026-10-08): vector values are "8 bytes per dimension".
    → **minor** (resolvable)
    → Correction: in Firestore, 768-d = 6 KB and 1152-d = 9 KB per vector (about 6–9 GB per 1 M videos), plus index-entry storage. Partly close OQ5.

13. **Claim (§1.6, §4):** "Firestore vector search fits Expause's stack", and kNN reads billed at 1 read per 100 entries, with growth with collection size "not verified".
    → https://firebase.google.com/docs/firestore/pricing (read 2026-10-08): "one read operation for each batch of up to 100 kNN vector index entries read by the query". Its example: a `limit: 5` query "reads 1,550 kNN vector index entries", billed 16 + 5 reads. The vector-search page says "The index type must be `flat`". A flat index searches exhaustively, so the entries read scale with the candidate set, not with `limit`.
    → **design concern**
    → Correction: estimate it. With no pre-filter over 1 M videos, a query reads about 1 M/100 = 10,000 reads. Multiply by the Firestore read price to get the cost per query. Recommend pre-filtered candidate sets (by language, region or recency) or another ANN store for anything beyond small corpora. "Fits the stack" needs this qualifier.

14. **Claim (§1.6, §4):** "at most 1000 results".
    → https://firebase.google.com/docs/firestore/vector-search (Limitations, "Last updated 2026-10-07 UTC"): "The maximum number of documents to return from a nearest-neighbor query is 1000 (Standard edition limitation only)". It also says: "Only the Python, Node.js, Go, and Java client libraries support vector search."
    → **minor**
    → Correction: add "(Standard edition)" and the client-library restriction. Expause's Dart/Flutter client cannot query vectors directly, so queries must go through a server or Cloud Function.

15. **Missing option: Google Cloud Vision label detection.** The doc never mentions it.
    → https://cloud.google.com/vision/pricing (read 2026-10-08): label detection free for the first 1,000 units/month, then $1.50 per 1,000 units (1,001–5 M) and $1.00 per 1,000 above 5 M. The page shows no deprecation notice. It is the API the ">10,000 entities" figure actually describes (finding 1).
    → **missing option** (high relevance)
    → Correction: add it as the closest continuity path after the Video Intelligence shutdown. It works per thumbnail, uses the same Google entity vocabulary (verify that `mid`s match Video Intelligence `entityId`s), and requires no synthetic video. Cost: about $0.0015 per thumbnail, so 100 thumbnails come to about $0.15 per video, or $0.0015 for one sprite. Put it in OQ1.

16. **Missing option: Gemini Embedding 2 (hosted multimodal embeddings).**
    → https://ai.google.dev/gemini-api/docs/embeddings (read 2026-10-08) lists `gemini-embedding-2` as **Stable**, "the first multimodal embedding model in the Gemini API": images (at most 6 per request), video (at most 120 s, at most 32 frames), text, a shared 8,192-token input, and output dimensions 128–3072 (768/1536 recommended). Pricing (https://ai.google.dev/gemini-api/docs/pricing): image $0.00012 each ($0.00006 batch), video $0.00079 per frame, text $0.20/MTok.
    → **missing option** (high relevance)
    → Correction: compare it with local SigLIP 2. It gives text and image in one space, so zero-shot labels still work by dot product. It is on Google, which is Expause's stack and Google's named migration family. 768-d fits Firestore's 2048 limit. It also accepts the synthetic video directly. Its drawbacks are that data leaves the infrastructure and that it creates vendor lock-in for stored vectors. The legacy Vertex `multimodalembedding@001` should be named as considered and set aside. I could not read its current status: the docs page timed out in the fetch tool.

17. **Missing option: Gemini Flash-Lite as the rich-tag tier.** The doc names Haiku only.
    → https://ai.google.dev/gemini-api/docs/pricing (read 2026-10-08): `gemini-3.5-flash-lite` costs $0.30 input and $2.50 output per MTok (thinking included), with Batch at half price.
    → **missing option** (low; it is more expensive than Haiku 5.5)
    → Correction: add one line saying it was considered. Haiku 5.5 is 3× cheaper on input and 5× cheaper on output, so it stays the first choice. Gemini matters only if Expause standardises on Google after the shutdown.

18. **Missing option: SigLIP 2 NaFlex (native aspect ratio).** Expause thumbnails are presumably 9:16. Fixed-resolution SigLIP and PE preprocessing squashes or crops them to a square.
    → The SigLIP 2 paper (https://arxiv.org/html/2502.14786, Appendix B) says NaFlex "processes images at their native aspect ratio" with variable sequence length. The checkpoints `google/siglip2-base-patch16-naflex` and `google/siglip2-so400m-patch16-naflex` are Apache-2.0 (HF API, read 2026-10-08). open_clip **main** has `ViT-B-16-SigLIP2-naflex.json`, but the **v3.3.0 tag has no NaFlex configs** (GitHub API, read 2026-10-08).
    → **missing option**
    → Correction: list NaFlex B/16 as an option for vertical thumbnails, available through `transformers` today. It should be included in the OQ10 eval. Note that the single-dependency plan ("open_clip only") does not cover it until the next open_clip release.

19. **Missing option: smaller and intermediate SigLIP 2 sizes.**
    → SigLIP 2 Table 1 (same URL): B/32 @256 = 74.0 % with 64 tokens, against 196 for B/16 @224, so roughly 3× cheaper on CPU. B/16 @384 = 80.6 %. So400m/16 @256 = 83.4 %. All are present as open_clip configs (`ViT-B-32-SigLIP2-256`, `ViT-B-16-SigLIP2-384`, `ViT-SO400M-16-SigLIP2-256`).
    → **missing option** (minor)
    → Correction: add B/32-256 as the "small" Apache option next to PE-Core-S. It is the cheapest way to stay in the SigLIP 2 family.

20. **Missing option: video-native embedding models (VideoPrism, InternVideo2).**
    → The HF API (read 2026-10-08) lists `google/videoprism-lvt-base-f16r288` and `-large-f8r288` as Apache-2.0, with a video-text (LvT) tower. The reference implementation is JAX, with keras-hub and community PyTorch ports. `OpenGVLab/InternVideo2-CLIP-1B-224p-f8` is tagged Apache-2.0 but is gated.
    → **missing option** (low relevance)
    → Correction: add a line saying they were considered and set aside, because Expause's input is a slideshow of unrelated thumbnails with no temporal continuity for a video model to exploit, and because they cost more on CPU. Revisit for real-video adopters.

21. **Missing option: Vertex `multimodalembedding@001`.** It is covered in finding 16. I record it separately only so the count matches the requested list.
    → https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-multimodal-embeddings (fetch truncated, status not read).
    → **missing option** (low)
    → Correction: mention it as the older Vertex model (1408-d image/video/text), with its lifecycle status to be checked. Prefer Gemini Embedding 2.

22. **Design concern: the taxonomy schema is over-built for v1** (§6). In one schema it has per-label backends (`backend: claude`), negative prompts, `exclusive_groups`, `propagate_up` plus the "parent ≥ max(child)" invariant, four aggregate modes plus `min_frame_fraction`, softmax-over-siblings mode, four calibration methods including isotonic tables, per-label template overrides, and per-request inline taxonomies plus per-label overrides.
    → This is my own judgement; no source applies.
    → **design concern**
    → Correction: v1 should have `id`, `name`, `prompts[]`, optional `parent` (display and roll-up only), optional `threshold`, plus global `templates` and `top_k`. Always report both `mean` and `max`. Add calibration only as output of `scenewise calibrate`. Defer negatives, exclusive groups, softmax mode, isotonic calibration and per-label backend routing until an eval shows they are needed. Per-label `backend: claude` makes the cost and latency of each request depend on what the taxonomy contains, so make the rich tier a per-request or per-deployment switch instead.

23. **Claim (§6 example YAML):** the example is presented as a valid taxonomy.
    → It is inconsistent on its own terms. `food.cooking` has `parent: food`, but there is no `food` label. `exclusive_groups` names `format.vertical` and `format.horizontal`, which are not defined. The `model` block binds a taxonomy to one model, although thresholds are model-specific and the cache key is already `(model_id, taxonomy_hash)`.
    → **minor**
    → Correction: fix the example so it validates against its own schema. Either move thresholds into a per-model `calibrations[model_id]` map, or state that a taxonomy file is only valid for the named model.

24. **Claim (§1.2, §3, §6):** "each label gets an independent probability"; `threshold: 0.10 # on the calibrated probability` with `calibration.default: none`; and "score -= max(sim(negatives))".
    → The SigLIP abstract (https://arxiv.org/abs/2303.15343) supports only "operates solely on image-text pairs". Nothing in S19 says zero-shot sigmoid outputs are calibrated per-label probabilities. In practice they depend on the prompt wording and the learned bias.
    → **design concern**
    → Correction: call them "independent scores" and not probabilities. Do not ship a default numeric threshold without calibration; use top-k plus a margin until `calibrate` has run. Specify the space in which negatives are subtracted (cosine before the logit scale and bias, or after). The current text is ambiguous.

25. **Design concern: "embeddings first, labels second" as the headline** (§1.1).
    → Expause today consumes sparse LABEL_DETECTION entities. OQ11 admits that nobody knows whether Expause's recommender can use dense vectors. After the shutdown (2027-09-14), Expause's real need is **label continuity**.
    → **design concern**
    → Correction: compute both in one pass, but make labels the primary contract, with an optional mapping to entity names or ids compatible with the old LABEL_DETECTION output. Make the embedding an opt-in output until OQ11 is answered. Also note the lock-in cost: changing the model re-embeds every stored vector. That favours a stable, widely mirrored checkpoint, or a hosted one with a lifecycle commitment.

26. **Minor: multilingual coverage is not discussed.**
    → SigLIP 2 is trained on multilingual WebLI with a multilingual tokenizer (S6, abstract: "multilingual"). The PE-Core README does not claim multilingual text.
    → **minor**
    → Correction: note that adopter taxonomies in other languages favour SigLIP 2 over PE-Core, and add this as a criterion in OQ10.

27. **Minor: S2 points to `docs.cloud.google.cn`.**
    → The canonical page is https://docs.cloud.google.com/video-intelligence/docs/deprecations.
    → **minor**
    → Correction: cite the .com URL.

28. **Minor: [S9] reads model configs from open_clip `main`, but the doc pins 3.3.0.** v3.3.0 was released on 2026-02-27, and `main` is about 7 months ahead (it has NaFlex and other configs, finding 18).
    → https://github.com/mlfoundations/open_clip/releases (read 2026-10-08).
    → **minor**
    → Correction: cite the `v3.3.0` tag for configs. Every config the doc recommends does exist at v3.3.0: I loaded `ViT-B-16-SigLIP2`, `PE-Core-B-16`, `PE-Core-S-16-384` and `ViT-SO400M-14-SigLIP2-378` with 3.3.0 and checked `embed_dim` (768/1024/512/1152).

## Claims verified correct

- LABEL_DETECTION output shape: segment, shot and frame levels; frame level "with one frame per second sampling"; `entityId`, `description`, `languageCode`; `categoryEntities`; the `SHOT_AND_FRAME_MODE` recommendation. REST `LabelDetectionConfig`: `SHOT_MODE` default; `builtin/stable` default, `builtin/latest`; frame 0.4 and video 0.3 defaults, range [0.1, 0.9] with clipping; `stationaryCamera`. Source: analyze-labels and `videos.annotate`, read 2026-10-08. The price is $0.10/min after 1,000 free min, and shot detection is free with label detection.
- SigLIP 2 Table 1: B/16 224 = 78.2, 256 = 79.1; L/16 256 = 82.5; So400m/14 384 = 84.1. Embed dims 768/768/1024/1152 (open_clip configs). Apache-2.0 on `google/siglip2-*` and `timm/ViT-B-16-SigLIP2`.
- PE-Core (perception_models README): S/16 384 = 72.7 % (K400 55.0); B/16 224 = 78.4 % (K400 65.6); L/14 336 = 83.5 % (K400 73.4); G/14 448 = 85.4 %. Apache-2.0 for code and weights; `timm/PE-Core-*` tagged apache-2.0.
- OpenCLIP CSV: ViT-B-32 DataComp-XL 69.17 % (151.28 M); SigLIP v1 So400m-384 83.08 % (877.96 M); EVA02-B-16 74.72 %; EVA02-L-14-336 80.39 %; OpenAI ViT-L-14 75.54 %; DFN5B H-14-378 986.71 M. The LAION DataComp B-32 checkpoint is MIT.
- MobileCLIP2 S0…S4 at 71.5…81.9 % and 11.4–321.6 M image params, `apple-amlr`. Apple ML Research Model License: "does not include any commercial exploitation, product development or use in any commercial product or service." DFN5B is `apple-amlr` at 0.84218. MetaCLIP 2 (including the newer S16 and mT5 variants) and jina-clip-v2 are CC-BY-NC-4.0, and jina-clip-v2 is commercial via API only. jina-clip-v2 is 512 px and 1024-d with Matryoshka down to 64.
- PyPI: `open-clip-torch` 3.3.0 (2026-02-27, MIT), `transformers` 5.19.0 (2026-10-06), `torch` 2.14.1 (2026-09-30), `sentence-transformers` 6.1.0 (2026-09-18), `timm` 1.0.30. open_clip releases: SigLIP2 in v2.31.0, MetaCLIP2 in v3.1.0, MobileCLIP2 in v3.2.0. PE-Core loads under 3.3.0, which I tested.
- `multilingual-e5-small` and `bge-m3` are MIT. `embeddinggemma-300m` is under the Gemma licence and gated.
- Haiku 5.5: $0.10 / $0.50 per MTok for prompts up to 100k, Batch $0.05 / $0.25, ID `claude-haiku-5-5`, described "for high-volume, latency-sensitive tasks such as classification", retirement not sooner than 2027-10-07. Image tokens = ⌈w/28⌉×⌈h/28⌉. The high-resolution tier (4.7 and later) allows 2576 px and 4784 tokens. The 5.5 arithmetic is correct.
- Firestore: at most 2048 dimensions; `flat` only; EUCLIDEAN, COSINE and DOT_PRODUCT; pre-filter through a composite index; no real-time listeners; page last updated 2026-10-07. kNN billing is one read per ≤100 index entries.
- pgvector v0.8.7: indexed `vector` up to 2,000 dimensions and `halfvec` up to 4,000.
- vec2text: "recover 92% of 32-token text inputs exactly". The SigLIP abstract quote is accurate. The CLIP prompt-ensembling figures (+1.3 %, +3.5 %, "almost 5%") match §3.1.4 of arXiv:2103.00020 as I recall it; I did not re-extract the PDF.
- The test machine is an Apple M4 with 4 performance cores, which matches "4 threads". The So400m latency reproduces within 3 %.
