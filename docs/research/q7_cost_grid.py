"""Q7 cost grid for scenewise: monthly AI processing cost per stage and runtime.

Stdlib only. Run:  python3 -I docs/research/q7_cost_grid.py
Every input is a named constant below so the grid can be recomputed.
Prices: USD, EU (Cloud Run Tier 1 europe-west1 / europe-west4; Vertex AI EU
multi-region / non-global), read 2026-10-08.
Each speed constant is tagged MEASURED (a number someone measured, possibly on
other hardware) or GUESS (this author's estimate). See q7-runtime-cost.md.
Revision: review rounds 1 and 2 (reviews/q7-review-r1.md, reviews/q7-review-r2.md).
"""

import math

# --------------------------------------------------------------------------
# Volume parameters
# --------------------------------------------------------------------------
MAU_VALUES = (1_000, 10_000, 100_000)
POSTING_RATES = (0.03, 0.05)          # share of MAU who post in a given week
VIDEOS_PER_POSTER_PER_MONTH = 4.33    # 1 per week
AVG_VIDEO_MIN = 5.0
ACTIVE_HOURS_PER_DAY = 16             # uploads spread over 16 h/day (GUESS)
DAYS_PER_MONTH = 30.4
HOURS_PER_MONTH = 730

# --------------------------------------------------------------------------
# Content parameters (all GUESS; Expause data needed)
# --------------------------------------------------------------------------
AUDIO_VIDEO_SHARE = 0.90       # videos that have an audio stream
SPEECH_VIDEO_SHARE = 0.60      # videos where VAD finds speech (subset of audio)
SPEECH_FRACTION = 0.70         # share of a speech video's duration that is speech
FRAME_INTERVAL_S = 10.0        # Expause previewsIntervalSeconds for 1-5 min videos (q1)
ESCALATED_FRAME_SHARE = 0.02   # frames sent to the tier-2 guard model

# Summary tokens per video (q3 scenario A: 29,400 in / 3,600 out per hour = 12 videos)
SUM_IN_TOK_SPEECH = 2_450
SUM_OUT_TOK_SPEECH = 300
SUM_IN_TOK_NOSPEECH = 1_160    # 800 prompt + 30 label lines x 12 tok (GUESS)
SUM_OUT_TOK_NOSPEECH = 150     # (GUESS)

# --------------------------------------------------------------------------
# Prices (USD)
# --------------------------------------------------------------------------
# Cloud Run, Tier 1 (europe-west1/west4), cloud.google.com/run/pricing
CR_REQ_CPU_S = 0.000024        # request-based service, per vCPU-second
CR_REQ_MEM_S = 0.0000025       # request-based service, per GiB-second
CR_REQ_PER_M = 0.40            # per 1M requests
CR_INST_CPU_S = 0.000018       # instance-based service / jobs, per vCPU-second
CR_INST_MEM_S = 0.000002       # instance-based service / jobs, per GiB-second
CR_DELAYED_CPU_S = 0.0000126   # Delayed Jobs (Preview; price dynamic, may change every 30 days)
CR_DELAYED_MEM_S = 0.0000014
CR_L4_S = 0.0001867            # L4, no zonal redundancy, per second
CR_WP_CPU_S = 0.000011244      # worker pools, per vCPU-second
CR_WP_MEM_S = 0.000001235      # worker pools, per GiB-second

APPLY_FREE_TIER = False        # main grid: off (per billing account; Expause likely uses it)
FREE_REQ_CPU_S, FREE_REQ_MEM_S = 180_000, 360_000          # request-based
FREE_INST_CPU_S, FREE_INST_MEM_S = 240_000, 450_000        # instance-based and jobs
FREE_DELAYED_CPU_S, FREE_DELAYED_MEM_S = 342_857, 642_857  # Delayed Jobs (us-central1 basis)

# Compute Engine (official pricing pages; spot is dynamic)
VM_E2_STD4_H = 0.1475          # e2-standard-4 (4 vCPU, 16 GB), europe-west4
VM_G2_STD4_H = 0.742916046     # g2-standard-4 (1x L4) on-demand, europe-west4
VM_G2_STD4_SPOT_H = 0.445676   # g2-standard-4 spot, europe-west4
VM_MAX_UTIL = 0.5              # plan VMs at <=50% busy to absorb peaks (GUESS)

# Claude Haiku 5.5, prompts <=100k tokens. Standard and Batch (50% off).
HAIKU_IN_PER_M = 0.10
HAIKU_OUT_PER_M = 0.50
HAIKU_BATCH_FACTOR = 0.5
# Endpoint choice (user decision, see doc section 2.3):
#   1.10 = Vertex AI EU multi-region endpoint (+10%, inference in the EU)
#   1.00 = Anthropic first-party API, inference_geo "global" (no EU option)
HAIKU_PRICE_MULT = 1.10
HAIKU_FIRSTPARTY_MULT = 1.00

# Gemini on Vertex AI, non-global (regional / EU multi-region) prices, per 1M tokens.
# 2.5 Flash-Lite retires on Vertex 2026-10-20 (q4), so it is no longer priced.
GEM31_AUDIO_IN_PER_M = 0.55    # 3.1 Flash-Lite audio in (global $0.50)
GEM31_OUT_PER_M = 1.65         # (global $1.50)
GEM35_AUDIO_IN_PER_M = 0.33    # 3.5 Flash-Lite in, any modality (global $0.30)
GEM35_OUT_PER_M = 2.75         # (global $2.50)
GEM_AUDIO_TOK_PER_S = 32       # documented generically on the Gemini audio page
GEM_CAPTION_OUT_TOK_PER_MIN = 260   # ~200 words + timestamps per speech minute (GUESS)
GEM_PROMPT_TOK = 300                # (GUESS)

# Google Speech-to-Text V2, standard models
STT_V2_PER_MIN = 0.016         # standard recognition, first 500k min/month
STT_V2_DYN_BATCH_PER_MIN = 0.003  # dynamic batch ("lower level of urgency")

