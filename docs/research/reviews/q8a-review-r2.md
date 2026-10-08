# Review r2 (final round): q8a-architecture-layout.md

Reviewer: a fresh review agent. I did not write the file or review round 1. Date: 2026-10-08. I re-opened every source below on 2026-10-08, using WebFetch on the Google Cloud, PEP, uv, import-linter, anyio and Cockburn pages, the PyPI JSON API, the PyTorch wheel indexes through curl, and raw GitHub at the cited onnxruntime commit.

Severity scale: wrong / unsupported / missing option / design concern / minor.

## Verdict

Round 1 was handled well. The new factual claims are almost all accurate: the PyTorch index contents, onnxruntime-gpu 1.30 on CUDA 13, CTranslate2 on CUDA 12, PEP 725 as a Draft, worker pools that cannot autoscale, llama-cpp-python as sdist-only, the OIDC audience default, GCS `ifGenerationMatch=0`, and the Cloud Tasks codes, deadline and headers.

The remaining problems are in the delivery protocol:
- The lease is shorter than the Cloud Tasks deadline, so it does not stop the second copy it claims to stop.
- A 409 is described as "acknowledged", but Cloud Tasks retries any non-2xx response.
- A notification sent after the terminal record can be lost.

There is also a layering hole. The wire contract lives in `service/`, but `app/publish.py` and the notifier both need it.

## Round-1 resolutions

| r1 # | Status in r2 |
|---|---|
| 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 17, 19, 20, 22, 23, 25, 26, 27, 28, 30, 32 | Resolved correctly. I checked the sources where the fix makes a claim. |
| 12 | Resolved for the visual side. The audio side has no equivalent: see #6 below. |
| 16 | Only partly resolved. The lease arithmetic does not stop the runaway-thread duplicate: see #1. |
| 21 | Resolved. One small gap remains (the `actAs` permission): see #14. |
| 29 | Resolved in §2.3, but contradicted by the §1.4 tree comment and §6.2 step 4: see #10. |
| 31 | Mostly resolved. The resolution table says `Blob` is sketched in §4–5, but it appears only as a comment in `ports.py`. `HttpCallback`, `StageOptions`, the five `Decision` variants and `FallbackTextGenerator` (which has no home in the tree) are still unsketched: see #15. |

### Partial rejections: are they sound?

- **#6 (`[external]` now): sound.** The pyproject spec says "Other tables are reserved for future use (tool-specific configuration should use the `[tool]` table)" (https://packaging.python.org/en/latest/specifications/pyproject-toml/, read 2026-10-08). PEP 725 is still Draft (last modified 2026-04-17, no Resolution).
- **#17 (do not compare the header with the queue's `maxAttempts`): sound and better than r1's proposal.** The headers page says "These headers provide information **only**. They should **not** be used as sources of identity". It also says `TaskRetryCount` "includes attempts where the task failed due to 5XX error codes", so the 503 "in progress" replies really would inflate it (https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks, updated 2026-10-07). With `maxAttempts: -1` the duration limit still applies, and the task is deleted only once both limits are exhausted (configuring-queues, updated 2026-10-07). The design holds.
- **#18 (no checkpointing in v1): sound.** The pre-flight budget rejection bounds the cost of a restart, and §12 records the decision.
- **#24 (reject `cu128`): sound, and the facts check out.** On the cu128 index, the newest cp312 x86_64 torch is `2.11.0+cu128` and the newest torchvision is `0.26.0+cu128`. On cu126, cu130 and cpu, the newest torch is `2.14.1`, and cu130/cpu have torchvision `0.29.1` (curl of https://download.pytorch.org/whl/{idx}/torch/, 2026-10-08). onnxruntime-gpu 1.30.0 requires `nvidia-cuda-runtime~=13.0` and `nvidia-cudnn-cu13~=9.0` through its `cuda`/`cudnn` extras. ctranslate2 4.8.2 is classified `NVIDIA CUDA :: 12 :: 12.4`. Moving the default stack to CUDA 12 for the fallback's sake would be wrong.

## Findings

### Delivery protocol (§6.2–6.3)

