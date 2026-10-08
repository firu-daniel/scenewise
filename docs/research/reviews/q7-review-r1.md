# Q7 review, round 1

Reviewer: fresh review agent (did not write Q7). Date: 2026-10-08.
Reviewed: `docs/research/q7-runtime-cost.md` and `docs/research/q7_cost_grid.py`.
Sources were re-read on 2026-10-08. The Cloud Run, Compute Engine and Speech-to-Text pages were downloaded and grepped, because WebFetch truncates them.

Script check: `python3 -I docs/research/q7_cost_grid.py` runs cleanly. Its output matches §6 line for line; a whitespace-insensitive diff shows only the doc's added "How to read" bullets and a `---` rule. The grid cells match the brief: 1,000×3% gives 129.9 videos / 650 min; 10,000×5% gives 2,165; 100,000×5% gives 21,650 videos / 108,250 min. I re-derived the hand arithmetic, and all of it is correct: rates, per-stage seconds, the Haiku and Gemini per-video figures, the worked example, the totals, and the 132 h job crossover.

Severity counts: wrong 3, unsupported 2, missing option 3, design concern 7, minor 10 (25 findings).

---

## Findings

### 1. Gemini 2.5 Flash-Lite is used as the hosted captions reference, but it retires on Vertex in 12 days
- **Claim:** "Gemini 2.5 Flash-Lite $0.0031" per video (§1, §5, §6, §7). The "Hosted APIs" column uses it. Open question 9 asks "Is Gemini 2.5 Flash-Lite still offered long-term?"
- **Source:**
  - Vertex AI model versions page (`docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions`, updated 2026-10-07): gemini-2.5-flash-lite, released 2025-07-22, **retirement 2026-10-20**. gemini-3.1-flash-lite retires "May 7, 2027 or later"; 3.5 Flash-Lite "July 21, 2027 or later".
  - Gemini API deprecations page (ai.google.dev, updated 2026-10-07): "No shutdown date announced", but "For any new projects, use our latest models: 3.5 Flash-Lite or 3.8 Flash".
  - Q4 already records the 2026-10-20 retirement, and that the Gemini API limits 2.5 models to existing users.
  - Gemini API pricing (updated 2026-10-07), per 1M tokens:
    - 3.1 Flash-Lite: audio in $0.50, out $1.50.
    - 3.5 Flash-Lite: audio in $0.30, out $2.50.
    - 2.5 Flash-Lite: $0.30 / $0.40, which Q7 quotes correctly.
- **Severity:** wrong (stale model choice; open question 9 is already answered by Q4).
- **Correction:**
  - Price the hosted captions reference on 3.1 or 3.5 Flash-Lite. With Q7's token assumptions that is **$0.0062 (3.1) / $0.0056 (3.5) per video**, against $0.0031.
  - Local CPU captions are then about 2.1–2.3× cheaper, not 1.2×.
  - The Hosted APIs captions row roughly doubles (100k×5%: about $121–134 instead of $68).
  - The 32 audio tokens/s rate is documented generically; the audio page does not state it per model (check for 3.x).
  - Close open question 9 by pointing to Q4.
  - Note that EU use means Vertex, where prices may differ.

### 2. The hosted captions baseline is not gated by VAD, but the local pipeline is
- **Claim:** "Local CPU vs Gemini 2.5 Flash-Lite (captions): Never; local is about 1.2× cheaper. Google STT V2 is about 27× dearer" (§7). §1 says 25×.
- **What the script does:**
  - Local ASR runs only on `SPEECH_VIDEO_SHARE` = 0.6 of videos, after a VAD/LID gate.
  - `hosted_per_video()` bills Gemini and STT on `AUDIO_VIDEO_SHARE` = 0.9 of videos, at full duration.
  - A real hosted design would keep the cheap local VAD (2.34 s = $0.00027) and send only speech videos.
