# Q7 review, round 2 (final)

Reviewer: fresh review agent (did not write Q7 or review round 1). Date: 2026-10-08.
Reviewed: `docs/research/q7-runtime-cost.md` (revised after round 1) and `docs/research/q7_cost_grid.py`.
Sources were re-read on 2026-10-08. The Cloud Run, Vertex AI and Speech-to-Text pricing pages were downloaded and grepped, because WebFetch truncates them.

Severity counts: wrong 3, unsupported 2, missing option 1, design concern 2, minor 7 (15 findings).

## Script check

- `python3 -I docs/research/q7_cost_grid.py` exits 0. A blank-line-insensitive diff of its output against §6 (from "### Derived per-video figures" to the end of the per-stage list) shows **no differences**. §6 is the verbatim output.
- No negative value in the output, with `APPLY_FREE_TIER = False` (the default) or with a copy set to `True` (0 occurrences of `-$`). With the switch on, the 1k cells fall to $0.022–0.075 for the CPU Haiku mixes, which is the Haiku fee alone. That is sane.
- The sensitivity rows (CPU ×0.5 / ×1 / ×2, GPU cold 60 s, Haiku first-party, free tier on) are present for all six cells.
- Re-derived by hand, all correct:
  - Rates: $0.000136, $0.000104, $0.0000728 and $0.000291 per second; worker pool $170.13/month.
  - The worked example.
  - The Haiku fee: $0.000345, or $0.000313 first-party.
  - Gated Gemini 3.1 Flash-Lite: $0.00403 per video.
  - STT V2 standard and dynamic batch: $0.03473 / $0.00662.
  - Every dollar figure in §1 and §7: the 25% CPU-job saving, $56/$102 at 100k×5%, $6/$9 at 10k×5%, $0.68 maximum Haiku endpoint gap, the 13× and 2.6× STT ratios, and +$0.7–5 for the 60 s GPU cold start.
- Cold-start probabilities against p = exp(−λ·900), λ = videos / 1,751,040 s:
  - 50% at 1,349 videos/month.
  - 32.9% at 2,165.
  - 10% at 4,480.
  - 1% at 8,960.
  - 0.13% at 12,990.

  All match §3.
- Frames: `floor(300/10)` = 30. This matches q5 round 2's K = floor(D/I) (7/12/30); the 5-minute case is 30 under either formula.

## Round-1 findings: resolution check

| r1 # | Verdict |
|---|---|
| 1 Gemini 2.5 FL | Resolved. Vertex non-global prices re-verified: 3.1 FL audio $0.55 / out $1.65; 3.5 FL $0.33 / $2.75; global $0.50/$1.50 and $0.30/$2.50 (cloud.google.com/vertex-ai/generative-ai/pricing, downloaded 2026-10-08). |
| 2 VAD gate | Resolved; arithmetic correct. |
| 3 Cold-start text | Resolved (see above). |
| 4 Haiku wait | Resolved. The overlap argument (summaries need captions and labels) is sound. |
| 5 8 GiB | Resolved in direction, but the supporting text misstates q2 (finding 1). |
| 6 Two images | Resolved; consistent with q8a §9.4 `ort-*`/`torch-*` selectors. |
| 7 Parakeet scaling | Resolved. q2 l.471: "about 32 RTFx on a 12.6 s clip with 4 threads". |
| 8 Shares | Resolved; the script prints them. |
| 9 Batched vLLM | Resolved. "At most about $10" matches the L4 job summaries cell ($9.82). |
| 10 Free-tier bug | Resolved: no negatives; credit per configuration. Small leftovers in finding 10. |
| 11 Batch slots | Resolved (486 slots, skip-if-empty). |
| 12 Switch advice | Resolved, but the latency bounds are understated (finding 3). |
| 13 CPU / Delayed jobs | Resolved. Prices re-verified. Execution-length caps are not modelled (finding 4). |
| 14 Batch APIs | Partly. Haiku Batch is priced at the Vertex EU rate, but Vertex batch is a different API from Anthropic's Message Batches (finding 6). |
| 15 EU residency | Resolved; claims re-verified (see the verified list). |
| 16 Concurrency | Resolved in the design. The §9 note about q8a is stale (finding 8). |
| 17 Decode/embedding | Resolved. |
| 18 STT ratio | Correctly superseded: 0.03473/0.00257 = 13.5×, stated as about 13× in §1 and §7. |
| 19–25 | Resolved. |

---

## Findings

