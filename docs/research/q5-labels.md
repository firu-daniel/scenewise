# Q5 — Labels for feed recommendations (roadmap item 4)

Research date: 2026-10-08 (revision r2, after reviews `reviews/q5-review-r1.md` and `reviews/q5-review-r2.md`; r2 is the final round). Every claim carries a source tag `[Sn]`. The Sources section gives the URL, the date read (all 2026-10-08) and the version where one exists. Statements marked **(inference)** are this author's reasoning, not a sourced fact. Figures marked **(computed)** are arithmetic on cited inputs; the inputs are named next to them. Anything unverified is listed under Open questions instead of being guessed.

---

## 1. Summary / recommendation

**Context.** Google has deprecated the whole Video Intelligence API: "Starting on September 14, 2026, Video Intelligence API is officially deprecated and will no longer be supported. You can continue using Video Intelligence API until September 14, 2027, when it will be shut down. We recommend migrating to Gemini family of models." [S2]. The owner has decided (U1, `user-decisions.md`) that **scenewise stays a complement**: Expause moves its own primary label signal elsewhere (for example Gemini or Cloud Vision), and scenewise remains a second opinion. Choosing that primary is **Expause's call, not scenewise's**. This document only lists the candidates (§5a) so the choice is informed.

What Expause consumes today [S49][S53]: `analyzeVideo` sends a synthetic video, built from the preview JPEGs and stretched to 5 s, with `features: ['LABEL_DETECTION', 'EXPLICIT_CONTENT_DETECTION']` and no `videoContext`, so the API defaults apply (`SHOT_MODE`, `builtin/stable`, video threshold 0.3 [S4]). It keeps only `segmentLabelAnnotations`, and from them `entity.description` and the last segment's confidence. The confidence is used **only to sort**. The top `analyzeVideoMaxLabels` (10) **names** are stored as `contentTags`, a `string[]`; no confidence, entity id, timestamp or vector is stored. The same call also feeds Expause's `explicit` signal, so the 2027-09-14 shutdown removes that too; explicit-content detection is the moderation question (q4), not this document's.

Recommendation:

1. **Labels are the primary output; embeddings are opt-in.** For each video, scenewise embeds every preview thumbnail with one open-weight contrastive model. It scores an adopter-supplied taxonomy against the cached text embeddings and returns a list of `{id, name, score_max, score_mean, calibrated}`, at most `top_k` long. Its `name`s map directly onto what Expause stores today (up to 10 label names). The pooled, L2-normalised video embedding comes out of the same pass at almost no extra cost. It is returned only when the request asks for it (`outputs: ["labels", "video_embedding"]`), until Expause confirms its recommender can use dense vectors (OQ11). Content embeddings mainly help cold start and content-to-content similarity. The YouTube paper [S20] shows only that *averaging learned ID embeddings* works and that dot-product nearest-neighbour serving is practical. It does not show that frame-content embeddings improve a recommender. That value must be checked offline (OQ11).
2. **Default model: SigLIP 2 ViT-B/16 (224 px) through `open_clip_torch` 3.3.0.** 78.2 % zero-shot ImageNet-1k [S6], Apache-2.0 weights [S7][S8][S31], 768-d [S45], multilingual text tower [S6]. Measured at a **median of 37 ms per image** on an Apple M4 (4 threads, batch 16; method in §3). Options, all Apache-2.0:
   - **Small:** SigLIP 2 **B/32-256** (74.0 % [S6], 17 ms/img measured), or PE-Core-S/16-384 (72.7 % [S11], 52 ms/img).
   - **Alternative:** PE-Core-B/16 (78.4 %, Kinetics-400 zero-shot 65.6 % [S10][S11], 1024-d, 43 ms/img). Its text tower is not documented as multilingual, so SigLIP 2 is preferred for non-English taxonomies (inference from [S6][S11]). Only the **PE-Core** weights (Apache-2.0) are recommended. The same `perception_models` repo also hosts Perception-LM, which is under a separate non-Apache licence (HF tag `license:other`, manually gated [S56]) and built on Llama; it is never recommended (U3).
   - **Vertical-thumbnail option:** SigLIP 2 **NaFlex B/16** keeps the native 9:16 aspect ratio instead of squashing it to a square, which the open_clip SigLIP 2 and PE-Core preprocessing do (`resize_mode: squash`) [S51]. It runs through `transformers` (SigLIP 2 support has been in regular releases since **v4.50.0**, 2025-03-21; tested here with **5.19.0**) [S44][S29]. It is *not* in the open_clip 3.3.0 configs, only on `main` [S45]. The paper finds the standard B variant *better* than NaFlex B on natural-image benchmarks, with NaFlex ahead on aspect-sensitive OCR/document benchmarks [S6]. So it is an eval candidate (OQ10), not the default. Measured at 53 ms/img with `max_num_patches=256`.
   - **Quality:** SigLIP 2 So400m/14-384 (84.1 % [S6], 1152-d), about 0.7–0.85 s per image on the M4. That is too slow for CPU-only serving at volume (inference).