- **Effect** (computed):
  - Gated 2.5 Flash-Lite = 0.6 × $0.00349 + $0.00027 = **$0.0024, cheaper than local CPU ($0.00268)**. The stated conclusion flips for the model Q7 priced.
  - Gated 3.1 / 3.5 Flash-Lite = $0.0044 / $0.0040, so local is about 1.5–1.6× cheaper.
  - STT V2 standard on speech videos only: $0.048 (about 18× local).
  - STT V2 **dynamic batch** at $0.003/min (verified on the STT pricing page, `cloud.google.com/speech-to-text/pricing`) costs $0.0135 ungated or $0.009 gated, about 3–5× local. Q7 lists this price but never uses it.
- **Severity:** design concern (unequal baselines; the ratios are not robust).
- **Correction:**
  - Gate the hosted captions by the same VAD in the script (a named constant).
  - Report the 3.x Flash-Lite figures and STT dynamic batch.
  - State that the captions decision is close and depends on the CPU benchmark.

### 3. The cold-start probability statement is wrong
- **Claim (§3):** "Cold starts are rare above about 1k videos/month: the probability is exp(−λ·900 s), so about 1% at 13k videos/month."
- **Computed with the doc's own λ** (16 active h/day, 30.4 days):

  | Videos/month | p_cold |
  |---|---|
  | 1,000 | 60% |
  | 2,165 | 33% |
  | about 4,500 | 10% |
  | about 8,950 | 1% |
  | 12,990 | **0.13%** |
- **Severity:** wrong.
- **Correction:** "Most videos cold-start below about 2k videos/month. Fewer than 10% do above about 4.5k. At 13k it is about 0.1%." The grid values themselves are correct, because the script computes p_cold properly.

### 4. Haiku wait time inside the request is not billed in the grid
- **Claim:**
  - Summaries are called "from the same Cloud Run request" (§2.2), synchronously, with concurrency 1 and request-based billing.
  - The recommended mix adds only the Haiku API fee (`mix()` takes `out["hosted"]["summaries"]`).
- **Why it matters:** request-based billing charges while a request is in flight (Cloud Run pricing page, "At least one request is being processed by the instance"). The 4 vCPU / 8 GiB instance is therefore billed while it waits for Haiku.
- **Effect (estimate):**
  - At 2–5 s per Haiku call: $0.00023–0.00058 per video. That is 0.7–1.9× the Haiku fee itself; at 100k×5% it adds about $5–13/month.
  - In the "L4 job + Haiku" mix, the same wait is billed at $0.000291/s: about $13–31/month at 100k×5%, unless the job makes the Haiku calls concurrently or leaves them out of the GPU job.
- **Severity:** design concern (a missing cost term).
- **Correction:** add `HAIKU_WAIT_S` and bill it at the runtime's rate in both mixes. Alternatively, make the summaries call concurrent with the local stages: q8a hosted adapters take no lock.

### 5. 8 GiB is probably too small for "all models in one image"
- **Claim:** 4 vCPU / 8 GiB with captions, LID, Freepik, SigLIP 2 and the guard VLM in one instance. Only the guard is flagged, in open question 6.
- **Source:**
  - Q2 §9 local measurement: a 334 s single Parakeet pass peaked at **5.10 GB RSS (onnx-asr)** and 6.56 GB (sherpa-onnx). VAD chunking should lower this, but nobody has measured it.
  - Q7 §3 lists SigLIP 2 at 1.50 GB fp32 (the text tower is included unless dropped), the guard VLM at Q4 2–2.5 GB plus its vision encoder and KV cache (run as an out-of-process llama.cpp server in the same container; q8a says that server "isolates crashes and memory"), Freepik at 0.17 GB, plus faster-whisper tiny, torch/onnxruntime and ffmpeg.
- **Severity:** design concern.
- **Correction:**
  - Size the instance at 16 GiB until the benchmark shows otherwise. The rate becomes $0.000136/s (+17%), and the recommended totals rise by about the same share of local compute.
  - Or load the guard lazily, or move it to its own service.
  - Load only SigLIP's image tower at runtime.
  - Add peak RSS to open question 1.

