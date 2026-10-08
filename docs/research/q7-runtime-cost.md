# Q7: Where it runs and what it costs

Research date: 2026-10-08. Revised the same day after review round 1 ([reviews/q7-review-r1.md](reviews/q7-review-r1.md), resolution in §9) and the final review round 2 ([reviews/q7-review-r2.md](reviews/q7-review-r2.md), resolution in §10). Every source was read on 2026-10-08 unless another date is given. Source tags like [S3] point to the Sources list. Figures marked **(estimate)** are this author's derivation, not a measurement or a quoted price. Speed inputs are tagged **MEASURED** or **GUESS** in §5 and in the script. Model choices come from Q2–Q6 and are not re-decided here. Prices are USD list prices for EU Tier-1 Cloud Run regions and EU Vertex AI endpoints, with no committed-use discounts.

Scope: only **AI processing** cost is counted. That means scenewise's own compute for running local models (now including media decoding and the transcript text embedding), plus hosted-model API fees, plus the instance time billed while scenewise waits for a hosted API. Storage, Cloud Tasks, egress and Expause's own compute are excluded. The Cloud Run free tier is switched **off** in the main grid (`APPLY_FREE_TIER = False`), because it is per billing account [S1] and Expause's existing Cloud Run usage probably consumes it already (open question 5). A "free tier on" row is in the sensitivity table.

Settled user decisions that apply ([user-decisions.md](user-decisions.md)): U3, the operator is EU-based; U4, Parakeet v2 with attribution, faster-whisper as the fallback.

---

## 1. Summary and recommendation

**Recommendation (Expause, now):**