# Synchronous waits billed on the calling runtime (all GUESS)
HAIKU_WAIT_S = 3.0             # one summary call, ~2.5k in / 300 out
GEMINI_CAPTION_WAIT_S = 6.0    # one ~3.5 min speech-audio caption call
STT_WAIT_S = 10.0              # standard recognition of ~3.5 min speech audio
HAIKU_JOB_PARALLEL = 8         # concurrent Haiku calls inside a batch job

# --------------------------------------------------------------------------
# Runtime shapes
# --------------------------------------------------------------------------
CPU_VCPU = 4
CPU_GIB = 16                   # safety default until measured; see doc section 3 (memory)
CPU_GIB_SMALL = 8              # sensitivity row: q2 measured the whole audio stack at 1.33 GB peak RSS
GPU_VCPU = 4                   # L4 minimum on Cloud Run
GPU_GIB = 16
MAX_JOBS_CPU = 1               # q8a: one job per CPU instance; concurrency = max_jobs

# --------------------------------------------------------------------------
# Speed parameters
# --------------------------------------------------------------------------
CPU_SPEED_FACTOR = 1.0         # sensitivity knob: 2.0 = every CPU step twice as fast
CLOUD_SLOWDOWN_VS_M4 = 2.5     # 4 Cloud Run vCPU vs 4 M4 P-core threads (GUESS)

# Captions
PARAKEET_M4_RTFX_4T = 32.3     # MEASURED: sherpa-onnx int8, 12.6 s clip, 4 threads, M4 (q2 L1)
PARAKEET_9800X3D_INT8_RTFX = 30.5  # MEASURED (onnx-asr page), thread count not stated; cross-check only
PARAKEET_GPU_RTFX = 57.6       # MEASURED: onnx-asr CUDA on a T4 (q2 S9); used as L4 lower bound
VAD_RTS_1THREAD = 165          # MEASURED: Silero V5 ONNX, 1 thread, Threadripper 3960X (q2 uses v6.2)
VAD_CLOUD_EFFICIENCY = 0.7     # one cloud vCPU thread vs that desktop thread (GUESS)
LID_WINDOW_S = 30              # q2: LID windows of 3-30 s over VAD speech
LID_S_PER_WINDOW_M4 = 0.65     # MEASURED: faster-whisper tiny int8, 0.4-0.9 s per clip on M4 (q2 L1)
# LID (CTranslate2) runs on CPU in GPU images too (q8a section 9.5).

# Vision
SIGLIP_INFER_MS_M4 = 37        # MEASURED: SigLIP 2 B/16 image tower, M4, 4 threads, median at batch 16 (q5 section 3)
SIGLIP_PREPROC_MS_M4 = 5.4     # MEASURED: preprocessing, 3-6 ms per image (q5 section 3)
JPEG_DECODE_MS_M4 = 3.5        # MEASURED: 720x1280 q60 JPEG decode (q5 section 3)
SIGLIP_MS_M4 = SIGLIP_INFER_MS_M4 + SIGLIP_PREPROC_MS_M4 + JPEG_DECODE_MS_M4   # 45.9 ms, as q5 section 5b
FREEPIK_MS_M4 = 400            # GUESS: EVA-02 B @448 ~6x the tokens of B/16 @224
GUARD_S_PER_FRAME_CPU = 20.0   # GUESS: 3-4B guard VLM on 4 vCPU
SIGLIP_MS_GPU = 5              # GUESS
FREEPIK_MS_GPU = 40            # GUESS from 28 ms MEASURED on an RTX 3090 bs1 (q4 S10)
GUARD_S_PER_FRAME_GPU = 0.5    # GUESS

# Shared work on the instance's CPU (both device types)
DECODE_S_CPU = 4.0             # GUESS: ffmpeg audio extract (~1 s) + 30 frame seeks (~3 s)
TEXT_EMBED_S_CPU = 0.5         # GUESS: multilingual-e5-small on one transcript (q5), speech videos
TEXT_EMBED_S_GPU = 0.05        # GUESS

# Local LLM summaries, Qwen3.5-4B Q4 (GUESS, scaled from q3 llama.cpp proxies)
LLM_CPU_PREFILL_TPS = 30       # 4 vCPU
LLM_CPU_GEN_TPS = 8
LLM_GPU_PREFILL_TPS = 3_000    # L4
LLM_GPU_GEN_TPS = 70

# Stage parallelism (review r2 #8): run the audio branch (VAD -> LID -> ASR) and the frame
# branch (Freepik, SigLIP, guard) concurrently in one job. Share of the shorter branch hidden
# behind the longer one. 0 = strictly serial (q8a v1: one worker thread per job). Unmeasured.
BRANCH_OVERLAP_HIDE = 0.0      # main grid
BRANCH_OVERLAP_HIDE_SENS = 0.5 # sensitivity row (GUESS)

# Cold start (CPU derived from q5's load measurement, review r2 #7)
CPU_IMAGE_START_S = 10         # GUESS: pull/import a 3-5 GB image + container start
SIGLIP_LOAD_S_M4 = 5.9         # MEASURED: ~1 s import + ~4.9 s model load, SigLIP 2 B/16, M4 (q5 section 3)
OTHER_MODELS_LOAD_S_M4 = 4.0   # GUESS: Parakeet int8, Silero, tiny, Freepik, e5-small (guard loaded lazily)
COLD_START_S_CPU = round(CPU_IMAGE_START_S + (SIGLIP_LOAD_S_M4 + OTHER_MODELS_LOAD_S_M4) * CLOUD_SLOWDOWN_VS_M4)
COLD_START_S_CPU_SENS = 60     # sensitivity row
COLD_START_S_GPU = 25          # GUESS: ~5 s driver (CR GPU docs) + image import + model load
COLD_START_S_GPU_SENS = 60     # sensitivity row
IDLE_WINDOW_S = 900            # CPU: idle instances kept "up to 15 minutes" (autoscaling page; upper bound)
IDLE_WINDOW_S_GPU = 600        # GPU: "or 10 minutes for GPUs" (same page; upper bound)
JOB_MIN_BILLED_S = 60          # jobs / instance-based: minimum 1 minute
GPU_TASK_MAX_S = 3600          # job task timeout with GPU: 1 h
CPU_HOURLY_TASK_MAX_S = 3600   # latency target: an hourly CPU run must finish within its hour,
                               # so work is sharded across parallel tasks above 1 h