### 6. A "same image" for the CPU service and the L4 job is a design concern
- **Claim:** "Keep the same image runnable as a Cloud Run GPU job (L4)" (§1).
- **Why:**
  - A CUDA-capable image (onnxruntime-gpu or torch with CUDA libraries) adds several GB to every CPU cold start and image pull.
  - The CPU service gets no benefit from those GB.
  - The Cloud Run GPU page (updated 2026-10-07) pins driver 580 / CUDA 13.0, so the GPU build has its own base-image constraints.
- **Severity:** design concern.
- **Correction:** build two image variants (`-cpu`, `-cuda`) from the same code and the same pinned weights layer. "Same code and weights", not "same image".

### 7. The Parakeet CPU speed scaling rests on an unstated thread count
- **Claim:** "`PARAKEET_DESKTOP_RTFX` 36.8 on Ryzen 9800X3D (16 threads)". The script divides by 16 threads and multiplies by 4 vCPU × 0.7, giving RTFx 6.44.
- **Source:** the onnx-asr benchmarks page (istupakov.github.io/onnx-asr/benchmarks, read 2026-10-08) states neither the thread count nor the audio length, and does not name the default precision. The CPU is a **Ryzen 7** 9800X3D, not the "Ryzen 9" in §5. onnxruntime's default intra-op thread count is the number of physical cores (8), so the 16-thread denominator is a guess.
- **Two inconsistencies:**
  - The doc sizes the image with **int8** weights (0.66 GB) but uses the **default-precision** speed (36.8). int8 on that CPU is 30.5, which gives RTFx 5.34 and ASR 24.8 s instead of 20.8 s.
  - Q2's own M4 measurements show RTFx 13.8–16.8 on a long single pass against 30–36 on short clips. Throughput depends on segment length, which the scaling ignores.
- **Severity:** unsupported.
- **Correction:**
  - Label the 16-thread assumption as a guess.
  - Use the int8 figure when the int8 weights are assumed.
  - Show the result as a range: ASR on 4 vCPU at roughly RTFx 3–13, depending on thread scaling.

### 8. The sensitivity text misstates which estimate dominates
- **Claim:** "The Freepik tier-1 cost is a pure estimate … the largest CPU item after ASR" (§1).
- **Computed** from the grid's own CPU seconds:
  - Freepik is 24 s per video, more than **all** of captions (23.1 s) and more than ASR+LID (20.8 s).
  - In the recommended configuration (63.1 CPU-s per video): Freepik 38%, ASR+LID 33%, guard 19%, SigLIP 6%, VAD 4%.
  - Freepik (`FREEPIK_MS_M4` = 400 ms, derived from token count) and the guard (`GUARD_S_PER_FRAME_CPU` = 20 s) are both unmeasured. Q4 says "No source gives CPU latency for any of these models". Together they make up **57%** of the recommended CPU cost.
- **Severity:** minor (wrong wording, but the conclusion should be sharper).
- **Correction:**
  - State that two pure guesses drive most of the recommended configuration's local cost, and that the ASR scaling drives another third.
  - Make the Freepik and guard measurements the first items of open question 1.

### 9. "Haiku is cheaper at every volume" against a batched local LLM is not supported
- **Claim:** "Never. Haiku is cheaper at every volume … Even a perfectly batched vLLM server would need about 4× higher throughput than our single-stream L4 estimate to break even" (§7). The 3.8× figure is computed correctly.
- **Source:** Q3 cites vLLM reaching about 19× Ollama's aggregate throughput on an A100 [Q3 S28]. The hourly L4 job processes about 30–45 videos per batch at 100k×5%, so batched summarisation is natural there, and 4× is plausible.
- **Severity:** unsupported (the "never" is too strong).
- **Correction:**
  - Say "Haiku is cheaper than any single-stream local LLM. A batched vLLM in the L4 job could break even (unmeasured)."
  - The recommendation still stands. The absolute stake is at most about $5/month at 100k×5%, and Q3 picks Haiku on quality and operational grounds.

