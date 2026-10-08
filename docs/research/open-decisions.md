# Open decisions, measurements and Expause facts

Compiled 2026-10-08 from the final research files q1–q8b. Decisions already settled in `user-decisions.md` (U1 complement role, U2 Python 3.12, U3 EU operator, U4 Parakeet CC-BY default) are not repeated. Items that one research file raised and a sibling file has since closed are listed at the end, so they are not reopened by mistake.

"Part 2" means the repository skeleton: layout, ports, one thin audio-extraction stage, gates and pinned dependencies. "Blocks Part 2: yes" means the skeleton would have to pick an answer (or bake in a default that is costly to change) before it can be written.

---

## 1. Decisions for the user

### Blocking Part 2

**D1. Ruff line length**
- Source: q8b §2 "Limits", open question 1.
- Question: should the ruff line length be 120 or the ruff default 88?
- Options:
  - **120**: fewer wrapped lines with long type annotations and pydantic fields; not the community default.
  - **88**: ruff/black default, familiar to every contributor; more wrapping.
- Research's choice: 120. The drafted `pyproject.toml` uses 120, but q8b gives no argument for it.
- Blocks Part 2: **yes** (`pyproject.toml`).

**D2. Name of the `WriteConflict` exception**
- Source: q8b §2 (N818 note), open question 6; q8a §4 (`ports.py`).
- Question: should q8a's `WriteConflict` port exception be renamed to satisfy ruff N818, or should the rule be ignored for that file?
- Options:
  - **Rename to `WriteConflictError`**: no suppression in core; diverges from q8a's text.
  - **Per-file ignore `"src/scenewise/ports.py" = ["N818"]`**: keeps q8a's name; adds a reviewed config escape hatch. An inline `noqa` is impossible because suppressions are banned in core.
- Research's choice: rename. It is the only option that adds no suppression.
- Blocks Part 2: **yes** (`ports.py`).

**D3. Where Pillow goes**
- Source: q8b open question 11; q8a §9.4 (`vision` extra), §1.4 (`adapters/media/images.py`).
- Question: should Pillow be a base dependency, or stay in the `vision` extra?
- Options:
  - **Base dependency**: `ImageReader` is a non-optional member of `Dependencies`, used for sprite sheets even without vision models; the PR tier can then contract-test `images.py`, and it leaves the coverage `omit` list. The cost is a slightly larger base install.
  - **Keep it in `vision`**: smaller base; `images.py` stays untested in the PR tier and stays omitted from coverage.
- Research's choice: base dependency. q8b argues for it but leaves the call to q8a.
- Blocks Part 2: **yes** (extras, coverage config).

**D4. Coverage for heavy adapters, and how the GCS contract test runs**
- Source: q8b §5, §6 (contract table), open question 2.
- Question: is "omit heavy adapters in the PR tier, with an advisory report in the models job" enough, and should the `gcs` `BlobStore` contract use an in-memory fake or the fake-gcs-server emulator?
- Options:
  - **Omit plus an advisory report (as drafted), with an in-memory fake of the GCS client**: simple and fast; heavy adapters have no merge-gating coverage.
  - **Combine the models-job coverage and gate it on main**: more honest coverage; the slower model job then gates.
  - **fake-gcs-server as a CI service container**: closer to real GCS behaviour (generations, preconditions); untested by the research and adds a container.
- Research's choice: omit plus advisory (the drafted config). No choice is made for GCS; the emulator was not tested.
- Blocks Part 2: **yes** (coverage config). The GCS part matters only once the `gcs` adapter exists.

**D5. CODEOWNERS for gate config**
- Source: q8b §4.2 (row 6), §13, open question 7.
- Question: which human account or team owns `pyproject.toml`, `uv.lock`, `scripts/`, `vulture_whitelist.py` and `.github/`?
- Options:
  - **The user's personal account**: simplest; every gate change waits on one person.
  - **A small human team**: no single point of failure; it needs a GitHub team.
  - Agent identities are excluded either way.