3. **Do not use MobileCLIP/MobileCLIP2, DFN, MetaCLIP 2, jina-clip-v2 or OpenAI CLIP weights.** The first four have research-only or non-commercial licences: Apple ML Research licence [S12][S13][S28], CC-BY-NC-4.0 [S14][S15]. OpenAI CLIP is excluded as a **policy choice**: its model card places "Any deployed use case of the model - whether commercial or not" out of scope [S46]. That is an intended-use statement, not a licence term; the weights carry no licence tag and the `openai/CLIP` code repo is MIT [S55].
4. **Transcript text embeddings** go in a separate vector (for example `multilingual-e5-small`, MIT, 384-d; or `bge-m3`, MIT, 1024-d) [S16][S17]. They are opt-in like the visual embedding.
5. **The taxonomy is data, not code: a minimal v1 schema** (§6). Labels have `id`, `name`, `prompts` and an optional `parent` and `external_id`; there are global `templates` and `top_k`. Per-model thresholds live in a **sidecar file** written only by `scenewise calibrate`, keyed to the taxonomy hash, preprocessing and score statistic they were fitted with; a mismatched entry is ignored. Everything else is deliberately deferred (§6.3).
6. **Scores are independent scores, not probabilities.** Every returned label carries its own `calibrated` flag. A calibrated label is returned when it reaches its fitted threshold. An uncalibrated label is returned only when it stands out from the video's other label scores (a per-video relative cut, §6.1 principle 5), so a video where nothing in the taxonomy applies gets **few or no labels**, not always `top_k`. No absolute threshold is ever applied without calibration. For the Expause integration, one `scenewise calibrate` run (labels bootstrapped with Haiku and spot-checked) is recommended before scenewise labels are written into production tags (OQ12).
7. **Cost does not separate the options; privacy, one-pass labels plus embedding, and vendor independence do.** Estimated per-video cost for a 60 s clip with **12 preview thumbnails** (computed, §5): local SigLIP 2 on Cloud Run CPU (europe-west1) ≈ **$0.00013** plus cold starts; Claude Haiku 5.5 ≈ **$0.00053** ($0.00027 Batch); Gemini Embedding 2 ≈ **$0.0014**; Cloud Vision label detection ≈ **$0.018**; Video Intelligence LABEL_DETECTION on the 5 s synthetic video ≈ **$0.0083** (prorated per Google's own worked example [S3]; ≈ $0.0167 with the explicit-content feature Expause also requests). All are below 5 cents per video; all but Cloud Vision are below 2 cents.
8. **Claude Haiku 5.5 stays the optional "rich tags" tier**, as a per-request or per-deployment switch (not per label). Prescribe `effort: low` or thinking disabled, a small `max_tokens` and structured output (§5). If Expause standardises on Google, the alternative is `gemini-3.1-flash-lite` ($0.25 / $1.50 per MTok [S37], Vertex retirement "May 7, 2027 or later" [S52]); Haiku 5.5 is 2.5× cheaper on input and 3× on output. `gemini-2.5-flash-lite` is **not** an option: it retires on Vertex AI on 2026-10-20 [S52].
9. **Storage: scenewise returns vectors, the adopter stores them.** Firestore vector search works for small or pre-filtered candidate sets only. It has a `flat` index, kNN reads are billed per 100 index entries scanned, and the query cannot be made from the Dart/Flutter client (§4). pgvector is the self-hosted alternative [S23].

---

## 2. What LABEL_DETECTION returns (Google Video Intelligence v1)

| Aspect | Fact | Source |
|---|---|---|
| Levels | **Segment** (whole video or user-specified segments → `segmentLabelAnnotations`), **shot** (auto-detected shots → `shotLabelAnnotations`), **frame** (sampled at 1 fps → `frameLabelAnnotations`) | [S1] |
| Entity | `entity` = `entityId` (Knowledge-Graph-style id), `description`, `languageCode` | [S1] |
| Hierarchy | `categoryEntities` = broader parent categories of the label | [S1] |
| Confidence | Per segment / per frame `confidence`. The docs do not define its calibration | [S1] |
| Mode | `labelDetectionMode`: `SHOT_MODE` (default), `FRAME_MODE`, `SHOT_AND_FRAME_MODE`. The docs recommend `SHOT_AND_FRAME_MODE` | [S1][S4] |
| Model | `model`: `builtin/stable` (default) or `builtin/latest` | [S4] |
| Thresholds | `frameConfidenceThreshold` default 0.4, `videoConfidenceThreshold` default 0.3 (applies to video and shot level), both clipped to 0.1–0.9 | [S4] |
| `stationaryCamera` | Hint for `SHOT_AND_FRAME_MODE` | [S4] |
| Vocabulary | Fixed and Google-owned. **No public vocabulary size exists for Video Intelligence.** The "over 10,000 entities" figure in Google's 2017 post belongs to **Cloud Vision** label detection, not Video Intelligence | [S5] |
| Price (stored video) | Label detection: 0–1,000 min/month free, then **$0.10/min** list price. The $0.09 and $0.08 columns are **Gemini Enterprise Flexible Savings Plan** prices (1-year and 3-year commitments), not volume tiers. Explicit content detection is priced the same ($0.10/min list). Shot detection $0.05/min, free with label detection. "Prices are per minute. Partial minutes are rounded up to the next full minute. Volume is per month." Google's worked example prorates: 1,000 requests of 1 min 22 s = "(82*1000)/60 = 1366.66 minutes"; the 366.66 billable minutes cost $36.67. So rounding applies to the monthly total, not to each request | [S3] (live page) |
| Lifecycle | Deprecated 2026-09-14, shutdown 2027-09-14, migrate to the Gemini family | [S2] |

What this means for Expause **(inference unless tagged)**:

- **Cost per video** ≈ (synthetic-video seconds / 60) × $0.10 beyond the free 1,000 min/month (computed from [S3]). `createSyntheticVideo(…, minDuration = 5, desiredFrameRate = 30)` sets the length to `max(5, K/30)` s [S53], which is exactly 5 s for every K ≤ 150 (all clips up to 150 min, given the 60 s interval cap). So label detection costs a flat 5/60 × $0.10 = **$0.0083** per video, for every K (computed). Clips under 10 s (K < 5) hit the 1 fps floor in the same function, so their video can be shorter and cheaper (inference from the ffmpeg command). Expause also requests `EXPLICIT_CONTENT_DETECTION` in the same call [S53], so its actual Video Intelligence bill is about **$0.0167** per video (computed).
- The synthetic video packs K previews into 5 s, at K/5 fps. The frame-level pass samples at 1 fps [S1], so it sees only about 5 of the K previews, and how segment labels are derived from shots is not documented. The Video Intelligence row in §5b is therefore a **cost** comparison, not an input-parity comparison (inference).
- The vocabulary is fixed and generic (objects, locations, activities). The adopter cannot add "skatepark trick", "ASMR", "#outfitcheck" or other app-specific interests. That gap is what zero-shot models fill.
- Shot boundaries in the synthetic video are artefacts of the stitching. Expause already uses only segment labels [S49], which is the right choice.
- LABEL_DETECTION returns no embedding.

---

## 3. Zero-shot model comparison

**Benchmark method (re-run for r1).**
- Machine and software: Apple M4 (4 performance cores), Python 3.12.14, `torch` 2.14.1, `open_clip_torch` 3.3.0, `timm` 1.0.30, `transformers` 5.19.0 (NaFlex only), `torch.set_num_threads(4)`, fp32, `torch.inference_mode()`.
- Inputs are synthetic only: 16 random-noise 1080×1920 (9:16) PIL images, passed through each model's own preprocessing.
- Timing: model load excluded; 2 warm-up passes, then 7 timed repeats. The table shows the **median ms per image at batch 16**, the median of two separate rounds that agreed within 8 %.
- The machine was **not idle**: other jobs kept the load average at about 5. The numbers are therefore conservative. The reviewer's run on the same machine gave 36.5 / 41.1 / 51.5 / 690 ms for SigLIP2-B/16 / PE-B / PE-S / So400m [review r1 #4], which agrees with these.
- Measured separately (median): preprocessing ≈ 3–6 ms per image; JPEG decode of a 720×1280 q60 synthetic JPEG ≈ 3.5 ms; cold start ≈ 1 s `import` plus ≈ 4.9 s model load from local cache (SigLIP 2 B/16).
- Batch 1 latency is higher (SigLIP 2 B/16: 47 ms). SigLIP 2 B/16 on 1 thread: 54 ms per image at batch 16.
- Scripts: scratchpad `q5/bench.py` and `q5/load.py` (not in the repo).

These are indicative numbers only. Cloud Run vCPUs are assumed to be about 2× slower than an M4 core (q7 estimate, unverified) (OQ6).

| Model (open_clip name unless noted) | IN-1k ZS | Image tower params | Embed dim | Input | CPU ms/img (M4, 4 thr, median) | Weights licence | Commercial? |
|---|---|---|---|---|---|---|---|
| ViT-B-32 `datacomp_xl_s13b_b90k` | 69.2 % [S26] | 88 M (151 M total [S26]) | 512 [S45] | 224 | 16 (r0 run, single) | MIT [S27] | Yes |
| **SigLIP 2 ViT-B-16** | 78.2 % [S6] | 92.9 M (measured) | 768 [S45] | 224 sq. | **37** | Apache-2.0 [S7][S8][S31] | Yes |
| SigLIP 2 ViT-B-16-256 | 79.1 % [S6] | 92.9 M | 768 [S45] | 256 sq. | 48 | Apache-2.0 [S8] | Yes |
| SigLIP 2 ViT-B-16-384 | 80.6 % [S6] | same | 768 | 384 sq. | not run | Apache-2.0 | Yes |
| **SigLIP 2 ViT-B-32-256** | 74.0 % [S6] | 94.6 M (measured) | 768 | 256 sq. (64 tokens) | **17** | Apache-2.0 | Yes |
| **SigLIP 2 NaFlex B/16** (`transformers`, `google/siglip2-base-patch16-naflex`) | no IN-1k table; below standard B on natural images [S6] | 92.9 M (measured) | 768 | native aspect, ≤256 patches (12×21 for 9:16) | 53 | Apache-2.0 [S43] | Yes |
| SigLIP 2 ViT-L-16-256 | 82.5 % [S6] | 316 M (measured) | 1024 [S45] | 256 | 158 (r0 run, single) | Apache-2.0 [S8] | Yes |
| SigLIP 2 So400m-14-378/384 | 84.1 % [S6] | 428 M (measured) | 1152 [S45] | 378/384 | 690–845 (reviewer / this run under load) | Apache-2.0 [S7] | Yes |
| SigLIP 2 So400m-16-256 | 83.4 % [S6] | — | 1152 | 256 | not run | Apache-2.0 | Yes |
| SigLIP (v1) So400m-14-384 | 83.1 % [S26] | 878 M total [S26] | 1152 | 384 | — | Apache-2.0 [S47] | Yes |
| **PE-Core-S-16-384** | 72.7 % (K400 ZS 55.0 %) [S11] | 23.8 M (measured) | 512 [S45] | 384 sq. | 52 | Apache-2.0 [S10][S11] | Yes |
| **PE-Core-B-16** | 78.4 % (K400 ZS 65.6 %) [S10][S11] | 93.7 M (measured) | 1024 [S45][S10] | 224 sq. | 43 | Apache-2.0 [S10] | Yes |
| PE-Core-L-14-336 | 83.5 % (K400 73.4 %) [S10][S11] | 0.32 B [S10] | 1024 [S45] | 336 | not run | Apache-2.0 [S10] | Yes |
| PE-Core-G-14-448 | 85.4 % [S10] | 1.88 B [S10] | — | 448 | not run (too big for CPU) | Apache-2.0 | Yes |
| EVA02-B-16 `merged2b` | 74.7 % [S26] | 150 M total [S26] | — | 224 | not run | MIT [S47] | Yes |
| EVA02-L-14-336 | 80.4 % [S26] | 428 M total [S26] | — | 336 | not run | MIT, not gated [S54] | Yes |
| OpenAI ViT-L-14 | 75.5 % [S26] | 428 M total [S26] | 768 | 224 | not run | No licence tag on the weights (repo code MIT [S55]); card: any deployed use "out of scope" [S46] | **No** (policy choice) |
| MobileCLIP2-S0 … S4 | 71.5 … 81.9 % [S12] | 11 – 322 M [S12] | — | — | — | **Apple ML Research Model licence: "Research Purposes … does not include … use in any commercial product or service"** [S13] | **No** |
| DFN5B ViT-H-14-378 | 84.2 % [S28] | 987 M total [S26] | — | 378 | — | `apple-amlr` tag (same as MobileCLIP2) [S28] | **No** |
| MetaCLIP 2 worldwide H/14 | not stated | whole model, not split by tower [S14] | — | — | — | CC-BY-NC-4.0 [S14] | **No** |
| jina-clip-v2 | not stated | **304 M** (EVA02-L; 0.9 B total with the 561 M text encoder) [S15] | 1024 (Matryoshka down to 64) [S15] | 512 | — | CC-BY-NC-4.0 [S15] | **No** (commercial only via Jina API) |

"sq." means the open_clip preprocessing squashes the image to a square (`resize_mode: squash`) [S51]. A 9:16 thumbnail is therefore distorted unless NaFlex is used, or unless the adopter pads or crops (inference; to be evaluated in OQ10).

**Considered and set aside:**
- **Video-native models** (VideoPrism LvT, Apache-2.0, JAX reference; InternVideo2-CLIP, Apache-2.0 tag, gated with automatic approval) [S48]. Expause's input is a short set of previews taken 2–60 s apart [S49][S53], with little temporal continuity for a video model to exploit, and these models cost more on CPU. Revisit them for adopters that send real video (inference).
- **Vertex `multimodalembedding@001`** (1408-d) [S39]. It retires on Vertex AI on **2027-04-01** [S52], and its text input is capped at "32 tokens (~32 words)" [S39], which is enough for short label prompts but rules it out for transcript text. Set aside in favour of `gemini-embedding-2` (§5a).

Libraries (versions read from PyPI and GitHub on 2026-10-08):

- `open_clip_torch` **3.3.0** (2026-02-27, MIT) [S29]. SigLIP 2 arrived in v2.31.0, PE-Core in v3.0.0, MetaCLIP 2 in v3.1.0 and MobileCLIP2 in v3.2.0 [S30]. The v3.3.0 tag contains every recommended config: `ViT-B-16-SigLIP2`, `ViT-B-32-SigLIP2-256`, `PE-Core-B-16`, `PE-Core-S-16-384`, `ViT-SO400M-14-SigLIP2-378`. It does **not** contain the NaFlex configs, which exist only on `main` [S45]. **Recommended single dependency for v1.**
- `transformers` **5.19.0** (2026-10-06) [S29]. Needed only if NaFlex wins the eval. SigLIP 2 first appeared in the preview tag `v4.49.0-SigLIP-2` and in the regular release **v4.50.0** (2025-03-21). NaFlex uses `AutoModel` / `AutoProcessor(..., max_num_patches=256)` [S44]. Tested here with 5.19.0.
- `torch` **2.14.1** (2026-09-30) [S29].

Zero-shot quality notes:

- Prompt templates matter. In CLIP, "A photo of a {label}." added 1.3 % on ImageNet, and ensembling 80 prompts added another 3.5 %, "almost 5%" in total. The ensemble is cached as averaged text embeddings, so it costs the same as one prompt at inference [S18].
- SigLIP's sigmoid loss "operates solely on image-text pairs" [S19]. Each label therefore gets an **independent score**, not one that is relative to the label set as with a softmax. Nothing in [S19] says these zero-shot scores are calibrated probabilities. They depend on prompt wording and the learned bias (inference). Google's own embedding guidance likewise says to "avoid using a fixed value threshold" [S39].
- SigLIP 2 is multilingual (multilingual tokenizer and training mix) [S6]. The PE-Core README makes no multilingual claim [S11].
- PE-Core reports zero-shot video results (Kinetics-400) [S11]. SigLIP 2 publishes none in [S6].

---

## 4. Labels vs embeddings for recommendations

| | Labels (LABEL_DETECTION, Cloud Vision or zero-shot) | Embeddings (frame → video, plus transcript) |
|---|---|---|
| What Expause consumes today | **Yes**: the top-10 label names (strings) as `contentTags`; confidence is used only for ordering and is not stored [S53] | No (OQ11) |
| Cold start | Good: rules such as "user follows #skate → show skate" | Good: content-to-content similarity without any interaction data (inference) |
| Expressiveness | Limited to the taxonomy | Captures style, mood and setting that no label names (inference) |
| Explainability / moderation / analytics | High | Low |
| Adopter-specific | Yes, if the taxonomy is adopter-supplied | Model-specific. Changing the model invalidates every stored vector |
| Cost in scenewise | One dot product per label once frame embeddings exist | By-product of the same pass |

What the YouTube paper does and does not show [S20], §3.2: "A user's watch history is represented by a variable-length sequence of sparse video IDs which is mapped to a dense vector representation via the embeddings … simply averaging the embeddings performed best among several strategies (sum, component-wise max, etc.)". Candidates are served by "nearest neighbor search in the dot product space". These are **learned ID embeddings**, not pixel or frame content embeddings. The paper supports averaging and dot-product serving as techniques. It is not evidence that content embeddings improve Expause's recommender.

**Lock-in (inference).** Stored vectors are tied to one checkpoint, so changing the model means re-embedding the whole corpus. That favours a stable, widely mirrored open checkpoint (SigLIP 2 weights are on HF under Apache-2.0), or a hosted model with a lifecycle commitment. `gemini-embedding-2` has "No shutdown date announced" [S38].

Aggregation **(inference, standard practice; no single authoritative source)**:

- Video embedding: L2-normalise each frame embedding, take the mean, then re-normalise. Use `pooling: "mean_l2"`.
- Labels: report both `score_max` (presence in any preview) and `score_mean` (prevalence) per label. Rank by `score_max` in v1. Whether `max`, `mean` or a top-3 mean ranks better is an OQ10 eval question.
- `score_max` depends on K: the maximum over 30 frames tends to be higher than over 7. A single threshold on it is therefore too strict for short clips and too lenient for long ones. v1 handles this in calibration (§6.2, K-stratified fit with a recorded K range), not with a new statistic (inference).

Storage size (computed from [S41]: Firestore counts vector values at "8 bytes per dimension"):

| Vector | float32 in transit | Firestore stored size | 1 M videos in Firestore |
|---|---|---|---|
| 512-d (PE-S, ViT-B-32) | 2 KB | 4 KB | ~3.8 GiB |
| 768-d (SigLIP 2 B, Gemini Embedding 2 @768) | 3 KB | 6 KB | ~5.7 GiB |
| 1024-d (PE-B, bge-m3) | 4 KB | 8 KB | ~7.6 GiB |
| 1152-d (So400m) | 4.5 KB | 9 KB | ~8.6 GiB |

These exclude index-entry storage, document name and other fields. At the us-central1 rate shown by default on the pricing page ($0.000205479 per GiB in the hourly view, ≈ $0.15 per GiB-month) [S42], 5.7 GiB costs about $0.86 per month (computed). The EU rate is OQ5.

Vector store options:

- **Firestore vector search** [S21]:
  - Up to 2048 dimensions; `EUCLIDEAN`/`COSINE`/`DOT_PRODUCT`. "The index type must be `flat`." Composite indexes allow pre-filtering.
  - At most 1000 results "(Standard edition limitation only)". No real-time snapshot listeners.
  - "Only the Python, Node.js, Go, and Java client libraries support vector search", so the Flutter/Dart app must query through a server or Cloud Function.
  - Page last updated 2026-10-07.
- **Firestore kNN billing** [S22]: "one read operation for each batch of up to 100 kNN vector index entries read by the query". Google's own example: a `limit: 5` query that "reads 1550 kNN vector index entries" is billed 16 + 5 reads. So cost follows the entries scanned, not `limit`.
  - **Estimate (computed; flat = exhaustive is an inference):** with no pre-filter over 1 M videos, one query reads about 1 M entries = 10,000 billed reads ≈ $0.003 at $0.03 per 100,000 reads (us-central1) [S42]. 1 M such queries cost about $3,000.
  - Verdict (inference): fine for small corpora or for narrow pre-filtered candidate sets (language, region, recency). Otherwise use a real ANN store.
- **pgvector 0.8.7**: HNSW and IVFFlat; indexed `vector` up to 2000 dims, `halfvec` up to 4000 [S23].
- Scenewise's own role **(inference)**: return vectors with `{model_id, dim, normalised, pooling}` metadata and leave storage to the adopter, consistent with a self-hosted OSS service.

Privacy of embeddings:

- Text embeddings can be inverted: vec2text recovers 92 % of 32-token inputs exactly [S32]. Transcript embeddings should therefore be treated as personal data, with the same retention and deletion rules as the transcript. Image-embedding inversion was not researched (OQ7).
- **(inference)** Video embeddings are derived from user content. They inherit the video's deletion lifecycle and must not reach third parties under a weaker policy than the media.

Transcript text embeddings: `intfloat/multilingual-e5-small` (MIT, 384-d, 512 positions) and `BAAI/bge-m3` (MIT, 1024-d, 8194 positions) [S16][S17]. `google/embeddinggemma-300m` is under the Gemma licence [S17].

---

## 5. Cost per video and the hosted options

### 5a. Hosted candidates (for Expause's own primary after 2027-09-14, and for scenewise tiers)

| Option | What it gives | Price | Notes |
|---|---|---|---|
| **Cloud Vision label detection** | Per-image labels: `mid` (Knowledge Graph MID), `description`, `score`, `topicality` [S35] | First 1,000 units/month free, then $1.50 per 1,000 (to 5 M), $1.00 per 1,000 above; one unit per image per feature [S34] | No deprecation notice on the pricing page [S34]. Closest continuity path: Google entity vocabulary (the ">10,000 entities" of [S5]), no synthetic video needed. Expause uses only `description` today [S49], so continuity is at the description level. Whether Vision `mid`s equal Video Intelligence `entityId`s is unverified (OQ4). **A candidate for Expause's own primary; Expause's call.** |
| **Gemini Embedding 2** (`gemini-embedding-2`, Stable) | One text/image/video/audio/PDF embedding space; default 3072-d, recommended 768/1536/3072; at most 6 images per request; video ≤120 s, at most 32 frames; 8,192 input tokens [S36] | Image $0.00012 each ($0.00006 batch); video $0.00079 per frame; text $0.20/MTok [S37] | Also on Vertex AI [S39]. Released 2026-04-22, "No shutdown date announced" [S38]. Zero-shot labels still work by text-image dot product. 768-d fits Firestore. Data leaves the operator's infrastructure, and stored vectors are locked to the vendor. **A candidate for Expause's own primary or embedding; Expause's call.** |
| **Claude Haiku 5.5** | Open-vocabulary tags with structured output | $0.10 / $0.50 per MTok in/out (prompts ≤100k), Batch 50 % off [S24] | Adaptive thinking, default effort `medium` [S33]. Thinking is billed as output, so set `effort: low` or disable thinking, and set a small `max_tokens`. 300 thinking tokens at $0.50/MTok = $0.00015, which would roughly add a third to the per-video cost below (computed). |
| **Gemini Flash-Lite** | Same role as Haiku | `gemini-3.1-flash-lite` $0.25 / $1.50; `gemini-3.5-flash-lite` $0.30 / $2.50 per MTok, output including thinking [S37] | `gemini-3.1-flash-lite`: Vertex retirement "May 7, 2027 or later" [S52]. Haiku 5.5 is 2.5× cheaper on input and 3× on output. Image-token count not checked. `gemini-2.5-flash-lite` ($0.10 / $0.40) shows no shutdown date on the Gemini API [S38] but **retires on Vertex AI on 2026-10-20** [S52], the route with EU regional endpoints, so it is excluded. Haiku stays first unless Expause standardises on Google. |
| Vertex `multimodalembedding@001` | 1408-d image/video/text [S39] | not checked | Retires 2027-04-01 [S52]; text capped at 32 tokens [S39]; set aside. |

### 5b. Per-video cost, like for like (computed)

Input assumptions:
- **K = number of preview thumbnails.** Previews are taken every 2 s (≤15 s clip), 3 s (≤30 s), 5 s (≤60 s), 10 s (≤5 min), then 20 / 40 / 60 s up to 10 / 30 min and beyond. Expause crops and analyses `K = floor(D/I)` previews (`columnCount`, one row) [S49][S53]. That gives **K = 7** for a 15 s clip, **12** for 60 s and **30** for 5 min. Scenewise reads the raw sprite sheets (q1), which hold `ceil(D/I)` sprites, so it can see one more when D is not a multiple of I (15 s → 8); at 60 s and 5 min it sees the same 12 and 30.
- Each preview has a 1280 px long side, so 720×1280 for vertical video [S49].
- Every option except Video Intelligence sees the same K thumbnails (Video Intelligence: see §2).
- Haiku gets them downscaled to 360×640. That is above the "very small images under 200 pixels" accuracy warning [S25], and is 13×23 = 299 tokens each [S25].
- The Haiku prompt adds about 1,000 taxonomy/instruction tokens and about 150 output tokens.
- **Local compute:** Cloud Run request-based billing, europe-west1 (a Tier 1 region), at $0.000024 per vCPU-s and $0.0000025 per GiB-s [S40]; shape 4 vCPU / 8 GiB as in q7 [S50] → $0.000116 per second.
- Local time per image = (37 ms inference + 5.4 ms preprocessing + 3.5 ms decode on the M4) × 2 for the assumed Cloud Run slowdown [S50] = 91.8 ms. This bills 4 vCPU for the whole time. On the M4, 4 threads gave 37 ms per image and 1 thread 54 ms (§3): about 148 vs 54 vCPU-ms per image. Single-thread workers (1 vCPU instances, or concurrency 4 with one thread each) would cut local compute cost by about 2.7× (computed). That matters only for q7 sizing.
- Free tiers are ignored.

| Option | K = 7 (15 s) | **K = 12 (60 s)** | K = 30 (5 min) |
|---|---|---|---|
| Local SigLIP 2 B/16, Cloud Run CPU | 0.64 s → $0.00007 | **1.1 s → $0.00013** | 2.75 s → $0.00032 |
| + one cold start (≈ 6 s on M4 × 2 = 12 s), amortised over the videos an instance serves | $0.0014 per cold start | same | same |
| Claude Haiku 5.5, K × 360×640 | $0.00038 (Batch $0.00019) | **$0.00053** (Batch $0.00027) | $0.0011 (Batch $0.00054) |
| Claude Haiku 5.5, K × 720×1280 (1196 tokens each) | $0.0010 | $0.0016 | $0.0038 |
| Gemini Embedding 2, K images | $0.00084 | **$0.0014** | $0.0036 |
| Cloud Vision labels, K images | $0.0105 | **$0.018** | $0.045 |
| Video Intelligence LABEL_DETECTION (5 s synthetic; prorated per [S3]) | $0.0083 | **$0.0083** | $0.0083 |
| (Expause's real VI bill: + EXPLICIT_CONTENT_DETECTION) | $0.0167 | $0.0167 | $0.0167 |

Reading **(inference)**:
- Local is cheapest per video, but a single cold start costs as much as about 10 warm videos. At low or bursty volume, the operational cost (container size, model load, minimum instances) matters more than the per-video number.
- Every option is under 5 cents per video. **Cost alone does not decide.** The case for the local default rests on four points:
  - the data stays in the operator's infrastructure (EU operator, U3);
  - one pass yields both labels and embedding;
  - adopters can define their own vocabulary;
  - there is no vendor lock-in on stored vectors.
- Haiku 4.5 is not costed: at $1 / $5 per MTok [S24] it is 10× Haiku 5.5's price for the same role, so there is no reason to prefer it.

Role of Haiku **(inference)**: it is good at open-vocabulary, compositional and trend tags ("GRWM", "unboxing") that CLIP-family models handle poorly. It is an optional tier, switched per request or per deployment, driven by the same taxonomy file (label names and prompts in the prompt, structured output). It can also bootstrap labelled data for `scenewise calibrate`. It does not produce embeddings.

---

## 6. Adopter-supplied taxonomy (minimal v1)

### 6.1 Principles

1. Scenewise ships **no** built-in vocabulary, only an example file.
2. Taxonomies are files (`SCENEWISE_TAXONOMY_PATH`, a file or a directory), selected per request by `taxonomy.id` (the file's `taxonomy_id`). Inline taxonomies are deferred. The API always uses the nested names `taxonomy.id`, `taxonomy.version`, `taxonomy.hash` and `model.id`.
3. Text embeddings are computed once per `(model.id, taxonomy.hash)` and cached. `taxonomy.hash` covers `labels` and `templates`.
4. A taxonomy is **model-independent** and contains no thresholds. Thresholds are model-specific and live in a **sidecar file** `<taxonomy file>.calibrations.json`, written only by `scenewise calibrate` and merged by the loader. The adopter's hand-edited YAML is never rewritten. Each calibration entry records the `model_id`, `taxonomy_hash`, `preprocess` (resize mode and size, e.g. `squash-224`) and `score_stat` (`max` in v1) it was fitted with. An entry is used only when all four match the serving setup. Otherwise it is ignored, a warning is logged, and its labels are served as uncalibrated. Any edit to labels or templates therefore invalidates every threshold until `calibrate` is re-run. Tuning a threshold on a small labelled set is calibration, not fine-tuning, so the no-fine-tuning decision is respected (inference).
5. **Calibration is per label, and so is the output flag.** For each video:
   - a label with a valid threshold (principle 4, and the video's K inside the entry's `k_range`) is **calibrated**. It is emitted when `score_max ≥ threshold`;
   - every other label is **uncalibrated**. It is emitted only when it stands out from this video's other labels: `z = (c − median) / (1.4826 · MAD) ≥ z_min`, where `c` is the label's frame-max cosine and the median and MAD are taken over all the taxonomy's labels for this video. `z_min` is a deployment setting (`SCENEWISE_UNCALIBRATED_Z`, default 2.0, to be tuned in OQ10). This relative cut is model-agnostic and applies no absolute threshold. A video where nothing in the taxonomy stands out gets no uncalibrated labels. Taxonomies with fewer than 8 labels have no meaningful median, so their uncalibrated labels are never emitted, and the loader warns once that they need `calibrate`;
   - emitted labels (both kinds) are ranked by `score_max` and cut to `top_k`. Each carries `calibrated: true|false`. Uncalibrated scores are never compared with a fitted threshold, and the two kinds are not distinguished in any other way.
6. Output always echoes `taxonomy.id`, `taxonomy.version`, `taxonomy.hash` and `model.id`, so the adopter can invalidate stale labels.

### 6.2 Schema and a valid example

Taxonomy file fields (pydantic model + exported JSON Schema):

| Field | Type | Rule |
|---|---|---|
| `schema_version` | int | must be `1` |
| `taxonomy_id` | str | `^[a-z0-9][a-z0-9_.-]*$`; served as `taxonomy.id` |
| `version` | str | free text, echoed as `taxonomy.version` |
| `templates` | list[str], ≥1 | each contains `{}` exactly once |
| `top_k` | int | 1–100, default 10 (matches Expause's `analyzeVideoMaxLabels` [S49]); a maximum, not a target |
| `labels[].id` | str | unique, same pattern as `taxonomy_id` |
| `labels[].name` | str | display name, returned as the label's description |
| `labels[].prompts` | list[str], ≥1 | text inserted into each template |
| `labels[].parent` | str, optional | must be another label's `id`; no cycles; used only for the output `path` (display/roll-up), with no score propagation |
| `labels[].external_id` | str, optional | opaque, echoed. For example a Knowledge Graph MID, so the adopter can align labels with Cloud Vision / Video Intelligence entities |

```yaml
schema_version: 1
taxonomy_id: expause-interests
version: "2026-10-01"
templates:                       # prompt ensemble; {} is replaced by each prompt
  - "a photo of {}."
  - "a vertical phone video frame showing {}."
top_k: 10
labels:
  - id: sport
    name: Sport
    prompts: ["people playing sport"]
  - id: sport.skateboarding
    name: Skateboarding
    parent: sport
    prompts: ["someone skateboarding", "a skateboard trick at a skatepark"]
  - id: food
    name: Food
    prompts: ["food", "a plate of food"]
  - id: food.cooking
    name: Cooking
    parent: food
    prompts: ["someone cooking in a kitchen"]
  - id: asmr
    name: ASMR
    prompts: ["an ASMR video with whispering and tapping"]
```

`external_id` is omitted in the example on purpose. No Knowledge Graph MID was verified for these labels, and inventing one would make the example wrong. Every `parent` resolves and every template contains `{}` once. (A real taxonomy this small would get no uncalibrated labels under principle 5; it is kept short for readability.)

Calibration sidecar `expause-interests.yaml.calibrations.json`, written by `scenewise calibrate`, never by hand:

```json
{
  "schema_version": 1,
  "entries": [
    {
      "model_id": "hf-hub:timm/ViT-B-16-SigLIP2",
      "taxonomy_hash": "sha256:...",
      "preprocess": "squash-224",
      "score_stat": "max",
      "k_range": [7, 30],
      "target_precision": 0.9,
      "fitted_at": "2026-10-05",
      "scenewise_version": "0.1.0",
      "labels": {
        "sport.skateboarding": { "threshold": 0.21, "n_pos": 64, "n_neg": 410 },
        "food.cooking": { "threshold": 0.18, "n_pos": 41, "n_neg": 433 }
      }
    }
  ]
}
```

Every `labels` key must exist in the taxonomy with that hash. Labels missing from `labels` (here `sport`, `food`, `asmr`) are uncalibrated.

Request (HTTP/JSON):

```json
{
  "video_id": "abc",
  "inputs": { "frames": ["..."] },
  "outputs": ["labels"],
  "taxonomy": { "id": "expause-interests" },
  "top_k": 5
}
```

`outputs` may add `"video_embedding"` and `"transcript_embedding"` (opt-in). The visual input forms are defined in q1.

Response:

```json
{
  "model": { "id": "hf-hub:timm/ViT-B-16-SigLIP2", "open_clip": "3.3.0" },
  "taxonomy": { "id": "expause-interests", "version": "2026-10-01", "hash": "sha256:..." },
  "labels": [
    { "id": "sport.skateboarding", "name": "Skateboarding", "path": ["sport", "sport.skateboarding"],
      "score_max": 0.31, "score_mean": 0.12, "frames": 12, "calibrated": true }
  ]
}
```

Scoring **(design proposal; inference)**:

1. Text vector per label = L2-normalised mean over `templates × prompts` embeddings, as in the CLIP ensembling of [S18].
2. Frame score = SigLIP `sigmoid(logit_scale · cos + logit_bias)`. For non-SigLIP models it is the cosine, and scores from different models are not comparable.
3. Video scores = `max` and `mean` over frames. Selection follows §6.1 principle 5, then ranking by `score_max` and the `top_k` cut.
4. `scenewise calibrate` takes a labels CSV `(video_id, label_id, is_positive)` and a frames manifest `(video_id, frame_path)`, the same frames scenewise would see in production (or a cache of per-frame scores from earlier runs). It fits one threshold per label on `score_max` for `--target-precision` (default 0.9). The labelled videos must span short, medium and long clips; the observed K range is recorded as `k_range`, and videos outside it are served uncalibrated. Labels with fewer than `--min-positives` (default 20) positives, or where no threshold reaches the target precision, are left out and stay uncalibrated. It writes or replaces the matching entry in the sidecar. No model weights change. Labels can be bootstrapped with Haiku (§5) and spot-checked by a person.

### 6.3 Deliberately deferred (add only when an eval shows the need)

- Negative prompts. If added, subtract in cosine space *before* the logit scale and bias, and say so in the schema.
- Exclusive groups; score propagation up the hierarchy (`propagate_up`, "parent ≥ max(child)").
- Aggregation modes beyond `max`/`mean` (`topk_mean`, `fraction_above`, `min_frame_fraction`).
- Softmax-over-siblings mode.
- Calibration methods beyond a threshold (Platt, temperature, isotonic).
- Per-label prompt hashes in calibration entries (so editing one label does not invalidate every threshold), and per-K-bucket thresholds or a top-3-mean statistic instead of the recorded `k_range` (only if the OQ10 eval shows `max` thresholds drifting with K).
- Per-label template overrides.
- Per-label backend routing (`backend: claude`). The rich tier is a per-request or per-deployment switch instead, so cost and latency do not depend on taxonomy contents.
- Inline per-request taxonomies, and per-request per-label overrides (only `top_k` may be overridden).

---

## 7. Open questions

1. ~~OQ1~~ **Resolved by U1 (2026-10-08):** scenewise stays a complement. Expause picks its own post-shutdown primary; the candidates are in §5a (Cloud Vision for vocabulary continuity, Gemini for Google's recommended path). Still open, for Expause: which one, and by when before 2027-09-14.
2. ~~OQ2~~ **Closed in r2:** the synthetic video is `max(5, K/30)` s, so 5 s for every realistic K, and `analyzeVideo` sends no `videoContext`, so the API defaults apply (`SHOT_MODE`, `builtin/stable`, thresholds 0.3 / 0.4) [S53][S4]. The label cost is a flat ≈ $0.0083 per video (§2). Only the K distribution of real clips remains, and it does not change any conclusion.
3. ~~OQ3~~ **Closed:** the pricing page was read live with curl [S3].
4. OQ4. The Video Intelligence vocabulary size is not published. Do Cloud Vision `mid`s and Video Intelligence `entityId`s come from the same Knowledge Graph id space for the same concept? Only matters if Expause keys on ids rather than `description`.
5. OQ5. Firestore: the EU (europe-west1 / eur3) read and storage rates, and the index-entry storage size of a vector index. Confirm that a `flat` kNN query reads every candidate entry (Query Explain) [S22]. Vector value size is now known: 8 bytes per dimension [S41].
6. OQ6. Real Cloud Run CPU latency (x86 vCPU, with or without ONNX/int8) and cold-start time for the chosen model. The 2× slowdown versus the M4 is a q7 estimate [S50].
7. OQ7. Privacy risk of image-embedding inversion, and whether video embeddings count as personal data under Expause's privacy policy.
8. ~~OQ8~~ **Closed in r2:** EVA02-L-14-336 `merged2b` is MIT and not gated [S54]. Every licence in §3 is now verified.
9. OQ9. Haiku 5.5 tagging quality on 360×640 vertical previews, and the real output-token count with `effort: low` or thinking disabled. This needs an eval set. Also the EU data-processing terms of each hosted option (Anthropic, Gemini API vs Vertex AI regional endpoints, Cloud Vision regional endpoint); not researched here. On the Vertex route, check model retirement dates first [S52] (2.5 Flash-Lite retires 2026-10-20).
10. OQ10. Model choice on a small Expause-labelled eval set (a few hundred videos × taxonomy): SigLIP 2 B/16 vs B/32-256 vs NaFlex B/16 vs PE-Core-B/16; squash vs pad for 9:16; `max` vs `mean` vs top-3-mean ranking, and whether a `max` threshold drifts with K across the `k_range`; the default `z_min` for uncalibrated output (§6.1 principle 5); English vs non-English prompts (favours SigLIP 2 [S6]). No public zero-shot benchmark on short-form UGC thumbnails was found.
11. OQ11. Does Expause's recommender (or a planned one) consume dense vectors at all, and where (Firestore, BigQuery, a separate service)? Until it does, embeddings stay opt-in. Their value should be measured offline before they become part of the default contract.
12. OQ12. **User decision: may scenewise labels reach Expause's production `contentTags` before a calibration run?**
    - *Yes, uncalibrated (relative cut only):* labels are available from day one with no labelling work. But `z_min` is untuned, and Expause stores names only, so it cannot filter weak labels later.
    - *No, calibrate first (recommended here):* one `scenewise calibrate` run on a few hundred Expause videos (Haiku-bootstrapped labels, human spot-check) before writing tags. It costs a few hours of labelling and one Haiku batch, gives per-label thresholds at a known precision, and must be repeated whenever the taxonomy or model changes.
    - Related Expause-side choice: keep storing names only, or also store `score_max` and `calibrated` so tags can be re-filtered without re-running scenewise. Both are outside scenewise's contract.

---

## 8. Review round 1 — resolution

Each finding from `reviews/q5-review-r1.md` was re-checked on 2026-10-08 against the source named.

| # | Finding | Resolution |
|---|---|---|
| 1 | ">10,000 entities" misattributed | **Fixed.** Confirmed in [S5]: the sentence sits in the Cloud Vision list ("Updated label detection model … vocabulary to over 10,000 entities"). §2 and OQ4 now say there is no public figure for Video Intelligence. |
| 2 | "≥ $0.10 per video" floor wrong | **Fixed.** The live page [S3] shows both the per-minute rounding sentence and the prorated 82 s × 1000 example ($36.67). §2 and §5b now use (seconds/60) × $0.10; a 5 s synthetic video ≈ $0.008. OQ3 closed. |
| 3 | "Local = $0" | **Fixed.** Replaced by a Cloud Run cost per video (europe-west1 Tier 1, request-based $0.000024/vCPU-s, $0.0000025/GiB-s [S40]) in §5b, compared with Haiku, Gemini Embedding 2, Cloud Vision and Video Intelligence. The reviewer's $0.00056 assumed 100 thumbnails and 7 s. With Expause's real K (8–31 previews [S49]; corrected to 7–30 in r2 #1) local is $0.0001–0.0003, still the same order as the hosted options, so the reviewer's conclusion (cost does not decide) is kept. |
| 4 | CPU timings, weak method | **Fixed.** Re-ran with 2 warm-ups, 7 repeats, median, two rounds, synthetic inputs (§3). B/16 37 ms, PE-B 43, PE-S 52 (the reviewer had 36.5 / 41.1 / 51.5); So400m 845 ms under load vs the reviewer's 690. Preprocessing, decode and cold start are now measured separately. The machine was not idle; this is stated. |
| 5 | YouTube paper cited for content embeddings | **Fixed.** Re-extracted from the PDF: the quote is in §3.2 and concerns learned video-ID embeddings. §1.1 and §4 now cite it only for averaging and dot-product serving. |
| 6 | OpenAI CLIP licence | **Fixed.** The card says "Any deployed use case of the model - whether commercial or not - is currently out of scope" [S46]. Marked **No**. |
| 7 | EVA02 / SigLIP v1 licences | **Fixed.** HF API: `timm/eva02_base_patch16_clip_224.merged2b` is MIT, `google/siglip-so400m-patch14-384` is Apache-2.0 [S47]. DFN5B `apple-amlr` confirmed [S28]. |
| 8 | jina / MetaCLIP 2 param column | **Fixed.** jina card: 304 M image encoder, 561 M text encoder, 0.9 B total [S15]. MetaCLIP 2 is no longer given a per-tower figure. |
| 9 | Haiku 4.5 sprite cost | **Fixed.** Standard tier, 1568-token cap [S25]; the older tokenizer gives ~30 % fewer tokens [S24]. Now ≈ $0.0031. |
| 10 | Adaptive thinking cost | **Fixed.** Default effort `medium` [S33]. §5a quantifies 300 thinking tokens = $0.00015 and prescribes `effort: low` or thinking disabled, plus a small `max_tokens` and structured output. |
| 11 | Unlike-for-like comparison (100 thumbnails vs one sprite) | **Fixed.** §5b uses the same K previews for every option, at stated resolutions, with K derived from Expause's interval table [S49]. |
| 12 | Firestore vector storage size | **Fixed.** "8 bytes per dimension" [S41]. The table now has a Firestore column (768-d = 6 KB). |
| 13 | Firestore kNN cost not estimated | **Fixed.** Google's 1550-entries example quoted [S22]. Estimate ≈ 10,000 reads ≈ $0.003 per unfiltered query over 1 M videos (us-central1 rate [S42]), with "flat = exhaustive" labelled inference. "Fits the stack" now carries the pre-filter qualifier. |
| 14 | 1000-result limit / client libraries | **Fixed.** "(Standard edition limitation only)" and the Python/Node.js/Go/Java-only restriction quoted [S21]; the Flutter implication added. |
| 15 | Missing Cloud Vision | **Fixed.** Added in §5a and §5b: pricing [S34], response fields [S35], no deprecation notice. Framed as a candidate for Expause's own primary (U1). |
| 16 | Missing Gemini Embedding 2 | **Fixed.** Added in §5a and §5b: Stable, limits and dims [S36], prices [S37], no shutdown date [S38]. One correction to the reviewer: the docs recommend 768/1536/3072 dims, and Vertex lists 128/768/1536 [S39]. |
| 17 | Missing Gemini Flash-Lite | **Fixed, with a correction.** The reviewer cited only `gemini-3.5-flash-lite` ($0.30/$2.50). The same page also lists `gemini-2.5-flash-lite` at $0.10/$0.40 with no shutdown date [S37][S38], which is about Haiku 5.5's price, not 3–5× dearer. §5a lists all three. *(r2 #7: 2.5 Flash-Lite retires on Vertex on 2026-10-20, so the alternative is now 3.1 Flash-Lite and the reviewer's original conclusion holds.)* |
| 18 | Missing SigLIP 2 NaFlex | **Fixed.** Apache-2.0 [S43]; in `transformers` regular releases since v4.50.0, tested on 5.19.0 [S44]; absent from open_clip v3.3.0 configs, present on `main` [S45]; benchmarked (53 ms/img). Added nuance from [S6] §3.1.1: the standard B beats NaFlex B on natural images, so NaFlex is an eval candidate, not the default. |
| 19 | Missing smaller SigLIP 2 sizes | **Fixed.** B/32-256 (74.0 %, 17 ms/img measured), B/16-384 (80.6 %) and So400m/16-256 (83.4 %) added from [S6] Table 1; configs present at v3.3.0 [S45]. |
| 20 | Missing video-native models | **Fixed.** VideoPrism and InternVideo2 noted as considered and set aside [S48]. |
| 21 | Missing Vertex `multimodalembedding@001` | **Fixed.** Listed and set aside (1408-d) [S39]. *(r2 #8 replaced the unsourced "superseded" with the real reasons.)* |
| 22 | Taxonomy schema over-built | **Fixed.** §6 is now a minimal v1; §6.3 lists every deferred feature. |
| 23 | Example YAML invalid / model binding | **Fixed.** `food` is defined, `exclusive_groups` is removed, the `model` block is removed, and thresholds moved to `calibrations[model_id]` (moved again to a sidecar file in r2 #17). The validation rules are tabled. |
| 24 | "Probability" wording, default threshold, negatives | **Fixed.** "Independent scores"; no uncalibrated threshold (top-k + `calibrated: false`; r2 #13/#15 replaced plain top-k with a per-label flag and a per-video relative cut); negatives deferred, with the cosine-space rule recorded for when they return. |
| 25 | Embeddings-first headline | **Fixed.** Labels are now primary and shaped like today's `contentTags` input (description + score, top 10 [S49]); embeddings are opt-in until OQ11; lock-in noted. The optional `external_id` covers id compatibility. |
| 26 | Multilingual not discussed | **Fixed.** SigLIP 2 abstract: "multilingual vision-language encoders" [S6]; the PE-Core README has no multilingual claim [S11]. Added to §1, §3 and OQ10. |
| 27 | S2 points to .cn | **Fixed.** S2 now cites docs.cloud.google.com; the quote was re-read there. |
| 28 | S9 reads `main`, doc pins 3.3.0 | **Fixed.** Configs are now cited at the `v3.3.0` tag [S45]; S9 is retired in favour of S45. |

No finding was rejected outright. Findings 3, 16 and 17 were accepted with the corrections noted.

---

## 8b. Review round 2 — resolution

Each finding from `reviews/q5-review-r2.md` was re-checked on 2026-10-08. Expause code was re-read (read only) at the lines cited [S53]; the Video Intelligence pricing page [S3], the Vertex lifecycle page [S52] and the Vertex embeddings page [S39] were re-fetched with curl; licences were re-read from the HF and GitHub APIs [S54][S55][S56]. No finding was rejected. This was the final round; what remains unsettled is in §7 (OQ10, OQ12).

| # | Finding | Resolution |
|---|---|---|
| 1 | Preview count off by one | **Fixed.** Confirmed `columnCount = Math.floor(durationToProcess / previewsIntervalSeconds)`, one row, and the success handler crops `columnCount` tiles. K = 7 / 12 / 30, with a note that the raw sheets hold `ceil(D/I)` (15 s → 8). §1.7 and the §5b table recomputed (local $0.00007 / $0.00013 / $0.00032 etc.); `frames` in the example is 12. Attribution now [S49][S53]. One small difference from the reviewer: Haiku at K = 7 is $0.00038, not $0.00039 (3,093 × $0.10/MTok + 150 × $0.50/MTok = $0.000384). |
| 2 | VI "volume tiers" are savings-plan prices | **Fixed.** The live table's columns are "Price (USD)" and the 1- and 3-year Gemini Enterprise Flexible Savings Plans. §2 corrected. |
| 3 | Synthetic-video length and config answerable | **Fixed.** `Math.max(minDuration = 5, previewsCount / 30)`; request has no `videoContext`. Flat $0.0083; "(if still 5 s; OQ2)" dropped; OQ2 closed. Added: K < 5 hits the function's 1 fps floor and can give a shorter video. |
| 4 | Explicit content detection also billed | **Fixed.** Same call requests `EXPLICIT_CONTENT_DETECTION`, priced at $0.10/min. §1 context, §2 and §5b note ≈ $0.0167 and that this is q4's subject. |
| 5 | VI does not see every preview | **Fixed.** Caveat added in §2 and §5b: the VI row is a cost comparison, not input parity. |
| 6 | `contentTags` holds names only | **Fixed.** Confirmed `contentTags: string[]` from `.map(label => label.name)`; confidence only sorts (last segment's). §1 and §4 corrected; this motivated the per-label selection rule (#15) and OQ12. |
| 7 | `gemini-2.5-flash-lite` retires on Vertex 2026-10-20 | **Fixed.** Confirmed on the Vertex lifecycle page, replacements "gemini-3.8-flash or gemini-3.1-flash-lite or Gemma 4". `gemini-3.1-flash-lite` ($0.25 / $1.50, retirement "May 7, 2027 or later") is now the Google alternative; Haiku 5.5 is 2.5× / 3× cheaper. |
| 8 | "Superseded" unsourced | **Fixed.** Replaced with the sourced reasons: retirement 2027-04-01 [S52], 32-token text cap [S39]. |
| 9 | OpenAI CLIP exclusion is not a licence term | **Fixed.** Reworded as a policy choice; repo code MIT confirmed [S55]. |
| 10 | EVA02-L licence | **Fixed.** HF API `license:mit`, not gated [S54]; OQ8 closed. |
| 11 | Interval range; InternVideo2 gating | **Fixed.** "2–60 s apart"; "gated with automatic approval" (`gated: "auto"`). |
| 12 | Calibrations go stale silently | **Fixed.** Entries now record `taxonomy_hash`, `preprocess` and `score_stat` with `model_id`; on any mismatch the entry is ignored with a warning and the labels are served uncalibrated (§6.1 principle 4). A per-label prompt hash is deferred (§6.3). |
| 13 | Partial calibration undefined | **Fixed.** The response-level `calibrated` became a per-label flag (no net new response field), and §6.1 principle 5 states the rule: calibrated labels by threshold, the rest by the uncalibrated cut, one merged ranking. Chose this over "top-k fill" because one rule for all uncalibrated labels is simpler. |
| 14 | `score_max` threshold depends on K | **Fixed** with the K-stratified option: `calibrate` needs labelled clips across lengths and records `k_range`; videos outside it are served uncalibrated. The K-robust statistic (top-3 mean) is kept as an OQ10 eval item and §6.3 deferral rather than changing the v1 output. |
| 15 | Uncalibrated top-k always returns k labels | **Fixed.** A per-video relative cut (robust z-score over the taxonomy's labels, `z_min` default 2.0) replaces plain top-k, so `top_k` is a maximum, and a video where nothing stands out gets none. No absolute uncalibrated threshold is introduced. One `calibrate` run is recommended for the Expause integration (§1.6); whether it is required is user decision OQ12. |
| 16 | `calibrate` inputs and outputs underspecified | **Fixed.** Labels CSV plus frames manifest (or cached per-frame scores); records `target_precision`, `n_pos`, `n_neg`, `taxonomy_hash`, `scenewise_version`; `--min-positives` default 20. |
| 17 | Tool rewrites hand-edited YAML | **Fixed.** Calibrations moved to a sidecar `<taxonomy>.calibrations.json`; the taxonomy schema lost its `calibrations` field. |
| 18 | `taxonomy_id` vs `taxonomy.id` | **Fixed.** The API uses nested `taxonomy.id` / `.version` / `.hash` and `model.id` throughout; the file field `taxonomy_id` is stated as the source of `taxonomy.id`. |
| 19 | "Below 2 cents" | **Fixed.** "Below 5 cents; all but Cloud Vision below 2 cents." |
| 20 | Haiku 4.5 costed on a sheet | **Fixed** by dropping the costing: at 10× Haiku 5.5's per-token price it is not a candidate. |
| 21 | Local cost bills 4 vCPU for 1.46× speed-up | **Fixed.** Note added in §5b: single-thread workers ≈ 2.7× cheaper; relevant only to q7. |
| 22 | Perception-LM in the same repo | **Fixed.** One line in §1.2: only PE-Core weights are recommended, never PLM (HF `license:other`, manually gated [S56]). |

## 9. Sources

All read 2026-10-08.

- [S1] Google Cloud, "Analyze videos for labels" — https://docs.cloud.google.com/video-intelligence/docs/analyze-labels (page last updated 2026-10-07)
- [S2] Google Cloud, "Video Intelligence API deprecations" — https://docs.cloud.google.com/video-intelligence/docs/deprecations
- [S3] Google Cloud, "Video Intelligence API pricing" — https://cloud.google.com/video-intelligence/pricing (read live with curl; list price, 1-/3-year Gemini Enterprise Flexible Savings Plan columns, explicit content detection row, worked example)
- [S4] Google Cloud, REST v1 `videos.annotate` / `LabelDetectionConfig` — https://docs.cloud.google.com/video-intelligence/docs/reference/rest/v1/videos/annotate
- [S5] Google Cloud blog, "Cloud Video Intelligence enters beta… and Cloud Vision gets new features" (2017-06-30) — https://cloud.google.com/blog/products/gcp/cloud-machine-learning-perception-services-updates-cloud-video-intelligence-enters-beta-and-cloud-vision-gets-new-features (the 10,000-entity figure is in the Cloud Vision list)
- [S6] Tschannen et al., "SigLIP 2", arXiv:2502.14786 v1 (2025-02-20), abstract, Table 1, §2.4.2, §3.1.1 — https://arxiv.org/html/2502.14786
- [S7] Hugging Face model card `google/siglip2-so400m-patch14-384` (Apache-2.0) — https://huggingface.co/google/siglip2-so400m-patch14-384
- [S8] Hugging Face API metadata for `google/siglip2-base-patch16-224`, `-256`, `so400m-patch14-384` (apache-2.0, lastModified 2025-02-21) — https://huggingface.co/api/models/google/siglip2-base-patch16-224
- [S9] (retired in r1; replaced by [S45])
- [S10] Hugging Face model card `facebook/PE-Core-L14-336` (Apache-2.0, PE-Core table) — https://huggingface.co/facebook/PE-Core-L14-336 ; and `timm/PE-Core-B-16` — https://huggingface.co/timm/PE-Core-B-16
- [S11] facebookresearch/perception_models README (PE-Core T/S/B/L/G, IN-1k and K400 zero-shot, Apache-2.0; no multilingual claim) — https://github.com/facebookresearch/perception_models
- [S12] Hugging Face model card `apple/MobileCLIP2-S4` (`apple-amlr`) — https://huggingface.co/apple/MobileCLIP2-S4
- [S13] Apple, `LICENSE_MODELS` (Apple Machine Learning Research Model licence) — https://raw.githubusercontent.com/apple/ml-mobileclip/main/LICENSE_MODELS
- [S14] Hugging Face model card `facebook/metaclip-2-worldwide-huge-quickgelu` (CC-BY-NC-4.0) — https://huggingface.co/facebook/metaclip-2-worldwide-huge-quickgelu
- [S15] Hugging Face model card `jinaai/jina-clip-v2` (CC-BY-NC-4.0; 561 M text + 304 M image, 0.9 B total) — https://huggingface.co/jinaai/jina-clip-v2
- [S16] Hugging Face `intfloat/multilingual-e5-small` (MIT, 384-d) — https://huggingface.co/intfloat/multilingual-e5-small
- [S17] Hugging Face `BAAI/bge-m3` (MIT, 1024-d) — https://huggingface.co/BAAI/bge-m3 ; `google/embeddinggemma-300m` (Gemma licence) — https://huggingface.co/google/embeddinggemma-300m
- [S18] Radford et al., "Learning Transferable Visual Models From Natural Language Supervision", arXiv:2103.00020 (§3.1.4) — https://arxiv.org/abs/2103.00020
- [S19] Zhai et al., "Sigmoid Loss for Language Image Pre-Training", arXiv:2303.15343 v4 — https://arxiv.org/abs/2303.15343
- [S20] Covington, Adams, Sargin, "Deep Neural Networks for YouTube Recommendations", RecSys 2016, §3.1–3.2 — https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/45530.pdf
- [S21] Firebase, "Search with vector embeddings" (last updated 2026-10-07) — https://firebase.google.com/docs/firestore/vector-search
- [S22] Firebase, "Understand Cloud Firestore billing" (kNN index-entry billing and the 1550-entries example; last updated 2026-10-07) — https://firebase.google.com/docs/firestore/pricing
- [S23] pgvector README (v0.8.7) — https://github.com/pgvector/pgvector
- [S24] Anthropic, Pricing (Haiku 5.5 $0.10/$0.50; Haiku 4.5 $1/$5; the 4.7+ tokenizer "approximately 30% more tokens") — https://platform.claude.com/docs/en/about-claude/pricing
- [S25] Anthropic, Vision (token formula; High-resolution 2576 px / 4784 tokens for 4.7+, Standard 1568 px / 1568 tokens; "very small images under 200 pixels") — https://platform.claude.com/docs/en/build-with-claude/vision
- [S26] OpenCLIP zero-shot results CSV — https://raw.githubusercontent.com/mlfoundations/open_clip/main/docs/openclip_results.csv
- [S27] Hugging Face API `laion/CLIP-ViT-B-32-DataComp.XL-s13B-b90K` (mit) — https://huggingface.co/laion/CLIP-ViT-B-32-DataComp.XL-s13B-b90K
- [S28] Hugging Face model card `apple/DFN5B-CLIP-ViT-H-14-378` (`apple-amlr`) — https://huggingface.co/apple/DFN5B-CLIP-ViT-H-14-378
- [S29] PyPI JSON API: `open-clip-torch` 3.3.0 (2026-02-27), `transformers` 5.19.0 (2026-10-06), `torch` 2.14.1 (2026-09-30), `sentence-transformers` 6.1.0 — https://pypi.org/pypi/open-clip-torch/json (and corresponding package URLs)
- [S30] open_clip GitHub releases — https://github.com/mlfoundations/open_clip/releases
- [S31] Hugging Face `timm/ViT-B-16-SigLIP2` (apache-2.0), `timm/PE-Core-S-16-384` (apache-2.0) — https://huggingface.co/timm/ViT-B-16-SigLIP2
- [S32] Morris et al., "Text Embeddings Reveal (Almost) As Much As Text", arXiv:2310.06816 — https://arxiv.org/abs/2310.06816
- [S33] Anthropic, Models overview (Haiku 5.5: adaptive thinking, default effort medium, retirement not sooner than 2027-10-07) — https://platform.claude.com/docs/en/about-claude/models/overview
- [S34] Google Cloud, "Cloud Vision pricing" (label detection tiers; unit = one feature per image) — https://cloud.google.com/vision/pricing
- [S35] Google Cloud, "Detect labels" (Cloud Vision: `mid`, `description`, `score`, `topicality`; last updated 2026-10-07) — https://docs.cloud.google.com/vision/docs/labels
- [S36] Google AI for Developers, "Embeddings" (`gemini-embedding-2` Stable, limits, dimensions) — https://ai.google.dev/gemini-api/docs/embeddings
- [S37] Google AI for Developers, "Gemini Developer API pricing" (Gemini Embedding 2; Flash-Lite models) — https://ai.google.dev/gemini-api/docs/pricing
- [S38] Google AI for Developers, "Gemini deprecations" (Gemini Developer API: `gemini-embedding-2` released 2026-04-22; `gemini-2.5-flash-lite` no shutdown date there, but see [S52] for Vertex) — https://ai.google.dev/gemini-api/docs/deprecations
- [S39] Google Cloud, "Get multimodal embeddings" (Vertex: `gemini-embedding-2` and `multimodalembedding@001` 1408-d; threshold guidance; last updated 2026-10-08) — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-multimodal-embeddings
- [S40] Google Cloud, "Cloud Run pricing" (Tier 1 list includes europe-west1/-west4; request-based $0.000024/vCPU-s, $0.0000025/GiB-s; instance-based $0.000018 / $0.000002) — https://cloud.google.com/run/pricing
- [S41] Firebase, "Storage size calculations" (vector "8 bytes per dimension") — https://firebase.google.com/docs/firestore/storage-size
- [S42] Google Cloud, "Firestore pricing" (default table us-central1: reads $0.03 per 100,000; stored data $0.000205479 per GiB in hourly view) — https://cloud.google.com/firestore/pricing
- [S43] Hugging Face API `google/siglip2-base-patch16-naflex`, `google/siglip2-so400m-patch16-naflex` (apache-2.0, lastModified 2025-02-21) — https://huggingface.co/api/models/google/siglip2-base-patch16-naflex
- [S44] Hugging Face Transformers, SigLIP2 model doc (NaFlex `max_num_patches`; "contributed … on 2025-02-21") — https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/siglip2.md ; release tags `v4.49.0-SigLIP-2` and v4.50.0 (2025-03-21) — https://github.com/huggingface/transformers/releases/tag/v4.50.0
- [S45] open_clip `src/open_clip/model_configs` at tag v3.3.0 (no NaFlex) vs `main` (NaFlex configs) — https://github.com/mlfoundations/open_clip/tree/v3.3.0/src/open_clip/model_configs
- [S46] Hugging Face model card `openai/clip-vit-large-patch14` ("Out-of-Scope Use Cases") — https://huggingface.co/openai/clip-vit-large-patch14
- [S47] Hugging Face API `timm/eva02_base_patch16_clip_224.merged2b` (mit), `google/siglip-so400m-patch14-384` (apache-2.0) — https://huggingface.co/api/models/timm/eva02_base_patch16_clip_224.merged2b
- [S48] Hugging Face API `google/videoprism-lvt-base-f16r288` (apache-2.0), `OpenGVLab/InternVideo2-CLIP-1B-224p-f8` (apache-2.0 tag, `gated: "auto"`) — https://huggingface.co/google/videoprism-lvt-base-f16r288
- [S49] scenewise research q1, `docs/research/q1-input-contract.md` §3.2–3.3 (Expause preview interval table, `columnCount = floor(duration / I)`, 1280 px previews, synthetic video, use of `segmentLabelAnnotations` description, top `analyzeVideoMaxLabels`)
- [S50] scenewise research q7, `docs/research/q7-runtime-cost.md` (Cloud Run shape 4 vCPU / 8 GiB; `CLOUD_SLOWDOWN_VS_M4` = 2.0, an estimate)
- [S51] open_clip configs on HF: `timm/ViT-B-16-SigLIP2` and `timm/PE-Core-B-16` `open_clip_config.json` (`resize_mode: squash`) — https://huggingface.co/timm/ViT-B-16-SigLIP2/raw/main/open_clip_config.json
- [S52] Google Cloud, Vertex AI "Model versions and lifecycle" (retirement dates: `gemini-2.5-flash-lite` 2026-10-20; `gemini-3.1-flash-lite` "May 7, 2027 or later"; `multimodalembedding@001` 2027-04-01; read with curl) — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
- [S53] Expause Cloud Functions source (read only), `cloud_functions/functions/src/functions/transcoding/app_transcoding.ts` (`:115-131` crop of `columnCount` tiles; `:420-445` `processVideoAnalysisResults`, `contentTags` = names; `:685-708` interval table and `columnCount = floor(D/I)`; `:955-976` `createSyntheticVideo`, `max(5, K/30)` s) and `video_analysis/video_analysis.ts:30-40` (features `LABEL_DETECTION` + `EXPLICIT_CONTENT_DETECTION`, no `videoContext`)
- [S54] Hugging Face API `timm/eva02_large_patch14_clip_336.merged2b` (`license:mit`, not gated) — https://huggingface.co/api/models/timm/eva02_large_patch14_clip_336.merged2b
- [S55] GitHub API `openai/CLIP` (MIT licence on the code repository) — https://api.github.com/repos/openai/CLIP
- [S56] Hugging Face API `facebook/Perception-LM-1B` (`license:other`, gated manual) and `facebook/PE-Core-B16-224` (`license:apache-2.0`) — https://huggingface.co/api/models/facebook/Perception-LM-1B
- Local benchmark: this author, 2026-10-08, Apple M4, Python 3.12.14, torch 2.14.1, open_clip_torch 3.3.0, timm 1.0.30, transformers 5.19.0; synthetic inputs; method in §3.