HOURLY_INTERVAL_S = 3600
DELAYED_RUNS_PER_DAY = 2       # minimum Delayed Job runs per day (GUESS); raised when work exceeds the cap
DELAYED_EXEC_MAX_S = 12 * 3600 # "total runtime duration of all tasks in a delayed job execution is 12 hours"
DELAYED_CAP_MARGIN = 0.75      # plan each execution at <=75% of the cap (variance in daily volume; GUESS)
DELAYED_PROVISION_MAX_S = 12 * 3600   # "provisioning ... potentially up to 12 hours"
BATCH_RESULT_MAX_S = 24 * 3600 # Vertex Claude batch: results "after 24 hours" at most
BATCH_COLLECT_POLL_S = 3600    # separate light trigger that collects batch results (GUESS)

STAGES = ("captions", "summaries", "moderation", "labels", "shared")
LOCAL3 = ("captions", "moderation", "labels", "shared")   # stages local in the Haiku mixes


# --------------------------------------------------------------------------
# Rates
# --------------------------------------------------------------------------
def rate(kind, gib=None):
    gib = CPU_GIB if gib is None else gib
    if kind == "req":
        return CPU_VCPU * CR_REQ_CPU_S + gib * CR_REQ_MEM_S
    if kind == "job":
        return CPU_VCPU * CR_INST_CPU_S + gib * CR_INST_MEM_S
    if kind == "delayed":
        return CPU_VCPU * CR_DELAYED_CPU_S + gib * CR_DELAYED_MEM_S
    if kind == "gpu":
        return CR_L4_S + GPU_VCPU * CR_INST_CPU_S + GPU_GIB * CR_INST_MEM_S
    raise ValueError(kind)


def free_credit(kind, billed_s, gib=None):
    """Free-tier credit for `billed_s` instance-seconds of one config (CPU and memory only)."""
    gib = CPU_GIB if gib is None else gib
    if kind == "req":
        fc, fm, pc, pm, v, g = FREE_REQ_CPU_S, FREE_REQ_MEM_S, CR_REQ_CPU_S, CR_REQ_MEM_S, CPU_VCPU, gib
    elif kind == "job":
        fc, fm, pc, pm, v, g = FREE_INST_CPU_S, FREE_INST_MEM_S, CR_INST_CPU_S, CR_INST_MEM_S, CPU_VCPU, gib
    elif kind == "delayed":
        fc, fm, pc, pm, v, g = FREE_DELAYED_CPU_S, FREE_DELAYED_MEM_S, CR_DELAYED_CPU_S, CR_DELAYED_MEM_S, CPU_VCPU, gib
    elif kind == "gpu":    # GPU seconds have no free tier; CPU/memory use the instance tier
        fc, fm, pc, pm, v, g = FREE_INST_CPU_S, FREE_INST_MEM_S, CR_INST_CPU_S, CR_INST_MEM_S, GPU_VCPU, GPU_GIB
    else:
        return 0.0
    return min(billed_s * v, fc) * pc + min(billed_s * g, fm) * pm


# --------------------------------------------------------------------------
# Work per video
# --------------------------------------------------------------------------
def frames_per_video():
    return math.floor(AVG_VIDEO_MIN * 60 / FRAME_INTERVAL_S)


def speech_seconds():
    return AVG_VIDEO_MIN * 60 * SPEECH_FRACTION


def lid_windows():
    return math.ceil(speech_seconds() / LID_WINDOW_S)


def cpu_rtfx(f=None):
    f = CPU_SPEED_FACTOR if f is None else f
    return PARAKEET_M4_RTFX_4T / CLOUD_SLOWDOWN_VS_M4 * f


def vad_seconds(f):
    return AUDIO_VIDEO_SHARE * AVG_VIDEO_MIN * 60 / (VAD_RTS_1THREAD * VAD_CLOUD_EFFICIENCY * f)