- Research's choice: none. Only the rule that agents must not be code owners.
- Blocks Part 2: **yes** (`.github/CODEOWNERS`, branch protection).

**D6. Local hook runner**
- Source: q8b §7 "Hooks", open question 10.
- Question: should prek or pre-commit be the documented hook runner?
- Options:
  - **prek 0.5.5**: fast, reads the same config format; younger project.
  - **pre-commit 4.6.2**: the long-standing default; slower, Python-based.
- Research's choice: none. Hooks are a local convenience only, and CI is the gate.
- Blocks Part 2: **yes**, but minor (which config file and README instructions to write).

**D7. A separate `input_unavailable` error code**
- Source: q1 open question 13 (first bullet); q8a §8 (error hierarchy).
- Question: should a missing or forbidden input (404, or 403 after retries) get its own `InputError` code, `input_unavailable`?
- Options:
  - **Add it**: a consumer can tell a missing staging object from a corrupt one.
  - **Reuse `corrupt_media` / `invalid_request`**: one code fewer; the two causes become indistinguishable.
- Research's choice: none; q1 gives both sides.
- Blocks Part 2: **yes**. The audio-extraction stage reads its input through `BlobStore` and must raise something when the input is missing.

**D8. A rule that logs never contain transcript text or signed URIs**
- Source: q1 open question 13 (third bullet); q8a §7.2.
- Question: should the logging setup state, and test, that logs carry no transcript text and no signed URIs?
- Options:
  - **Adopt it in the skeleton**: matches q1's plaintext-lifecycle argument (§8.7); cheap to add while structlog is set up.
  - **Leave it as q8a has it**: binding only `job_id`/`stage`/`attempt` implies the rule but does not state it.
- Research's choice: none.
- Blocks Part 2: **yes** (logging setup and its test), though small.

### Not blocking Part 2: architecture and contract

**D9. Routing fields in `JobRecord`**
- Source: q1 open question 13 (second bullet).
- Question: should `JobRecord` carry `schema_version`, `scenewise_version` and `external_ref`?
- Options:
  - **Add them**: Expause's Cloud Storage intake can route a record without reading `result.json`.
  - **Leave them out**: a smaller record; Expause derives routing from `job_id` (`um-{mediaId}-r{rev}`).
- Research's choice: none.
- Blocks Part 2: no, if the skeleton stops short of the job record. Decide it before the HTTP/job path is built.

**D10. DASH manifests and scene sampling in v1**
- Source: q8a §0 and §12, Q-17 (fourth bullet), Q-18; q1 §4.2 (`AudioManifest.format: "hls" | "dash"`) and §4.3 (`VideoForFrames.format`, `sampling: "scene"`).
- Question: should v1 accept DASH manifests and `sampling: "scene"`, which q1's contract lists but q8a does not implement?
- Options:
  - **HLS only, with `file` + `interval` frames; DASH gives `manifest_unsupported`**: no untrusted-XML parsing. Expause's default path is a single file and its backfill uses HLS.
  - **Add DASH `SegmentTemplate`/`SegmentList`**: wider caller support; needs hardened XML parsing (Expat "billion laughs" warning) and its own tests.
  - Either way, q1's Literal types must be narrowed to match, or the gap documented.
- Research's choice: HLS only, `file` + `interval` (q8a default).
- Blocks Part 2: no. The thin stage only needs `file` input. The contract types written later must follow this decision.

**D11. Torch and the GIL during vision inference**
- Source: q8a Q-5.
- Question: if open_clip/torch inference holds the GIL, should vision run in a subprocess?
- Options:
  - **Accept the risk and measure it in the model test tier**: the probe timeout (5 s × 3) bounds the risk; no extra cost.
  - **Run vision in a subprocess**: `/healthz` is never starved; it costs a second model copy and IPC.