### 1. q2 *did* measure peak RSS with ≤30 s segments
- **Claim (§3, Memory):** "Peak RSS for 30 s segments has not been measured; it should be far lower (guess: 1–2 GB)."
- **Source:** q2-captions.md §6.2 (l.481, current file): "Memory: about 1.3 GB peak RSS per worker process with Parakeet int8 (sherpa, 4 threads), Silero, Whisper tiny int8 and the audio tagger all loaded, after one 30 s speech segment … 1.04 GB resident after loading, 1.33 GB peak … macOS arm64 gave 1.8–2.3 GB … A 2 GiB Cloud Run instance is the floor and 4 GiB leaves headroom." [Q2 L1]
- **Severity:** wrong (it states that a measurement in a sibling document does not exist).
- **Correction:**
  - Cite q2 §6.2: the whole audio stack measured 1.33 GB peak on linux/amd64.
  - The remaining budget is then guard (2–3 GB + KV) + SigLIP image tower + Freepik + e5-small + torch runtime + the input file in the in-memory filesystem. That is roughly 5–7 GB (estimate), so 16 GiB is a safety choice, not a need.
  - Keep 16 GiB until the benchmark, but add an 8 GiB sensitivity row: the rate is $0.000116/s, −15% on every CPU-service cost.

### 2. `SIGLIP_MS_M4 = 66` is tagged MEASURED [Q5], but q5 no longer reports 66 ms
- **Claim (§5 Speeds, script l.122):** "SigLIP 2 B/16, M4, 4 threads (q5)" = 66 ms, MEASURED.
- **Source:** q5-labels.md §3 table (current): SigLIP 2 ViT-B-16 **37 ms** median per image at batch 16. Preprocessing is 3–6 ms and JPEG decode 3.5 ms; batch-1 latency is 47 ms. q5 §5b uses 37 + 5.4 + 3.5 = 45.9 ms per image. 66 ms was round 0's single-run figure, which q5 review r1 #4 replaced.
- **Severity:** unsupported (a MEASURED tag on a superseded number).
- **Correction:**
  - Use about 46 ms (inference + preprocessing + decode), or 47 ms (batch 1), and cite q5 §3.
  - Labels then become 30 × 46 × 2.5 ≈ 3.4 s per video ($0.00047), not 5.0 s.
  - The SigLIP share falls from 7% to about 5%, and the "measured-on-M4 inputs about 31%" sentence changes slightly.
  - No conclusion changes.

### 3. The latency bounds of the job columns are understated
- **Claim (§1, §2.4, §6):** "accept up to 1 h (hourly) or 24 h (Delayed Job) of latency"; "If results may arrive up to a day late … Delayed Job".
- **Source:** docs.cloud.google.com/run/docs/delayed-jobs (read 2026-10-08):
  - "The provisioning of a delayed job execution is potentially up to 12 hours, and the total runtime duration of all tasks in a delayed job execution is 12 hours."
  - "a delayed execution will complete within 24 hours".
- **Why the bound is longer:**
  - The grid schedules 2 runs a day (`DELAYED_RUNS_PER_DAY`). An upload therefore waits up to 12 h for the next run, then up to 24 h for that run to complete.
  - With the Haiku Batch API, §2.4 item 4 collects results "on the next run", which adds another 12 h cycle (Batch results are available "after all rows have completed or after 24 hours", Vertex Claude batch page).
  - The worst case is therefore about 48 h or more, not 24 h.
  - For the hourly job, the bound is the slot interval plus the run time. At 100k×5%, a run takes about 52 min at CPU ×1 (44.5 videos × 70 s), so latency is up to about 2 h.
- **Severity:** wrong.
- **Correction:**
  - State the bounds as: hourly ≈ 1 h + run time (up to about 2 h at the largest cell); Delayed Job + Haiku Batch ≈ up to 2–2.5 days worst case.
  - Alternatively, model more delayed runs per day and collect Batch results in a separate light trigger.
  - Feed this into open question 3.

### 4. Execution-length caps are not checked for the CPU jobs
- **Claim (§2.4 item 3):** "Above about one hour of work per run it shards across tasks (a GPU task is limited to 1 h)". The script passes `task_max_s` only for GPU jobs (`batch_overhead(..., GPU_TASK_MAX_S)`). The CPU hourly job and the Delayed Job are modelled as one task.
- **Computed:**
  - Delayed Job at 100k×5%: 21,650 / 60.8 runs ≈ 356 videos per run × 70.2 s ≈ **6.9 h** per execution at CPU ×1, and **13.8 h at ×0.5**. That exceeds the 12 h limit, and "When a delayed job's execution has reached the maximum duration limit, the execution is cancelled by the system" [S22].
  - Because the page caps "the total runtime duration of all tasks", sharding may not help. More runs per day would.
  - CPU hourly job at 100k×5%, ×0.5: about 6,200 s of work per hourly slot. One task cannot keep up (the service equivalent is 180% busy), so the 1 h promise needs ≥ 2 parallel tasks.