def work_seconds(device, f=None, overlap=None):
    """Billed wall seconds per average video, per stage, on one instance of `device`.
    `overlap` = share of the shorter of (audio branch, frame branch) hidden behind the longer."""
    f = CPU_SPEED_FACTOR if f is None else f
    overlap = BRANCH_OVERLAP_HIDE if overlap is None else overlap
    n = frames_per_video()
    sp = speech_seconds()
    slow = CLOUD_SLOWDOWN_VS_M4 / f
    lid = lid_windows() * LID_S_PER_WINDOW_M4 * slow        # CPU on both devices
    if device == "cpu":
        asr = sp / cpu_rtfx(f)
        siglip = SIGLIP_MS_M4 * slow / 1000
        freepik = FREEPIK_MS_M4 * slow / 1000
        guard = GUARD_S_PER_FRAME_CPU / f
        pre, gen = LLM_CPU_PREFILL_TPS * f, LLM_CPU_GEN_TPS * f
        embed = TEXT_EMBED_S_CPU / f
    else:
        asr = sp / PARAKEET_GPU_RTFX
        siglip, freepik = SIGLIP_MS_GPU / 1000, FREEPIK_MS_GPU / 1000
        guard = GUARD_S_PER_FRAME_GPU
        pre, gen = LLM_GPU_PREFILL_TPS, LLM_GPU_GEN_TPS
        embed = TEXT_EMBED_S_GPU
    parts = {
        "vad": vad_seconds(f),
        "lid": SPEECH_VIDEO_SHARE * lid,
        "asr": SPEECH_VIDEO_SHARE * asr,
        "freepik": n * freepik,
        "guard": n * ESCALATED_FRAME_SHARE * guard,
        "siglip": n * siglip,                               # shared by labels and moderation
        "decode": DECODE_S_CPU / f,
        "embed": SPEECH_VIDEO_SHARE * embed,
        "llm": (SPEECH_VIDEO_SHARE * (SUM_IN_TOK_SPEECH / pre + SUM_OUT_TOK_SPEECH / gen)
                + (1 - SPEECH_VIDEO_SHARE) * (SUM_IN_TOK_NOSPEECH / pre + SUM_OUT_TOK_NOSPEECH / gen)),
    }
    stages = {
        "captions": parts["vad"] + parts["lid"] + parts["asr"],
        "summaries": parts["llm"],
        "moderation": parts["freepik"] + parts["guard"],
        "labels": parts["siglip"],
        "shared": parts["decode"] + parts["embed"],
    }
    if overlap > 0:
        # Wall time saved by running the two branches concurrently; booked against the
        # shorter branch's stage(s) so per-stage rows stay non-negative.
        audio = stages["captions"]
        frame = stages["moderation"] + stages["labels"]
        saved = overlap * min(audio, frame)
        if audio <= frame:
            stages["captions"] -= saved
        else:
            for s in ("moderation", "labels"):
                stages[s] -= saved * stages[s] / frame
    return stages, parts


# --------------------------------------------------------------------------
# Hosted API fees per video
# --------------------------------------------------------------------------
def haiku_cost(tin, tout, mult=None, batch=False):
    mult = HAIKU_PRICE_MULT if mult is None else mult
    b = HAIKU_BATCH_FACTOR if batch else 1.0
    return (tin * HAIKU_IN_PER_M + tout * HAIKU_OUT_PER_M) / 1e6 * mult * b


def haiku_summary_fee(mult=None, batch=False):
    return (SPEECH_VIDEO_SHARE * haiku_cost(SUM_IN_TOK_SPEECH, SUM_OUT_TOK_SPEECH, mult, batch)
            + (1 - SPEECH_VIDEO_SHARE) * haiku_cost(SUM_IN_TOK_NOSPEECH, SUM_OUT_TOK_NOSPEECH, mult, batch))


def gemini_fee(in_per_m, out_per_m):
    """One speech video's speech audio (after the local VAD gate) captioned by Gemini."""
    sp = speech_seconds()
    return ((sp * GEM_AUDIO_TOK_PER_S + GEM_PROMPT_TOK) * in_per_m
            + sp / 60 * GEM_CAPTION_OUT_TOK_PER_MIN * out_per_m) / 1e6


def hosted_caption_options(f=None, gib=None):
    """Per-video captions cost, gated exactly like the local path (VAD on audio videos,
    API only on speech videos and only on speech seconds), billed on Cloud Run CPU."""
    f = CPU_SPEED_FACTOR if f is None else f
    r = rate("req", gib)
    gate = vad_seconds(f) * r
    sp_min = speech_seconds() / 60
    s = SPEECH_VIDEO_SHARE
    return {
        "Gemini 3.1 Flash-Lite (Vertex EU)": gate + s * (gemini_fee(GEM31_AUDIO_IN_PER_M, GEM31_OUT_PER_M) + GEMINI_CAPTION_WAIT_S * r),
        "Gemini 3.5 Flash-Lite (Vertex EU)": gate + s * (gemini_fee(GEM35_AUDIO_IN_PER_M, GEM35_OUT_PER_M) + GEMINI_CAPTION_WAIT_S * r),
        "STT V2 standard": gate + s * (sp_min * STT_V2_PER_MIN + STT_WAIT_S * r),
        "STT V2 dynamic batch (async only)": gate + s * sp_min * STT_V2_DYN_BATCH_PER_MIN,
    }


def hosted_reference_fees():
    n = frames_per_video()
    return {
        # q4: 432x768 frames = 448 tokens each, ~500 prompt, 40 out/frame + 200 thinking
        "moderation": haiku_cost(n * 448 + 500, n * 40 + 200),
        # q5: 1600x900 sprite = 58*33 tokens + 1k prompt, 150 out, thinking disabled
        "labels": haiku_cost(58 * 33 + 1000, 150),
    }


# --------------------------------------------------------------------------
# Grid
# --------------------------------------------------------------------------
def arrival_rate_per_s(videos):
    return videos / (DAYS_PER_MONTH * ACTIVE_HOURS_PER_DAY * 3600)


def nonempty_slots(videos, slots):
    """Expected number of non-empty batch slots when `videos` arrive at random (skip-if-empty)."""
    return slots * (1 - math.exp(-videos / slots)) if videos > 0 else 0.0


def batch_plan(videos, per_video_s, slots, cold_s, task_max_s=None):
    """Batch job per non-empty slot: parallel tasks needed to keep each task under `task_max_s`,
    billed overhead beyond the work (cold start per task, 60 s minimum), and run wall time."""
    n = nonempty_slots(videos, slots)
    if n == 0:
        return {"overhead_s": 0.0, "slots": 0.0, "tasks": 0, "work_s": 0.0, "wall_s": 0.0}
    work = videos * per_video_s / n
    tasks = math.ceil((cold_s + work) / task_max_s) if task_max_s else 1
    while task_max_s and cold_s + work / tasks > task_max_s:   # cold start repeats per task
        tasks += 1
    billed = max(JOB_MIN_BILLED_S * tasks, cold_s * tasks + work)
    return {"overhead_s": n * (billed - work), "slots": n, "tasks": tasks, "work_s": work,
            "wall_s": cold_s + work / tasks}