- Research's choice: accept and measure.
- Blocks Part 2: no (labels/moderation feature).

**D12. A CUDA 12 image for the faster-whisper fallback**
- Source: q8a Q-8, §9.5.
- Question: is a `cu126` image ever needed so that faster-whisper (LID gate, fallback ASR) can run on GPU?
- Options:
  - **CPU is enough**: no second CUDA image.
  - **Build a cu126 image**: only if the LID gate on every job turns out too slow on CPU.
- Research's choice: CPU is enough.
- Blocks Part 2: no.

**D13. Auth for self-hosted deployments**
- Source: q8a Q-13, §6.5.
- Question: outside GCP, does a reverse proxy do auth, or does scenewise verify bearer/OIDC tokens itself?
- Options:
  - **A reverse proxy**: no code.
  - **In-app verification**: self-contained; adds google-auth on the push path.
- Research's choice: a reverse proxy.
- Blocks Part 2: no.

**D14. The local job-record store**
- Source: q8a Q-14.
- Question: is the single-host `storage/local.py` CAS (lock plus `O_EXCL`) enough, or is a SQLite-backed record mode needed?
- Options:
  - **Single-host local store**: enough for docker-compose self-hosting.
  - **A SQLite-backed `BlobStore` mode**: multi-process safety; more code.
- Research's choice: single-host local store.
- Blocks Part 2: no. The default is what the skeleton builds.

### Not blocking Part 2: product and runtime

**D15. Latency requirement per output**
- Source: q7 open question 3, §2.4; q3 open question 2 (synchronous vs Batch Haiku).
- Question: must results (summaries especially) arrive while the uploader is still looking, or may they arrive hours or days later?
- Options:
  - **Synchronous Cloud Run service with synchronous Haiku**: about 1–2 min; nothing extra to build; $218/month at 100k × 5%.
  - **Hourly CPU or L4 job**: about 1.2–2 h; saves about $54–98/month at 100k × 5%; needs a batch intake, a pending store and a `run-batch` CLI.
  - **Delayed Job, with synchronous or batch Haiku**: about 31 h to 2.3 days; saves about $102–106/month; Preview, plus a separate Vertex batch adapter.
- Research's choice: the synchronous service. At realistic volumes the batch modes save little and need new intake code.
- Blocks Part 2: no.

**D16. Haiku endpoint**
- Source: q7 §2.3, open question 12; q5 OQ9 (EU terms of hosted options).
- Question: should Haiku 5.5 be called through Anthropic's first-party API or through Vertex AI's EU multi-region endpoint?
- Options:
  - **Anthropic first-party**: cheapest, newest features, Message Batches in the same SDK. Inference is `global` or `us` only, with US workspace storage, so transcripts need a transfer basis.
  - **Vertex AI EU**: inference stays in the EU, and billing and IAM stay in Google Cloud. It costs +10% (at most +$0.68/month in the grid), needs the `anthropic[vertex]` extra and its own batch adapter, and features may lag.
- Research's choice: Vertex AI EU (the cost grid's default, for residency at under $1/month). q7 still names it a user decision.
- Blocks Part 2: no. It decides the `llm-anthropic` extra's spec, so settle it before that extra is pinned.

**D17. Emission thresholds for summaries and chapters, and whether chapters are wanted**
- Source: q3 open question 4, "Minimum length".
- Question: do the judgement thresholds (chapters only for videos of at least 120 s with at least 3 valid chapters; a summary only from about 40 words) hold for Expause, and are chapters useful in a short-video UI at all?
- Options:
  - **Adopt the thresholds now and tune them on samples**: a working default from day one.
  - **Summaries only, no chapters for short-form**: simpler; loses chapters on longer videos.
  - **Calibrate on Expause samples first**: better fit; delays the feature.
- Research's choice: the stated thresholds, marked as judgement, for the product owner to confirm.
- Blocks Part 2: no.