### 10. The free-tier toggle produces negative totals (script bug)
- **Claim:** `APPLY_FREE_TIER` lets the grid be recomputed. Open question 5 says "the smallest cells drop to about $0".
- **What happens:** I ran a copy with `APPLY_FREE_TIER = True`. The recommended column reads **−$1.171** (1k×3%) and **−$1.967** (1k×5%).
- **Cause:**
  - The credit is computed from all-local busy seconds, which include the 94.5 s local LLM, and is stored in `cr_cpu["overhead"]`.
  - `mix()` then copies that overhead into the Haiku mix, which never incurs the LLM seconds.
- **Severity:** wrong (the script is wrong under its own documented switch; the published grid has the switch off and is unaffected).
- **Correction:**
  - Compute the free-tier credit per configuration from that configuration's own billed seconds.
  - Clamp the total at ≥ 0.
  - Apply the instance-based free tier (240k vCPU-s) to the GPU columns as well, or state that it is excluded.

### 11. The hourly L4 job floor assumes 730 batches but uploads arrive in 16 h/day
- **Claim:** "Below about 130 h the job's per-batch minimum (60 s × 730 batches ≈ $12.7/month floor) dominates"; crossover ≥ 132 h.
- **Why:** the model puts all arrivals into 16 active hours, so a scheduler that skips empty queues runs about 486 batches, not 730.
- **Re-run** with `GPU_JOB_BATCHES_PER_MONTH = 486`:
  - The crossover moves to **≥ 85 h**.
  - 10k×3% costs $8.88 instead of $13.14, so the L4 job + Haiku beats the recommended $11.07 there too.
- **Severity:** minor.
- **Correction:** derive the batch count from `ACTIVE_HOURS_PER_DAY` (with skip-if-empty), or state the 730 assumption as conservative.

### 12. The "switch to the L4 job at ~130 h" advice ignores how small the saving is and what the switch requires
- **Claim:** "a cheaper steady-state path once volume passes about 130 video-hours/month" (§1).
- **Why:**
  - The saving is about $0 at 132 h, **$4.35/month** at 10k×5%, $66 at 100k×3% and $113 at 100k×5% (from the grid).
  - The switch needs a second runtime path, an up-to-1 h latency, and an intake mechanism the architecture does not have. q8a §6.4(a) designs the Cloud Run job path as **one `jobs.run` per media** for long media. Run per video, the GPU job would bill at least 60 s + cold start each time: about $0.0175+ per video, or about $378/month at 100k×5%.
  - GPU jobs are non-zonal and best-effort, with a default quota of 3 GPUs per region (GPU jobs page, updated 2026-10-07). A CPU fallback is therefore needed.
- **Severity:** design concern.
- **Correction:**
  - State the switch point in dollars ("worth it at about 1,000+ video-h/month, where it saves $65–115/month").
  - Note that hourly micro-batching needs a scheduler plus a pending-job store (not in q8a), and a CPU fallback when no L4 is available.

### 13. Cheaper CPU batch options are missing: Cloud Run CPU jobs and Delayed Jobs
- **Claim:** the grid compares the latency-tolerant L4 job only against the request-based CPU service. Delayed Jobs is "not researched".
- **Source:** Cloud Run pricing page (read 2026-10-08):
  - Jobs: CPU $0.000018 per vCPU-s, memory $0.000002 per GiB-s, so 4 vCPU / 8 GiB = **$0.000088/s**, 24% below request-based.
  - Delayed Jobs: CPU $0.0000126, memory $0.0000014, so **$0.0000616/s**, 47% below. "Prices are dynamic and can change up to once every 30 days".
- **Effect (estimate):** an hourly CPU job + Haiku at 10k×3% costs about $8.6/month, against $11.07 (recommended) and $13.14 (L4 job). It is the cheapest option in that cell, with no GPU quota risk.
- **Severity:** missing option.
- **Correction:** add "CPU job (hourly) + Haiku" and a Delayed Jobs sensitivity column to the script. The constants partly exist already.

### 14. Batch APIs are missing for the latency-tolerant path
- **Claim:** the hosted figures use standard prices only.
- **Source:**
  - Anthropic pricing page (read 2026-10-08): Haiku 5.5 Batch costs $0.05 / $0.25 per MTok.
  - STT V2 dynamic batch costs $0.003/min.
  - Gemini batch prices are 50% of standard.