def delayed_runs_per_day(videos, per_video_s, cold_s):
    """Delayed Job runs per day: at least DELAYED_RUNS_PER_DAY, more when one execution's total
    task runtime would exceed DELAYED_EXEC_MAX_S x DELAYED_CAP_MARGIN (one task per execution,
    because the cap counts the runtime of all tasks, so sharding does not help)."""
    work_day = videos / DAYS_PER_MONTH * per_video_s
    runs = DELAYED_RUNS_PER_DAY
    while cold_s + work_day / runs > DELAYED_EXEC_MAX_S * DELAYED_CAP_MARGIN:
        runs += 1
    return runs


def grid_cell(videos, f=None, gpu_cold=None, haiku_mult=None, cpu_cold=None, gib=None, overlap=None):
    f = CPU_SPEED_FACTOR if f is None else f
    gpu_cold = COLD_START_S_GPU if gpu_cold is None else gpu_cold
    cpu_cold = COLD_START_S_CPU if cpu_cold is None else cpu_cold
    gib = CPU_GIB if gib is None else gib
    ws_cpu, _ = work_seconds("cpu", f, overlap)
    ws_gpu, _ = work_seconds("gpu", f, overlap)
    lam = arrival_rate_per_s(videos)
    p_cold = math.exp(-lam * IDLE_WINDOW_S)
    p_cold_gpu = math.exp(-lam * IDLE_WINDOW_S_GPU)
    hourly_slots = ACTIVE_HOURS_PER_DAY * DAYS_PER_MONTH
    sum_fee = haiku_summary_fee(haiku_mult)
    sum_fee_batch = haiku_summary_fee(haiku_mult, batch=True)
    out = {}
    plans = {}

    def config(kind, ws, stages_local, summary, extra_wait_s, overhead_s, overhead_usd=0.0):
        r = rate(kind, gib)
        c = {s: videos * ws[s] * r for s in stages_local}
        for s in STAGES:
            c.setdefault(s, 0.0)
        if summary is not None:
            c["summaries"] = videos * (summary + extra_wait_s * r)
        c["overhead"] = overhead_s * r + overhead_usd
        busy = videos * (sum(ws[s] for s in stages_local) + extra_wait_s)
        c["billed_s"] = busy + overhead_s
        c["kind"] = kind
        return c

    req_fee = videos * CR_REQ_PER_M / 1e6
    cold_cpu = videos * p_cold * cpu_cold

    # A. Cloud Run CPU service, request-based, all local (incl. local LLM)
    out["cr_cpu"] = config("req", ws_cpu, STAGES, None, 0.0, cold_cpu, req_fee)
    # B. Cloud Run L4 service, instance-based, all local: idle tail E[min(gap, W)] billed
    idle = (1 - math.exp(-lam * IDLE_WINDOW_S_GPU)) / lam if lam > 0 else 0
    out["cr_gpu"] = config("gpu", ws_gpu, STAGES, None, 0.0, videos * (p_cold_gpu * gpu_cold + idle))
    # C. L4 hourly job, all local
    p = batch_plan(videos, sum(ws_gpu.values()), hourly_slots, gpu_cold, GPU_TASK_MAX_S)
    out["gpu_job"] = config("gpu", ws_gpu, STAGES, None, 0.0, p["overhead_s"])
    # D. Hosted reference: gated Gemini 3.1 FL captions, Haiku summaries/moderation/labels,
    #    decode on Cloud Run CPU; synchronous waits billed for captions and summaries.
    r_req = rate("req", gib)
    hc = hosted_caption_options(f, gib)["Gemini 3.1 Flash-Lite (Vertex EU)"]
    hr = hosted_reference_fees()
    mult = HAIKU_PRICE_MULT if haiku_mult is None else haiku_mult
    h = {"captions": videos * hc,
         "summaries": videos * (sum_fee + HAIKU_WAIT_S * r_req),
         "moderation": videos * hr["moderation"] / HAIKU_PRICE_MULT * mult,
         "labels": videos * hr["labels"] / HAIKU_PRICE_MULT * mult,
         "shared": videos * ws_cpu["shared"] * r_req,
         "overhead": req_fee, "kind": "req",
         # Cloud Run request-based seconds it bills: VAD gate, Gemini and Haiku waits, decode
         "billed_s": videos * (vad_seconds(f) + SPEECH_VIDEO_SHARE * GEMINI_CAPTION_WAIT_S
                               + HAIKU_WAIT_S + ws_cpu["shared"])}
    out["hosted"] = h
    # E. Always-on VMs, all local, allocated across stages by busy-time share
    for key, hourly, ws in (("vm_e2", VM_E2_STD4_H, ws_cpu),
                            ("vm_g2", VM_G2_STD4_H, ws_gpu),
                            ("vm_g2_spot", VM_G2_STD4_SPOT_H, ws_gpu)):
        out[key] = vm_config(videos, hourly, ws, STAGES, None)
    # F. Haiku mixes (local captions / moderation / labels / shared)
    # F1. Recommended: Cloud Run CPU service + synchronous Haiku (wait billed)
    out["rec"] = config("req", ws_cpu, LOCAL3, sum_fee, HAIKU_WAIT_S, cold_cpu, req_fee)
    # F2. e2 VM + Haiku (the wait overlaps other work on a VM; not billed extra)
    out["vm_e2_haiku"] = vm_config(videos, VM_E2_STD4_H, ws_cpu, LOCAL3, sum_fee)
    # F3. Cloud Run CPU hourly job + Haiku (parallel sync calls); sharded to finish within the hour
    jw = HAIKU_WAIT_S / HAIKU_JOB_PARALLEL
    p = batch_plan(videos, sum(ws_cpu[s] for s in LOCAL3) + jw, hourly_slots, cpu_cold, CPU_HOURLY_TASK_MAX_S)
    plans["cpu_job_haiku"] = p
    out["cpu_job_haiku"] = config("job", ws_cpu, LOCAL3, sum_fee, jw, p["overhead_s"])
    # F4. L4 hourly job + Haiku (parallel sync calls)
    p = batch_plan(videos, sum(ws_gpu[s] for s in LOCAL3) + jw, hourly_slots, gpu_cold, GPU_TASK_MAX_S)
    plans["gpu_job_haiku"] = p
    out["gpu_job_haiku"] = config("gpu", ws_gpu, LOCAL3, sum_fee, jw, p["overhead_s"])
    # F5. Cloud Run CPU Delayed Job + Haiku Batch (Vertex batch prediction; no wait billed).
    #     Runs per day raised so that one execution stays under the 12 h cap.
    per_v = sum(ws_cpu[s] for s in LOCAL3)
    runs = delayed_runs_per_day(videos, per_v, cpu_cold)
    p = batch_plan(videos, per_v, runs * DAYS_PER_MONTH, cpu_cold)
    p["runs_per_day"] = runs
    plans["delayed_batch"] = p
    out["delayed_batch"] = config("delayed", ws_cpu, LOCAL3, sum_fee_batch, 0.0, p["overhead_s"])
    # F5b (printed only): same Delayed Job with parallel synchronous Haiku instead of Batch
    runs_s = delayed_runs_per_day(videos, per_v + jw, cpu_cold)
    p = batch_plan(videos, per_v + jw, runs_s * DAYS_PER_MONTH, cpu_cold)
    p["runs_per_day"] = runs_s
    plans["delayed_sync"] = p
    out["delayed_sync"] = config("delayed", ws_cpu, LOCAL3, sum_fee, jw, p["overhead_s"])

    for c in out.values():
        c["free_credit"] = free_credit(c["kind"], c["billed_s"], gib)
    out["_plans"] = plans
    return out


