# Review r1: q1-input-contract.md

Reviewer: a fresh review agent that did not write the file. All Expause code was re-read on 2026-10-08 at HEAD `32ed0bf18` (2026-09-22). Paths are relative to `/Users/daniel/Work/expause/cloud_functions/functions/src/functions/` unless they start with `lib/` (Flutter) or `expause_web/`. External sources were re-opened on 2026-10-08. faster-whisper was re-read at the cited commit `9fa78645`.

Severity scale:
- **wrong**: the source contradicts the claim.
- **unsupported**: the source does not back the claim as written, or a material caveat is missing.
- **missing**: a consideration or option the research should have covered.
- **design concern**: a problem with the proposed contract or adapter.
- **minor**: citation, wording or precision.

Overall, the Expause code reading is very accurate. Every one of more than 60 `file:line` citations I checked points at the right code (see "Verified as correct"). The main problems are in the adapter design: the hook point's failure mode, the cost of stitching inside the 180 s function, and the claim that Cloud Tasks protects the GPU box. Schema gaps come next.

## Findings

1. **"The adapter hook goes immediately before [`triggerVideoEncryption`] … Errors are caught and only logged"** and **"Expause encryption and publishing are not delayed"** (lines 19, 518, 533)
   → What the code does:
   - `triggerVideoEncryption` is reached only on the try-path of `onTranscodeJobSucceeded` (`transcoding/app_transcoding.ts:223`).
   - The `catch` at `:224-239` sets `isProcessing: false` **without** starting encryption.
   - The handler runs under a hard 180 s timeout (`transcoding/transcode_job_updated.ts:11`) and has no Pub/Sub retry option (`:8-17`). It already waits synchronously on the GVI long-running operation (`video_analysis/video_analysis.ts:42-43`).
   - A try/catch does not stop a timeout. If adapter work pushes the handler past 180 s, the instance is killed before `:223`. The media then stays `isProcessing: true`, its segments are never encrypted or copied to the CDN, and the plaintext stays in the transcoder bucket.
   - The existing code is already fragile here. `previewOutputFiles.length` at `:215` throws if no previews sheet was found (`previewOutputFiles` is only set inside `if (previewsName)`, `:116-138`), and that also skips encryption.

   → **design concern** (high)

   → Fixes:
   - State that the hook is on the critical path to publishing.
   - Bound it with an explicit time budget, for example `Promise.race` with about 30 s, then skip and log.
   - Do only O(1)-ish server-side work there (see finding 2). Enqueuing the task must never throw.
   - Alternatively, put the adapter into the encryption loop instead: `onEncryptVideo` iteration −1, before the first batch (`video_encryption/video_encryption.ts:57`). That runs in its own function invocation with its own timeout.
   - Correct line 533. Publishing *is* delayed by the hook's duration, and it is blocked entirely if the hook times out.

2. **Option A: "stitch init + segments with `cat` … This needs about 1 s of work and roughly 1.44 MB/min … fits the 180 s / 1 GiB function for typical lengths"** (line 523)
   → The 0.05 s `cat` in §6.3 was measured on local disk.
   - In the function, the cost is dominated by **N separate GCS downloads**, one per 6 s segment: 601 for 1 h, 901 for 90 min. Then comes one upload of 86–130 MB.
   - Cloud Functions gen2 `/tmp` is an in-memory filesystem that counts against the 1 GiB.
   - Expause's maximum length is **90 min**, not 1 h:
     - Flutter Remote Config default `contentMaxSeconds => 5400` (`lib/domain/enums/remote_configs_defaults.dart:36`), enforced at `lib/presentation/utils/content_utils.dart:25`.
     - Web default `contentMaxSeconds: 5400` (`expause_web/src/domain/constants/remoteConfigDefaults.ts:202`).
     - Both can be overridden from Remote Config. The server enforces no cap.

   → **unsupported**

   → Recommend **server-side GCS `compose`** instead of download + `cat`:
   - Byte concatenation is exactly what §6.3 proved valid.
   - `compose` takes up to 32 source objects per call, and composites can be composed again. That is about 30 calls for 901 segments, with no bytes passing through the function.
   - Measure it on a 90 min job. Drop the "about 1 s" figure unless it is measured in Cloud Functions.