- **Severity:** missing option.
- **Correction:** in the hourly-job columns, which already accept up to 1 h of latency, also show Batch-priced summaries. Q3 recommends Batch only for backfills, so note the trade-off (results arrive within up to 24 h).

### 15. EU data residency for Haiku is not considered, although GitHub is rejected partly on that ground
- **Claim:** GitHub Actions is ruled out partly because it "would also take EU personal data out of Google Cloud" (§1, §4), while the recommended design sends transcripts, labels and moderation frames to the Anthropic first-party API.
- **Source:** Anthropic pricing page (read 2026-10-08):
  - `inference_geo` offers only "global" (default) or "us" (1.1×) on the first-party API.
  - On Google Cloud, Claude has "regional and multi-region endpoints [with] a 10% premium over global endpoints".
  - User decision U3: the operator is EU-based.
- **Severity:** missing option.
- **Correction:**
  - Add the option "Haiku 5.5 via Vertex AI, EU regional or multi-region endpoint (+10%)". Its cost impact is negligible: at most about $0.7/month at 100k×5%.
  - Check that Haiku 5.5 is available in an EU Vertex region.
  - Make the residency argument consistent across options.

### 16. Concurrency 1 contradicts q8a, and the queueing effects are not modelled
- **Claim:** "concurrency 1" (§1).
- **Source:**
  - q8a §6.3: "Cloud Run `--concurrency = max_jobs + 2`, so health and `GET` requests are not queued behind jobs", with `max_jobs = 1` on small CPU instances. That gives a concurrency of 3, with the job count limited by the in-process limiter.
  - At 100k×5% the recommended configuration keeps one instance about 78% busy during active hours (21,650 × 63.1 s over 16 h/day). Scale-out, peaks and the extra cold starts are not modelled.
- **Severity:** design concern (small cost impact, real latency impact).
- **Correction:**
  - Say "one job per instance (`max_jobs = 1`), Cloud Run concurrency per q8a".
  - Note that p_cold understates cold starts once the load is above about 0.3 instance.

### 17. Some local costs are left out of the grid
- **Claim:** "only AI processing cost is counted".
- **What is missing:**
  - Q5 recommends a transcript text embedding (`multilingual-e5-small`), which the grid omits.
  - Frame decoding (ffmpeg on 30 frames plus audio extraction) is also omitted, although it runs on the same billed vCPUs.
- **Severity:** minor.
- **Correction:** add small named constants (e.g. `TEXT_EMBED_S_CPU`, `DECODE_S_CPU`), or state the exclusion explicitly.

### 18. The STT V2 ratio is inconsistent
- **Claim:** "about 25× dearer" (§1) vs "about 27× dearer" (§7).
- **Computed:** $0.072 / $0.00268 = 26.9 (vs local CPU); $0.072 / $0.00314 = 22.9 (vs Gemini).
- **Severity:** minor.
- **Correction:** use about 27× vs local in both places. See also finding 2 on the gated baseline.

### 19. The c4 price *is* on the official page
- **Claim:** "$0.4151/h on-demand … (third-party table [S9]; the row was not found in the official page HTML)".
- **Source:** `cloud.google.com/products/compute/pricing/general-purpose`, downloaded 2026-10-08, contains `c4-standard-8 … $0.415107 / 1 hour`. The same page has other per-region tables, e.g. one with $0.39534/h.
- **Severity:** minor.
- **Correction:** cite the official page; the region mapping still comes from the third-party table [S9].

### 20. g2 EU availability is understated
- **Claim:** the g2-standard-4 row lists "europe-west4" in the availability column, although the same row quotes europe-west1 prices.
- **Source:** gcloud-compute.com/g2-standard-4.html (data 2026-10-04): europe-west1, europe-west3 and europe-west4 in the EU. europe-west1 costs $0.7783 on-demand and $0.4529 spot.
- **Severity:** minor.
- **Correction:** list europe-west1/3/4.