def worst_latency_h(key, plan):
    """Worst-case hours from upload to all results, for the batch columns."""
    if key in ("cpu_job_haiku", "gpu_job_haiku"):
        return (HOURLY_INTERVAL_S + plan["wall_s"]) / 3600
    interval = 24 * 3600 / plan["runs_per_day"]
    base = interval + DELAYED_PROVISION_MAX_S + plan["wall_s"]
    if key == "delayed_batch":
        base += BATCH_RESULT_MAX_S + BATCH_COLLECT_POLL_S
    return base / 3600


def vm_config(videos, hourly, ws, stages_local, summary):
    busy_h = sum(videos * ws[s] for s in stages_local) / 3600
    n_vm = max(1, math.ceil(busy_h / (HOURS_PER_MONTH * VM_MAX_UTIL)))
    total = n_vm * hourly * HOURS_PER_MONTH
    tws = sum(ws[s] for s in stages_local)
    c = {s: total * ws[s] / tws for s in stages_local}
    for s in STAGES:
        c.setdefault(s, 0.0)
    if summary is not None:
        c["summaries"] = videos * summary
    c.update(overhead=0.0, n_vm=n_vm, billed_s=0.0, kind="vm")
    return c


def total(c, free=None):
    free = APPLY_FREE_TIER if free is None else free
    t = sum(c[s] for s in STAGES) + c["overhead"]
    if free:
        t -= c["free_credit"]
    return max(0.0, t)


COLS = (("cr_cpu", "CR CPU, all local"), ("cr_gpu", "CR L4 service, all local"),
        ("gpu_job", "L4 hourly job, all local"), ("hosted", "Hosted reference"),
        ("vm_e2", "e2 VM, all local"), ("vm_g2", "g2 VM, all local"), ("vm_g2_spot", "g2 spot VM, all local"),
        ("rec", "**CR CPU + Haiku (rec.)**"), ("vm_e2_haiku", "e2 VM + Haiku"),
        ("cpu_job_haiku", "CPU hourly job + Haiku"), ("gpu_job_haiku", "L4 hourly job + Haiku"),
        ("delayed_batch", "CPU Delayed Job + Haiku Batch"))
KEY_COLS = ("rec", "cpu_job_haiku", "gpu_job_haiku", "delayed_batch", "vm_e2_haiku", "hosted")
LABEL = dict(COLS)


def fmt(x):
    return f"${x:,.2f}" if x >= 0.995 else f"${x:,.3f}"


def cells():
    for mau in MAU_VALUES:
        for r in POSTING_RATES:
            yield mau, r, mau * r * VIDEOS_PER_POSTER_PER_MONTH


def crossover(k1, k2, f=None, lo=1.0, hi=20_000.0):
    """Video-hour ranges (scanned 1-20,000 h) where config k2 is cheaper than k1."""
    ranges, start, vh, prev = [], None, lo, lo
    while vh <= hi:
        c = grid_cell(vh * 60 / AVG_VIDEO_MIN, f)
        cheaper = total(c[k2]) < total(c[k1])
        if cheaper and start is None:
            start = vh
        if not cheaper and start is not None:
            ranges.append((start, prev))
            start = None
        prev, vh = vh, vh * 1.01
    if start is not None:
        ranges.append((start, None))
    if not ranges:
        return "never in 1-20,000 h"
    return ", ".join(f"{a:,.0f}-{b:,.0f} h" if b else f">= {a:,.0f} h" for a, b in ranges)