**D18. Fallback when Haiku refuses a summary**
- Source: q3 open question 7.
- Question: when Haiku 5.5 refuses (likely on moderation-flagged videos), what should the client-side retry be?
- Options:
  - **Haiku 4.5**: same vendor, contract and prompt path; 10× the price, may refuse too, and a previous-generation model.
  - **An open-weight model**: cheap and independent of Anthropic's classifiers; a second backend to evaluate, weaker chaptering, and the operator owns its output on flagged content.
  - **No retry**: no summary for refused videos.
- Research's choice: none. Measure the refusal rate in the q3 eval first.
- Blocks Part 2: no.

**D19. Partial English captions on mostly non-English videos**
- Source: q2 open question 13, §4.4.
- Question: should English windows be captioned whenever there are at least about 2 s of English speech, or only when English also reaches a minimum share of speech?
- Options:
  - **Absolute minimum only**: every English sentence is captioned; a track may cover only a small part of the speech, with `partial_language: true`.
  - **Add a share minimum (for example 30%)**: avoids tracks that look broken; drops real English captions.
- Research's choice: absolute minimum only.
- Blocks Part 2: no.

**D20. Primary ASR runtime**
- Source: q2 open question 14, §5.1.
- Question: should Parakeet run on sherpa-onnx or on a vendored, patched onnx-asr?
- Options:
  - **sherpa-onnx 1.13.8**: TDT durations and log-probabilities without patching, audio tagging in the same runtime, a larger user base. It is a non-vendorable native dependency with a second bundled onnxruntime.
  - **onnx-asr 0.12.0**: pure Python, MIT, vendorable, one onnxruntime. scenewise would own a durations patch, and the project has a single maintainer.
- Research's choice: sherpa-onnx. Both stay CI-tested behind the port, so the choice is reversible.
- Blocks Part 2: no (the captions feature).

**D21. "Unknown"-language speech windows**
- Source: q2 open question 15.
- Question: what happens to speech windows the `tiny` LID model cannot label confidently?
- Options:
  - **A: drop them, with a flag**: safe against pseudo-English; loses some short or noisy English.
  - **B: caption them if Parakeet's mean token log-probability passes a threshold**: only after T3 shows that it separates the languages.
  - **C: use `base` for LID (about 145 MB)**: fewer unknowns; a larger model.
- Research's choice: A (the default).
- Blocks Part 2: no.

**D22. Music flag, "[music]" cues and lyrics**
- Source: q2 open questions 16 and 6.
- Question: should scenewise ship the AudioSet tagger as a metadata `music` flag, show visible "[music]" (SDH-style event) cues, caption lyrics, or wait for test T1?
- Options:
  - **Metadata flag now**: cheap; invisible to viewers.
  - **Visible "[music]" cues**: better accessibility; risk of false cues (digital silence scored "Music" 0.33–0.37).
  - **Wait for T1**: no risk; nothing ships.
  - Lyrics captions are a separate yes/no; Parakeet on sung vocals is untested.
- Research's choice: none. T1 should come first. The tagger was trained on AudioSet, which is built from YouTube clips; whether that provenance matters is a legal call for Expause.
- Blocks Part 2: no.

**D23. Output for audio with no speech**
- Source: q1 §9 (says "Q2 decides"); q2 does not decide it.
- Question: for audio with no speech (`no_speech`, `cue_count: 0`), should scenewise write no VTT or a header-only VTT?
- Options:
  - **No VTT**: nothing to serve, and consistent with `no_audio_stream`.
  - **A header-only `WEBVTT` file**: players that expect a track always get a valid file.
- Research's choice: none (an unowned item).
- Blocks Part 2: no.

**D24. Nemotron 3.5 Content Safety as a tier-2 candidate**
- Source: q4 open question 15, summary item 2.
- Question: should Nemotron stay on the tier-2 guard shortlist while NVIDIA's licence name is inconsistent?
- Options:
  - **Keep it**: it scores above ShieldGemma 2 in Mistral's table and takes custom policies.
  - **Drop it until clarified**: two different licence names, no continuous score, and Shieldstral (Apache-2.0) already scores higher.