### 21. Script hygiene
- **Issue:**
  - `HAIKU_MOD_VIDEO_SHARE`, `CR_WP_CPU_S` and `CR_WP_MEM_S` are defined but never used.
  - The worker-pool figures in §2.1 ($144 and $661/month) are computed outside the script, so they are not reproducible from it. I re-derived them; both are correct.
  - `cost_at(..., stages=...)` has a dead parameter.
- **Severity:** minor.
- **Correction:** use or delete the unused constants, and print the worker-pool figures from the script.

### 22. The VAD speed figure is for a different version than Q2 recommends
- **Claim:** "`VAD_RTS_1THREAD` 165, Silero V5 ONNX".
- **Source:** Silero wiki (read 2026-10-08): V5 ONNX at 189 µs per 31.25 ms chunk, RTS 165, 1 thread, on a Threadripper 3960X. The wiki gives no V6 figure, but Q2 recommends Silero VAD v6.2.
- **Severity:** minor (VAD is 4% of the CPU time).
- **Correction:** note the version gap. Also note that 1-thread VAD leaves 3 of the 4 billed vCPUs idle unless it runs alongside frame work.

### 23. Hosted Haiku moderation and labels ignore the newer tokenizer and thinking
- **Claim:** the Haiku moderation and labels token counts come from Q4/Q5.
- **Source:** Q3 notes that Haiku 5.5 uses the newer tokenizer and thinks adaptively by default. Q4 includes 200 thinking tokens; Q5 includes none.
- **Severity:** minor (reference-only columns).
- **Correction:** state that the labels figure assumes thinking is disabled.

### 24. The GPU job's 25 s billed start-up is optimistic for a CUDA image
- **Claim:** `COLD_START_S_GPU` = 25 s.
- **Source:** the GPU services page says "approximately 5 seconds" for the instance with drivers. Image import and model loading are not covered. The best-practices page warns that "An image containing a large model will take longer to import".
- **Severity:** minor (at 60 s the 100k×5% job overhead rises from $5.31 to about $12.7).
- **Correction:** treat it as a sensitivity parameter in open question 2.

### 25. Q7's GitHub rejection of Expause backfills is a judgement, not a quoted rule
- **Claim:** Expause backfills are "not testing the project" under the ToS clause.
- **Source:** the GitHub Additional Products terms (effective 2026-08-27) prohibit "any other activity unrelated to the production, testing, deployment, or publication of the software project" on GitHub-hosted runners, plus "as part of a serverless application". The quote is correct.
- **Severity:** design concern (wording only; the conclusion holds on cost and data-location grounds alone).
- **Correction:** label it "(judgement)" and lead with the cost and data-location reasons.

---

## Verified correct (brief)

**Cloud Run pricing page** (downloaded 2026-10-08):
- Tier 1 includes europe-west1 and europe-west4; europe-west3 (Frankfurt) is Tier 2.
- Request-based prices are $0.000024 per vCPU-s, $0.0000025 per GiB-s and $0.40 per 1M requests, with a free tier of 180k vCPU-s, 360k GiB-s and 2M requests.
- Instance-based and jobs prices are $0.000018 and $0.000002, with a free tier of 240k vCPU-s and 450k GiB-s.
- The free tier is "aggregated across projects by billing account".
- Billing covers start-up, shutdown and requests in flight. "Idle instances that are not minimum instances are not charged".
- Instance-based billing and jobs have a minimum of 1 minute.
- L4 costs $0.0001867/s non-zonal and $0.0002909/s zonal; RTX PRO 6000 costs $0.00036522/s.
- Delayed Jobs costs $0.0000126 / $0.0000014, and the "dynamic … once every 30 days" wording is quoted correctly.
- Worker pools cost $0.000011244 / $0.000001235.
- Q7's computed rates and $/h are correct: $0.000116/s; $0.000291/s = $1.0465/h; worker pools $144 and $661/month.

**Billing settings page** (updated 2026-10-07):
- "Charged for the entire lifecycle of instances, even when there are no incoming requests."
- "Never stay idle for more than 15 minutes after processing a request."
- "Can be shut down at any time."
- So the 15-minute claim is an upper bound, as Q7 says.