- Run scenewise as one **Cloud Run service on CPU**, in **europe-west1** (or whichever Tier-1 EU region holds Expause's buckets).
  - Billing: request-based, which bills only while a request is in flight, plus start-up.
  - Instances: minimum 0, **4 vCPU / 16 GiB to start, 8 GiB as the target once the benchmark confirms the peak** (§3). `max_jobs = 1` and Cloud Run concurrency = `max_jobs` as in q8a, called by Cloud Tasks with the synchronous push handler and the 1800 s deadline (q8a §6.3).
  - Why 16 GiB first: Q2 measured the whole audio stack at **1.33 GB peak RSS** for a 30 s segment [Q2 §6.2]. The rest of the job (the tier-2 guard with its KV cache, the SigLIP image tower, Freepik, e5-small, the torch runtime and the input file in the in-memory filesystem) brings the estimate to about 5–7 GB. The guard model's RAM is the unknown that decides it. 16 GiB is a safety margin, not a measured need. 8 GiB costs **14–15% less** in every CPU column (sensitivity row "CPU 8 GiB").
  - It runs captions (sherpa-onnx Parakeet int8 + Silero VAD + faster-whisper `tiny` LID gate, per Q2), moderation tier 1 and 2, labels (SigLIP 2) and the optional transcript embedding locally.
- **Summaries and chapters use Claude Haiku 5.5, synchronously**, as Q3 recommends. The instance stays billed while it waits for Haiku. The grid counts that wait: 3 s (guess) ≈ $0.0004 per video, about as much as the Haiku fee itself.
  - Local Qwen3.5-4B on Cloud Run CPU costs about **$0.0129 per video**, against **$0.00075** for Haiku including the billed wait: about 17× more (estimate).
  - **Which Haiku endpoint is a user decision** (§2.3, open question 12). Vertex AI's EU multi-region endpoint keeps inference in the EU at +10%. The Anthropic first-party API offers only `global` or `us` inference and US-only workspace storage. The grid uses the Vertex EU price. The difference is at most $0.68/month in the grid.
- **Monthly AI cost of this setup** (estimate, CPU speed ×1, 16 GiB): **$1.89** (1k MAU × 3%), **$3.11**, **$16.28**, **$25.23**, **$131.15**, **$218.46** (100k MAU × 5%).
  - If Cloud Run vCPUs are half as fast as assumed: $3.10 to $421.
  - If they are twice as fast: $1.28 to $117.
  - At 8 GiB: $1.62 to $187 (§6 sensitivity table).
- **Bake model weights into the image.** Build **two image variants from the same code and the same pinned weights layer**: `-cpu` (the service) and `-cuda` (cu130, for an L4 job). With one image, every CPU cold start would pull several GB of CUDA libraries it never uses (§2.5).
- **If Expause accepts results up to about 2 h late**, a **Cloud Run CPU job run hourly** is cheaper than the service at every volume in the grid.
  - It costs about 25% less and carries no GPU quota risk.
  - The worst case is the 1 h slot plus the run time: up to 1.9 h at 100k × 5%. Above about 1 h of work per slot, the run is sharded across parallel tasks.
  - Above roughly 60 video-hours/month an **L4 hourly job** is cheaper again. That crossover moves between 1 h and 320 h across the CPU-speed range, so it must wait for the benchmark.
  - Both need a batch intake that q8a does not have (§2.4).
  - Savings over the recommended service: about $54/month (CPU job) and $98/month (L4 job) at 100k × 5%; $7 and $10 at 10k × 5%.
- **If results may arrive two to three days late** (backfills, digests), a Cloud Run **Delayed Job** is the cheapest option: $0.81 to $112/month.
  - It is Preview with a dynamic price and can wait up to 12 h for provisioning [S22].
  - It uses Haiku batch prediction on Vertex AI. Worst-case latency is about 49–56 h, because the next run, provisioning, the run itself and the up-to-24 h batch window add up (§2.4).
  - With synchronous Haiku inside the same job, the worst case is about 24–31 h, for $0.03–4.32/month more.
  - Vertex batch prediction is a different API from Anthropic's Message Batches, so it needs its own adapter (§2.3).
- **Do not use**:
  - **A Cloud Run GPU service** for this traffic. It needs instance-based billing, and an idle GPU instance stays billed for up to 10 minutes after each request [S1][S3][S29]. Sporadic uploads therefore pay for mostly idle L4 time: $24–$642/month in the grid.
  - **Always-on VMs**: g2-standard-4 costs $542/month on-demand or about $325/month on spot [S8]; e2-standard-4 costs $108/month per VM [S8].
    - Neither scales to zero, and both add operations work.
    - An e2 VM + Haiku matches the recommended service only from about 920 video-hours/month (CPU ×1). The CPU hourly job is cheaper than both there.
  - **GitHub Actions** for anything but CI and evaluations.
    - It costs about 3× a Cloud Run L4 per hour.
    - It would move EU user data to GitHub-hosted runners outside Google Cloud.
    - The terms also restrict runner use to the software project (§4; whether Expause backfills fall outside that is a judgement).

**What the grid says per stage** (per 5-minute video, CPU speed ×1, all estimates; §6):

| Stage | Local, Cloud Run CPU | Local, L4 (busy time only) | Hosted (same gate, EU endpoint, wait billed) | Cheapest sensible choice |
|---|---|---|---|---|
| Captions | $0.0026 | $0.0033 (LID and VAD stay on the CPU in the GPU image) | Gemini 3.1 Flash-Lite $0.0040; 3.5 Flash-Lite $0.0037; STT V2 standard $0.035; STT V2 dynamic batch $0.0066 (async only) | Local, but **close**: at CPU speed ×0.5 local is $0.0051, dearer than gated Gemini 3.x ($0.0040–0.0043). Decide after the benchmark |
| Summaries + chapters | $0.0129 (Qwen3.5-4B) | $0.0012 | Haiku 5.5 $0.00075 (fee $0.00035 + wait $0.00041) | **Haiku 5.5** |
| Moderation (tier 1 + 2) | $0.0057 | $0.0004 | Haiku on 30 frames $0.0023 (fee only) | Local. Haiku is cheaper than *CPU* but refuses explicit frames (Q4), so it is not a substitute |
| Labels | $0.0005 | $0.00004 | Haiku tagging $0.0004 (fee only) | Local. Haiku returns no embedding (Q5) |
| Shared (decode + text embedding) | $0.0006 | $0.0012 | n/a | needed by every option |

**Where the numbers are weakest.** No source gives Cloud Run vCPU speeds for any of these models.

- In the recommended mix (69 CPU-s per video), **two pure guesses make up 61% of the local seconds**: Freepik tier 1 (`FREEPIK_MS_M4`, 44%) and the tier-2 guard (`GUARD_S_PER_FRAME_CPU`, 17%).
- The inputs measured on the M4 (Parakeet, LID, SigLIP) make up about 29%, but they all pass through one guessed M4-to-Cloud-Run factor (2.5).
- What that means, from the sensitivity table:
  - CPU speed ×0.5 moves the recommended total by ×1.6–1.9; ×2 moves it by ×0.54–0.68. The small cells move less because their cold-start share is fixed.
  - The L4-vs-CPU crossovers move by more than 10×.
- The CPU cold start (35 s, derived from q5's SigLIP load measurement; §3) adds about 35 s of latency to most videos below about 1,350 videos/month. At 60 s it costs $0.4–2.4/month more.

**The first engineering task is a 1-hour benchmark on Cloud Run** (open question 1). Measure, in this order:

1. Freepik and the guard.
2. ASR, LID and SigLIP.
3. Cold start and **peak RSS with the guard loaded** (decides 8 vs 16 GiB).
4. Whether running the audio and frame branches concurrently saves the 9–14% the grid's "parallel branches" row assumes.

Every crossover in §7 moves with these results.

---

## 2. Runtime options per stage

### 2.1 Platform facts (Google Cloud, read 2026-10-08)

| Option | EU availability | Billing | Price (Tier 1: europe-west1 and europe-west4 are both Tier 1 [S1]) | Limits / notes |
|---|---|---|---|---|
| **Cloud Run service, request-based** | All EU regions | Billed while starting, while shutting down, and while ≥1 request is in flight. Idle non-min instances are not billed [S1] | CPU $0.000024/vCPU-s; memory $0.0000025/GiB-s; $0.40 per 1M requests. Free tier 180k vCPU-s, 360k GiB-s and 2M requests per month per billing account [S1] | Max 8 vCPU / 32 GiB per instance; 4 vCPU allows up to 16 GiB, above 16 GiB needs 6 vCPU [S23]; request timeout 60 min [S7]. Cloud Tasks HTTP dispatch is at most 30 min (q8a). **4 vCPU / 16 GiB = $0.000136/s** (computed) |
| **Cloud Run service, instance-based** | All EU | Whole instance lifetime, minimum 1 min [S1]. "Charged for the entire lifecycle of instances, even when there are no incoming requests"; an instance "will never stay idle for more than 15 minutes" [S6] | CPU $0.000018/vCPU-s; memory $0.000002/GiB-s. Free tier 240k vCPU-s, 450k GiB-s [S1] | **Required for GPUs** [S3] |
| **Cloud Run GPU (service, job or worker pool)** | **L4: europe-west1 and europe-west4. RTX PRO 6000: europe-west4 only** [S3][S5][S10] | Instance-based. "Approximately 5 seconds" to start with drivers; services can scale to zero [S3] | L4 without zonal redundancy **$0.0001867/s**; with zonal redundancy $0.0002909/s. RTX PRO 6000 $0.00036522/s (non-zonal) [S1] | L4 needs at least 4 vCPU / 16 GiB; RTX PRO 6000 at least 20 vCPU / 80 GiB. Default quota 3 GPUs per region, non-zonal [S3]. Driver 580 / CUDA 13.0. **L4 + 4 vCPU + 16 GiB = $0.000291/s = $1.0465/h** (computed) |
| **Cloud Run job** | All EU; GPU as above | Instance-based, minimum 1 min [S1] | Same as instance-based. **4 vCPU / 16 GiB = $0.000104/s** (computed), 24% below request-based | Task timeout 168 h, or **1 h with GPUs** [S7]. The grid also caps an hourly CPU task at 1 h, for latency, and shards above that (§2.4). GPU jobs run non-zonal only and are best-effort against the 3-GPU quota [S5]; a CPU fallback is needed |
| **Cloud Run Delayed Jobs** | Listed in the pricing table | Instance-based | CPU $0.0000126/vCPU-s; memory $0.0000014/GiB-s ("Prices are dynamic and can change up to once every 30 days") [S1]. **4 / 16 = $0.0000728/s**, 47% below request-based. Own free tier 342,857 vCPU-s / 642,857 GiB-s [S1] | **Preview** (Pre-GA terms). Provisioning "potentially up to 12 hours"; "the total runtime duration of all tasks in a delayed job execution is 12 hours", and an execution that reaches it "is cancelled by the system"; so an execution completes within 24 h. `gcloud beta run jobs create --delay-execution`, or run any job as delayed with `execute --delay-execution` [S22]. **GPU:** the pricing page lists L4 ($0.0001867/s) and RTX PRO 6000 ($0.00036522/s) for Delayed Jobs at the normal GPU rate, with no discount [S1]; the feature page does not document GPU use [S22] |
| **Cloud Run worker pool** | All EU; GPU as above | Instance-based; manual instance count. "GPU worker pools cannot be autoscaled" [S10] | CPU $0.000011244/vCPU-s; memory $0.000001235/GiB-s; L4 $0.0001867/s [S1] | Pull-based, not Cloud Tasks push. Always-on 4 vCPU / 16 GiB about $170/month; L4 + 4 / 16 about $661/month (printed by the script) |
| **Compute Engine g2-standard-4** (1× L4, 4 vCPU, 16 GiB) | europe-west1, europe-west3, europe-west4 [S9] | Per second while running | **$0.742916/h on-demand, $0.445676/h spot** (spot is dynamic) in europe-west4 [S8]. europe-west1: $0.7783/h on-demand, about $0.45/h spot [S8][S9] | Spot can be pre-empted. Always-on: $542 / $325 per month |
| **Compute Engine e2-standard-4** (4 vCPU, 16 GB) | All EU | Per second | **$0.1475/h** europe-west4 [S8] ($107.67/month) | e2 CPU platform is not fixed, so per-vCPU speed may differ from Cloud Run (judgement) |
| Compute Engine c4-standard-8 | europe-west4 | Per second | $0.415107/h on-demand on the official general-purpose pricing page [S8]; region mapping and $0.1812/h spot from [S9] | Not used in the grid |

### 2.2 Per-stage choice

| Stage | Model (Q2–Q5) | Runtime now | Later or alternative | Why |
|---|---|---|---|---|
| Captions | Silero VAD v6.2 → own ≤30 s segmentation → faster-whisper `tiny` LID gate → Parakeet-TDT-0.6b-v2 int8 on sherpa-onnx (Q2). Fallback faster-whisper large-v3-turbo | Cloud Run CPU service | CPU or L4 hourly job if latency allows | About 19 CPU-s per video (estimate). On an L4 the ASR drops to about 2 s, but LID (CTranslate2) and VAD stay on the CPU in the GPU image (q8a §9.5), so captions on the L4 instance still take about 11 s and cost more than on the CPU service |
| Summaries + chapters | Haiku 5.5 sync (Q3); local Qwen3.5-4B for self-hosters | Haiku via Vertex AI EU multi-region **or** Anthropic API (user decision, §2.3), called in the same request after captions and labels (it needs them as input, so it cannot overlap them) | Haiku batch in a latency-tolerant job (Vertex batch prediction, its own adapter, §2.3) | Haiku is about 17× cheaper than CPU Qwen per video even with its wait billed |
| Moderation | Freepik nsfw_image_detector, plus SigLIP 2 zero-shot (shared with labels), plus a guard VLM on escalated frames | Cloud Run CPU | CPU or L4 job | Freepik on CPU (about 1 s per frame, guess) is now the largest single item; the guard (20 s per escalated frame, guess) adds about 12 s per video |
| Labels + embedding | SigLIP 2 ViT-B/16 (one pass) | Cloud Run CPU | CPU or L4 job | 30 frames × about 115 ms ≈ 3.4 s per video (45.9 ms on the M4 = 37 ms inference + 5.4 ms preprocessing + 3.5 ms JPEG decode, measured in q5 §3, × 2.5) |
| Shared | ffmpeg decode (audio + 30 frames); `multilingual-e5-small` transcript embedding (opt-in, Q5) | same instance | — | About 4.3 s per video, all guessed |
| Translation (deferred, Q6) | Haiku 5.5 | API | n/a | Note only: about $0.015–0.034 per target language per video-hour [Q6] |

**Why one service rather than one per stage.**

- Every stage of a video runs in the same request, so audio and frames are decoded once.
- Per-stage services would multiply cold starts and image pulls.
- Splitting off the guard model into a separate service is worth it only if the benchmark shows it pushes peak memory above 16 GiB (judgement).

**Option: run the audio and frame branches concurrently** (not in q8a v1; sensitivity row "parallel branches").

- The audio branch (VAD → LID → ASR, 18.9 s) and the frame branch (Freepik, SigLIP, guard, 45.4 s) are independent until the summary step. Together they make up most of a job.
- Several of their steps use the 4 billed vCPUs poorly:
  - Silero VAD is single-threaded.
  - q5 measured SigLIP at 37 ms per image with 4 threads against 54 ms with 1 thread: 148 vs 54 vCPU-ms per image [Q5 §5b].
- Running the two branches in two threads, each with fewer intra-op threads (for example 2 + 2), should therefore hide much of the shorter branch behind the longer one.
- Request-based billing follows wall time, so the saving is direct. The grid's row assumes **50% of the shorter branch is hidden (guess)**: 68.7 → 59.2 s per video, **−14% billed seconds**, −9% to −13% on the monthly totals.
- Unmeasured (open question 1). The alternative is a 2 vCPU shape for frame-only work, which needs its own service.
- In q8a each job runs in one worker thread. This option would be an `app`-level stage-parallelism decision inside `handle_delivery` (follow-up for q8a, open question 13).

**Concurrency and load** (aligned with q8a §6.3). One job per instance (`max_jobs = 1`), Cloud Run concurrency = `max_jobs`, Cloud Tasks `maxConcurrentDispatches ≤ max_instances × max_jobs`. q8a's GPU default is `max_jobs = 2`. Under instance billing that only reduces idle time, so the L4 service column, which assumes one job at a time, is a conservative upper bound. A 5-minute video (about 72 s at CPU ×1, about 140 s at ×0.5, plus Haiku) sits far inside q8a's 1500 s attempt budget. Cost is almost unaffected by scale-out under request-based billing (each busy second is billed once). Latency is affected: at 100k × 5% the recommended setup is busy about 89% of active hours in one-instance-equivalents (printed per cell in §6), so Cloud Run runs 2+ instances at peaks, and the single-instance cold-start formula below understates cold starts once load passes about 0.3 instance.

### 2.3 Haiku endpoint and EU data residency (decision for the user)

Transcripts, labels and (optionally) moderation frames leave scenewise when Haiku is called. For an EU operator (U3) the two ways to call Haiku 5.5 differ:

| | **Anthropic first-party API** | **Vertex AI, EU multi-region endpoint** |
|---|---|---|
| Where inference runs | `inference_geo`: `"global"` (default, "may run in any available geography") or `"us"` (×1.1). **No EU option** [S24] | ML processing within the European Union multi-region (`aiplatform.eu.rep.googleapis.com`) [S25][S26] |
| Where data is stored at rest | Workspace geo: "Currently, `"us"` is the only available workspace geo" [S24] | Google Cloud, under Expause's existing Google Cloud terms (not further checked) |
| Haiku 5.5 price per MTok | $0.10 in / $0.50 out; Batch $0.05 / $0.25 [S11] | **$0.11 / $0.55**; Batch $0.055 / $0.275 ("Regional and multi-region endpoints include a 10% pricing premium over global endpoints") [S25][S27]. Single-region endpoints (e.g. europe-west1) serve only Sonnet 4.6 and older; Haiku 5.5 is on global, US and EU multi-region [S25][S26] |
| Status | GA | GA; batch predictions and prompt caching supported; retirement not before 2027-10-07 [S26] |
| Cost difference in the grid | baseline | +$0.004/month (1k × 3%) to +$0.68/month (100k × 5%) |
| For it | Lowest price; new API features usually land here first; one vendor contract with Anthropic | Inference stays in the EU; billing, IAM and audit stay inside Google Cloud, which is where Expause and its data already are; consistent with the reason GitHub-hosted runners are rejected (§4) |
| Against it | Personal data (transcripts) is processed outside the EU; needs a transfer basis (DPA/SCCs; not checked here) | 10% more; features can lag the first-party API; quotas are per project (EU multi-region: 1,500 QPM [S26]) |

**Default in the grid:** Vertex AI EU (`HAIKU_PRICE_MULT = 1.10`), because it is the residency-preserving choice and the cost gap is under $1/month. **The user decides** (open question 12).

**What scenewise needs for each side:**

- **Synchronous calls.** The `anthropic` SDK has a Vertex client, `AnthropicVertex(project_id=..., region="eu")`. With `region="eu"` it calls `aiplatform.eu.rep.googleapis.com` [S25]. Anthropic's install step for it is `pip install -U "anthropic[vertex]"` [S25]: the `vertex` extra brings the Google auth dependencies.
  - q8a currently defines `llm-anthropic = ["anthropic>=1.12"]` (q8a §9.4), which **does not cover Vertex**.
  - If Vertex is chosen, q8a's extra must become `llm-anthropic = ["anthropic[vertex]>=1.12"]`. Alternatively, add a separate `llm-anthropic-vertex = ["anthropic[vertex]>=1.12"]` so that first-party users do not pull Google auth.
  - The adapter config needs `provider: "anthropic" | "vertex"`, the Google Cloud `project_id` and `region` (`eu`).
  - This is a q8a follow-up.
- **Batch calls** (Delayed Job column only). On Vertex, Anthropic's Message Batches endpoint is "not supported" [S25]. Vertex has its own **batch prediction for Claude** [S28]:
  - Input is a BigQuery table or a JSONL file in Cloud Storage in the Claude request format. Output goes to BigQuery or JSONL in Cloud Storage.
  - "The global endpoint for partner models isn't supported", and "the batch prediction job and your table must be in the same region".
  - Full results arrive "after all rows have completed or after 24 hours, whichever comes first".
  - By default a project can run 4 concurrent batch requests.
  - Haiku 5.5 is listed, and its model page lists batch predictions among the supported features [S26]. **Whether batch jobs run in the `eu` multi-region is not stated on the batch page**; confirm on the Claude regions page before building on it (open question 12).
  - Batch therefore needs **its own adapter**, not the `anthropic` SDK: write a JSONL file to an EU bucket, create a `batchPredictionJobs` job, poll it, and read the output. On the first-party API, Message Batches is a different adapter again, inside the `anthropic` SDK.

### 2.4 Latency-tolerant mode: what it would need in q8a

The three job columns in the grid (CPU hourly job, L4 hourly job, CPU Delayed Job) are cheaper than the service, but **q8a has no batch intake.**

- q8a's job path (§6.4(a)) runs **one `jobs.run` per media**, meant for long media.
- Run that way for every upload, each video would pay the 60 s job minimum plus a cold start. On an L4 that is at least 60 s × $0.000291 ≈ $0.0175 per video, or about $378/month at 100k × 5% (estimate), which defeats the purpose.

A micro-batch mode would need (judgement, not designed here):

1. **A pending-request store.** Expause (or a thin scenewise endpoint) writes each request to a queue that a job can drain: a GCS prefix, a Firestore collection, or a Pub/Sub pull subscription. Cloud Tasks push cannot hold work for a job.
2. **A trigger.** Cloud Scheduler runs `jobs.run` hourly, or a Delayed Job at least twice a day. It skips the run when the store is empty (the grid assumes skip-if-empty).
3. **A `scenewise run-batch` CLI.** It claims pending requests (the same job record and CAS as q8a), processes them with the same `handle_delivery`, and publishes as usual. Run-length limits are modelled in the script:
   - **Hourly jobs** (CPU and L4): one task must finish within its hour, both for latency and because a GPU task is limited to 1 h [S7]. Above that the run shards across parallel tasks, each paying its own cold start (`CPU_HOURLY_TASK_MAX_S`, `GPU_TASK_MAX_S`). At CPU ×0.5 and 100k × 5% the CPU job needs 2 tasks per slot. Every other cell needs 1.
   - **Delayed Jobs:** the 12 h cap counts "the total runtime duration of all tasks" [S22], so sharding does not help. The script instead raises the runs per day until one execution stays under 75% of the cap (`DELAYED_EXEC_MAX_S`, `DELAYED_CAP_MARGIN`). At CPU ×1 the largest cell runs 6.8 h per execution at 2 runs a day, which is inside the cap. At ×0.5 it needs 4 runs a day; one 13.6 h run would have been cancelled.
4. **Summaries in batch mode.** There are two ways:
   - Parallel synchronous Haiku calls (grid: 8 in flight, so the billed wait is 3 s / 8 per video).
   - Haiku batch prediction, the Delayed Job column. That is a separate Vertex adapter (§2.3), plus a light collector trigger (grid: hourly) that publishes summaries when the batch output lands.
5. **A CPU fallback** for the L4 job, because GPU jobs are best-effort against a 3-GPU regional quota [S5].
6. **A product decision** on the worst-case latency below (open question 3).

**Worst-case latency, upload to last result** (printed per cell in §6; GUESS-free except the run time):

| Mode | Formula | Grid range (CPU ×1) |
|---|---|---|
| Service (recommended) | cold start + job | about 35 s + 72 s at low volume |
| CPU hourly job + Haiku | 1 h slot + cold start + run time per task | 1.0 h (small cells) to **1.9 h** (100k × 5%) |
| L4 hourly job + Haiku | same | 1.0 to 1.2 h |
| CPU Delayed Job + sync Haiku | 24 h / runs per day + 12 h provisioning + run time | 24 h to **31 h** |
| CPU Delayed Job + Haiku batch | the above + 24 h batch window + 1 h collector poll | 49 h to **56 h** (about 2–2.3 days) |

STT V2 **dynamic batch** ($0.003/min) has the same shape: it is asynchronous at "a lower level of urgency" [S20], so it fits only this mode, not the synchronous push handler.

### 2.5 One image or two

Build **two variants from one Dockerfile**: `scenewise:<ver>-cpu` (onnxruntime CPU, CPU torch) and `scenewise:<ver>-cuda` (q8a's `cu130` selector: torch +cu130, onnxruntime-gpu, cuDNN). Share the code and one pinned weights layer, so the two variants produce the same results from the same models.

- The CUDA libraries add several GB (estimate) that the CPU service would pull on every cold start for no benefit.
- The GPU variant is tied to the Cloud Run driver (580 / CUDA 13.0 [S3]); the CPU variant has no such constraint.
- CTranslate2 (LID, fallback ASR) is CUDA 12 and runs on CPU in both variants (q8a §9.5).

---

## 3. Model weights, memory and cold start

**Sizes** (Hugging Face API, read 2026-10-08, unless marked):

| Model | Size |
|---|---|
| Parakeet int8 for sherpa-onnx (Q2 primary) | about 0.66 GB (encoder 652 MB [Q2]) |
| Parakeet ONNX fp32 (onnx-asr) [S16] | 2.5 GB (not shipped) |
| faster-whisper `tiny` (LID) | about 76 MB [Q2] |
| Silero VAD v6.2 ONNX | about 2 MB |
| SigLIP 2 ViT-B/16 open_clip safetensors [S16] | 1.50 GB on disk, most of it the large-vocabulary text tower. At runtime load only the image tower; the label text embeddings are pre-computed and cached (Q5) |
| Freepik nsfw_image_detector [S16] | 0.17 GB |
| Guard VLM (Shieldstral 3B / ShieldGemma 2 4B) at Q4, plus vision projector | about 2–3 GB (estimate, not checked) |
| `multilingual-e5-small` (opt-in transcript embedding) | about 0.5 GB fp32 (estimate) |
| Qwen3.5-4B Q4 (self-hosters only) | about 2.5 GB (estimate) |

**Totals:** the CPU image carries about 3–5 GB of weights, below Google's "best suited for smaller models less than 10 GB" for image-baked models [S4]. The CUDA variant adds the CUDA libraries.

**Memory: start at 16 GiB, target 8 GiB** (estimate until measured).

- **Audio stack, measured.** Q2 measured peak RSS with Parakeet int8 (sherpa, 4 threads), Silero, Whisper `tiny` int8 and the audio tagger all loaded, after one 30 s speech segment: **1.04 GB resident after loading, 1.33 GB peak**, on linux/amd64 [Q2 §6.2, L1]. Q2 calls 2 GiB the floor and 4 GiB comfortable for audio alone.
  - The 5.1–6.6 GB peaks of a single 334 s pass are the reason Q2 caps segments at about 30 s. They are not a sizing figure.
- **The rest, estimated** (no measurement):
  - Guard VLM in its out-of-process llama.cpp server: 2–3 GB of weights plus KV cache and vision projector, about 0.5–1 GB.
  - SigLIP 2 image tower with the torch runtime: about 1–1.5 GB.
  - Freepik EVA-02: about 0.3 GB.
  - e5-small: about 0.5 GB.
  - The input file in Cloud Run's in-memory filesystem, which counts against instance memory [S7][S23]: up to a few hundred MB for a 5-minute UGC file.
  - Frame buffers: about 20 MB (q8a §9.3).
- **Total: about 5–7 GB.** The guard is the largest and least certain part: Q4 has not yet fixed the model or quantisation (open question 6).
- **Choice.**
  - 4 vCPU allows 2–16 GiB [S23].
  - 16 GiB costs $0.000136/s, against $0.000116/s at 8 GiB. 8 GiB is **−15% on the rate** and −14 to −15% on every CPU-service total (sensitivity row "CPU 8 GiB").
  - The grid keeps **16 GiB** until the benchmark, because one OOM on an odd UGC file costs a retry and a cold start. 16 GiB is a safety choice, not a need.
  - **Drop to 8 GiB if the measured peak with the guard loaded stays below about 6 GiB** (open question 1). Loading the guard lazily (only when a frame escalates) helps both memory and cold start.
  - If the guard pushes the peak above 16 GiB, move it to its own service rather than going to 6 vCPU / 24 GiB.

**Model-loading options**, from Google's GPU inference best-practices page (updated 2026-10-07) [S4]:

| Option | What Google says | Fit for scenewise |
|---|---|---|
| **Bake into the image** | "best suited for smaller models less than 10 GB". Changing models means a rebuild. "An image containing a large model will take longer to import into Cloud Run." | **Default.** Weights are under 10 GB. The image is immutable and versioned with the code (models are pinned per release). No VPC is needed. |
| Cloud Storage via gcloud CLI download | "Google recommends downloading ML models from Cloud Storage". Needs Direct VPC (all-traffic egress) and Private Google Access, plus enough RAM, because the files land in memory | Use when an adopter swaps models without rebuilding. The in-memory filesystem counts against instance memory [S7] |
| Cloud Storage FUSE volume mount | Faster than a download at start-up; `cache-dir` or `enable-buffered-read` reduce read time | Good for self-hosters with many model variants |
| Download from the internet (HF Hub) at start-up | Not recommended ("reliability risk") | **Never in production.** Fine in dev |

**Cold start:**

- Cloud Run sets "no direct limit" on container image size [S7], but "an image containing a large model will take longer to import" [S4].
- **CPU, derived (estimate): 35 s** = 10 s image import and container start (GUESS) + (5.9 s SigLIP import and load, MEASURED on the M4 in q5 §3, + 4 s for Parakeet, Silero, `tiny`, Freepik and e5-small, GUESS) × 2.5 (`CLOUD_SLOWDOWN_VS_M4`).
  - The guard is assumed to load lazily. With 2% of frames escalating, about 45% of videos (1 − 0.98³⁰) still load it at some point, so the real figure may be higher.
  - The sensitivity row uses 60 s.
- **GPU: 25 s** (guess): driver start about 5 s [S3], plus image import and model load. Sensitivity 60 s.
- **How often.** Computed from p_cold = exp(−λ · W), with λ = videos / (30.4 × 16 × 3,600 s).
  - W = 900 s for CPU instances and 600 s for GPU. Cloud Run "might keep instances idle for a period of time after they finish handling requests", "up to 15 minutes, or 10 minutes for GPUs" [S29]. Both values are upper bounds; a shorter real retention raises p_cold (open question 8).
  - On CPU, **most videos cold-start below about 1,350 videos/month** (p = 50%), and about a third do at 2,165 videos/month.
  - **Fewer than 10% do above about 4,500** videos/month, fewer than 1% above about 9,000, and at 12,990 videos/month it is about **0.1%**.
- **Cost.** At the smallest cell, cold starts cost about $0.58/month at 35 s, or $0.99 at 60 s. They add about 35–60 s of latency to nearly every video there. The latency matters more than the cost.
- The formula assumes one instance. Above about 0.3 instance of load (the two 100k cells, at 53% and 89%), scale-out adds cold starts that the grid does not model.

---

## 4. GitHub Actions

| Question | Finding |
|---|---|
| Prices | Linux 2-core $0.006/min, 4-core $0.012, 8-core $0.022. **GPU 4-core (Tesla T4 16 GB, 28 GB RAM) $0.052/min = $3.12/h** [S13][S14]. That is about 3× a Cloud Run L4 + 4 vCPU instance ($1.05/h), and the GPU is slower. |
| Included minutes | Free 2,000 / Pro 3,000 / Team 3,000 / Enterprise 50,000 per month. Standard runners are free on public repos. "Larger runners are always charged for, even when used by public repositories" [S15][S17] |
| Time limits | 6 h per job on GitHub-hosted runners, 5 days self-hosted, 35 days per workflow run [S15] |
| Terms | Actions must not be used for "the provision of a stand-alone or integrated application or service offering the Actions product", "as part of a serverless application", or, on GitHub-hosted runners, "any other activity unrelated to the production, testing, deployment, or publication of the software project" (effective 2026-08-27) [S12] |
| **Verdict** | **CI only, plus project-related evaluation:** unit tests, an accuracy regression on public benchmark sets, ONNX conversion/quantisation as a release artefact, and building and publishing both image variants. **Not** for Expause backfills, for two factual reasons: they cost about 3× a Cloud Run L4 job per hour, and they would move EU user data out of Google Cloud to GitHub-hosted runners. A third reason is a judgement: an operator's production backfill is arguably "unrelated to the production, testing … of the software project" under the quoted clause. Backfills go to a **Cloud Run job** in Expause's project (≤ 1 h per task with GPU [S7], so shard by video list). |

---

## 5. Parameters

All are named constants at the top of `q7_cost_grid.py`. **MEASURED** means someone measured the number, usually on other hardware; **GUESS** means this author's estimate.

**Volume**

| Name | Value | Source |
|---|---|---|
| `MAU_VALUES` | 1,000 / 10,000 / 100,000 | brief |
| `POSTING_RATES` | 3% / 5% | brief |
| `VIDEOS_PER_POSTER_PER_MONTH` | 4.33 | brief |
| `AVG_VIDEO_MIN` | 5 | brief |
| `ACTIVE_HOURS_PER_DAY` | 16 | GUESS; sets the arrival rate (cold starts, idle tails) and the number of hourly batch slots (486/month, skip-if-empty) |

**Content** (all GUESS; Expause data needed, open question 4)

| Name | Value | Note |
|---|---|---|
| `AUDIO_VIDEO_SHARE` | 0.90 | Expause does not persist `hasAudio` (Q1) |
| `SPEECH_VIDEO_SHARE` | 0.60 | videos that pass the VAD gate; local ASR **and hosted captions** run only on these |
| `SPEECH_FRACTION` | 0.70 | share of a speech video that VAD passes on (210 s, 7 LID windows of ≤30 s) |
| `FRAME_INTERVAL_S` | 10 → 30 frames | Expause `previewsIntervalSeconds` for 1–5 min videos (Q1) |
| `ESCALATED_FRAME_SHARE` | 0.02 | |
| Summary tokens | 2,450 in / 300 out (speech); 1,160 / 150 (no speech) | Q3 scenario A ÷ 12; no-speech is a guess |
| Haiku moderation (reference) | 30 × 448 + 500 in / 30 × 40 + 200 out | Q4 (200 thinking tokens) |
| Haiku labels (reference) | 58 × 33 + 1,000 in / 150 out | Q5; assumes thinking disabled (Haiku 5.5 thinks adaptively by default, Q3) |

**Prices**

| Name | Value | Source |
|---|---|---|
| Cloud Run prices | as in §2.1 | [S1] |
| `VM_*` | as in §2.1 | [S8][S9] |
| Haiku 5.5 | $0.10 / $0.50 per MTok; Batch ×0.5; `HAIKU_PRICE_MULT` 1.10 (Vertex EU) | [S11][S25][S27] |
| Gemini 3.1 Flash-Lite, Vertex non-global | audio in $0.55, out $1.65 per MTok (global $0.50 / $1.50; Gemini API $0.50 / $1.50) | [S27][S18] |
| Gemini 3.5 Flash-Lite, Vertex non-global | in $0.33, out $2.75 (global $0.30 / $2.50) | [S27][S18] |
| `GEM_AUDIO_TOK_PER_S` | 32 | Gemini audio page, stated generically, not per model [S19] |
| `GEM_CAPTION_OUT_TOK_PER_MIN` / `GEM_PROMPT_TOK` | 260 / 300 | GUESS |
| STT V2 | standard $0.016/min; dynamic batch $0.003/min | [S20] |
| `HAIKU_WAIT_S` / `GEMINI_CAPTION_WAIT_S` / `STT_WAIT_S` | 3 / 6 / 10 s | GUESS; billed at the calling runtime's rate |
| `HAIKU_JOB_PARALLEL` | 8 | GUESS; concurrent Haiku calls inside a batch job |

**Shapes**

| Name | Value | Source |
|---|---|---|
| `CPU_VCPU` / `CPU_GIB` | 4 / 16 | §3 (safety default) |
| `CPU_GIB_SMALL` | 8 | sensitivity row; target if the measured peak stays below about 6 GiB (§3) |
| `GPU_VCPU` / `GPU_GIB` | 4 / 16 | L4 minimum [S3] |
| `MAX_JOBS_CPU` | 1 | q8a §6.3 |

**Speeds**

| Name | Value | Kind | Source / note |
|---|---|---|---|
| `CPU_SPEED_FACTOR` | 1.0 (sensitivity 0.5 and 2) | knob | scales every CPU step |
| `CLOUD_SLOWDOWN_VS_M4` | 2.5 | GUESS | 4 Cloud Run vCPUs (on Compute Engine a vCPU is one hardware thread, so about 2 physical cores) vs 4 M4 performance-core threads. Was 2.0 |
| `PARAKEET_M4_RTFX_4T` | 32.3 → **RTFx 12.9 on 4 vCPU** | MEASURED (M4) | sherpa-onnx int8, 12.6 s clip, 4 threads [Q2 L1]; short segments match Q2's ≤30 s segmentation. Long single passes ran at 13.8–16.8 [Q2 L1] |
| `PARAKEET_9800X3D_INT8_RTFX` | 30.5 | MEASURED (desktop), cross-check only | onnx-asr page; thread count and audio length not stated. Scaled to 4 vCPU × 0.7: RTFx 5.3 if it used 16 threads, 10.7 if 8 — both inside the ×0.5 sensitivity band |
| `PARAKEET_GPU_RTFX` | 57.6 | MEASURED (T4) | onnx-asr CUDA [Q2 S9]; lower bound for L4 |
| `VAD_RTS_1THREAD` × `VAD_CLOUD_EFFICIENCY` | 165 × 0.7 | MEASURED (V5, Threadripper) × GUESS | Silero wiki gives V5 only; Q2 uses v6.2 [S21]. Single-threaded, so 3 of 4 vCPUs idle unless overlapped with frame work (`BRANCH_OVERLAP_HIDE`) |
| `LID_S_PER_WINDOW_M4` | 0.65 s × 7 windows × 2.5 | MEASURED (M4) × GUESS | faster-whisper `tiny` int8, 0.4–0.9 s per clip [Q2 L1]. Runs on CPU in GPU images too (q8a §9.5) |
| `SIGLIP_MS_M4` = `SIGLIP_INFER_MS_M4` + `SIGLIP_PREPROC_MS_M4` + `JPEG_DECODE_MS_M4` | 37 + 5.4 + 3.5 = 45.9 → 115 ms | MEASURED (M4) × GUESS | q5 §3: median at batch 16, 4 threads; preprocessing 3–6 ms; JPEG decode 3.5 ms; q5 §5b uses the same 45.9 ms. (Was 66 ms, q5's superseded round-0 figure) |
| `FREEPIK_MS_M4` | 400 → 1.0 s | **GUESS** | EVA-02 B at 448 px ≈ 6× the tokens of B/16 at 224. No CPU figure exists (Q4) |
| `GUARD_S_PER_FRAME_CPU` / `_GPU` | 20 / 0.5 s | **GUESS** | No CPU figure exists (Q4) |
| `FREEPIK_MS_GPU` / `SIGLIP_MS_GPU` | 40 / 5 ms | GUESS | Freepik from 28 ms MEASURED on an RTX 3090 [Q4 S10] |
| `DECODE_S_CPU` / `TEXT_EMBED_S_CPU` | 4 / 0.5 s | GUESS | ffmpeg; e5-small on speech videos. Overlaps slightly with the JPEG decode inside `SIGLIP_MS_M4` (conservative) |
| `BRANCH_OVERLAP_HIDE` | 0 (grid) / 0.5 (`_SENS`, sensitivity) | GUESS | share of the shorter of audio branch and frame branch hidden by running them concurrently (§2.2) |
| `LLM_CPU_*` / `LLM_GPU_*` | 30 / 8 and 3,000 / 70 tok/s | GUESS | scaled from Q3's llama.cpp proxies |

**Cold start, idle and batches**

| Name | Value | Source |
|---|---|---|
| `COLD_START_S_CPU` | 35 s = `CPU_IMAGE_START_S` 10 (GUESS) + (`SIGLIP_LOAD_S_M4` 5.9 MEASURED [Q5 §3] + `OTHER_MODELS_LOAD_S_M4` 4 GUESS) × 2.5; sensitivity 60 s | derived (was a flat 15 s guess) |
| `COLD_START_S_GPU` | 25 s; sensitivity 60 s | GUESS |
| `IDLE_WINDOW_S` / `IDLE_WINDOW_S_GPU` | 900 / 600 | upper bounds: "up to 15 minutes, or 10 minutes for GPUs" [S29] |
| `JOB_MIN_BILLED_S` | 60 | [S1] |
| `GPU_TASK_MAX_S` / `CPU_HOURLY_TASK_MAX_S` | 3,600 / 3,600 | GPU task limit [S7]; CPU: latency target (run finishes within its hour), sharded above it |
| Hourly batch slots | 16 × 30.4 = 486/month, expected non-empty = 486 × (1 − e^(−videos/486)) | was a fixed 730 |
| `DELAYED_RUNS_PER_DAY` | 2 (minimum) | GUESS; raised automatically while one execution would exceed `DELAYED_EXEC_MAX_S` × `DELAYED_CAP_MARGIN` |
| `DELAYED_EXEC_MAX_S` / `DELAYED_CAP_MARGIN` | 12 h / 0.75 | cap on the total task runtime of one execution [S22] / GUESS |
| `DELAYED_PROVISION_MAX_S` / `BATCH_RESULT_MAX_S` / `BATCH_COLLECT_POLL_S` | 12 h / 24 h / 1 h | [S22] / [S28] / GUESS; latency only |
| `VM_MAX_UTIL` | 0.5 | GUESS |

**Model formulas** (per video)

- **Cloud Run CPU service** = (local seconds + Haiku wait) × $0.000136, plus cold starts videos × e^(−λ·900) × 35 s × $0.000136, plus $0.40 per 1M requests. λ = videos / (30.4 × 16 × 3,600 s).
- **Cloud Run L4 service** = busy-s × $0.000291, plus videos × [(1 − e^(−λW))/λ + p_cold × 25 s] × $0.000291, with W = 600 s (the idle tail E[min(next gap, 10 min)]).
- **Hourly / delayed job** = (work + per-video Haiku wait ÷ 8) × job rate, plus per non-empty slot max(60 s × tasks, cold × tasks + work) − work. Hourly: tasks = the smallest number with cold + work/tasks ≤ 1 h. Delayed: one task, runs per day raised until cold + daily work / runs ≤ 0.75 × 12 h.
- **Parallel branches (sensitivity)**: wall time per video minus 0.5 × min(audio branch, frame branch).
- **Hosted captions** = VAD gate on Cloud Run CPU + 0.6 × (API fee on 210 s of speech + synchronous wait × $0.000136).
- **VM** = ⌈busy-h / (730 × 0.5)⌉ × hourly × 730, split across stages by busy-time share.
- **Free tier (sensitivity row)**: each configuration gets its own credit, min(billed vCPU-s, free vCPU-s) × CPU price + min(billed GiB-s, free GiB-s) × memory price, from its own billed seconds and its own tier (request, instance/jobs, Delayed Jobs; GPU seconds get none); totals are clamped at ≥ 0. The hosted reference now gets the request-based credit on its own Cloud Run seconds (VAD gate, decode, synchronous waits). With `APPLY_FREE_TIER = True` the headings say "free tier on" and each cell prints a "free-tier credit" row.

**Worked example** (1,000 MAU × 3%, captions on the Cloud Run CPU service, CPU ×1):

1. Videos = 1,000 × 0.03 × 4.33 = **129.9**, i.e. 10.8 video-hours.
2. VAD = 0.9 × 300 s / (165 × 0.7) = **2.34 s**.
3. LID = 0.6 × 7 × 0.65 s × 2.5 = **6.83 s**. ASR = 0.6 × 210 s / 12.9 = **9.75 s**.
4. Captions total 18.9 s × $0.000136 = **$0.00257 per video**, × 129.9 = **$0.334/month**.
5. Cold starts: λ = 129.9 / 1,751,040 s = 7.42e-5 /s, p_cold = e^(−0.0668) = 0.935, so 0.935 × 35 s × $0.000136 × 129.9 = $0.578/month (the overhead row, together with $0.00005 of request fees).
6. Haiku summary per video = [0.6 × (2,450 × 0.10 + 300 × 0.50) + 0.4 × (1,160 × 0.10 + 150 × 0.50)] / 1e6 × 1.10 = **$0.000345**, plus the billed wait 3 s × $0.000136 = $0.000408.

---

## 6. Cost grid

Output of `python3 -I docs/research/q7_cost_grid.py`, pasted verbatim.

**How to read the columns:**

- "all local" columns run all four stages locally, including a local LLM for summaries.
- **Hosted reference** = gated Gemini 3.1 Flash-Lite captions (Vertex EU), Haiku summaries, Haiku moderation on all 30 frames, Haiku labels, plus local decode. It is a price reference, not a valid design: Haiku moderation refuses explicit frames, and Haiku labels return no embedding.
- The "+ Haiku" columns replace the local LLM with Haiku 5.5 (Vertex EU price). The service and VM columns call it synchronously; the hourly jobs call it 8 at a time; the Delayed Job uses Haiku batch prediction at the Vertex EU batch price ($0.055 / $0.275 per MTok [S27]), which needs its own adapter (§2.3). Under each cell, "Batch runs" gives tasks per run, run length and worst-case latency, and the cost of using synchronous Haiku in the Delayed Job instead.
- "summaries" includes the billed wait for Haiku where one exists. "shared" is decode + text embedding. "overhead" is cold starts, idle GPU tails, job minimum billing and request fees.
- The three **job** columns need the batch intake described in §2.4, which q8a does not have. Their worst-case latency is printed under each cell: about 1–2 h for the hourly jobs, about 2–2.3 days for the Delayed Job with Haiku batch (1–1.3 days with synchronous Haiku). The Delayed-Job column's Haiku batch needs the Vertex batch-prediction adapter (§2.3).

### Derived per-video figures

- Frames per video: 30 (interval 10 s); speech per speech video: 210 s in 7 LID windows
- Parakeet RTFx on 4 vCPU: 12.9 (M4 measured 32.3 / slowdown 2.5); cross-check from 9800X3D int8 30.5: 5.3 (16-thread guess) to 10.7 (8-thread guess)
- SigLIP 2 B/16 per frame: 45.9 ms on M4 (inference 37 + preprocessing 5.4 + JPEG decode 3.5) -> 115 ms on Cloud Run
- CPU cold start: 35 s = image/container 10 s + (SigLIP load 5.9 s + other models 4.0 s) x 2.5; sensitivity 60 s
- Cloud Run CPU 4 vCPU / 16 GiB: request-based $0.000136/s ($0.4896/h); job $0.000104/s; Delayed Job $0.0000728/s. At 8 GiB: request-based $0.000116/s (-15%)
- Cloud Run L4 + 4 vCPU / 16 GiB, instance-based: $0.000291/s ($1.0465/h)
- Always-on worker pool, 4 vCPU / 16 GiB: $170.13/month; L4 + 4 / 16: $660.77/month
- Haiku summary fee per video: $0.000345 (x1.1 endpoint), first-party global $0.000313, Batch $0.000172; billed wait 3 s on CR CPU = $0.000408

| Stage | CPU s/video | CR CPU $/video | L4 s/video | L4 $/video (busy only) |
|---|---|---|---|---|
| captions | 18.9 | $0.00257 | 11.35 | $0.00330 |
| summaries | 94.5 | $0.01285 | 4.07 | $0.00118 |
| moderation | 42.0 | $0.00571 | 1.50 | $0.00044 |
| labels | 3.4 | $0.00047 | 0.15 | $0.00004 |
| shared | 4.3 | $0.00058 | 4.03 | $0.00117 |

Local CPU seconds in the recommended mix: 68.7 s/video. Shares: freepik 44%, guard 17%, asr 14%, lid 10%, siglip 5%, vad 3%, decode 6%, embed 0%
Audio branch 18.9 s, frame branch 45.4 s; running them concurrently with 50% of the shorter hidden: 59.2 s/video (-14% wall and billed seconds)

### Captions per video: local vs hosted, same speech gate

| Option | $/video at CPU speed x0.5 | x1 | x2 |
|---|---|---|---|
| Local Parakeet + VAD + LID, CR CPU | $0.00514 | $0.00257 | $0.00129 |
| Gemini 3.1 Flash-Lite (Vertex EU) | $0.00434 | $0.00403 | $0.00387 |
| Gemini 3.5 Flash-Lite (Vertex EU) | $0.00402 | $0.00370 | $0.00354 |
| STT V2 standard | $0.03505 | $0.03473 | $0.03457 |
| STT V2 dynamic batch (async only) | $0.00694 | $0.00662 | $0.00646 |

### Monthly AI processing cost (USD), free tier off

#### MAU 1,000 x 3% -> 129.9 videos, 10.8 video-hours

| Stage | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| captions | $0.334 | $0.429 | $0.429 | $0.523 | $12.49 | $291.68 | $174.98 | $0.334 | $29.66 | $0.256 | $0.429 | $0.179 |
| summaries | $1.67 | $0.154 | $0.154 | $0.098 | $62.36 | $104.68 | $62.80 | $0.098 | $0.045 | $0.050 | $0.059 | $0.022 |
| moderation | $0.742 | $0.057 | $0.057 | $0.299 | $27.72 | $38.55 | $23.12 | $0.742 | $65.87 | $0.567 | $0.057 | $0.397 |
| labels | $0.061 | $0.006 | $0.006 | $0.052 | $2.27 | $3.85 | $2.31 | $0.061 | $5.40 | $0.047 | $0.006 | $0.033 |
| shared | $0.076 | $0.152 | $0.152 | $0.076 | $2.84 | $103.57 | $62.13 | $0.076 | $6.74 | $0.058 | $0.152 | $0.041 |
| overhead | $0.578 | $23.06 | $1.19 | $0.000 | $0.000 | $0.000 | $0.000 | $0.578 | $0.000 | $0.415 | $1.33 | $0.137 |
| **total** | **$3.46** | **$23.86** | **$1.99** | **$1.05** | **$107.68** | **$542.33** | **$325.34** | **$1.89** | **$107.72** | **$1.39** | **$2.03** | **$0.808** |

Cold-start probability 93.5%; recommended service busy 1% of active hours (1 instance-equivalent). VMs: e2 1, e2+Haiku 1, g2 1.
Batch runs: CPU hourly job 1 task(s), run 2 min, worst latency 1.0 h; L4 hourly job 1 task(s), run 1 min, worst 1.0 h; Delayed Job 2 runs/day, run 0.1 h, worst 49 h with Haiku Batch, 24 h with sync Haiku (+$0.026/month).

#### MAU 1,000 x 5% -> 216.5 videos, 18.0 video-hours

| Stage | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| captions | $0.557 | $0.714 | $0.714 | $0.871 | $12.49 | $291.68 | $174.98 | $0.557 | $29.66 | $0.426 | $0.714 | $0.298 |
| summaries | $2.78 | $0.256 | $0.256 | $0.163 | $62.36 | $104.68 | $62.80 | $0.163 | $0.075 | $0.083 | $0.098 | $0.037 |
| moderation | $1.24 | $0.094 | $0.094 | $0.499 | $27.72 | $38.55 | $23.12 | $1.24 | $65.87 | $0.946 | $0.094 | $0.662 |
| labels | $0.101 | $0.009 | $0.009 | $0.087 | $2.27 | $3.85 | $2.31 | $0.101 | $5.40 | $0.078 | $0.009 | $0.054 |
| shared | $0.127 | $0.254 | $0.254 | $0.127 | $2.84 | $103.57 | $62.13 | $0.127 | $6.74 | $0.097 | $0.254 | $0.068 |
| overhead | $0.922 | $37.86 | $1.72 | $0.000 | $0.000 | $0.000 | $0.000 | $0.922 | $0.000 | $0.636 | $1.95 | $0.151 |
| **total** | **$5.73** | **$39.18** | **$3.05** | **$1.75** | **$107.68** | **$542.33** | **$325.34** | **$3.11** | **$107.75** | **$2.27** | **$3.12** | **$1.27** |

Cold-start probability 89.5%; recommended service busy 1% of active hours (1 instance-equivalent). VMs: e2 1, e2+Haiku 1, g2 1.
Batch runs: CPU hourly job 1 task(s), run 2 min, worst latency 1.0 h; L4 hourly job 1 task(s), run 1 min, worst 1.0 h; Delayed Job 2 runs/day, run 0.1 h, worst 49 h with Haiku Batch, 24 h with sync Haiku (+$0.043/month).

#### MAU 10,000 x 3% -> 1,299.0 videos, 108.2 video-hours

| Stage | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| captions | $3.34 | $4.29 | $4.29 | $5.23 | $12.49 | $291.68 | $174.98 | $3.34 | $29.66 | $2.56 | $4.29 | $1.79 |
| summaries | $16.69 | $1.54 | $1.54 | $0.978 | $62.36 | $104.68 | $62.80 | $0.978 | $0.448 | $0.498 | $0.589 | $0.224 |
| moderation | $7.42 | $0.566 | $0.566 | $2.99 | $27.72 | $38.55 | $23.12 | $7.42 | $65.87 | $5.67 | $0.566 | $3.97 |
| labels | $0.608 | $0.057 | $0.057 | $0.524 | $2.27 | $3.85 | $2.31 | $0.608 | $5.40 | $0.465 | $0.057 | $0.326 |
| shared | $0.760 | $1.52 | $1.52 | $0.760 | $2.84 | $103.57 | $62.13 | $0.760 | $6.74 | $0.581 | $1.52 | $0.407 |
| overhead | $3.17 | $188.91 | $3.29 | $0.001 | $0.000 | $0.000 | $0.000 | $3.17 | $0.000 | $1.65 | $3.29 | $0.155 |
| **total** | **$31.99** | **$196.88** | **$11.26** | **$10.48** | **$107.68** | **$542.33** | **$325.34** | **$16.28** | **$108.12** | **$11.42** | **$10.31** | **$6.87** |

Cold-start probability 51.3%; recommended service busy 5% of active hours (1 instance-equivalent). VMs: e2 1, e2+Haiku 1, g2 1.
Batch runs: CPU hourly job 1 task(s), run 4 min, worst latency 1.1 h; L4 hourly job 1 task(s), run 1 min, worst 1.0 h; Delayed Job 2 runs/day, run 0.4 h, worst 49 h with Haiku Batch, 24 h with sync Haiku (+$0.259/month).

#### MAU 10,000 x 5% -> 2,165.0 videos, 180.4 video-hours

| Stage | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| captions | $5.57 | $7.14 | $7.14 | $8.71 | $12.49 | $291.68 | $174.98 | $5.57 | $29.66 | $4.26 | $7.14 | $2.98 |
| summaries | $27.81 | $2.56 | $2.56 | $1.63 | $62.36 | $104.68 | $62.80 | $1.63 | $0.746 | $0.831 | $0.982 | $0.373 |
| moderation | $12.37 | $0.944 | $0.944 | $4.99 | $27.72 | $38.55 | $23.12 | $12.37 | $65.87 | $9.46 | $0.944 | $6.62 |
| labels | $1.01 | $0.094 | $0.094 | $0.873 | $2.27 | $3.85 | $2.31 | $1.01 | $5.40 | $0.775 | $0.094 | $0.543 |
| shared | $1.27 | $2.54 | $2.54 | $1.27 | $2.84 | $103.57 | $62.13 | $1.27 | $6.74 | $0.968 | $2.54 | $0.678 |
| overhead | $3.39 | $274.10 | $3.49 | $0.001 | $0.000 | $0.000 | $0.000 | $3.39 | $0.000 | $1.75 | $3.49 | $0.155 |
| **total** | **$51.42** | **$287.39** | **$16.78** | **$17.47** | **$107.68** | **$542.33** | **$325.34** | **$25.23** | **$108.42** | **$18.04** | **$15.19** | **$11.35** |

Cold-start probability 32.9%; recommended service busy 9% of active hours (1 instance-equivalent). VMs: e2 1, e2+Haiku 1, g2 1.
Batch runs: CPU hourly job 1 task(s), run 6 min, worst latency 1.1 h; L4 hourly job 1 task(s), run 2 min, worst 1.0 h; Delayed Job 2 runs/day, run 0.7 h, worst 50 h with Haiku Batch, 25 h with sync Haiku (+$0.432/month).

#### MAU 100,000 x 3% -> 12,990.0 videos, 1,082.5 video-hours

| Stage | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| captions | $33.42 | $42.86 | $42.86 | $52.29 | $24.97 | $291.68 | $174.98 | $33.42 | $29.66 | $25.55 | $42.86 | $17.89 |
| summaries | $166.89 | $15.38 | $15.38 | $9.78 | $124.71 | $104.68 | $62.80 | $9.78 | $4.48 | $4.98 | $5.89 | $2.24 |
| moderation | $74.20 | $5.66 | $5.66 | $29.92 | $55.45 | $38.55 | $23.12 | $74.20 | $65.87 | $56.74 | $5.66 | $39.72 |
| labels | $6.08 | $0.566 | $0.566 | $5.24 | $4.54 | $3.85 | $2.31 | $6.08 | $5.40 | $4.65 | $0.566 | $3.26 |
| shared | $7.60 | $15.22 | $15.22 | $7.60 | $5.68 | $103.57 | $62.13 | $7.60 | $6.74 | $5.81 | $15.22 | $4.07 |
| overhead | $0.083 | $504.19 | $3.53 | $0.005 | $0.000 | $0.000 | $0.000 | $0.083 | $0.000 | $1.77 | $3.53 | $0.155 |
| **total** | **$288.26** | **$583.88** | **$83.23** | **$104.82** | **$215.35** | **$542.33** | **$325.34** | **$131.15** | **$112.15** | **$99.51** | **$73.74** | **$67.32** |

Cold-start probability 0.1%; recommended service busy 53% of active hours (1 instance-equivalent). VMs: e2 2, e2+Haiku 1, g2 1.
Batch runs: CPU hourly job 1 task(s), run 31 min, worst latency 1.5 h; L4 hourly job 1 task(s), run 8 min, worst 1.1 h; Delayed Job 2 runs/day, run 4.1 h, worst 53 h with Haiku Batch, 28 h with sync Haiku (+$2.59/month).

#### MAU 100,000 x 5% -> 21,650.0 videos, 1,804.2 video-hours

| Stage | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| captions | $55.69 | $71.43 | $71.43 | $87.14 | $37.46 | $291.68 | $174.98 | $55.69 | $59.33 | $42.59 | $71.43 | $29.81 |
| summaries | $278.15 | $25.64 | $25.64 | $16.30 | $187.07 | $104.68 | $62.80 | $16.30 | $7.46 | $8.31 | $9.82 | $3.73 |
| moderation | $123.66 | $9.44 | $9.44 | $49.87 | $83.17 | $38.55 | $23.12 | $123.66 | $131.74 | $94.57 | $9.44 | $66.20 |
| labels | $10.14 | $0.944 | $0.944 | $8.73 | $6.82 | $3.85 | $2.31 | $10.14 | $10.80 | $7.75 | $0.944 | $5.43 |
| shared | $12.66 | $25.36 | $25.36 | $12.66 | $8.52 | $103.57 | $62.13 | $12.66 | $13.49 | $9.68 | $25.36 | $6.78 |
| overhead | $0.010 | $508.82 | $3.53 | $0.009 | $0.000 | $0.000 | $0.000 | $0.010 | $0.000 | $1.77 | $3.53 | $0.155 |
| **total** | **$480.31** | **$641.63** | **$136.35** | **$174.70** | **$323.02** | **$542.33** | **$325.34** | **$218.46** | **$222.81** | **$164.67** | **$120.54** | **$112.10** |

Cold-start probability 0.0%; recommended service busy 89% of active hours (1 instance-equivalent). VMs: e2 3, e2+Haiku 2, g2 1.
Batch runs: CPU hourly job 1 task(s), run 52 min, worst latency 1.9 h; L4 hourly job 1 task(s), run 13 min, worst 1.2 h; Delayed Job 2 runs/day, run 6.8 h, worst 56 h with Haiku Batch, 31 h with sync Haiku (+$4.32/month).

### Totals overview (free tier off)

| Cell | Videos | Video-h | CR CPU, all local | CR L4 service, all local | L4 hourly job, all local | Hosted reference | e2 VM, all local | g2 VM, all local | g2 spot VM, all local | **CR CPU + Haiku (rec.)** | e2 VM + Haiku | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1,000 x 3% | 130 | 11 | $3.46 | $23.86 | $1.99 | $1.05 | $107.68 | $542.33 | $325.34 | $1.89 | $107.72 | $1.39 | $2.03 | $0.808 |
| 1,000 x 5% | 216 | 18 | $5.73 | $39.18 | $3.05 | $1.75 | $107.68 | $542.33 | $325.34 | $3.11 | $107.75 | $2.27 | $3.12 | $1.27 |
| 10,000 x 3% | 1,299 | 108 | $31.99 | $196.88 | $11.26 | $10.48 | $107.68 | $542.33 | $325.34 | $16.28 | $108.12 | $11.42 | $10.31 | $6.87 |
| 10,000 x 5% | 2,165 | 180 | $51.42 | $287.39 | $16.78 | $17.47 | $107.68 | $542.33 | $325.34 | $25.23 | $108.42 | $18.04 | $15.19 | $11.35 |
| 100,000 x 3% | 12,990 | 1,082 | $288.26 | $583.88 | $83.23 | $104.82 | $215.35 | $542.33 | $325.34 | $131.15 | $112.15 | $99.51 | $73.74 | $67.32 |
| 100,000 x 5% | 21,650 | 1,804 | $480.31 | $641.63 | $136.35 | $174.70 | $323.02 | $542.33 | $325.34 | $218.46 | $222.81 | $164.67 | $120.54 | $112.10 |

### Sensitivity of the key columns (monthly totals)

Rows: CPU speed x0.5 / x1 / x2 (every CPU step, incl. VAD, LID and decode on GPU images); CPU cold start 60 s; GPU cold start 60 s; CPU instances at 8 GiB; audio and frame branches in parallel (50% of the shorter hidden); Haiku via first-party API (x1.0); free tier on (credit per configuration).

| Cell | Case | **CR CPU + Haiku (rec.)** | CPU hourly job + Haiku | L4 hourly job + Haiku | CPU Delayed Job + Haiku Batch | e2 VM + Haiku | Hosted reference |
|---|---|---|---|---|---|---|---|
| 1,000 x 3% | CPU x0.5 | $3.10 | $2.32 | $2.03 | $1.46 | $107.72 | $1.17 |
| 1,000 x 3% | CPU x1 | $1.89 | $1.39 | $2.03 | $0.808 | $107.72 | $1.05 |
| 1,000 x 3% | CPU x2 | $1.28 | $0.929 | $2.03 | $0.484 | $107.72 | $0.990 |
| 1,000 x 3% | CPU cold 60 s | $2.30 | $1.69 | $2.03 | $0.906 | $107.72 | $1.05 |
| 1,000 x 3% | GPU cold 60 s | $1.89 | $1.39 | $2.69 | $0.808 | $107.72 | $1.05 |
| 1,000 x 3% | CPU 8 GiB | $1.62 | $1.19 | $2.03 | $0.687 | $107.72 | $1.01 |
| 1,000 x 3% | parallel branches | $1.72 | $1.26 | $2.03 | $0.719 | $107.72 | $1.05 |
| 1,000 x 3% | Haiku 1st-party | $1.89 | $1.39 | $2.03 | $0.806 | $107.72 | $1.01 |
| 1,000 x 3% | free tier on | $0.045 | $0.045 | $1.32 | $0.022 | $107.72 | $0.814 |
| 1,000 x 5% | CPU x0.5 | $5.13 | $3.81 | $3.27 | $2.35 | $107.75 | $1.94 |
| 1,000 x 5% | CPU x1 | $3.11 | $2.27 | $3.12 | $1.27 | $107.75 | $1.75 |
| 1,000 x 5% | CPU x2 | $2.10 | $1.49 | $3.12 | $0.729 | $107.75 | $1.65 |
| 1,000 x 5% | CPU cold 60 s | $3.77 | $2.72 | $3.12 | $1.38 | $107.75 | $1.75 |
| 1,000 x 5% | GPU cold 60 s | $3.11 | $2.27 | $4.22 | $1.27 | $107.75 | $1.75 |
| 1,000 x 5% | CPU 8 GiB | $2.66 | $1.93 | $3.12 | $1.08 | $107.75 | $1.69 |
| 1,000 x 5% | parallel branches | $2.83 | $2.05 | $3.12 | $1.12 | $107.75 | $1.75 |
| 1,000 x 5% | Haiku 1st-party | $3.10 | $2.26 | $3.12 | $1.27 | $107.74 | $1.69 |
| 1,000 x 5% | free tier on | $0.075 | $0.075 | $2.03 | $0.037 | $107.75 | $1.36 |
| 10,000 x 3% | CPU x0.5 | $28.41 | $20.70 | $15.28 | $13.36 | $108.12 | $11.65 |
| 10,000 x 3% | CPU x1 | $16.28 | $11.42 | $10.31 | $6.87 | $108.12 | $10.48 |
| 10,000 x 3% | CPU x2 | $10.21 | $6.78 | $8.34 | $3.63 | $108.12 | $9.90 |
| 10,000 x 3% | CPU cold 60 s | $18.54 | $12.60 | $10.31 | $6.98 | $108.12 | $10.48 |
| 10,000 x 3% | GPU cold 60 s | $16.28 | $11.42 | $14.92 | $6.87 | $108.12 | $10.48 |
| 10,000 x 3% | CPU 8 GiB | $13.95 | $9.73 | $10.31 | $5.85 | $108.12 | $10.14 |
| 10,000 x 3% | parallel branches | $14.61 | $10.14 | $10.00 | $5.98 | $108.12 | $10.48 |
| 10,000 x 3% | Haiku 1st-party | $16.24 | $11.38 | $10.27 | $6.85 | $108.08 | $10.12 |
| 10,000 x 3% | free tier on | $11.06 | $6.20 | $6.97 | $1.65 | $108.12 | $8.14 |
| 10,000 x 5% | CPU x0.5 | $45.45 | $33.50 | $23.48 | $22.17 | $108.42 | $19.42 |
| 10,000 x 5% | CPU x1 | $25.23 | $18.04 | $15.19 | $11.35 | $108.42 | $17.47 |
| 10,000 x 5% | CPU x2 | $15.13 | $10.31 | $11.05 | $5.94 | $108.42 | $16.49 |
| 10,000 x 5% | CPU cold 60 s | $27.65 | $19.29 | $15.19 | $11.46 | $108.42 | $17.47 |
| 10,000 x 5% | GPU cold 60 s | $25.23 | $18.04 | $20.09 | $11.35 | $108.42 | $17.47 |
| 10,000 x 5% | CPU 8 GiB | $21.63 | $15.38 | $15.19 | $9.66 | $108.42 | $16.90 |
| 10,000 x 5% | parallel branches | $22.45 | $15.91 | $14.68 | $9.86 | $108.42 | $17.47 |
| 10,000 x 5% | Haiku 1st-party | $25.17 | $17.97 | $15.13 | $11.32 | $108.35 | $16.87 |
| 10,000 x 5% | free tier on | $20.01 | $12.82 | $10.72 | $6.13 | $108.42 | $13.82 |
| 100,000 x 3% | CPU x0.5 | $252.45 | $194.03 | $123.44 | $132.25 | $219.83 | $116.55 |
| 100,000 x 3% | CPU x1 | $131.15 | $99.51 | $73.74 | $67.32 | $112.15 | $104.82 |
| 100,000 x 3% | CPU x2 | $70.51 | $53.13 | $48.89 | $34.86 | $112.15 | $98.96 |
| 100,000 x 3% | CPU cold 60 s | $131.21 | $100.77 | $73.74 | $67.43 | $112.15 | $104.82 |
| 100,000 x 3% | GPU cold 60 s | $131.15 | $99.51 | $78.69 | $67.32 | $112.15 | $104.82 |
| 100,000 x 3% | CPU 8 GiB | $112.53 | $84.89 | $73.74 | $57.31 | $112.15 | $101.38 |
| 100,000 x 3% | parallel branches | $114.45 | $86.73 | $70.62 | $58.38 | $112.15 | $104.82 |
| 100,000 x 3% | Haiku 1st-party | $130.75 | $99.10 | $73.33 | $67.12 | $111.75 | $101.22 |
| 100,000 x 3% | free tier on | $125.93 | $94.29 | $68.52 | $62.10 | $112.15 | $99.60 |
| 100,000 x 5% | CPU x0.5 | $420.62 | $321.03 | $203.38 | $220.47 | $330.49 | $194.25 |
| 100,000 x 5% | CPU x1 | $218.46 | $164.67 | $120.54 | $112.10 | $222.81 | $174.70 |
| 100,000 x 5% | CPU x2 | $117.38 | $87.37 | $79.12 | $57.99 | $115.14 | $164.93 |
| 100,000 x 5% | CPU cold 60 s | $218.46 | $165.93 | $120.54 | $112.21 | $222.81 | $174.70 |
| 100,000 x 5% | GPU cold 60 s | $218.46 | $164.67 | $125.49 | $112.10 | $222.81 | $174.70 |
| 100,000 x 5% | CPU 8 GiB | $187.43 | $140.48 | $120.54 | $95.43 | $222.81 | $168.97 |
| 100,000 x 5% | parallel branches | $190.62 | $143.37 | $115.35 | $97.19 | $115.14 | $174.70 |
| 100,000 x 5% | Haiku 1st-party | $217.78 | $163.99 | $119.86 | $111.76 | $222.14 | $168.70 |
| 100,000 x 5% | free tier on | $213.24 | $159.45 | $115.32 | $106.88 | $222.81 | $169.48 |

### Crossovers (video-hours per month; second option cheaper)

| First | Second | CPU x0.5 | CPU x1 | CPU x2 |
|---|---|---|---|---|
| **CR CPU + Haiku (rec.)** | CPU hourly job + Haiku | >= 1 h | >= 1 h | >= 1 h |
| **CR CPU + Haiku (rec.)** | L4 hourly job + Haiku | >= 1 h | >= 19 h | >= 73 h |
| CPU hourly job + Haiku | L4 hourly job + Haiku | >= 1 h | >= 61 h | >= 318 h |
| **CR CPU + Haiku (rec.)** | e2 VM + Haiku | 464-794 h, >= 940 h | 921-1,593 h, >= 1,849 h | 1,777-3,165 h, >= 3,566 h |
| CR CPU, all local | CR L4 service, all local | >= 1,230 h | >= 2,646 h | >= 6,225 h |
| CR CPU, all local | g2 spot VM, all local | >= 613 h | >= 1,230 h | >= 2,468 h |

### Per-stage, per-video: local CR CPU vs hosted (both linear in volume)

- captions: local $0.00257 vs hosted $0.00403 -> local cheaper by 1.6x
- summaries: local $0.01285 vs hosted $0.00075 -> hosted cheaper by 17.1x
- moderation: local $0.00571 vs hosted $0.00230 -> hosted cheaper by 2.5x
- labels: local $0.00047 vs hosted $0.00040 -> hosted cheaper by 1.2x

---

## 7. Crossovers and sensitivity

Thresholds are in video-hours per month (1 video-hour = 12 five-minute videos). The six grid cells sit at 11, 18, 108, 180, 1,082 and 1,804 video-hours. Ranges are from the crossover table in §6 (CPU ×0.5 / ×1 / ×2).

| Comparison | Where the second option becomes cheaper | Reading |
|---|---|---|
| Local LLM vs Haiku (summaries) | Haiku is cheaper than a **single-stream** local LLM at every volume: about 17× vs CPU Qwen (wait included), and about 3× vs a fully busy L4 | A **batched** vLLM server inside the L4 job could break even if it reaches about 3× the single-stream L4 throughput assumed here; Q3 cites vLLM at about 19× Ollama's aggregate throughput on an A100 [Q3 S28]. Unmeasured. At stake: at most about $10/month at 100k × 5%. Haiku stays the choice on quality and operations (Q3) |
| Local CPU vs hosted captions, same speech gate | Local is 1.6× cheaper than Gemini 3.1 Flash-Lite and 1.4× cheaper than 3.5 Flash-Lite (Vertex EU, wait billed) at CPU ×1. **At CPU ×0.5 both Gemini models are cheaper.** STT V2 standard is about 13× dearer than local; STT V2 dynamic batch about 2.6× (async only) | **Close call that the benchmark decides.** Gemini also changes the product (multilingual captions without the LID gate) and its word-timestamp quality is unverified |
| CR CPU service + Haiku → CPU hourly job + Haiku | Cheaper at every volume (24% lower rate, small job overhead) | Only if results may arrive up to about 2 h later (worst case: 1 h slot + run time, §2.4) and the §2.4 batch intake is built. Saves $0.5/month at 1k × 3%, $7 at 10k × 5%, $54 at 100k × 5% |
| CR CPU service + Haiku → L4 hourly job + Haiku | ≥ 1 / **19** / 73 h | Same conditions, plus a CPU fallback for GPU quota. Saves $10/month at 10k × 5% and $98 at 100k × 5% (CPU ×1) |
| CPU hourly job → L4 hourly job | ≥ 1 / **61** / 318 h | **The most fragile crossover**: it moves more than 300× across the CPU-speed range (mainly the longer CPU cold start, now 35 s, lowered it from 92 h). The 60 s GPU cold-start sensitivity moves it further up. Do not build the L4 path before the benchmark |
| CR CPU + Haiku → e2 VM + Haiku | 464–794 h and ≥ 940 h / **921–1,593 h and ≥ 1,849 h** / 1,777–3,165 h and ≥ 3,566 h (steps as VMs are added) | At CPU ×1 the 100k cells are $112 vs $131 and $223 vs $218. It also brings VM operations; the CPU job is cheaper than both |
| All-local CR CPU → CR L4 *service* | ≥ 1,230 / 2,646 / 6,225 h | Only when the L4 is never idle. Not a design for Expause |
| All-local CR CPU → g2 spot VM | ≥ 613 / 1,230 / 2,468 h | Same idea. Fixed $325/month, pre-emptible |
| Haiku vs local (moderation, labels) | Haiku is cheaper than *CPU* per video (2.5× and 1.2×), dearer than L4 | Cost does not decide these stages. Refusals (moderation) and the missing embeddings (labels) do (Q4, Q5) |

**What drives the CPU numbers** (recommended mix, CPU ×1, 69 CPU-s per video): Freepik 44% and the guard 17% (both pure guesses), ASR 14%, LID 10%, decode 6%, SigLIP 5%, VAD 3%. Swapping Freepik for Marqo's 5.6M-parameter model (Q4's small fallback) would remove most of the largest item, at an accuracy cost that is not measured. Running the guard only on frames that Freepik or SigLIP rate POSSIBLE or higher is already assumed (2% escalation).

**Other sensitivities** (rows in §6):

| Row | Effect on the recommended service (other columns in §6) |
|---|---|
| CPU cold start 60 s (instead of 35 s) | +$0.41 (1k × 3%) to +$2.42 (10k × 5%); about $0 at 100k, where instances stay warm. The latency (about 1 min on most videos below about 1,350 videos/month) matters more |
| GPU cold start 60 s | +$0.7–5/month on the L4 job columns only |
| CPU at 8 GiB | −14% to −15% on every CPU column ($1.62 to $187) |
| Audio and frame branches in parallel (50% of the shorter hidden, guess) | −9% (1k × 3%) to −13% (100k × 5%) |
| Haiku via first-party API | at most −$0.68/month |
| Free tier on | the two 1k cells fall to about $0.05–0.08/month; every larger cell saves about $5.2/month |

---

## 8. Open questions

Questions 3 and 12 are user decisions; the rest are measurements, checks or follow-ups in sibling documents.

1. **Cloud Run CPU benchmark (blocking for every CPU number):** on a 4 vCPU / 16 GiB Cloud Run instance in europe-west1 (gen2), measure, in this order:
   - Freepik EVA-02 per frame and the guard VLM per escalated frame (61% of local seconds, both pure guesses);
   - sherpa-onnx Parakeet int8 RTFx on ≤30 s segments, faster-whisper `tiny` LID per window, SigLIP 2 B/16 image tower per frame, Silero VAD, ffmpeg decode;
   - **peak RSS** of the whole job with the guard loaded. Q2's 1.33 GB covers the audio stack only. A peak below about 6 GiB means 8 GiB (−15%); above 16 GiB means a separate guard service;
   - cold start, from image pull to model ready, for the `-cpu` image (grid: 35 s derived, 60 s sensitivity), with and without lazy guard loading;
   - wall time with the audio and frame branches running concurrently (2 + 2 intra-op threads) against serial (grid row: −14% per video, guessed).

   Then set `CLOUD_SLOWDOWN_VS_M4` and the GUESS constants from the measurements and re-run the script.
2. **L4 throughput for the same set** with the `-cuda` image:
   - whether onnx-asr/sherpa-onnx TensorRT works on driver 580 / CUDA 13 [S3];
   - the GPU job's real billed start-up;
   - whether a batched vLLM summariser is worth it.
3. **Decision for the user: latency requirement per output.** The options trade money for delay; the batch modes also need the §2.4 batch intake to be built.

   | Mode | Results at the latest | At 100k × 5%, CPU ×1 |
   |---|---|---|
   | Recommended service | about 1–2 min | $218 |
   | CPU hourly job | about 2 h | $165 |
   | L4 hourly job | about 1.2 h, with a CPU fallback | $121 |
   | Delayed Job + synchronous Haiku | about 31 h | $116 |
   | Delayed Job + Haiku batch | about 2.3 days | $112 |

   - **For the service:** results arrive while the uploader is still looking, and nothing new needs building. At 10k MAU the batch modes save only $7–14/month.
   - **For a batch mode:** at 100k × 5% the hourly CPU job saves about $54/month, and the Delayed Job saves about $106/month.
4. **Expause content mix:**
   - the share of videos with an audio stream and with speech;
   - the speech fraction;
   - typical length (the 5-minute average is an assumption from the brief);
   - the real escalation rate.
5. **Free tier:** is Expause's billing account already using the Cloud Run free tier? If not, the 1k cells drop to about $0.05–0.08/month (sensitivity row).
6. **Which tier-2 guard model and quantisation (Q4)**, and its RAM. This is the main input to the 8 vs 16 GiB choice (§3). If the guard pushes the peak above 16 GiB, move it to its own service rather than going to 6 vCPU / 24 GiB.
7. **Delayed Jobs** (Preview, dynamic price):
   - GPU support is priced (L4 and RTX PRO 6000 at the normal rate [S1]) but not documented on the feature page [S22].
   - Whether "total runtime duration of all tasks" means summed task time (the grid's reading) or wall time is not stated.
   - The launch stage of GPU jobs and GPU worker pools is still not stated either [S5][S10].
8. **Cold-start and idle behaviour:**
   - The cold-start latency for a 3–5 GB CPU image has not been measured.
   - Cloud Run's real idle retention is unknown: the documentation gives only upper bounds ("up to 15 minutes, or 10 minutes for GPUs" [S29]; instance-based "never more than 15 minutes" and "can be shut down at any time" [S6]). A shorter retention raises p_cold.
9. **Gemini on Vertex AI EU** (hosted-captions alternative only):
   - data-residency and logging terms;
   - word-timestamp quality;
   - whether the 32 audio tokens/s rate holds for the 3.x Flash-Lite models;
   - whether Expause would accept multilingual captions without the LID gate;
   - **whether 3.1 and 3.5 Flash-Lite are served on the `eu` multi-region endpoint (`aiplatform.eu.rep.googleapis.com`).** Google's pricing page gives only global and non-global prices. Third-party reports (an ai-dial-adapter-vertexai GitHub issue, an n8n forum thread) suggest that 3.x is on `eu` but not on single EU regions, and that some SDK versions resolve `eu` to the wrong host. This is not authoritative; confirm on Google's model locations page.
   - (2.5 Flash-Lite is settled: it retires on Vertex on 2026-10-20, Q4.)
10. **Region:** which EU region holds Expause's buckets and Cloud Tasks queues? europe-west1 has L4 but not RTX PRO 6000 [S3]. Spot g2 prices differ between europe-west1 and west4 [S9].
11. **e2 vs Cloud Run per-vCPU speed:** the grid assumes they are equal.
12. **Decision for the user: the Haiku endpoint for Expause** (§2.3). The grid assumes Vertex EU.

    | | Anthropic first-party API | Vertex AI, EU multi-region |
    |---|---|---|
    | Inference location | `global` (any geography) or `us` (×1.1); no EU option | EU (`aiplatform.eu.rep.googleapis.com`) |
    | Data at rest | US workspace geo only | Google Cloud, under Expause's existing terms |
    | Price | $0.10 / $0.50 per MTok (baseline) | +10%: at most +$0.68/month in the grid |
    | Batch | Message Batches, in the same SDK | Vertex batch prediction: separate adapter (GCS/BigQuery JSONL, results within 24 h, 4 concurrent jobs per project by default); EU multi-region support for Claude batch to confirm |
    | q8a extra | `llm-anthropic = ["anthropic>=1.12"]`, as it is | must become `anthropic[vertex]>=1.12`, or a separate `llm-anthropic-vertex` extra |

    - **For first-party:** it is cheaper, new API features land there first, the batch API is in the same SDK, and Expause has one vendor contract.
    - **For Vertex EU:** transcripts (personal data) stay in the EU, so no transfer basis (DPA/SCCs) is needed for them. Billing, IAM and audit stay in Google Cloud, where Expause and its data already are. This is consistent with rejecting GitHub-hosted runners (§4).
    - **Against Vertex EU:** features can lag the first-party API, and quotas are per project (EU multi-region: 1,500 QPM [S26]).
13. **q8a follow-ups from this document:**
    - the `llm-anthropic` extra and the Vertex adapter config (§2.3);
    - a Vertex batch-prediction adapter if the Delayed Job mode is chosen;
    - a `run-batch` CLI and pending store for any batch mode (§2.4);
    - optional stage parallelism (audio ∥ frames) inside `handle_delivery` (§2.2).
14. **q5 follow-up:** q5 §3/§5b compute local cost with the older Cloud Run assumptions (4 vCPU / 8 GiB, slowdown ×2.0 [Q5 S50]). With this document's ×2.5 and 16 GiB, q5's local-cost figures rise by about 46% (1.25 × 1.17). No q5 conclusion changes. If the benchmark settles on 8 GiB, the rise is 25%.

---

## 9. Review round 1 — resolution

| # | Finding (severity) | Resolution |
|---|---|---|
| 1 | Gemini 2.5 Flash-Lite retires on Vertex in 12 days (wrong) | **Fixed.** Re-verified: Gemini API pricing (updated 2026-10-07) gives 3.1 Flash-Lite audio $0.50 / out $1.50 and 3.5 Flash-Lite $0.30 / $2.50 [S18]; Vertex pricing gives the non-global (EU) prices $0.55 / $1.65 and $0.33 / $2.75 [S27]; Q4 records the 2026-10-20 retirement. Hosted captions now use the Vertex EU prices of both 3.x models. Old open question 9 closed by pointing to Q4; the 32 tokens/s caveat is kept (open question 9) |
| 2 | Hosted captions not gated by VAD (design concern) | **Fixed.** Hosted captions now pay the same local VAD gate and run only on speech videos and speech seconds; their synchronous wait is billed. STT V2 dynamic batch is priced ($0.003/min, re-verified [S20]) and marked async-only. Result: local is 1.4–1.6× cheaper than gated Gemini 3.x at CPU ×1, and dearer at CPU ×0.5. The doc now calls captions a close call |
| 3 | Cold-start probability statement wrong (wrong) | **Fixed.** Recomputed from the formula: 50% at about 1,350 videos/month, 33% at 2,165, 10% at about 4,500, 1% at about 9,000, 0.1% at 12,990 (§3) |
| 4 | Haiku wait not billed (design concern) | **Fixed.** `HAIKU_WAIT_S` = 3 s (guess) is billed at the runtime's rate in every Haiku mix; the jobs divide it by `HAIKU_JOB_PARALLEL` = 8. Overlapping it with local stages is not possible because summaries take captions and labels as input (§2.2) |
| 5 | 8 GiB too small (design concern) | **Fixed.** 16 GiB throughout ($0.000136/s; 4 vCPU allows up to 16 GiB [S23]). Q2's measurement and its ≤30 s segmentation are taken into account (§3); peak RSS is in open question 1; SigLIP loads only the image tower |
| 6 | "Same image" for CPU and L4 (design concern) | **Fixed.** Two variants (`-cpu`, `-cuda`) from one Dockerfile, shared code and weights layer (§2.5), matching q8a's `cpu`/`cu130` selectors |
| 7 | Parakeet CPU scaling rests on an unstated thread count (unsupported) | **Fixed differently.** The base is now Q2's own measurement of the chosen runtime (sherpa-onnx int8, 4 threads, short clip, M4) through the same M4 factor as SigLIP. The 9800X3D figure is kept as a cross-check, with the 8- and 16-thread readings (RTFx 10.7 / 5.3) printed; both lie within the ×0.5 sensitivity. "Ryzen 9" corrected to Ryzen 7. The M4 factor itself was raised from 2.0 to 2.5 (judgement, §5) |
| 8 | Sensitivity text misstates the dominant estimate (minor) | **Fixed.** The script prints the shares; §1 and §7 say Freepik and the guard (both guesses) make up 60%, and open question 1 measures them first |
| 9 | "Haiku cheaper at every volume" vs batched vLLM (unsupported) | **Fixed.** Reworded to "cheaper than a single-stream local LLM; a batched vLLM in the L4 job could break even at about 3× throughput (unmeasured)" (§7) |
| 10 | Free-tier toggle gives negative totals (wrong) | **Fixed.** The credit is computed per configuration from its own billed seconds and its own tier (request / instance-jobs / Delayed Jobs; GPU seconds get none), and totals are clamped at ≥ 0. A "free tier on" row is printed for the key columns; no value is negative |
| 11 | Hourly job assumes 730 batches (minor) | **Fixed.** Slots derive from `ACTIVE_HOURS_PER_DAY` (486/month), and only expected non-empty slots are billed (skip-if-empty) |
| 12 | L4-job switch advice ignores size of saving and prerequisites (design concern) | **Fixed.** Savings stated in dollars; §2.4 lists what q8a would need (pending store, scheduler, `run-batch` CLI, CPU fallback, product decision) and why q8a's per-media `jobs.run` does not work per upload ($0.0175+ per video) |
| 13 | Cloud Run CPU jobs and Delayed Jobs missing (missing option) | **Fixed.** Added "CPU hourly job + Haiku" and "CPU Delayed Job + Haiku Batch" columns. Re-verified Delayed Jobs: Preview, up to 12 h provisioning, 12 h task timeout [S22]; prices and the 30-day dynamic-price note [S1] |
| 14 | Batch APIs missing (missing option) | **Fixed.** The Delayed Job column uses Haiku Batch (re-verified $0.05 / $0.25 first-party, $0.055 / $0.275 Vertex EU [S11][S27]); STT V2 dynamic batch is priced; Gemini Batch is not used because hosted captions are not recommended |
| 15 | EU data residency for Haiku not considered (missing option) | **Fixed, as a user decision.** Verified: first-party `inference_geo` is only `global` or `us`, workspace geo only `us` [S24]; Vertex serves Haiku 5.5 (GA) on global, US and EU multi-region endpoints at +10% ($0.11 / $0.55), single-region endpoints only up to Sonnet 4.6 [S25][S26][S27]. Both sides in §2.3; open question 12. The grid uses Vertex EU |
| 16 | Concurrency 1 contradicts q8a; queueing not modelled (design concern) | **Fixed.** `max_jobs = 1`, Cloud Run concurrency = `max_jobs`, as q8a §6.3 now reads. The script prints the busy share per cell; §3 notes that p_cold understates cold starts above about 0.3 instance |
| 17 | Decode and text embedding left out (minor) | **Fixed.** New "shared" stage: `DECODE_S_CPU` 4 s and `TEXT_EMBED_S_CPU` 0.5 s (guesses) |
| 18 | STT V2 ratio inconsistent (minor) | **Superseded.** With the gate and billed wait, STT V2 standard is about 13× local everywhere in the doc |
| 19 | c4 price is on the official page (minor) | **Fixed.** Cited [S8] for $0.415107/h; [S9] only for the region mapping and spot |
| 20 | g2 EU availability understated (minor) | **Fixed.** europe-west1/3/4 [S9] |
| 21 | Script hygiene (minor) | **Fixed.** Unused `HAIKU_MOD_VIDEO_SHARE` removed; worker-pool constants now used to print the always-on pool cost; the dead `stages` parameter is gone |
| 22 | VAD speed figure is for V5, not v6.2 (minor) | **Fixed.** Version gap and the single-thread idle-vCPU note added (§5) |
| 23 | Haiku moderation/labels ignore tokenizer and thinking (minor) | **Fixed.** Labels assume thinking disabled; noted in §5. Tokenizer differences are not modelled (reference-only columns) |
| 24 | 25 s GPU start-up optimistic (minor) | **Fixed.** 60 s sensitivity row added (+$0.7–5/month on the L4 job columns); open question 2 |
| 25 | GitHub rejection of backfills is a judgement (design concern) | **Fixed.** §4 leads with cost and data location; the ToS reading is labelled a judgement |

---

## 10. Review round 2 — resolution

Final round ([reviews/q7-review-r2.md](reviews/q7-review-r2.md)). Each finding was re-checked against its source on 2026-10-08 before it was applied. Anything still open is in §8 (as a user decision where it is one).

| # | Finding (severity) | Resolution |
|---|---|---|
| 1 | q2 did measure peak RSS with ≤30 s segments (wrong) | **Fixed.** §3 now cites q2 §6.2: the whole audio stack peaks at 1.33 GB (1.04 GB after loading) on linux/amd64. The full job is estimated at about 5–7 GB, and the guard is the deciding unknown. 16 GiB stays as a safety default until the benchmark; 8 GiB is the target if the peak stays below about 6 GiB. New constant `CPU_GIB_SMALL` and a "CPU 8 GiB" sensitivity row (−14 to −15%). §1, §3, open questions 1 and 6 |
| 2 | `SIGLIP_MS_M4 = 66` superseded (unsupported) | **Fixed.** Now 37 + 5.4 + 3.5 = 45.9 ms (inference + preprocessing + JPEG decode), the same figure as q5 §3/§5b, as three MEASURED constants. Labels fall to 3.4 s and $0.00047 per video; the SigLIP share falls from 7% to 5%; the measured-input share is now 29%. No conclusion changes |
| 3 | Job latency bounds understated (wrong) | **Fixed.** Verified on the Delayed Jobs page: provisioning up to 12 h, a 12 h total task runtime, completion within 24 h; batch results within 24 h (Vertex Claude batch page). The script now prints the worst case per cell (`worst_latency_h`). Hourly jobs: 1 h slot + run time, 1.0–1.9 h. Delayed Job + Haiku batch: next run + 12 h provisioning + run + 24 h batch + 1 h collector = 49–56 h. With synchronous Haiku instead: 24–31 h for +$0.03–4.32/month. Batch results are now collected by a separate light trigger, as the reviewer suggested. §1, §2.4 table, §6 notes, open question 3 |
| 4 | Execution-length caps not checked for CPU jobs (design concern) | **Fixed in the script.** The hourly CPU job shards so that each task finishes within the hour (`CPU_HOURLY_TASK_MAX_S`); cold start is paid per task. 2 tasks are needed at CPU ×0.5 and 100k × 5%. The Delayed Job raises its runs per day until one execution stays at or below 75% of the 12 h cap (`DELAYED_EXEC_MAX_S`, `DELAYED_CAP_MARGIN`). It stays at one task, because the cap counts all tasks. At CPU ×0.5 and 100k × 5% it needs 4 runs a day instead of a 13.6 h run that would be cancelled. §2.1, §2.4 |
| 5 | "`llm-anthropic` covers both" wrong (wrong) | **Fixed.** Verified: Anthropic's Vertex page installs `anthropic[vertex]`; q8a l.659 has `anthropic>=1.12`. §2.3 now says the q8a extra must become `anthropic[vertex]>=1.12` (or a separate `llm-anthropic-vertex` extra) if Vertex is chosen. The adapter needs `project_id` and `region="eu"`. Recorded as a q8a follow-up (open question 13) |
| 6 | Haiku batch on Vertex is a different API (design concern) | **Fixed.** Verified: "Message Batches" is listed under "Features not supported" on Vertex. Vertex batch prediction takes BigQuery or GCS JSONL input, does not support the global endpoint, needs the job and the table in the same region, returns results within 24 h, and allows 4 concurrent jobs per project by default; Haiku 5.5 is listed. §2.3 describes the separate adapter; §2.4 item 4 and open question 12 carry it. EU-multi-region support for Claude batch is not stated on the batch page, so it stays to be confirmed (open question 12) |
| 7 | 15 s CPU cold start unsupported (unsupported) | **Fixed.** Now derived: 10 s image (guess) + (5.9 s SigLIP import and load, measured in q5 §3, + 4 s for the other models, guess) × 2.5 = 35 s. A "CPU cold 60 s" row is added (+$0.41 at 1k × 3%, up to +$2.42). Lazy guard loading is noted as a mitigation. The overhead row at 1k × 3% rises from $0.25 to $0.58 |
| 8 | Missing option: overlap the audio and frame branches (missing option) | **Added.** §2.2 describes it. A "parallel branches" sensitivity row (`BRANCH_OVERLAP_HIDE_SENS` = 0.5, guess) gives −14% billed seconds per video and −9% to −13% on the totals; the main grid stays serial, as in q8a v1. Open question 1 measures it; open question 13 records it as a q8a follow-up |
| 9 | Stale §9 note on q8a concurrency (minor) | **Fixed.** The parenthesis is dropped. §2.2 notes q8a's GPU `max_jobs = 2` (the L4 service column is a conservative upper bound) and the 1500 s budget against 72–140 s per video |
| 10 | Free-tier switch leftovers (minor) | **Fixed.** The headings follow `APPLY_FREE_TIER`, each cell prints a "free-tier credit" row when it is on, and the hosted reference gets the request-based credit on its Cloud Run seconds. Tested with the switch on: no negative totals |
| 11 | Delayed Jobs GPU prices (minor) | **Fixed.** Verified in the downloaded pricing page: L4 $0.0001867/s and RTX PRO 6000 $0.00036522/s in the Delayed Jobs table, the same as the normal GPU rate. The feature page does not mention GPUs. §2.1 and open question 7 |
| 12 | Gemini 3.x EU endpoint assumed (minor) | **Fixed as an open item.** No Google page found that lists 3.x Flash-Lite locations. Third-party reports point to `eu` multi-region only; added to open question 9 |
| 13 | q5 uses the older shape and slowdown (minor) | **Recorded** as a q5 follow-up (open question 14): +46% on q5's local-cost figures (+25% if 8 GiB is chosen). q5 is not edited here |
| 14 | Idle-retention source (minor) | **Fixed.** Now cites the instance-autoscaling page: "up to 15 minutes, or 10 minutes for GPUs" [S29]. The GPU service now uses W = 600 s (`IDLE_WINDOW_S_GPU`), so the L4 service column falls (for example $34.56 → $23.86 at 1k × 3%); it stays "do not use". Both values are upper bounds (open question 8) |
| 15 | Rounding of the ×2 sensitivity (minor) | **Fixed** with the new numbers: ×1.6–1.9 at CPU ×0.5 and ×0.54–0.68 at ×2 (§1) |

Changes in the totals of the recommended service, round 1 → round 2 (CPU ×1): $1.59 → $1.89, $2.62 → $3.11, $14.73 → $16.28, $23.74 → $25.23, $133.77 → $131.15, $222.90 → $218.46. The small cells rise because of the longer cold start; the large cells fall because of the faster SigLIP figure. No recommendation changed.

---

## 11. Sources

All read 2026-10-08 unless stated.

- [S1] Google Cloud, Cloud Run pricing: Tier-1 region list, free tiers (request, instance, Delayed Jobs, worker pools), request/instance/jobs/delayed-jobs/worker-pool and GPU rates, "Delayed Jobs Prices are dynamic and can change up to once every 30 days", billable-instance-time rules. https://cloud.google.com/run/pricing
- [S3] Google Cloud, GPU support for Cloud Run services (last updated 2026-10-07): regions, minimum CPU/memory, ~5 s start, instance-based billing required, quota, zonal redundancy, driver 580 / CUDA 13.0. https://docs.cloud.google.com/run/docs/configuring/services/gpu
- [S4] Google Cloud, Best practices: AI inference on Cloud Run services with GPUs (last updated 2026-10-07): model loading options, "< 10 GB" guidance. https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices
- [S5] Google Cloud, GPU for Cloud Run jobs (last updated 2026-10-07). https://docs.cloud.google.com/run/docs/configuring/jobs/gpu
- [S6] Google Cloud, Billing settings for services (last updated 2026-10-07): instance-based billing lifecycle, 15-minute idle maximum. https://docs.cloud.google.com/run/docs/configuring/billing-settings
- [S7] Google Cloud, Cloud Run quotas and limits (last updated 2026-10-07): 8 vCPU / 32 GiB, 60 min request timeout, job task timeout 168 h or 1 h with GPU, no direct image-size limit. https://docs.cloud.google.com/run/quotas
- [S8] Google Cloud, Compute Engine accelerator-optimized and general-purpose pricing (HTML table data): g2-standard-4 europe-west4 $0.742916046/h, spot $0.445676/h; europe-west1 $0.778293004/h; e2-standard-4 europe-west4 $0.1475/h; c4-standard-8 $0.415107/h. https://cloud.google.com/products/compute/pricing/accelerator-optimized and https://cloud.google.com/products/compute/pricing/general-purpose
- [S9] gcloud-compute.com (third-party, data updated 2026-10-04), region mapping (g2-standard-4 in europe-west1/3/4) and c4 spot: https://gcloud-compute.com/g2-standard-4.html, https://gcloud-compute.com/e2-standard-4.html, https://gcloud-compute.com/c4-standard-8.html
- [S10] Google Cloud, GPU for Cloud Run worker pools (last updated 2026-10-07). https://docs.cloud.google.com/run/docs/configuring/workerpools/gpu
- [S11] Anthropic, Pricing: Haiku 5.5 $0.10 / $0.50 per MTok (≤100k-token prompts), Batch $0.05 / $0.25; US-only `inference_geo` ×1.1. https://platform.claude.com/docs/en/about-claude/pricing
- [S12] GitHub Terms for Additional Products and Features, Actions section (effective 2026-08-27). https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
- [S13] GitHub Docs, Actions runner pricing. https://docs.github.com/en/billing/reference/actions-runner-pricing
- [S14] GitHub Docs, Larger runners reference (GPU runner: Tesla T4, 16 GB VRAM, 4 cores, 28 GB RAM). https://docs.github.com/en/actions/reference/runners/larger-runners
- [S15] GitHub Docs, Actions limits. https://docs.github.com/en/actions/reference/limits
- [S16] Hugging Face model API (file sizes): istupakov/parakeet-tdt-0.6b-v2-onnx, timm/ViT-B-16-SigLIP2, Freepik/nsfw_image_detector. https://huggingface.co/api/models/{repo}?blobs=true
- [S17] GitHub Docs, GitHub Actions billing. https://docs.github.com/en/billing/concepts/product-billing/github-actions
- [S18] Google, Gemini API pricing (last updated 2026-10-07): 3.1 Flash-Lite audio in $0.50, out $1.50; 3.5 Flash-Lite $0.30 / $2.50. https://ai.google.dev/gemini-api/docs/pricing
- [S19] Google, Gemini API audio understanding ("32 tokens per second of audio", last updated 2026-09-23). https://ai.google.dev/gemini-api/docs/audio
- [S20] Google Cloud, Speech-to-Text pricing (V2 standard $0.016/min to 500k min; dynamic batch $0.003/min, "processes audio at a lower level of urgency"; rounded up per 1 s). https://cloud.google.com/speech-to-text/pricing
- [S21] Silero VAD wiki, Performance Metrics (V5 ONNX 189 µs per 31.25 ms chunk, RTS 165, 1 thread). https://github.com/snakers4/silero-vad/wiki/Performance-Metrics
- [S22] Google Cloud, Delayed jobs (last updated 2026-10-07): Preview; provisioning "potentially up to 12 hours"; "the total runtime duration of all tasks in a delayed job execution is 12 hours"; an execution at the limit "is cancelled by the system"; completes within 24 h; `--delay-execution`; GPUs not mentioned. https://docs.cloud.google.com/run/docs/delayed-jobs
- [S23] Google Cloud, Configure memory limits for services (last updated 2026-10-07): 4 vCPU allows 2–16 GiB; above 16 GiB needs 6 vCPU; memory must cover files written to the file system. https://docs.cloud.google.com/run/docs/configuring/services/memory-limits
- [S24] Anthropic, Data residency: `inference_geo` "global" (default) or "us"; "Currently, "us" is the only available workspace geo"; on Google Cloud the region is set by the endpoint. https://platform.claude.com/docs/en/build-with-claude/data-residency
- [S25] Anthropic, Claude on Google Cloud (Vertex AI): `claude-haiku-5-5`; global, multi-region (us, eu) and regional endpoints; "Regional and multi-region endpoints include a 10% pricing premium over global endpoints"; regional endpoints serve Sonnet 4.6 and earlier. https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai
- [S26] Google Cloud, Claude Haiku 5.5 model page (GA, released 2026-10-07, retirement not before 2027-10-07, regions: US multi-region, Europe multi-region, global; batch predictions supported; multi-region quota 1,500 QPM) and Deployments and endpoints (EU multi-region host `aiplatform.eu.rep.googleapis.com`). https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-5-5 , https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations
- [S27] Google Cloud, Vertex AI / Agent Platform pricing: Claude Haiku 5.5 global $0.10 / $0.50 (Batch $0.05 / $0.25), regional / multi-region $0.11 / $0.55 (Batch $0.055 / $0.275); Gemini 3.1 Flash-Lite audio in $0.50 global / $0.55 non-global, output $1.50 / $1.65; Gemini 3.5 Flash-Lite $0.30 / $0.33 in, $2.50 / $2.75 out. https://cloud.google.com/vertex-ai/generative-ai/pricing
- [S28] Google Cloud, Batch predictions with Anthropic Claude models (Agent Platform docs): BigQuery or Cloud Storage JSONL input and output; "The global endpoint for partner models isn't supported"; "The batch prediction job and your table must be in the same region"; results "after all rows have completed or after 24 hours, whichever comes first"; 4 concurrent batch requests per project by default; Haiku 5.5 listed. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/claude/batch
- [S29] Google Cloud, About instance autoscaling in Cloud Run services: idle instances kept "up to 15 minutes, or 10 minutes for GPUs". https://docs.cloud.google.com/run/docs/about-instance-autoscaling
- Findings files used for models and speeds: `q1-input-contract.md`, `q2-captions.md`, `q3-summaries-chapters.md`, `q4-moderation.md`, `q5-labels.md`, `q6-translation.md`, `q8a-architecture-layout.md`, `user-decisions.md` (all in this directory).