- Research's choice: drop it until clarified. The summary admits it "only once that is resolved".
- Blocks Part 2: no.

**D25. Uncalibrated labels in Expause's `contentTags`**
- Source: q5 OQ12.
- Question: may scenewise labels reach Expause's production `contentTags` before a calibration run? A related Expause-side question: should Expause also store `score_max`/`calibrated`?
- Options:
  - **Yes, uncalibrated**: labels from day one; `z_min` is untuned, and because only names are stored, weak tags cannot be filtered later.
  - **Calibrate first**: one `scenewise calibrate` run on a few hundred videos (Haiku-bootstrapped, human spot-check); a few hours of work, repeated whenever the taxonomy or model changes.
- Research's choice: calibrate first.
- Blocks Part 2: no.

**D26. TranslateGemma for subtitle translation (when Q6 is scheduled)**
- Source: q6 open question 1.
- Question: are TranslateGemma's Gemma Terms (downstream restrictions, Google's remote-restriction right, 2K-token input) acceptable?
- Options:
  - **Accept it**: strong WMT24++ numbers, no fee.
  - **Reject it**: Apache-2.0 Gemma 4 / Qwen3 and OpenMDW Seed-X avoid non-OSI terms and the context limit.
- Research's choice: leans against. The recommended local options are Qwen3, Gemma 4 and Seed-X, not TranslateGemma.
- Blocks Part 2: no (translation is deferred).

**D27. Thinking setting for Haiku translation**
- Source: q6 open question 6.
- Question: when translation is scheduled, should Haiku 5.5 run with thinking off or on at low effort?
- Options:
  - **Off**: cheapest ($0.015–0.034 per language-hour); the docs warn that JSON tool calls can be skipped.
  - **On at low effort**: more reliable cue-ID JSON; up to about 2× the output cost.
- Research's choice: none. A pilot on real cues decides.
- Blocks Part 2: no.

**D28. Translation source: original transcript or English pivot**
- Source: q6 open question 7.
- Question: should subtitles be translated from the source-language transcript or through an English pivot?
- Options:
  - **The source transcript**: no compounding of errors; needs multilingual ASR, since Parakeet v2 is English-only.
  - **An English pivot**: reuses the English pipeline; compounds errors.
- Research's choice: implicitly the source transcript (q6's default path is a source-language transcript, then LLM translation). Not decided explicitly.
- Blocks Part 2: no.

### Not blocking Part 2: Expause-side choices scenewise must accommodate

**D29. Expause's primary moderation and label signal after Video Intelligence**
- Source: q4 open question 1 and §"Video Intelligence deprecation"; q5 OQ1 and §5a.
- Question: after Video Intelligence shuts down on 2027-09-14, should Expause's primary signal be Cloud Vision (SafeSearch plus label detection) or Gemini Flash-Lite?
- Options:
  - **Cloud Vision**: same Likelihood enum, per image, deterministic, no prompt to maintain, vocabulary continuity for labels. About $0.0015 per frame for SafeSearch and about $0.018 per video for labels.
  - **Gemini 3.1/3.5 Flash-Lite**: Google's named replacement, custom policies, cheaper per frame. It needs a prompt, its own evaluation and safety filters off, is not a native Likelihood, and the models turn over fast.
- Research's choice: q4 recommends SafeSearch as the cheapest migration, settled by a pre-shutdown shadow run. The scenewise combination rule works with either.
- Blocks Part 2: no.

**D30. How captions are served**
- Source: q1 open question 6, §5.4.
- Question: should Expause encrypt the VTT for paid content, and serve it as a sidecar `<track>` or as an HLS `SUBTITLES` rendition?
- Options:
  - **A sidecar `<track>`, unencrypted**: simplest.
  - **An HLS `SUBTITLES` rendition**: native in players; needs a WebVTT media playlist and `X-TIMESTAMP-MAP`.
  - **Encrypting the VTT**: protects paid content; more Expause-side work.