**GPU services page** (2026-10-07):
- L4 is available in europe-west1 and europe-west4; RTX PRO 6000 in europe-west4 only; no other EU region has either.
- L4 needs at least 4 vCPU / 16 GiB (8 / 32 recommended). RTX PRO 6000 needs 20 / 80.
- Start-up takes about 5 s, and services scale to zero.
- Instance-based billing is required.
- The default quota is 3 GPUs, non-zonal.
- The driver is 580 / CUDA 13.0.
- No launch stage is stated.

**GPU jobs page** (2026-10-07): non-zonal only, no launch stage stated, quota as above.

**GPU worker pools page:** "cannot be autoscaled"; no launch stage stated.

**Quotas page** (2026-10-07): 8 vCPU / 32 GiB; 60 min request timeout; job task timeout 168 h, or 1 h with GPUs; "no direct limit" on image size.

**GPU best-practices page** (2026-10-07):
- "best suited for smaller models less than 10 GB".
- The Cloud Storage download path needs Direct VPC with all-traffic egress plus Private Google Access.
- FUSE `cache-dir` and `enable-buffered-read`.
- Internet download carries a "reliability risk".

**Compute Engine:**
- g2-standard-4 costs $0.742916046/h and $0.445676/h spot; $0.778293004/h appears in the official HTML; europe-west4 and europe-west1 are mapped via gcloud-compute.com.
- e2-standard-4 costs $0.1475/h (europe-west4).
- The monthly totals of $542.33, $325.34 and $107.67 are correct.

**GitHub:**
- Runner prices: Linux 2-core $0.006/min, 4-core $0.012, 8-core $0.022, 4-core GPU $0.052.
- The GPU runner is a Tesla T4 with 16 GB VRAM, 4 vCPU and 28 GB RAM.
- Included minutes: 2,000 / 3,000 / 3,000 / 50,000.
- Limits: 6 h per job, 5 days self-hosted, 35 days per workflow.
- The ToS quotes and the 2026-08-27 effective date are correct.
- $3.12/h is about 3× $1.05/h.

**Anthropic pricing:** Haiku 5.5 costs $0.10 / $0.50 per MTok for prompts of 100k tokens or fewer.

**Gemini pricing:**
- 2.5 Flash-Lite costs $0.30 per M audio-in tokens and $0.40 per M out.
- Audio is "32 tokens per second" (audio page, updated 2026-09-23).

**Speech-to-Text pricing:** V2 standard costs $0.016/min from 0 to 500k min; dynamic batch costs $0.003/min; billing is rounded up per 1 s.

**Speed inputs match their sources:**
- Q2: 36.8 / 30.5 CPU, 57.6 T4 CUDA (TensorRT fp16 237).
- Q5: SigLIP 2 B/16 at 66 ms on M4 with 4 threads.
- Q4: Freepik at 28 ms on an RTX 3090.
- Q3: token counts (2,450 / 300 per speech video = Scenario A ÷ 12) and the llama.cpp proxies. The CPU 30 / 8 and L4 3,000 / 70 tok/s figures are reasonable extrapolations. L4 memory bandwidth (about 300 GB/s) is similar to the T4's, so 70 tok/s for a 4B Q4 model is, if anything, conservative.

**Q1:** a 10 s preview interval for videos of 5 min or less gives 30 frames.

**Arithmetic re-derived** (all correct):
- Per-stage CPU seconds: 23.1 / 94.5 / 36.0 / 4.0.
- L4 seconds: 4.71 / 4.07 / 1.50 / 0.15.
- Haiku summary $0.000313; Haiku moderation $0.00209; Haiku labels $0.00037; Gemini 2.5 Flash-Lite $0.00314.
- Worked example: λ = 7.42e-5, p_cold = 0.935, overhead $0.211, L4 idle tail 870 s ≈ $33.
- Job floor: 730 × 60 s × $0.000291 = $12.73.
- Recommended totals: $1.20 to $165.17. L4 job + Haiku at 100k×5%: $52.09.
- Crossovers: 132 h; e2 bands 1,230–1,725 h etc.; consistent with the grid.