3. **"Cloud Tasks queues offer `maxConcurrentDispatches` and back-off [S12], which protects a self-hosted GPU box"** (line 550)
   → [S12] defines `max_concurrent_dispatches` as "the maximum number of tasks in the queue that can run at once". [S9] says a task succeeds on any 2xx. (https://docs.cloud.google.com/tasks/docs/configuring-queues, …/rest/v2/projects.locations.queues.tasks, read 2026-10-08)
   - Section 8.1 has scenewise return `202` "within seconds". So a dispatch completes when the job is *accepted*, not when it finishes.
   - Queue concurrency therefore limits only concurrent POSTs, not concurrent GPU work.
   - Cloud Tasks retries cover only acceptance failures. Processing failures after `202` are never retried by Cloud Tasks.

   → **wrong** (it contradicts the doc's own async design)

   → State that scenewise must have its own bounded work queue and retry policy. Its admission control should answer `429`/`503` when full, so that Cloud Tasks backs off ([S9] says those codes trigger a higher back-off). Cloud Tasks gives durable delivery and rate limiting of submissions only.

4. **Columns computed from two durations (§7.3 item 2; open question 4)**
   → Confirmed, and it is worse than the doc says:
   - **The Flutter client sends the trimmed length.** It sets `media.duration = _cropMillisecondsTo - _cropMillisecondsFrom` when trimmed (`lib/presentation/screens/publish/preview_content_screen.dart:194-201`).
   - Job start uses ffprobe of the untrimmed source (`transcoding/app_transcoding.ts:776-777, 810-811`).
   - **The interval itself can differ, not just the column count.**
     - Example: a 120 s source trimmed to 50 s.
     - At job start: I = 10 s, columnCount = 12. Sprites are taken on the trimmed output, so about 5 sprites at 0, 10, …, 40 s.
     - At slicing: `floor(50000/1000) = 50` gives I = 5 s and columns = 10 (`:123-124`, `:684-708`).
     - The sheet is cut into 10 tiles, and each preview's implied time is wrong by 2×.
   - Web uploads always send `timeStartExpression: null` (`expause_web/src/domain/remappers/userMedia/userMediaRemapper.ts:142`), so on web only rounding and client-vs-probe differences apply.
   - Small edge: `Math.floor(undefined/1000) ?? 15` is `NaN`, not 15 (`:123`), because `??` never fires on `NaN`.

   → **unsupported** (the doc understates it as "can differ")

   → Mark open question 4 as **answered: yes, for every trimmed Flutter upload**. In §7.3 item 2, say that `interval_frames` over the sliced previews is **untrustworthy for trimmed uploads**, both in tile boundaries and in timestamps. Recommend:
   - (a) the adapter sends the raw sheet, `columnCount` from the job config and the sheet width before `:157`; or
   - (b) the adapter re-derives tiles itself; or
   - (c) `kind: "video"` from the lowest video rendition.

   Also record the existing bug for Expause (out of scope to fix here).

5. **"Possible second sheet … unverified" (§7.3 item 3; open question 3)**
   → [S1] defines `columnCount` as "maximum number of sprites per row … default 0, which indicates no maximum limit". It defines `rowCount` as "maximum number of rows per sprite sheet. When the sprite sheet is full, a new sprite sheet is created." `interval` is "Starting from `0s`, create sprites at regular intervals" (read 2026-10-08).
   - With `rowCount: 1`, a sheet is full after `columnCount` sprites.
   - Sprites at 0, I, 2I, … below D number `ceil(D/I)`. That exceeds `floor(D/I)` whenever D is not an exact multiple of I.
   - So, per the docs, a second sheet is expected for **almost every untrimmed upload**, not only "possibly".
   - New edge: for D < I (for example a 1 s clip, I = 2), `columnCount = 0` means **no limit**, and slicing with 0 columns yields no previews.

   → **unsupported** (understated), and partly answers open question 3

   → Say "expected per [S1] whenever D mod I ≠ 0". Keep it in the open questions only for empirical confirmation on one real job (list the `previews*` objects). Note the `columnCount = 0` edge.

6. **Option B / the `segments` and `manifest` inputs carried in the Cloud Task body**
   → `tasks.create`: "The maximum task size is 100KB" (https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks/create, read 2026-10-08).
   - A 90 min job has about 901 segment URIs.
   - At about 100 bytes per `gs://` URI that is about 90 KB. Signed HTTPS URLs run to roughly 500 or more characters, which is several hundred KB.

   → **missing**

   → State the 100 KB limit. Say that `segments` must be passed by reference: a manifest URI, or a `segments_list_uri` pointing at a JSON file in the input bucket. Option A (one object) avoids the problem.

7. **"`job_id = "{mediaId}"` for idempotency. Cloud Tasks retries any non-2xx, and scenewise de-duplicates on `job_id`"** (line 530) and `JobRequest.job_id` "repeat POST with same id → same job" (line 140)
   → `tasks.create`: "Explicitly specifying a task ID enables task de-duplication"; such a call fails with `ALREADY_EXISTS`, and IDs of deleted or executed tasks are not reusable for "up to 24 hours (or 9 days …)" (same URL).

   → **design concern**
   - Also set the Cloud Task **name** (for example `sw-{mediaId}-v{n}`), so that a duplicate Pub/Sub delivery of `transcoder_topic` (at-least-once) does not create two tasks.
   - Define what "same `job_id`, different body" does: return `409 job_id_conflict`, or compare a request hash.
   - Re-processing (a model upgrade, a backfill) needs a new id. `job_id = mediaId` alone makes re-runs impossible. Use `"{mediaId}:{pipeline_rev}"` or a separate `idempotency_key`, and have results carry a `supersedes` field.

8. **"`oidcToken: {serviceAccountEmail, audience}`" for Expause → scenewise; "OIDC ID token" for scenewise → Expause callback** (lines 126, 529, 537; open question 10)
   → [S8] lists the fields (`serviceAccountEmail`, `audience`) and the roles (Service Account User granted to the Cloud Tasks service agent, plus Enqueuer). It does **not** say what the default audience is, and it does not say a non-Google endpoint can verify the token. It only says ID tokens "should generally be used for any handler running on Google Cloud" and that targets can be "any HTTP endpoint with an external IP address" (https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks, read 2026-10-08).

   → **missing**
   - A self-hosted scenewise must verify Google-signed JWTs itself: Google JWKS, `aud` equal to the configured audience, `email` on an allowlist. Put that in the contract.
   - Always set `audience` explicitly.
   - For the callback, OIDC from a non-GCP host needs a long-lived service-account key, which is a security liability. Make **HMAC the default for self-hosted deployments**, with a timestamp header, a replay window and a key id for rotation, and keep OIDC for deployments on GCP.
   - Note that Expause's existing task handlers do no auth at all (for example `content/on_task_publish_content.ts:4-8`). The new `onSceneWiseResult` must verify the request; it must not copy that pattern.

9. **Callback delivery semantics are unspecified** (§4.4, §8.2)
   → **design concern**
   - The doc does not define retry or back-off when Expause returns non-2xx or times out.
   - It does not say whether delivery is at-least-once. If it is, the handler must be idempotent on `(job_id, result_revision)`.
   - It does not define the maximum body size (prefer `vtt_uri` above some kilobyte threshold), or whether one callback or one per stage is sent.
   - It does not say how long `GET /v1/jobs/{id}` keeps results.
   - Add a `Delivery` retry policy and a `result_revision`/`attempt` field, and document the retention TTL.

10. **Errors and partial results** (§5.1)
    → `StageStatus.reason: str | None` is free text, and `JobResult.status = "failed"` has no error object. Nothing covers HTTP responses for `POST /v1/jobs` (400 validation, 409 conflict, 413 too large, 429/503 busy), or job-level failures before any stage runs (input fetch 403/404, an expired signed URL, `input_encrypted`).

    → **design concern**
    - Add `error: {code: Enum, message, retryable: bool, stage: str | None}` at job and stage level.
    - Make `reason` a closed enum: `no_audio_stream`, `no_speech`, `input_encrypted`, `input_unavailable`, `timeout`, `model_error`, `unsupported_codec`.
    - Specify the `POST` response codes.
    - Say whether `partial` triggers a callback, and whether a later retry can upgrade it.

11. **Versioning** (`schema_version: Literal["1"]`, lines 139, 291)
    → **design concern**
    - The doc has no compatibility policy (additive-only fields within a major version, behaviour on unknown fields, how a client asks for v2).
    - Results carry no per-stage output schema version.
    - Add `scenewise_version`, a declared rule ("minor versions add optional fields only; clients ignore unknown fields"), and `extra="ignore"` on outputs and `extra="forbid"` on inputs (or the reverse), stated explicitly.

12. **URI schemes `file://` and arbitrary `https://` in requests** (line 133)
    → **design concern** (security)
    - Accepting `file://` from a network request is a local-file-read vector.
    - Arbitrary `https://` is an SSRF vector (metadata server `169.254.169.254`, internal hosts).
    - Restrict both by server config: allowed schemes, a bucket and host allowlist, and `file://` only in a local/CLI mode.

13. **Plaintext copy in `gs://{SCENEWISE_IN}` for paid or encrypted content** (§8.1 A)
    → Expause encrypts every segment for paywalled and early-access content (`allowUnlock`, `unlockCharge`, `allowEarlyAccess` at `transcoding/transcode_user_video.ts:61-63, 120-122`).

    → **missing**
    - A durable plaintext `audio.m4a` (and the VTT/transcript) in another bucket bypasses that protection.
    - Specify:
      - a lifecycle delete rule on the input bucket (for example 7 days, or deletion on job completion);
      - IAM limited to the scenewise service account;
      - a `DELETE /v1/jobs/{id}` (or a purge) for Expause's account-deletion flows (`DELETE_ACCOUNT_*`, `common/app_constants.ts:132-140`).
    - Open question 6 (encrypt the VTT?) should be linked to this.

14. **Time base: "0 at the first output sample"** (line 133) and §6.3 item 5 ("`init + segment_2` alone reports `start: 12.010667`")
    → The 0.010667 s is AAC priming (512 samples at 48 kHz), which shows that the stitched audio's first PTS need not be 0. RFC 8216 §3.5 says WebVTT in HLS "SHOULD" carry `X-TIMESTAMP-MAP`, and when it is absent "the client MUST assume that the WebVTT cue time of 0 maps to an MPEG-2 timestamp of 0" (https://www.rfc-editor.org/rfc/rfc8216, read 2026-10-08).

    → **missing**
    - State that scenewise normalises cue times to the **presentation** timeline: subtract the first audio PTS, or align to the video track's first PTS when both are known.
    - Say whether VTT output includes `X-TIMESTAMP-MAP` when it is meant for HLS packaging.
    - Add this to open question 2 (does Transcoder's first audio `tfdt` start at 0?).

15. **"faster-whisper batched mode … caps each speech chunk at 30 s … with no overlap, because the cuts fall in silence"** (line 409)
    → `vad.py` at `9fa78645` says chunks longer than `max_speech_duration_s` "will be split at the timestamp of the last silence that lasts more than 98ms … Otherwise, they will be split aggressively just before max_speech_duration_s" (`faster_whisper/vad.py:28-31`, `min_silence_at_max_speech = 98`, `:47`).
    - Batched mode also forces `condition_on_previous_text=False` (`transcribe.py:549`), while sequential mode defaults to `True` (`:277`).

    → **unsupported** (overstated)

    → Say "cuts fall in silence *when a silence of at least 98 ms exists within the 30 s budget*; otherwise mid-speech". Note that the sequential and batched rows also differ in conditioning on previous text, which partly explains their WER and robustness differences.

16. **Experiment reproducibility** (§6.2)
    → **unsupported** (method under-specified)
    - The script and data are not committed, and the text is not published. Commit them, or at least the TTS text and the commands.
    - The per-segment rows do not say whether each segment ran through sequential `transcribe` or the batched pipeline, or whether VAD was on. With VAD, a 6 s segment may be trimmed further.
    - The doc does not say whether the 18 segments were batched together (a batched per-segment run would amortise wall time even though FLOPs stay 5×).
    - "2.1–2.8 s" implies repeated runs, but the number of runs and the warm or cold state are not stated.
    - The text normaliser is unnamed; name it (for example Whisper's `EnglishTextNormalizer`).
    - The arithmetic checks out: +49 % = (104.26 + 17 × 3) / 104.26; 6.7× and 9.2× WER; 2.7–4.5× and 3.1–5.5× wall time.

17. **"Stitched, batched + VAD … 0.9 %" vs "sequential … 1.1 %"** (table, line 427-428; summary "0.9–1.1 %")
    → 104 s of TTS is about 250–280 words, so 0.2 percentage points is about **half a word**. The doc treats the two stitched modes as distinguishable by WER (line 428 is bold).

    → **minor**

    → Report error counts next to the percentages. State that the two stitched modes are tied on WER for this clip and differ only in speed. The large effect (per-segment 7–13 % against about 1 %, roughly 20 against 3 errors, about one per segment boundary) is robust and plausible.

18. **Generalisation of the speed penalty** (summary line 10-12; §6.2 caveat)
    → The caveat about Parakeet is correct but sits only in §6.2. Parakeet TDT (FastConformer) has no 30 s padding, and the wall-time multipliers are Whisper-specific.

    → **minor** (over-generalisation in the summary)

    → In §1, label the speed multipliers "Whisper-family". Keep "stitch always" on the boundary and context argument, which is model-independent and enough on its own.

19. **"Hugging Face chunked pipeline, the classic overlap approach … [S7]"** (line 411-413)
    → The blog is entirely about **Wav2Vec2 (CTC)**: stride "on one side is 1/6th of the chunk_length_s", "around the chunking border, inference tends to be of poor quality", and chunking "is not technically 100% the same thing as running the model on the whole file" (https://huggingface.co/blog/asr-chunking, read 2026-10-08). The quotes are accurate and the 1.5× arithmetic is right.

    → **minor**

    → Say it is the CTC-model chunking method. Whisper in `transformers` uses a different (sequence-level) merge.

20. **"Scenewise reads the CDN bucket and decrypts … AES-128-CBC"** (§8.3) and the backfill (open question 7)
    → Correct per `encryption/encryption_manager.ts:287-299` (Node `createCipheriv("aes-128-cbc")`, default PKCS#7 padding). But the IV is the random per-media secret, while the HLS playlist advertises a constant `IV=0x1234567890abcdef…` (`encryption/encryption_storage.ts:78-79`). The whole file, including the fMP4 init segment, is encrypted, so a standard HLS AES-128 decryptor would not work.

    → **missing** (a backfill detail)

    → State that backfill decryption must use the Secret Manager IV with `shiftKeyBytes`, not the playlist IV, and must decrypt init segments as well.

21. **"`encrypt_video/{uid}`"** (line 94)
    → Correct, but it has a consequence the doc misses. The document is keyed by **user**, not media (`video_encryption/video_encryption.ts:18-20`). Two uploads by one user that finish close together overwrite `mediaId` with `merge: true`, so the first media's remaining plaintext can be orphaned in the transcoder bucket.

    → **minor**

    → Note that the "plaintext window" can be unbounded in this edge case. Scenewise must not rely on that, but it means the transcoder bucket is not a guaranteed-deleted area.

22. **"runs ffprobe on the source"** (line 39)
    → ffprobe runs on `dynamicUrl`, a client-supplied download URL (`transcoding/transcode_user_video.ts:45`, `transcoding/app_transcoding.ts:776`), not on `inputUri`.

    → **minor**

    → Say "ffprobe on the client-supplied `dynamicUrl` (normally the same raw upload)".

23. **"`payload.config.spriteSheets[0].interval`"** as the authoritative interval (line 495)
    → It is correct that `getJob` is fetched at `:47-50` and that the previews sheet is pushed first (`:826-834`). The value is a protobuf `Duration` serialised by `JSON.stringify`, so `seconds` may be a string or Long, and `nanos` may be present.

    → **minor**

    → Tell the adapter to parse it as `Number(seconds) + (nanos ?? 0) / 1e9`.

24. **`Likelihood` "same scale as GVI" / "the adapter maps them to GVI's integer positions"** (lines 366, 395-396)
    → Expause's scale is `PORNOGRAPHY_LIKELIHOODS = ['UNKNOWN', 'VERY_UNLIKELY', …]` with `ALLOWED_PORNOGRAPHY_LIKELIHOOD = 4`, and blocking is `> 4`, that is VERY_LIKELY only (`common/app_constants.ts:209-216, 229`; `transcoding/app_transcoding.ts:457-462`).

    → **minor**
    - Add `UNKNOWN` to the enum, or state that the mapping is index + 1.
    - In §8.2, the example "scenewise `LIKELY` while GVI is below threshold" should read "scenewise `VERY_LIKELY` while GVI ≤ `LIKELY`" to match the real threshold.

25. **Detection of audio-less media "by absence of `TYPE=AUDIO` in `master.m3u8`"** (§9)
    → This is supported by Expause's own parser, which expects audio as `#EXT-X-MEDIA:…TYPE=AUDIO` lines in the Transcoder master and as `audio/mp4` AdaptationSets in DASH (`transcoding/app_transcoding.ts:303-310, 369-380`). The doc does not cite this.

    → **minor**

    → Cite these lines as evidence, which strengthens §9.

26. **Open question 1 (audio file names)**
    → [S1] gives only "the default is `MuxStream.key` with the extension suffix … Individual segments also have an incremental 10-digit zero-padded suffix … such as `mux_stream0000000123.ts`". It states **no rule for init segments**; the only example is `my-hd-stream-init.m4s` under DASH `SEGMENT_LIST`.
    - The encryption code only works if everything is flat. It lists with `delimiter: '/'` (`encryption/encryption_storage.ts:153-156`), and its regex `[a-zA-Z0-9_-]+\.m4s` cannot match a path containing `/` (`:96`).
    - If Transcoder wrote per-stream subfolders, those files would never be encrypted or published, and playback would be broken. Expause playback works, so the layout is very likely flat, for example `audio_480p_fmp4{10 digits}.m4s`.
    - No real file names exist anywhere in the repos (searched `lib/`, `expause_web/src`, `cloud_functions/`, `workflow/`).

    → **minor** (partly answered)

    → Keep it open, but record "flat layout, implied by the encryption loop working". The recommendation to parse the playlist stands.

27. **WebVTT example and NOTE placement** (§5.2)
    → Correct per [S11] (CRD 20 May 2026, confirmed). Hours are "required if hours is non-zero", milliseconds are exactly 3 digits, cue ids are optional, and NOTE blocks are allowed before the first cue with text on the same line.

    → **minor**

    → Note that a STYLE block, if added later, must come before the first cue.

## Open questions answered

- **Q4 (mis-slicing): answered, yes.** Flutter trimmed uploads send the trimmed duration (`lib/presentation/screens/publish/preview_content_screen.dart:194-201`), while job start probes the untrimmed source. Both the interval and the column count can differ (finding 4). Web never trims (`expause_web/src/domain/remappers/userMedia/userMediaRemapper.ts:142`).
- **Q3 (second sheet): answered on paper.** By [S1]'s `rowCount` semantics and sprites taken from 0 s, a second sheet occurs whenever D mod I ≠ 0. That is almost always for untrimmed uploads. It still needs one real-job listing to confirm (finding 5).
- **Q5 (headroom; maximum duration): answered for the duration.**
  - The maximum is **5400 s (90 min)** by Remote Config default on both clients (`lib/domain/enums/remote_configs_defaults.dart:36`, `expause_web/src/domain/constants/remoteConfigDefaults.ts:202`).
  - Flutter's `longVideoSecondsDuration = 3600` (`lib/domain/constants/app_constants.dart:41`) is used for some flows.
  - At 90 min that is about 901 audio segments and about 130 MB at 192 kbps.
  - The doc's download + `cat` inside the 180 s / 1 GiB handler is risky at that size. Use GCS `compose` (findings 1 and 2).
- **Q1 (file names): partly answered.** The layout is flat, implied by the encryption loop. The init segment name is still unknown (finding 26).

## Verified as correct (brief)

- §3.1:
  - The callable checks (`transcode_user_video.ts:30-39`); the media doc fields with no `hasAudio` (`:86-138`); the resolutions and the output URI (`:141-150`); `UPLOAD_MEDIA_PATH_SEGMENT` (`common/app_constants.ts:69`).
  - `getVideoMetadata` `hasAudio` (`app_transcoding.ts:572-618`, `:597`); only `resolution` persisted (`:793-799`); trim (`:854-862`); resolution filter (`:801-807`).
  - Video ES/mux with a 3 s GOP and 6 s fMP4 segments (`:878-905`); audio gated on `hasAudio`, `aac` 192 kbps per resolution, `audio_{res}p_fmp4` (`:915-934`).
  - Manifests (`:847-851`, constants `:61-66`); sprite config, the 1280 long side and `quality: 60` (`:819-842`, `:108`); topic (`:844`).
  - The interval table and `columnCount = floor(D/I)` (`:684-715`).
- §3.2: `transcodeJobUpdated` 180 s / 1 GiB / 1 CPU (`transcode_job_updated.ts:8-17, 35-37`). Every step and line in `onTranscodeJobSucceeded` (`:40-245`): the thumbnail move (`:83-102`), `findStorageFile` first match (`storage/app_storage.ts:33-47`, `:40`), rename (`:105-118`), `tileWidth` (`:735`), uploads with `max-age=604800` (`:137-154`), sheet delete (`:157`), light manifests (`:165-199`), `previews` write (`:201-208`), analysis (`:215`), encryption trigger (`:223`), raw delete (`:241-244`).
- §3.3: the synthetic video (`video_analysis.ts:15`; `app_transcoding.ts:955-980`, at least 5 s); the GVI request and features (`:34-42`); the return shape (`:46-47`); label handling with the last segment's confidence and the top 10 (`app_transcoding.ts:426-445`); max likelihood (`:447-462`); writes (`:467-529`, `:531-564`). No GVI timestamps are used.
- §3.4:
  - Key and IV secrets XOR-masked with sha256(name) (`encryption_manager.ts:38-50, 216-249`).
  - The `encrypt_video` trigger, the 100-object flat listing, the iteration re-fire and `completeContentProcessing` (`video_encryption.ts:18-31, 44-108`; `encryption_storage.ts:150-161`; `app_constants.ts:135`; `content_utils.ts:330, 378`).
  - Whole-file AES-128-CBC of every object including `.m4s` and init, upload to the CDN under the same name, plaintext deletion (`encryption_storage.ts:51, 73-138`).
  - Previews and thumbnail never encrypted.
- §3.5: the storage table; chat and community `hasAudio` gating (`chat_video_transcoding.ts:206`, `community_video_transcoding.ts:217`); `analyzeVideo` has a single caller (`:414`).
- §3.6: four HTTP-target task kinds, none with `oidcToken`; the queue names (`cloud_tasks_utils.ts`; `app_constants.ts:2-5`).
- External sources:
  - Whisper: `CHUNK_LENGTH = 30`, `N_SAMPLES`, `pad_or_trim` "as expected by the encoder" [S3].
  - faster-whisper `pad_or_trim` to 3000 frames (`audio.py:117-129`); used in batched (`transcribe.py:517`) and sequential (`:1185`) paths; VAD `max_speech_duration_s=chunk_length` (`:396-425`); batched VAD on by default (README) [S4][S5].
  - WhisperX "twelve-fold transcription speedup" and "drifting, hallucination & repetition" [S6].
  - RFC 8216 §3.3: `tfdt` in every `traf`, init = `ftyp` + `moov` [S10]. RFC 8216 §4.3.4.2.1: SUBTITLES renditions need a Media Playlist URI (open question 6 is correct).
  - Cloud Tasks: 2xx means success, otherwise retried; `dispatchDeadline` 15 s–30 min, default 10 min [S8][S9].
  - Transcoder sprite and segment naming with a 10-digit suffix; `interval` starts at 0 s; `startTimeOffset` on the output timeline [S1].
- Arithmetic: +49 % audio; 1.44 MB/min; 6–9× WER; 2.7–4.4× and 3–5.5× wall time; HF 1.5× for 30 s / 5 s strides.