- Research's choice: none.
- Blocks Part 2: no.

**D31. Backfill of existing videos**
- Source: q1 open question 7, §8.8.
- Question: should existing (encrypted) videos be backfilled by decrypting adapter-side in Expause, or skipped?
- Options:
  - **Decrypt adapter-side and submit HLS**: full coverage. It needs Expause's non-standard IV handling.
  - **Skip them**: new uploads only; no decryption code.
- Research's choice: none. A backfill design is given if it is wanted.
- Blocks Part 2: no.

**D32. Chat and community videos**
- Source: q1 open question 8.
- Question: are chat and community videos in scope?
- Options:
  - **In scope**: more coverage. They have their own encryption loops and no GVI today, so each needs its own hook.
  - **User-generated media only**: the q1 design as written.
- Research's choice: none (q1 scopes to user-generated video).
- Blocks Part 2: no.

**D33. Soft delete on Expause's default (upload) bucket**
- Source: q1 open question 12 (user-decision bullet), §8.7.
- Question: should soft delete be turned off on the default bucket, where raw uploads stay restorable for 7 days after deletion?
- Options:
  - **Retention 0**: the plaintext window ends at deletion, consistent with the transcoder and staging buckets. It removes recovery for every other file in that bucket.
  - **Keep the 7-day default**: recovery is kept; plaintext raw video stays restorable for 7 days.
  - **Move raw video uploads to their own bucket with retention 0**: the middle path, at the cost of a migration.
- Research's choice: none. scenewise works with any choice. Retention 0 on the *transcoder* bucket is a requirement, not a choice (E13).
- Blocks Part 2: no.

---

## 2. Measurements and checks for the first feature task prompts

Grouped by the feature task that should carry them.

**Runtime / deployment task**
- A Cloud Run CPU benchmark, 4 vCPU / 16 GiB, europe-west1 gen2 (q7 OQ1, the first engineering task). Measure, in order:
  - Freepik and the tier-2 guard per frame;
  - Parakeet int8 RTFx, `tiny` LID, SigLIP 2 B/16, Silero, ffmpeg decode;
  - peak RSS with the guard loaded, which decides 8 vs 16 GiB or a separate guard service;
  - cold start of the `-cpu` image, with and without lazy guard loading;
  - audio and frame branches in parallel vs serial.
  Then re-run the cost script. Also covers q2 OQ2, q4 OQ9, q5 OQ6, q3 OQ5 and q8a Q-11 (push-budget cost factors).
- L4 throughput with the `-cuda` image: TensorRT on driver 580, billed GPU start-up, whether batched vLLM pays (q7 OQ2).
- Whether Cloud Run health probes take a request slot at `concurrency = max_jobs`, on a deployed revision (q8a Q-19).
- Real idle retention and cold-start behaviour (q7 OQ8). e2 vs Cloud Run per-vCPU speed (q7 OQ11).
- Delayed Jobs: GPU support, and whether the 12 h cap is summed or wall time (q7 OQ7). Only if a batch mode is chosen (D15).
- Whether Vertex Claude batch prediction runs in the `eu` multi-region (q7 §2.3). Only if D16 is Vertex and batch is used.