1. **Claim (§6.3, last Deadlines bullet; resolution #16): "If a thread still outlives the deadline (a hang inside a native call), the lease (budget + 60 s) makes the retry answer `InProgress` instead of starting a second copy."**
   - Source: Cloud Tasks retries only after `dispatchDeadline` passes ("the request is cancelled and the attempt is marked as a `DEADLINE_EXCEEDED` failure"; "whether the worker stops processing depends on the worker", REST reference, updated 2026-09-30). Cloud Run on timeout: "the container instance that served the request is not terminated" (request-timeout page, updated 2026-10-07).
   - Analysis: by the doc's own numbers, the lease runs out at 1500 + 60 = 1560 s, but the Cloud Tasks retry cannot arrive before 1800 s + backoff. So when the deadline-triggered retry comes, the lease has always expired already. `decide_attempt` returns `Start(attempts + 1)`, and a second copy runs beside the hung thread, possibly on the same instance and against the same GPU lock. The lease protects only against early duplicate deliveries, not against the runaway case it is cited for. The cooperative deadline also cannot interrupt a single long native call: the whole-file `transcribe()` is one call.
   - Two further gaps:
     - Nothing fences the zombie. When it finally reaches publish, it overwrites the deterministic `result.json`/`captions.vtt` that the second attempt wrote.
     - Its terminal CAS then fails with `WriteConflict`, and the doc does not say what happens next.
   - Severity: **wrong**. The claim is false under the stated configuration.
   - Correction:
     - Set `lease_until = now + dispatchDeadline + margin` (≥ 1860 s), or renew the lease from the runner between stages (a heartbeat CAS).
     - Treat the claim's generation as a fencing token. Write results under an attempt-scoped prefix (`…/{job_id}/a{n}/`) and have the terminal record point to it. On `WriteConflict` at publish, discard the results and log.
     - Add a watchdog: if a job thread outlives deadline + grace, fail `/healthz` (a Cloud Run liveness probe), so the instance is replaced instead of holding the GPU lock and an admission token for ever.

2. **Claim (§6.2 step 2): "`request_digest` differs → `Conflict` (InputError `job_id_conflict`, 409, acknowledged)". The §8 table repeats "409 + problem".**
   - Source: "A successful response, in the range [200 - 299] … If any other HTTP response code is returned or no response is received, the task will be retried" (REST reference, updated 2026-09-30).
   - Analysis: a 409 is not an acknowledgement. Under the documented queue config (`maxAttempts: -1`, `maxRetryDuration` about 12 h), a reused `job_id` is retried for 12 hours, and every retry gets a 409 again.
   - Severity: **wrong**.
   - Correction: return **200** with the problem document (or the existing record plus `error_code=job_id_conflict`) on the push path, as the doc already does for the other terminal input errors. Keep 409 only for an interactive (non-Cloud Tasks) caller, if one is ever supported, or drop it.

3. **Claim (§6.2 step 4/5, §10): publish = "results, then a terminal record via CAS, then `notify`". On a later delivery, terminal → `AlreadyDone`, acknowledged with 200.**
   - Analysis: the callback is at-most-once. Two cases lose it:
     - `notify` fails after the terminal record is written (the Expause endpoint is down, or the instance dies between the two steps). If the failure is treated as a `RetryableError`, step 5 tries to "write the record back … released" over a record that is already terminal. Either the write conflicts, or it reopens a finished job. If the failure is swallowed, the callback is simply gone.
     - The retry hits `AlreadyDone` and never re-notifies.

     The doc presents reconciliation as covering only the "storage down" case, but it also silently absorbs every lost callback.
   - Severity: **design concern**.
   - Correction: add `notified: bool` to `JobRecord`. In `AlreadyDone` with `notified == False`, re-send the callback and then CAS `notified = True`, which makes callbacks at-least-once; the receiver dedupes on `job_id`. Alternatively, state explicitly that callbacks are best-effort and that `GET /v1/jobs/{id}` is the source of truth.

4. **Claim (§5, §8 table): `to_domain` ValueError → `InputError`. §6.2 step 5: `InputError` → terminal FAILED record + 200. The 422 row says "Body fails schema validation (no record can be keyed)".**
   - Analysis: `to_domain()` runs before `handle_delivery`, and `handle_delivery` takes a `Job`. So a body that parses (with a readable `job_id`) but breaks a domain invariant cannot reach step 5's terminal-record path. Examples are a bad sprite grid, `start > end`, or a `job_id` failing the regex. Its fate is undefined: it is either a 422 that is retried for 12 h, or an unhandled exception. Only truly unparseable bodies have no key.
   - Severity: **design concern**.
   - Correction: split the wire parse into two steps. First, the envelope (`job_id`, digest of the raw body), so a record can be keyed. Then the full `to_domain` inside `handle_delivery`, so that its `InputError` becomes a terminal `FAILED invalid_request` and a 200. Reserve 422 for bodies with no usable `job_id`.

5. **Claim (§6.3 Platform settings): "Cloud Run `--concurrency = max_jobs + 2`, so health and `GET` requests are not queued behind jobs … 429s are a safety net, not the normal path."**
   - Source: Cloud Run routes up to `concurrency` requests to an instance and does not know which ones are jobs. The GPU page says only "Determine and set an optimal maximum concurrency" (https://docs.cloud.google.com/run/docs/configuring/services/gpu, updated 2026-10-07).
   - Analysis: with concurrency 4 and `max_jobs` 2, Cloud Run will route a third and fourth *job* to a warm instance before it scales out. That is exactly a burst after a cold start, when a GPU instance takes minutes to load models. Those jobs get 429 and then Cloud Tasks' "higher backoff rate". So 429s are the normal path during bursts. Probes do not take request slots, and `GET` is rare (reconciliation only).
   - Severity: **design concern** (minor).
   - Correction: set `--concurrency = max_jobs`. That lets Cloud Run's own scaling and queueing do admission, so the in-app limiter really is a safety net. Accept that a rare `GET` may wait.

### Layering and dependency rule

6. **Claim (§4, finding 12 resolution): frame acquisition is `app/frames.py` dispatching on `VisualSource`.**
   - Analysis: there is no counterpart for `AudioSource`, which has `AudioFile`, `AudioSegments`, `AudioManifest` (HLS/DASH) and `NoAudio`. `MediaTool.audio_track(parts: Sequence[Path])` takes local files only. Nothing in the tree:
     - fetches an HLS/DASH manifest;
     - resolves its segment URIs through `BlobStore`;
     - or decides to hand ffmpeg a URL. That would bypass `BlobStore` and cannot read `gs://` anyway.

     `AudioManifest` is therefore unimplementable as laid out.
   - Severity: **design concern** (missing piece).
   - Correction: add `app/audio.py::acquire_audio(audio, deps, *, deadline)`, mirroring `frames.py`. Put manifest parsing (pure: playlist text → segment URIs) in `domain/manifests.py`, or state that `AudioManifest` is out of v1.

7. **Claim (§1.5, §1.4): the versioned wire contract and `from_domain()` live in `service/http/schemas.py`. `app/publish.py` writes `result.json`. `adapters/notify/http_callback.py` POSTs `JobResult`. `app` never imports `service`, and adapters never import `app` or `service`.**
   - Analysis: `result.json` and the callback body *are* the q1 §5 wire contract, which Expause codes against. Under the dependency rule, neither `app/publish.py` nor the notifier can import the models that define it. Either each one re-implements the serialisation (three copies of one contract that will drift), or the rule is broken. The same applies to `status.json` and to the `GET /v1/jobs/{id}` body. The import linter will catch the violation as soon as someone writes the obvious code.
   - Severity: **design concern** (an inconsistency in the dependency rule).
   - Correction: move the wire models and mappers to a module that `app` may import, for example `app/wire.py` or an `app/contract/` package (pydantic is already allowed in `app`). `service/http` imports them from there. Change `Notifier.notify` to take pre-serialised bytes (`notify(body: bytes, *, callback)`), so the adapter stays contract-agnostic.

8. **Claim (§1.5): the layers contract "with `exhaustive = true` encodes this exactly, because every top-level child of `scenewise` is one of the five (plus `__init__`/`__main__`)".**
   - Source: import-linter: exhaustive checks "that the contract declares every possible layer"; modules that should not fail go in `exhaustive_ignores` (https://import-linter.readthedocs.io/en/stable/contract_types/layers/, read 2026-10-08). The page does not exempt `__main__`.
   - Analysis: `scenewise.__main__` is a top-level child module. q8b's contract has no `exhaustive_ignores`, and q8b's seeded test did not include a `__main__`. Excluding it is very likely required, and the doc does not show that it is not.
   - Severity: **unsupported** (minor).
   - Correction: add `exhaustive_ignores = ["__main__"]` to the q8b contract and to Q-15, or move the entry into `service/__main__.py` and use `python -m scenewise.service`.

9. **Claim (§0 Heavy deps; §9.4): "The base install has no torch". The accelerator selectors `cpu`/`cu130` contain `torch` and `torchvision` as well as onnxruntime.**
   - Analysis: every image that uses the default ASR must pass `cpu` or `cu130`, and so installs torch and torchvision even with no `vision` extra. A Parakeet-only GPU image then carries the torch cu130 stack: `cuda-toolkit==13.0.3`, `nvidia-cudnn-cu13==9.24.0.43`, NCCL, nvshmem and so on (torch 2.14.1 `requires_dist`, PyPI). That is several GB that onnxruntime-gpu does not need. The claim holds only for the base install, not for any useful one.
   - Severity: **design concern**.
   - Correction: split the selectors (`ort-cpu`/`ort-cu130` for onnxruntime and `torch-cpu`/`torch-cu130` for vision, with a pairwise conflicts matrix), or state the cost honestly. Note that uv's docs show `extra`-scoped sources only for packages listed in that extra, so moving torch out of the selector needs a check that the routing still applies.

10. **Claim (§2.3): "`app/delivery.py` is the only code that writes the job record and calls `app/publish.py`". §1.4 says `publish.py` writes results "…; notify", and §6.2 step 4 says `publish` does "results, then a terminal record via CAS, then `notify`".**
    - Severity: **minor** (internal inconsistency).
    - Correction: decide on one. Cleanest: `publish` writes artifacts only, and `delivery` owns every record write and the notify call (which also suits #1's fencing and #3's `notified` flag).

11. **Claim (§5): `AttemptInfo.transport_retry: int | None  # from X-CloudTasks-TaskRetryCount (logged only)`.**
    - Analysis: a field in the pure domain decision input that the decision never reads is ceremony. Logging belongs in `service/http/push.py` (bind it to the structlog context).
    - Severity: **minor** (over-engineering).
    - Correction: drop the field from `AttemptInfo`, and bind the header in `push.py`.

### Size discipline (q8b `MAX_LINES = 400`)

12. **Claim (§1.4): `service/http/schemas.py` holds "the versioned wire contract (q1 §4/§5): pydantic models; to_domain()/from_domain()".**
    - Analysis: one module would hold the request side and the result side. The request side covers 4 audio kinds, 4 visual kinds, context, stage options, delivery/callback and `external_ref`, as discriminated unions. The result side covers the transcript, cues, summary, chapters, moderation, labels, outcomes and the `JobRecord`. Both mapper directions sit in the same module. That is plausibly 450–600 lines and the most likely first breach of q8b's 400-line gate. `adapters/media/ffmpeg.py` is borderline too: probe JSON parsing, init+segment concat for fMP4/MPEG-TS, rawvideo reading, kill-on-timeout and stderr-to-error mapping. Every other module in the tree looks comfortably under 400. `ports.py` at "≈120 lines" is optimistic once each port carries its Liskov contract in its docstring (§3), but the doc's own split-at-200 rule covers that.
    - Severity: **design concern** (minor).
    - Correction: plan `schemas` as a package from the start (`requests.py`, `results.py`, `mapping.py`), which fits #7's move. Say that `ffmpeg.py` may split into `probe.py` and `decode.py` inside `adapters/media/`.

### Citations and smaller gaps

13. **Quotation accuracy.**
    - The doc quotes Cloud Run's guide as "should return HTTP 200 only after task processing is complete". The page says the service "must return an HTTP 200 code to confirm success after processing of the task is complete" (https://docs.cloud.google.com/run/docs/triggering/using-tasks, updated 2026-10-07).
    - The doc quotes anyio as "Python can't cancel a thread". The page says "there is no mechanism in Python to cancel code running in a thread" (https://anyio.readthedocs.io/en/stable/threads.html).
    - The meaning is unchanged in both cases, but these are paraphrases in quotation marks.
    - Severity: **minor**.
    - Correction: use the verbatim wording.

14. **§6.5: the service account is described only as holding `roles/run.invoker`.**
    - Source: OidcToken: "The service account must be within the same project as the queue. The caller must have iam.serviceAccounts.actAs permission for the service account" (https://docs.cloud.google.com/tasks/docs/reference/rest/v2/OidcToken).
    - Severity: **missing option** (minor).
    - Correction: state that the SA lives in the queue's project and that the task creator needs `iam.serviceAccounts.actAs` (for example `roles/iam.serviceAccountUser`) on it.

15. **Unsketched names (r1 #31 residue).**
    - `Blob` appears only in a comment on `ports.py`.
    - `HttpCallback`, `StageOptions` and `Start`/`AlreadyDone`/`InProgress`/`GiveUp`/`Conflict` are named but never sketched.
    - `FallbackTextGenerator` has no module. Rule 3 (adapter independence per kind) allows `adapters/llm/fallback.py`, so put it there.
    - Severity: **minor**.

16. **Retrying a terminally failed job.**
    - Analysis: after `FAILED` (`deadline_exceeded`, `attempts_exhausted`, a transient backend outage that exhausted attempts), every re-enqueue with the same `job_id` returns `AlreadyDone`. The doc does not tell Expause that a retry needs a new `job_id`. Reconciliation (§6.2) only covers the 404 case.
    - Also, after a `RetryableError` release, the record's state stays `RUNNING` with an expired lease, so `GET` reports "running" while nothing runs.
    - Severity: **minor** (missing contract statement).
    - Correction: document "retry = new `job_id`" (or an explicit `POST /v1/jobs/{id}:retry` later), and add a `RETRY_WAIT` state, or derive "waiting" from `lease_until < now` in the GET mapping.

17. **§6.4(b): worker pools are rejected as "an always-on GPU".**
    - Source: the page says "GPU worker pools cannot be autoscaled", but also that "worker pools that are set to instance-based billing can still scale to zero" (https://docs.cloud.google.com/run/docs/configuring/workerpools/gpu, updated 2026-10-07).
    - Analysis: the instance count can be set manually or by an external scaler, so "always-on" is a cost of not building a scaler, not a platform fact. The rejection still stands for v1.
    - Severity: **minor**.
    - Correction: reword to "no built-in autoscaling; zero-to-N would need an external scaler".

## Verified correct (new or changed claims)

- Cloud Tasks REST reference (updated 2026-09-30):
  - 2xx is success, and other codes or no response are retried;
  - 429/503 get higher backoff, and `Retry-After` "is considered";
  - `dispatchDeadline` defaults to 10 min, lies in [15 s, 30 min], and the cancel-on-deadline wording is accurate.
- Headers page (2026-10-07): `TaskRetryCount` is 0 on the first attempt, `TaskExecutionCount` excludes 5XX failures, and the "information only, not identity" statement is accurate.
- configuring-queues (2026-10-07): `-1` is unlimited, `0s` is unlimited, and "the task is deleted" when the limits are reached.
- Cloud Run request timeout (2026-10-07): default 5 min, maximum 60 min, 504 on timeout, the instance is not terminated, and the over-15-min idempotent/resumable advice is accurate.
- Billing (2026-10-07): "CPU is only allocated during request processing". GPU page: "You must use instance-based billing to use the GPU feature"; L4 needs ≥4 CPU/16 GiB, RTX PRO 6000 needs ≥20 CPU/80 GiB, and the driver is 580.x (13.0).
- Jobs execute (2026-10-07): args, env, task count and timeout can be overridden; the `:run` endpoint is correct; overrides need `roles/run.developer`.
- OIDC: if the audience is omitted, "the URI specified in target will be used". Cloud Run accepts "the URL of the receiving service or a configured custom audience", and "Custom domains are currently not supported for the aud value" (2026-10-07).
- GCS preconditions (2026-10-07): `ifGenerationMatch=0` means create only if absent, a mismatch gives 412, and read-then-write with the generation is the documented safe read-modify-write.
- PyTorch indexes (curl, 2026-10-08):
  - cu130/cpu/cu126 have torch 2.14.1;
  - cu128 stops at 2.11.0;
  - torchvision 0.29.1 exists for `+cpu` and `+cu130`, and requires `torch>=2.14.0`.
- torch 2.14.1 on PyPI requires `cuda-toolkit[...]==13.0.3` and `nvidia-cudnn-cu13` on Linux.
- onnxruntime-gpu 1.30.0: `cuda` and `cudnn` extras exist, pinning `nvidia-cuda-runtime~=13.0` and `nvidia-cudnn-cu13~=9.0`.
- onnx-asr 0.12.0 has no hard onnxruntime dependency (`cpu`/`gpu`/`hub` extras), so `onnx-asr[hub]` plus a selector does not double-install onnxruntime.
- ctranslate2 4.8.2 is classified CUDA 12.4.
- llama-cpp-python 0.3.36 is a single sdist with no wheels on PyPI.
- open-clip-torch 3.3.0 requires `torchvision` and `timm>=1.0.17`.
- PyPI latest versions: anyio 4.15.1, timm 1.0.30, google-cloud-storage 3.16.0, onnx-asr 0.12.0.
- PEP 725: Draft, Standards Track, created 2023-08-17, last modified 2026-04-17; it defines `[external]` (`build-requires`, `host-requires`, `dependencies`) and cites PEP 804.
- Worker pools GPU (2026-10-07): "GPU worker pools cannot be autoscaled"; L4 and RTX PRO 6000 are supported; no launch stage is given.
- onnxruntime `b131c79b6f` (2026-10-08): `// release GIL to allow multiple python threads to invoke Run() in parallel.` followed by `py::gil_scoped_release` in `onnxruntime_pybind_state.cc`, at lines 3101 and 3210.
- The torch 2.14 `OutOfMemoryError` doc URL resolves (HTTP 200).
- The Cockburn quotes match apart from italics, and the page is dated 2005-09-04.
- anyio's default thread limiter is 40.