- **Severity:** design concern (cost is nearly unaffected; feasibility and latency are).
- **Correction:**
  - Give the CPU hourly job `task_max_s = 3600` (for latency) and the Delayed Job a 12 h execution cap, both in the script.
  - Raise `DELAYED_RUNS_PER_DAY` automatically when work exceeds the cap, or flag the cell as infeasible.
  - Mention the cap in §2.1/§2.4.

### 5. "The `llm-anthropic` extra covers both" is wrong as written
- **Claim (§2.3):** "the `anthropic` SDK supports Vertex through `AnthropicVertex` [S25], so the `llm-anthropic` extra covers both."
- **Source:**
  - Anthropic, Claude on Google Cloud (platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai, read 2026-10-08): the install step is `pip install -U "anthropic[vertex]"`.
  - q8a §9.4 l.659 defines `llm-anthropic = ["anthropic>=1.12"]`, without the `vertex` extra, so the Google auth dependencies are missing.
- **Severity:** wrong.
- **Correction:**
  - Either q8a's extra becomes `anthropic[vertex]>=1.12`, or a separate `llm-anthropic-vertex` extra is added. Note this as a q8a follow-up.
  - The adapter config also needs `region="eu"` (multi-region) and a project id.

### 6. Haiku Batch on Vertex EU is a different API, and the grid's Delayed-Job column assumes it
- **Claim (§2.3, §6):** the Delayed Job column uses "Haiku Batch" at the Vertex EU batch price ($0.055 / $0.275, which is correct per Vertex pricing). §2.4 item 4 speaks of "the Haiku Batch API".
- **Source:**
  - The Anthropic Vertex page lists, under "Features not supported", "API endpoints (Message Batches, Models, …)".
  - Vertex "Batch predictions with Anthropic Claude models" (docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/claude/batch, read 2026-10-08):
    - Input and output go through a BigQuery table or a JSONL file in Cloud Storage.
    - "The global endpoint for partner models isn't supported."
    - "The batch prediction job and your table must be in the same region."
    - Results arrive "after all rows have completed or after 24 hours, whichever comes first".
    - The default is 4 concurrent batch requests per project.
  - Haiku 5.5 is listed. The Haiku 5.5 model page lists "batch predictions" among its supported features and its regions as US multi-region, Europe multi-region and global.
- **Severity:** design concern.
- **Correction:**
  - State that batch mode on the residency-preserving endpoint needs a separate Vertex batch-prediction adapter (a GCS JSONL writer, the Vertex `batchPredictionJobs` API, an EU-located bucket), not the `anthropic` SDK's Message Batches.
  - State also that EU-multi-region support for Claude batch should be confirmed on the Claude regions page.
  - Add this to §2.4 item 4 and open question 12.

### 7. The 15 s CPU cold start is not supported, and it has no sensitivity row
- **Claim (§3, §5):** `COLD_START_S_CPU` = 15 s ("container start + model load", GUESS). Only the GPU cold start gets a 60 s sensitivity row.
- **Source:**
  - q5 §3 measured SigLIP 2 B/16 alone at about 1 s `import` + 4.9 s model load on the M4. q5 §5b uses "≈ 6 s on M4 × 2 = 12 s" for SigLIP alone.
  - With q7's 2.5× factor, SigLIP alone is about 15 s, before Parakeet, Freepik, `tiny`, e5-small, the 2–3 GB guard and the pull of a 3–5 GB image.
  - Google's best-practices page warns that "An image containing a large model will take longer to import" [S4].