**Captions task**
- T1, a music and no-speech test set: instrumental, vocals, music under speech, ambient/silence, real Expause clips. Measure the Silero ratio, Parakeet output with and without VAD, and the AudioSet tagger plus an RMS gate (q2 T1, OQ1, OQ6).
- T2, timestamps: sherpa start + duration vs onnx-asr vs NeMo word times; tune the cue end extension, the segmentation cap and the cut search window (q2 T2, OQ4).
- T3, LID: `tiny` vs `base` on real Expause clips; the p ≥ 0.5 and ≈2 s thresholds; whether Parakeet log-probabilities separate languages; accented English (q2 T3, OQ5). Feeds D19 and D21.
- T4, a process smoke test: three runtimes in one process, both import orders, peak RSS (q2 T4).
- Parakeet vs faster-whisper int8 turbo / distil-large-v3.5 on the same CPU; int8 vs fp32 WER (q2 OQ2, OQ3).
- Parakeet per-segment penalty (q1 OQ9), optional.
- Optional candidate checks: ARK-ASR-0.6B maintenance, timestamps and CPU speed; Granite-speech punctuation and timestamps; Voxtral price and timestamps, if an EU hosted fallback is wanted; Gemini on Vertex EU for hosted captions (q2 OQ7, OQ8, OQ12; q7 OQ9).

**Expause adapter / input task (built in Expause)**
- Transcoder audio timing: `elst media_time`, first PTS, `tfdt`; whether fMP4 stitches with `cat` (q1 OQ2).
- Second previews sheet and partial-sheet padding, which decides whether `count` is mandatory (q1 OQ3).
- Init and playlist object names for the segment path (q1 OQ1).
- p99 duration of `transcodeJobUpdated`, to size the 120 s skip threshold (q1 OQ5).
- Server-side copy latency for a 130 MB object; whether `MuxStream.fileName` may contain `/` (q1 OQ11).
- Billing of the extra audio mux stream on a real invoice or SKU report (q1 OQ10).
- Bucket locations (staging = transcoder region, EU, compatible with the `europe-west1` intake); transcoder bucket soft delete set to 0 (q1 OQ12).

**Summaries task**
- A 50–100-video eval: Haiku 5.5 vs Qwen3.5-4B / 9B / 35B-A3B, with and without frame labels; refusal rate (q3 OQ1, OQ7). Feeds D18.
- `llama-bench` on self-host hardware (q3 OQ5); self-hosted GPU prices (q3 OQ6).
- OpenRouter per-provider structured output and thinking-off, through a smoke test with `require_parameters: true` (q3 OQ9).
- Calibrating the 120 s / 40-word thresholds on real samples (q3 OQ4; see D17).

**Moderation task**
- A shadow run on Expause: primary vs scenewise vs candidate replacement primary, logged against moderator outcomes (q4 evaluation plan). It also answers SafeSearch-vs-VI equivalence (q4 OQ2) and feeds D29.
- Haiku on explicit frames: refuse, or only decline to describe? Does NCMEC hash-matching apply to API traffic? (q4 OQ3)
- CPU latency of Freepik, Marqo, Falconsai, SigLIP2, Shieldstral GGUF and Nemotron (q4 OQ9).
- Licence checks: NudeNet (q4 OQ6), LlavaGuard weights (OQ7), Nemotron (D24), and evaluation dataset terms for commercial use (OQ12).
- Unverified items: Shieldstral claims, ShieldGemma 2 input resolution, Haiku resolution tier (q4 OQ10, OQ11).
- Gemini terms: Vertex terms, Vertex prices, whether safety filters can be turned off (q4 OQ5).

**Labels task**
- An eval set of a few hundred Expause videos: SigLIP 2 B/16 vs B/32-256 vs NaFlex vs PE-Core-B/16; squash vs pad; max vs mean vs top-3; drift with K; default `z_min`; English vs non-English prompts (q5 OQ10).
- Haiku tagging quality and token counts (q5 OQ9).
- Firestore EU vector rates and index size; flat kNN scan behaviour (q5 OQ5).
- Whether Cloud Vision `mid`s and VI `entityId`s share an id space, only if Expause keys on ids (q5 OQ4).
- Offline value of content embeddings for the recommender, once D-facts below are known (q5 OQ11).