def main():
    ws_cpu, parts_cpu = work_seconds("cpu")
    ws_gpu, _ = work_seconds("gpu")
    r_req, r_job, r_del, r_gpu = rate("req"), rate("job"), rate("delayed"), rate("gpu")
    ft = "free tier on" if APPLY_FREE_TIER else "free tier off"

    print("### Derived per-video figures\n")
    print(f"- Frames per video: {frames_per_video()} (interval {FRAME_INTERVAL_S:g} s); "
          f"speech per speech video: {speech_seconds():.0f} s in {lid_windows()} LID windows")
    print(f"- Parakeet RTFx on {CPU_VCPU} vCPU: {cpu_rtfx():.1f} (M4 measured {PARAKEET_M4_RTFX_4T} / slowdown "
          f"{CLOUD_SLOWDOWN_VS_M4}); cross-check from 9800X3D int8 {PARAKEET_9800X3D_INT8_RTFX}: "
          f"{PARAKEET_9800X3D_INT8_RTFX * 4 / 16 * 0.7:.1f} (16-thread guess) to "
          f"{PARAKEET_9800X3D_INT8_RTFX * 4 / 8 * 0.7:.1f} (8-thread guess)")
    print(f"- SigLIP 2 B/16 per frame: {SIGLIP_MS_M4:.1f} ms on M4 (inference {SIGLIP_INFER_MS_M4} + preprocessing "
          f"{SIGLIP_PREPROC_MS_M4} + JPEG decode {JPEG_DECODE_MS_M4}) -> {SIGLIP_MS_M4 * CLOUD_SLOWDOWN_VS_M4:.0f} ms on Cloud Run")
    print(f"- CPU cold start: {COLD_START_S_CPU} s = image/container {CPU_IMAGE_START_S} s + (SigLIP load "
          f"{SIGLIP_LOAD_S_M4} s + other models {OTHER_MODELS_LOAD_S_M4} s) x {CLOUD_SLOWDOWN_VS_M4}; "
          f"sensitivity {COLD_START_S_CPU_SENS} s")
    print(f"- Cloud Run CPU {CPU_VCPU} vCPU / {CPU_GIB} GiB: request-based ${r_req:.6f}/s (${r_req*3600:.4f}/h); "
          f"job ${r_job:.6f}/s; Delayed Job ${r_del:.7f}/s. At {CPU_GIB_SMALL} GiB: request-based "
          f"${rate('req', CPU_GIB_SMALL):.6f}/s ({rate('req', CPU_GIB_SMALL)/r_req - 1:+.0%})")
    print(f"- Cloud Run L4 + {GPU_VCPU} vCPU / {GPU_GIB} GiB, instance-based: ${r_gpu:.6f}/s (${r_gpu*3600:.4f}/h)")
    print(f"- Always-on worker pool, {CPU_VCPU} vCPU / {CPU_GIB} GiB: "
          f"${(CPU_VCPU*CR_WP_CPU_S + CPU_GIB*CR_WP_MEM_S)*HOURS_PER_MONTH*3600:,.2f}/month; "
          f"L4 + {GPU_VCPU} / {GPU_GIB}: ${(CR_L4_S + GPU_VCPU*CR_WP_CPU_S + GPU_GIB*CR_WP_MEM_S)*HOURS_PER_MONTH*3600:,.2f}/month")
    print(f"- Haiku summary fee per video: ${haiku_summary_fee():.6f} (x{HAIKU_PRICE_MULT} endpoint), "
          f"first-party global ${haiku_summary_fee(HAIKU_FIRSTPARTY_MULT):.6f}, Batch ${haiku_summary_fee(batch=True):.6f}; "
          f"billed wait {HAIKU_WAIT_S:g} s on CR CPU = ${HAIKU_WAIT_S*r_req:.6f}\n")

    print("| Stage | CPU s/video | CR CPU $/video | L4 s/video | L4 $/video (busy only) |")
    print("|---|---|---|---|---|")
    for s in STAGES:
        print(f"| {s} | {ws_cpu[s]:.1f} | ${ws_cpu[s]*r_req:.5f} | {ws_gpu[s]:.2f} | ${ws_gpu[s]*r_gpu:.5f} |")
    print()
    loc = sum(ws_cpu[s] for s in LOCAL3)
    print(f"Local CPU seconds in the recommended mix: {loc:.1f} s/video. Shares: " + ", ".join(
        f"{k} {parts_cpu[k]/loc:.0%}" for k in ("freepik", "guard", "asr", "lid", "siglip", "vad", "decode", "embed")))
    ws_ov, _ = work_seconds("cpu", overlap=BRANCH_OVERLAP_HIDE_SENS)
    loc_ov = sum(ws_ov[s] for s in LOCAL3)
    print(f"Audio branch {ws_cpu['captions']:.1f} s, frame branch {ws_cpu['moderation'] + ws_cpu['labels']:.1f} s; "
          f"running them concurrently with {BRANCH_OVERLAP_HIDE_SENS:.0%} of the shorter hidden: "
          f"{loc_ov:.1f} s/video ({loc_ov/loc - 1:+.0%} wall and billed seconds)")
    print()

    print("### Captions per video: local vs hosted, same speech gate\n")
    print("| Option | $/video at CPU speed x0.5 | x1 | x2 |")
    print("|---|---|---|---|")
    row = [work_seconds("cpu", f)[0]["captions"] * r_req for f in (0.5, 1.0, 2.0)]
    print("| Local Parakeet + VAD + LID, CR CPU | " + " | ".join(f"${x:.5f}" for x in row) + " |")
    for name in hosted_caption_options():
        row = [hosted_caption_options(f)[name] for f in (0.5, 1.0, 2.0)]
        print(f"| {name} | " + " | ".join(f"${x:.5f}" for x in row) + " |")
    print()

    print(f"### Monthly AI processing cost (USD), {ft}\n")
    for mau, rr, videos in cells():
        cell = grid_cell(videos)
        lam = arrival_rate_per_s(videos)
        util = lam * (loc + HAIKU_WAIT_S) / MAX_JOBS_CPU
        print(f"#### MAU {mau:,} x {rr:.0%} -> {videos:,.1f} videos, {videos*AVG_VIDEO_MIN/60:,.1f} video-hours\n")
        print("| Stage | " + " | ".join(c[1] for c in COLS) + " |")
        print("|---|" + "---|" * len(COLS))
        for s in STAGES + ("overhead",):
            print(f"| {s} | " + " | ".join(fmt(cell[k][s]) for k, _ in COLS) + " |")
        if APPLY_FREE_TIER:
            cr = [min(cell[k]["free_credit"], total(cell[k], False)) for k, _ in COLS]
            print("| free-tier credit | " + " | ".join(("-" + fmt(x)) if x > 0 else fmt(0.0) for x in cr) + " |")
        print("| **total** | " + " | ".join(f"**{fmt(total(cell[k]))}**" for k, _ in COLS) + " |")
        pl = cell["_plans"]
        print(f"\nCold-start probability {math.exp(-lam*IDLE_WINDOW_S):.1%}; recommended service busy "
              f"{util:.0%} of active hours (1 instance-equivalent). VMs: e2 {cell['vm_e2']['n_vm']}, "
              f"e2+Haiku {cell['vm_e2_haiku']['n_vm']}, g2 {cell['vm_g2']['n_vm']}.")
        print(f"Batch runs: CPU hourly job {pl['cpu_job_haiku']['tasks']} task(s), run {pl['cpu_job_haiku']['wall_s']/60:.0f} min, "
              f"worst latency {worst_latency_h('cpu_job_haiku', pl['cpu_job_haiku']):.1f} h; "
              f"L4 hourly job {pl['gpu_job_haiku']['tasks']} task(s), run {pl['gpu_job_haiku']['wall_s']/60:.0f} min, "
              f"worst {worst_latency_h('gpu_job_haiku', pl['gpu_job_haiku']):.1f} h; "
              f"Delayed Job {pl['delayed_batch']['runs_per_day']} runs/day, run {pl['delayed_batch']['wall_s']/3600:.1f} h, "
              f"worst {worst_latency_h('delayed_batch', pl['delayed_batch']):.0f} h with Haiku Batch, "
              f"{worst_latency_h('delayed_sync', pl['delayed_sync']):.0f} h with sync Haiku "
              f"(+{fmt(total(cell['delayed_sync']) - total(cell['delayed_batch']))}/month).\n")

    print(f"### Totals overview ({ft})\n")
    print("| Cell | Videos | Video-h | " + " | ".join(c[1] for c in COLS) + " |")
    print("|---|---|---|" + "---|" * len(COLS))
    for mau, rr, videos in cells():
        cell = grid_cell(videos)
        print(f"| {mau:,} x {rr:.0%} | {videos:,.0f} | {videos*AVG_VIDEO_MIN/60:,.0f} | "
              + " | ".join(fmt(total(cell[k])) for k, _ in COLS) + " |")

    print("\n### Sensitivity of the key columns (monthly totals)\n")
    print(f"Rows: CPU speed x0.5 / x1 / x2 (every CPU step, incl. VAD, LID and decode on GPU images); "
          f"CPU cold start {COLD_START_S_CPU_SENS} s; GPU cold start {COLD_START_S_GPU_SENS} s; "
          f"CPU instances at {CPU_GIB_SMALL} GiB; audio and frame branches in parallel "
          f"({BRANCH_OVERLAP_HIDE_SENS:.0%} of the shorter hidden); Haiku via first-party API (x1.0); "
          f"free tier on (credit per configuration).\n")
    print("| Cell | Case | " + " | ".join(LABEL[k] for k in KEY_COLS) + " |")
    print("|---|---|" + "---|" * len(KEY_COLS))
    for mau, rr, videos in cells():
        cases = (("CPU x0.5", grid_cell(videos, 0.5), False),
                 ("CPU x1", grid_cell(videos, 1.0), False),
                 ("CPU x2", grid_cell(videos, 2.0), False),
                 (f"CPU cold {COLD_START_S_CPU_SENS} s", grid_cell(videos, cpu_cold=COLD_START_S_CPU_SENS), False),
                 (f"GPU cold {COLD_START_S_GPU_SENS} s", grid_cell(videos, gpu_cold=COLD_START_S_GPU_SENS), False),
                 (f"CPU {CPU_GIB_SMALL} GiB", grid_cell(videos, gib=CPU_GIB_SMALL), False),
                 ("parallel branches", grid_cell(videos, overlap=BRANCH_OVERLAP_HIDE_SENS), False),
                 ("Haiku 1st-party", grid_cell(videos, haiku_mult=HAIKU_FIRSTPARTY_MULT), False),
                 ("free tier on", grid_cell(videos), True))
        for name, c, free in cases:
            print(f"| {mau:,} x {rr:.0%} | {name} | " + " | ".join(fmt(total(c[k], free)) for k in KEY_COLS) + " |")

    print("\n### Crossovers (video-hours per month; second option cheaper)\n")
    pairs = (("rec", "cpu_job_haiku"), ("rec", "gpu_job_haiku"), ("cpu_job_haiku", "gpu_job_haiku"),
             ("rec", "vm_e2_haiku"), ("cr_cpu", "cr_gpu"), ("cr_cpu", "vm_g2_spot"))
    print("| First | Second | CPU x0.5 | CPU x1 | CPU x2 |")
    print("|---|---|---|---|---|")
    for k1, k2 in pairs:
        print(f"| {LABEL[k1]} | {LABEL[k2]} | " + " | ".join(crossover(k1, k2, f) for f in (0.5, 1.0, 2.0)) + " |")

    print("\n### Per-stage, per-video: local CR CPU vs hosted (both linear in volume)\n")
    hr = hosted_reference_fees()
    hosted_pv = {"captions": hosted_caption_options()["Gemini 3.1 Flash-Lite (Vertex EU)"],
                 "summaries": haiku_summary_fee() + HAIKU_WAIT_S * r_req,
                 "moderation": hr["moderation"], "labels": hr["labels"]}
    for s in ("captions", "summaries", "moderation", "labels"):
        lo, ho = ws_cpu[s] * r_req, hosted_pv[s]
        print(f"- {s}: local ${lo:.5f} vs hosted ${ho:.5f} -> "
              f"{'local' if lo < ho else 'hosted'} cheaper by {max(lo, ho)/min(lo, ho):.1f}x")


if __name__ == "__main__":
    main()