- **Severity:** unsupported (the guess sits below a sibling document's own per-model figure).
- **Correction:**
  - Raise the base guess (for example 30–60 s), or derive it from q5's load measurement × 2.5 summed over the models.
  - Add a "CPU cold 60 s" sensitivity row. At 1k×3% the overhead goes from $0.25 to about $1.0/month (computed: 0.935 × 60 s × $0.000136 × 129.9). The latency effect (about 1 min on nearly every video below about 1,350 videos/month) matters more than the cost.
  - Note lazy loading of the guard as a mitigation.

### 8. Missing option: overlap single-threaded and poorly scaling steps on the 4 billed vCPUs
- **Claim (§2.2, §5):** one job per instance on 4 vCPU. VAD is single-threaded ("3 of 4 vCPUs idle unless overlapped with frame work", §5), but the grid bills all stages strictly in series.
- **Source:** q5 §5b (l.190): "On the M4, 4 threads gave 37 ms per image and 1 thread 54 ms … about 148 vs 54 vCPU-ms per image … Single-thread workers … would cut local compute cost by about 2.7× (computed). That matters only for q7 sizing."
- **Severity:** missing option.
- **Correction:**
  - Add the option of running the audio branch (VAD → LID → ASR) and the frame branch (Freepik, SigLIP) concurrently inside one job (two threads, each with fewer intra-op threads), or of sizing a 2 vCPU instance for the frame work.
  - Under request-based billing the cost follows wall time, so this could cut the 70 s per video materially. That is unmeasured; put it in open question 1.
  - q8a runs each job in one worker thread, so this would be an `app`-level stage-parallelism decision (follow-up for q8a).

### 9. The §9 note on q8a concurrency is stale
- **Claim (§9 row 16):** "the current q8a text reads `max_jobs + 2`; this doc follows the finalised rule".
- **Source:** q8a-architecture-layout.md §6.3 (l.523) now reads "Cloud Run `--concurrency = max_jobs`" (q8a r2 finding 5 fixed). The 1800 s `dispatch_deadline_s` and the 1500 s `attempt_budget_s` (l.513–515) are consistent with q7 §1. q8a also sets `max_jobs = 2` on GPU by default; the L4 service column implicitly assumes one job at a time.
- **Severity:** minor.
- **Correction:**
  - Drop the parenthesis.
  - Optionally note that q8a's GPU default is `max_jobs = 2`. Under instance billing that only reduces idle time, so the L4 service column is a conservative upper bound.
  - Optionally note that a 5-minute video (about 73 s at ×1, about 150 s at ×0.5) sits far inside the 1500 s budget.

### 10. Free-tier switch: small leftovers
- **Issue:**
  - With `APPLY_FREE_TIER = True`, the headings still print "free tier off" (`main()` hard-codes the string in two places).
  - The per-stage rows never show the credit; only the totals do.
  - The "Hosted reference" column has `kind = "none"`, so it gets no credit, although it bills Cloud Run request-based seconds (the VAD gate, decode and synchronous waits).
  - Totals are clamped and non-negative, as claimed.
- **Severity:** minor.
- **Correction:**
  - Print the heading from the flag.
  - Add a "free-tier credit" row.
  - Give the hosted reference the request-based credit on its Cloud Run seconds.

### 11. Delayed Jobs GPU: the pricing page answers part of open question 7
- **Claim (§2.1, OQ 7):** "GPU support not stated."
- **Source:** cloud.google.com/run/pricing (downloaded 2026-10-08). The Delayed Jobs table lists "GPU Type NVIDIA L4 non-zonal redundancy (per second) $0.0001867" and RTX PRO 6000 $0.00036522, next to CPU $0.0000126 and memory $0.0000014. The delayed-jobs doc page does not mention GPUs.
- **Severity:** minor.
- **Correction:** "Pricing lists L4 / RTX PRO 6000 for Delayed Jobs at the normal GPU rate (no discount); the feature page does not document GPU use."

### 12. Gemini 3.x EU endpoint availability is assumed, not checked
- **Claim (§1, §5, §6):** "Gemini 3.1 / 3.5 Flash-Lite (Vertex EU)", priced at the non-global rate [S27].
- **Source:**
  - The Vertex pricing page gives only Global vs "Non-global" prices; it does not say which locations serve the 3.x Flash-Lite models.
  - Third-party reports (github.com/epam/ai-dial-adapter-vertexai issue 471; n8n community thread "Gemini-3.1-flash-lite not supported in Google Vertex Chat Model node") suggest that 3.x models are served on the `eu` multi-region endpoint, not on single regions such as europe-west4. These are not authoritative.
- **Severity:** minor (reference option only).
- **Correction:** add to open question 9: "confirm on Google's model/locations page that 3.1/3.5 Flash-Lite are served on `aiplatform.eu.rep.googleapis.com`".

### 13. Cross-document drift: q5 still uses q7's old shape and slowdown
- **Claim:** q7 now uses 16 GiB and `CLOUD_SLOWDOWN_VS_M4` = 2.5.
- **Source:** q5-labels.md §3 and §5b, and q5 [S50] (l.464): "Cloud Run shape 4 vCPU / 8 GiB; `CLOUD_SLOWDOWN_VS_M4` = 2.0". q5 §5b computes its local cost with "× 2 for the assumed Cloud Run slowdown [S50]".
- **Severity:** minor.
- **Correction:** record in q7 §9 (or as a q5 follow-up) that q5's local-cost figures should be rescaled. ×2.5 and 16 GiB raise them by about 46% (1.25 × 1.17). No q5 conclusion changes.

### 14. The idle-retention source for the request-based service is the instance-based page
- **Claim (§3, §5):** `IDLE_WINDOW_S = 900`, "upper bound [S6]", used for p_cold of the request-based CPU service.
- **Source:** [S6] (billing settings) describes instance-based billing ("will never stay idle for more than 15 minutes"). The pricing page says only that idle non-minimum instances are not charged.
- **Severity:** minor.
- **Correction:** cite Cloud Run's instance-autoscaling page for idle retention of request-based services, or state that the same 15-minute upper bound is assumed. A shorter real retention raises p_cold; add that to open question 8.

### 15. Rounding of the ×2 sensitivity
- **Claim (§1):** "×0.55–0.6 at ×2".
- **Computed:** 0.965/1.59 = 0.61 and 119.60/222.90 = 0.54 (×0.5: 1.77–1.93, stated as "×1.8–1.9", which is fine).
- **Severity:** minor.
- **Correction:** "about ×0.55–0.6" is acceptable; "×0.54–0.61" is exact.

---

## Verified correct (new or changed claims)

- **Vertex Haiku 5.5:**
  - Model page (docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-5-5, read 2026-10-08): "Generally available", released 2026-10-07, retirement "Not sooner than October 7, 2027".
  - Regions: United States multi-region, Europe multi-region, global. ML processing for Europe is multi-region.
  - Batch predictions and prompt caching are supported. The multi-region quota is 1,500 QPM.
- **Vertex pricing** (downloaded 2026-10-08):
  - Haiku 5.5 global $0.10 / $0.50, Batch $0.05 / $0.25.
  - Regional / multi-region $0.11 / $0.55, Batch $0.055 / $0.275.
- **Anthropic Vertex page:**
  - "Regional and multi-region endpoints include a 10% pricing premium over global endpoints".
  - Multi-region `us`/`eu`, `aiplatform.eu.rep.googleapis.com`.
  - "Specific regional endpoints support Claude Sonnet 4.6 and earlier; newer models use the global or multi-region endpoints."
- **Anthropic data residency** (platform.claude.com/docs/en/manage-claude/data-residency):
  - `inference_geo` is only `"global"` (default, "may run in any available geography") or `"us"`; US-only inference is 1.1×.
  - "Currently, `"us"` is the only available workspace geo".
  - On Google Cloud the region is set by the endpoint.
- **Gemini on Vertex:**
  - 3.1 Flash-Lite audio input: global $0.50, non-global $0.55. Output: $1.50 / $1.65.
  - 3.5 Flash-Lite input (text, image, video, audio): $0.30 / $0.33. Output: $2.50 / $2.75.
- **STT V2** (downloaded 2026-10-08):
  - Standard costs $0.016/min for 0–500k min.
  - Dynamic batch costs $0.003/min, "processes audio at a lower level of urgency".
  - Each request is rounded up to 1 s.
- **Cloud Run pricing:**
  - Jobs: $0.000018 / $0.000002, minimum 1 minute, free tier 240k vCPU-s / 450k GiB-s.
  - Delayed Jobs: $0.0000126 / $0.0000014, "Prices are dynamic and can change up to once every 30 days", free tier 342,857 vCPU-s / 642,857 GiB-s "(based on us-central1 pricing)". The europe-west1 and west4 rows are included.
- **Delayed Jobs page:**
  - Preview.
  - Provisioning "potentially up to 12 hours"; task timeout 12 h; completes within 24 h.
  - `gcloud beta run jobs create --delay-execution` and `execute --delay-execution` (with `--async`).
- **Memory limits page:** 4 vCPU allows "2 to 16 GiB"; 6 vCPU "4 to 24 GiB"; the maximum is 32 GiB; writing files to the file system counts against memory.
- **MEASURED tags, other than finding 2:**
  - Parakeet 32.3 RTFx (q2 l.471).
  - LID 0.4–0.9 s per clip (q2 l.326).
  - Freepik 28 ms on an RTX 3090 (q4 l.74).
  - 9800X3D int8 30.5 and T4 57.6 (q2 l.73).
  - Freepik and the guard are correctly GUESS; q4 says "No source gives CPU latency for any of these models".
- **q8a consistency:**
  - `--concurrency = max_jobs`, `max_jobs = 1` on small CPU instances.
  - 1800 s `dispatchDeadline`, 1500 s attempt budget, one `jobs.run` per media for long media (§6.4(a)).
  - CTranslate2 on CPU (§9.5).
  - `cpu`/`cu130` image variants.