**Tooling task (Part 2 can carry these as follow-ups)**
- Whether Dependabot's `uv` ecosystem bumps `[tool.uv] required-version` (q8b OQ4).
- `uv audit` stays an alert; switch to pip-audit 2.10.1 if its format changes (q8b OQ3).
- Licences of the CMU flite voice data and the `hf-internal-testing/tiny-random-*` models (q8b OQ5).
- Whether macOS Homebrew ffmpeg has libflite; commit fixtures plus a generator script either way (q8b OQ9).
- Mutation testing (mutmut) as a nightly advisory later, once the domain has code (q8b OQ8). Optional.

**Translation (deferred)**
- chrF/COMET head-to-head for Seed-X, MADLAD, Opus-MT, Canary, Haiku 5.5 and Qwen3 on Expause languages; Haiku token counts per script (q6 OQ4, OQ6).
- Meta Omnilingual MT weights and licence (q6 OQ2); DeepL/Google context and glossary support (q6 OQ9).

**Legal sign-offs (not measurements, not scenewise decisions)**
- CC-BY-4.0 NOTICE wording, where Expause shows the credit, and confirmation that caption outputs carry no attribution duty (q2 OQ11; U4 settles the default).
- AudioSet training-data provenance of the tagger (q2 OQ16; see D22).

---

## 3. Expause facts only the user can supply

- **Content mix:**
  - share of videos with an audio stream;
  - share of videos with speech, and the speech fraction;
  - length distribution (the 5-minute average is an assumption);
  - share of speechless videos (q3 OQ3, q7 OQ4, q6 OQ8).
- **Volumes:** MAU and upload rate; real escalation rate; human-review capacity; target escalation rate (q4 OQ14, q7 OQ4).
- **Moderation release gate:** the precision target at LIKELY or above, and the number N of reviewed escalations, before `max` mode is offered (q4 evaluation plan item 4).
- **CSAM process:** the legally required detection and reporting process (hash matching, NCMEC/IWF), and whether it must run before frames reach scenewise or any third-party API (q4 OQ4).
- **Frames per video:** how many preview thumbnails Expause sends to its moderation and label calls today, and whether scenewise should score the same frames (q4 OQ13).
- **GCP region:** which EU region holds Expause's buckets and Cloud Tasks queues (q7 OQ10; q1 OQ12).
- **Billing:** whether Expause's billing account already uses the Cloud Run free tier (q7 OQ5).
- **Recommender:** whether it consumes dense vectors at all, and where (Firestore, BigQuery, a separate service) (q5 OQ11).
- **Privacy:** whether video embeddings count as personal data under Expause's privacy policy (q5 OQ7).
- **Target languages for translated subtitles:** if English↔European only, Canary-1b-v2 becomes an option (q6 OQ5).
- **Deadline for the post-VI primary migration** before 2027-09-14 (q5 OQ1).
- **Sprite and preview configuration:** the Transcoder job configs that give grid, interval, offset and tile size (q1 §4.3). Expause supplies them, scenewise never infers them.

---

## 4. Raised in one file, already closed in another (do not reopen)

- q8a Q-12 (200-on-completion vs 202): q1 r3 adopts q8a's synchronous push handler.
- q8a Q-16 (callback semantics): q1 r3 adopts best-effort callbacks plus mandatory reconciliation.
- q8a Q-17:
  - Expause-shaped route: q1 sends the generic `JobRequest`, with no Expause code in scenewise.
  - `retry`/`redeliver`/purge/`DELETE` endpoints: q1 §8.5 has none in v1.
  - `sheets_prefix`: q1 uses an explicit `sheets` list.
  - `job_id` pattern: settled.
- q1 OQ14, OQ15 and OQ16 (422 split, 1500 s budget, 202): closed in q1.
- q3 OQ8 (EU operator): settled by U3.
- q5 OQ2, OQ3 and OQ8: closed in q5.
- q6 OQ3 (Seed-X licence): closed in q6.
- q8b module-size limit: q8b sets 500 lines for all roots, replacing q8a's 400 (q8b finding 11).
