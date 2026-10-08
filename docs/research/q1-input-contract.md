# Q1 — Input contract and the Expause adapter

Research date: 2026-10-08. Revision r3, final (addresses `reviews/q1-review-r1.md` and `reviews/q1-review-r2.md`; aligned with the final `q8a-architecture-layout.md`). Every external source was read on 2026-10-08. Source IDs such as [S1] refer to the **Sources** section. Every Expause claim cites `file:line` at Expause HEAD `32ed0bf18` (2026-09-22), relative to `/Users/daniel/Work/expause/cloud_functions/functions/src/functions/` unless the path starts with `lib/` (Flutter) or `expause_web/`. The Expause code was read only, never changed. The Expause-side changes described here are a design, to be built in Expause later. Anything not verified is listed under **Open questions**.

Settled user decisions that apply here (`user-decisions.md`): scenewise is a **complement** to Expause's primary moderation/label signal (U1); Python 3.12+ (U2); the operator is EU-based (U3); **Parakeet TDT is the default ASR**, faster-whisper the fallback (U4). Parakeet does not pad its input to 30 s the way Whisper does, which matters for section 6.

---

## 1. Summary and recommendation

- **Captions run over one continuous audio track, never per 6-second segment.** The argument that holds for any model is about boundaries and context: a word cut at a segment edge is lost, and each segment starts with no context. On one 104 s TTS clip cut into Expause-style 6 s fMP4 AAC segments (section 6, *indicative*: one synthetic clip, Whisper models only):
  - Independent per-segment transcription made **26 errors in 349 words (7.4 % WER)** with `base.en` and **45 (12.9 %)** with `small.en`. The stitched track made **3–4 (0.9–1.1 %)** and **5–6 (1.4–1.7 %)**. That is about one extra error per segment boundary.
  - The wall-time penalty (per-segment 2.7–5.0× slower than stitched with batched VAD) is **Whisper-specific**: each 6 s segment pays a full 30 s encoder pass. Parakeet, the default (U4), does not pad, so its speed penalty is not known and probably smaller. The accuracy argument alone is enough to require one track.
- **Who stitches: nobody, by default.** Expause's Transcoder job gets one extra **standalone audio-only MP4 mux stream** (`container: "mp4"`, built from the existing lowest-resolution AAC elementary stream, not added to any manifest). The Transcoder then writes one continuous `scenewise_audio.mp4` next to the HLS/DASH output [S1]. Per Google's pricing, an audio stream in a job that already has video "counts as complimentary" [S15]. Scenewise still accepts `segments` (by reference) and `manifest` inputs and stitches them itself, for other callers and for backfills.
- **Trigger: the Expause success handler only copies two or three objects and enqueues one Cloud Task, under a hard time budget, and never throws.** It **copies** (never moves or deletes) `scenewise_audio.mp4` and the raw previews sprite sheet(s) to a private staging bucket. The sources stay where they are, and the encryption loop deletes them **without downloading or encrypting them** (a mandatory one-line rule, section 8.3). So nothing the hook does, even after its timeout, can make an object disappear under the encryption loop. Then it enqueues a Cloud Task whose body is a generic `JobRequest` of about 1–2 KB, built by Expause. It holds **object references, not segment lists** (Cloud Tasks caps a task at 100 KB [S13]). Encryption and publishing then go ahead as today. The delay is a few server-side GCS operations (the copy latency for a 90 min, ~130 MB file is an open question). Nothing is downloaded or stitched inside the 180 s handler (section 8).
- **Execution follows q8a's settled contract: `POST /v1/jobs` is a synchronous Cloud Tasks push handler.**
  - It returns `200` + `JobRecord` only when the job is terminal (succeeded, partial or failed). A duplicate of a finished job is acknowledged with `200`. A body with a readable `job_id` that fails validation gets a terminal `failed`/`invalid_request` record and `200`; only a body with no usable `job_id` gets `422`.
  - A job still running gets `503` + `Retry-After`. A full admission limiter gives `429` + `Retry-After`. A digest mismatch (same `job_id`, different body) gets `200` with `outcome: "rejected"` and a `job_id_conflict` problem, and no record is written (q8a §6.2 step 8). Cloud Tasks backs off harder on `429`/`503` and honours `Retry-After` [S9].
  - **The Cloud Tasks queue is the work queue.** Scenewise keeps a durable job record in GCS (lease, attempt counter, conditional writes) and always writes a failure record before the final `200`.
  - Deadlines: Cloud Run and `dispatchDeadline` are both 1800 s, and scenewise's budget is 1500 s. Media that will not fit is rejected up front with `exceeds_push_budget`, which Expause records as its own status (section 8.5).
- **Idempotency:** `job_id = "um-{mediaId}-r{rev}"` (fits q8a's final `JobId` pattern `^[A-Za-z0-9._:-]{1,200}$`, not `.` or `..`). The Cloud Task name is a hash of `job_id`, so duplicate Pub/Sub deliveries are de-duplicated (Pub/Sub is at-least-once [S22]; Cloud Tasks rejects a name that is still retained with `ALREADY_EXISTS` [S13]). Names are retained for *up to* 24 h, so this is best-effort, not a guaranteed window. Scenewise's job record de-duplicates execution: the same `job_id` with the same request digest is acknowledged, and a different body is rejected (`job_id_conflict`, in a `200`). Re-processing uses `rev + 1` and `supersedes`. Reconciliation re-enqueues under a **distinct** task name (section 8.3 step 6).
- **Visual input:** the raw Transcoder sprite sheet(s), with grid, interval, offset and tile size **all supplied explicitly** from the Transcoder job config. Scenewise never infers them. The `previewNNNN.jpeg` files Expause slices today are **wrong for every trimmed Flutter upload** (section 7.3, recorded as Expause issue E1).
- **Results back:** the push response goes to Cloud Tasks, not to Expause, so Expause cannot use the response body.
  - **Recommended:** Expause reads the **job record and `result.json` in GCS**, in buckets it owns. A Cloud Storage `onObjectFinalized` trigger on `status.json` tells it when to read [S29]. Delivery is at-least-once [S30], so the handler is idempotent.
  - A daily reconciliation does `GET /v1/jobs/{id}` for anything without a terminal record.
  - Optional: q8a's HTTP callback, used only as a hint. It is authenticated with an OIDC ID token on GCP [S23], or with Standard-Webhooks HMAC elsewhere [S20].
- **Plaintext lifecycle:** all copies (staging, record, results) live in Expause-owned buckets.
  - The staging bucket has soft delete off (the default is 7 days [S19]), a lifecycle delete at 3 days as a backstop [S18], and read-only access for scenewise.
  - **The transcoder bucket must have soft delete off too.** Every plaintext object deleted there (the copied sources, every segment the encryption loop deletes) otherwise stays restorable for 7 days. Its current setting was not read (Expause issue E13).
  - Expause deletes the staging prefix when it ingests the terminal record. Account deletion is a prefix delete on Expause's side, with no scenewise endpoint needed.
- **Input URIs are allow-listed:** `gs://` on configured buckets and `https://` on configured hosts only, with no redirects and no private or link-local addresses [S21]. `file://` is accepted only in CLI/local mode, never by the HTTP service.
- **Audio-less videos:** the Transcoder writes no audio at all (`transcoding/app_transcoding.ts:910-935`), so `scenewise_audio.mp4` does not exist. The task says `has_audio: false`. Scenewise reports `captions.status = "skipped"` with `reason = "no_audio_stream"`, which is different from `no_speech` (section 9).

---

## 2. Scope

This document covers what scenewise accepts and returns at its boundary, and the design of the Expause adapter. The adapter is built later, **in Expause**, against the generic contract: scenewise contains no Expause code (q8a §1.3). Model choice is out of scope (see Q2–Q5). Execution, the job record, status codes and the error hierarchy are settled by Q8a (`q8a-architecture-layout.md` §6–§8). Section 8.5 restates them, and Q1 adopts them. Where Q1 disagrees, the objection is under **Open questions** with both sides stated.

---

## 3. Expause pipeline as verified

### 3.1 Upload and job start (user-generated video)

1. The client uploads the raw file to the **default bucket** (`DEFAULT_BUCKET_NAME`) at `filePath`, then calls the callable `transcodeUserVideo` (`transcoding/transcode_user_video.ts:8`). The callable checks that `filePath` has 3 parts and that the second part is the caller's uid (`:30-39`).
2. The callable writes `users/{uid}/media/{mediaId}` with `isProcessing: true`, `previews: []`, the client-supplied `duration` (ms) and other fields, including `allowUnlock`, `unlockCharge` and `allowEarlyAccess` (`:61-63`, `:86-138`). The document has **no `hasAudio` field**.
3. `startTranscoderJob` is called with input `gs://{DEFAULT_BUCKET}/{filePath}`, output `gs://{TRANSCODER_BUCKET}/media/{uid}/{mediaId}/` and resolutions `[2160, 1080, 720, 480]` (`:141-150`). `UPLOAD_MEDIA_PATH_SEGMENT = 'media'` (`common/app_constants.ts:69`).
4. `startTranscoderJob` (`transcoding/app_transcoding.ts:766-953`) works as follows:
   - It runs ffprobe on **`dynamicUrl`, a URL the client supplies** (normally the download URL of the same raw upload) (`transcoding/transcode_user_video.ts:45`, `transcoding/app_transcoding.ts:776`, `getVideoMetadata` at `:572-618`). It gets `hasAudio = streams.some(codec_type === "audio")` (`:597`). It persists only `resolution` (`:793-799`).
   - Optional trim: `editList[0].startTimeOffset` and `endTimeOffset` come from `timeStartExpression` and `timeEndExpression` (`:854-862`). Flutter sends them when the user trims. Web always sends `null` (`expause_web/src/domain/remappers/userMedia/userMediaRemapper.ts:142`).
   - It keeps only resolutions at or below the input's short side. If none qualify, it uses the input resolution (`:801-807`).
   - **Video:** one H.264 elementary stream per resolution with `gopDuration` 3 s (`:878-896`). Each is muxed as `container: "fmp4"`, `segmentDuration: 6 s`, `individualSegments: true`, with mux key `video{res}p_fmp4` (`:899-905`).
   - **Audio:** only `if (hasAudio)` (`:915`). There is **one AAC stream per video resolution**, `audio_{res}p`, `{codec: "aac", bitrateBps: 192000}` (`:916-922`). Each is muxed separately as fMP4 with 6 s individual segments, key `audio_{res}p_fmp4` (`:925-931`). The audio renditions are identical copies (same codec and bitrate), up to 4 of them.
   - **Manifests:** HLS `master.m3u8` and DASH `manifest.mpd` (`:847-851`, names at `common/app_constants.ts:61-66`). Every mux stream is added to both (`:907-908`, `:933-934`).
   - **Sprite sheets** (`:819-842`):
     - Previews: `filePrefix: "previews"`, `interval: {seconds: previewsIntervalSeconds}`, `columnCount`, `rowCount: 1`, `quality: 60`. Only the long side is set to 1280 px: `spriteWidthPixels` for landscape, `spriteHeightPixels` for portrait, and the Transcoder computes the other side (`:819-834`; `UPLOAD_PREVIEWS_WIDTH = 1280` at `common/app_constants.ts:108`).
     - Thumbnail: `totalCount: 1` (`:835-842`).
   - Completion is signalled on Pub/Sub topic `transcoder_topic` (`:844`).
5. `computeSpriteSheetPreviewsParams(duration)` (`transcoding/app_transcoding.ts:684-715`) sets the preview interval:

   | Duration (s) | Interval I |
   |---|---|
   | ≤15 | 2 s |
   | ≤30 | 3 s |
   | ≤60 | 5 s |
   | ≤300 | 10 s |
   | ≤600 | 20 s |
   | ≤1800 | 40 s |
   | longer | 60 s |

   `columnCount = floor(duration / I)` and `rowCount = 1` (`:707-708`). At job start, `duration` is the **ffprobe duration of the untrimmed source** (`:776-777`, `:810-811`).
6. **Maximum duration: 90 min.** The Remote Config default `contentMaxSeconds` is 5400 on both clients (`lib/domain/enums/remote_configs_defaults.dart:36`, enforced at `lib/presentation/utils/content_utils.dart:22-27`; `expause_web/src/domain/constants/remoteConfigDefaults.ts:202`). It can be overridden remotely, and the server enforces no cap. At 90 min there are about 901 audio segments per rendition and about 130 MB of audio at 192 kbps.

### 3.2 Transcoder success handler

`transcodeJobUpdated` is a Pub/Sub function on `transcoder_topic` with `timeoutSeconds: 180`, 1 GiB, 1 CPU and **`concurrency: 80`** (so up to 80 handlers share one instance's 1 GiB). It sets no retry option (`transcoding/transcode_job_updated.ts:8-17`). On `SUCCEEDED` it awaits `onTranscodeJobSucceeded(jobName)` (`:35-37`). That handler (`transcoding/app_transcoding.ts:40-245`):

1. Fetches the Transcoder job with `getJob` and JSON round-trips it into `payload` (`:47-50`). It reads `uid` and `mediaId` from the output URI (`:52-56`) and loads the media document (`:58-67`).
2. Moves the thumbnail from the transcoder bucket to the **CDN bucket** at `media/{uid}/{mediaId}/thumbnail.jpeg`, then deletes the original (`:83-102`).
3. Finds the previews sprite sheet. `findStorageFile` returns the **first** object whose name contains `"previews"` (`storage/app_storage.ts:33-47`, `:40`). The handler renames it to `previews.jpeg` (`transcoding/app_transcoding.ts:105-118`).
   - It recomputes the interval and `columnCount` from **`media.duration` (client-supplied, ms) / 1000** (`:123-124`), downloads the sheet (`:127`) and crops it into `preview0000.jpeg`, `preview0001.jpeg`, … with ffmpeg.
   - `tileWidth = floor(sheetWidth / columnCount)`, 1 row (`:719-764`, `:735`).
4. Uploads each preview to the **CDN bucket** at `media/{uid}/{mediaId}/previewNNNN.jpeg`, unencrypted, with `cacheControl: public, max-age=604800` (`:137-154`). It then deletes the sprite sheet from the transcoder bucket (`:157`).
5. Builds `master_light.m3u8` and `manifest_light.mpd` (with 1080p and 2160p removed) in the transcoder bucket (`:165-199`). The parser expects audio as `#EXT-X-MEDIA:…TYPE=AUDIO` lines in HLS (`:303-310`) and as `audio/mp4` AdaptationSets in DASH (`:369-380`).
6. Writes `previews: [encoded paths]` to the media document (`:201-208`).
7. Runs **video analysis** on the local previews (`:215`, which calls `analyzePreviewsVideo` at `:411-420`). This waits synchronously on the GVI long-running operation (`video_analysis/video_analysis.ts:42-43`). Its errors are caught (`:417-419`). But `previewOutputFiles.length` at `:215` throws if no sheet was found, because `previewOutputFiles` is only set inside `if (previewsName)` (`:116-138`).
8. Calls **`triggerVideoEncryption(uid, mediaId)`** (`:223`). This is reached **only on the try path**.
9. The `catch` (`:224-239`) sets `isProcessing: false` **without starting encryption**.
10. Deletes the original upload from the default bucket (`:241-244`).

**Consequence for any hook placed here:** it is on the critical path to publishing. A thrown error lands in the catch, and the media is never encrypted. A timeout kills the instance before `:223`. In both cases the media keeps plaintext segments in the transcoder bucket and none in the CDN bucket. A try/catch does not protect against the 180 s timeout.

### 3.3 Video analysis (GVI)

- `analyzeVideo` builds a **synthetic video** from the preview JPEGs (`video_analysis/video_analysis.ts:15`). `createSyntheticVideo` (`transcoding/app_transcoding.ts:955-980`) stretches the frames to at least 5 s at an adjusted frame rate (libx264).
- The video is sent as base64 `inputContent` with `features: ['LABEL_DETECTION', 'EXPLICIT_CONTENT_DETECTION']` (`video_analysis/video_analysis.ts:34-42`). The function returns `[segmentLabelAnnotations, explicitAnnotation]` (`:46-47`).
- How the results are used:
  - **Labels:** only `entity.description` and the last segment's `confidence`, sorted, top `analyzeVideoMaxLabels` (`transcoding/app_transcoding.ts:426-445`).
  - **Explicit content:** the max `pornographyLikelihood` over frames, as an index into `PORNOGRAPHY_LIKELIHOODS = ['UNKNOWN', 'VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE', 'LIKELY', 'VERY_LIKELY']`. `blocked` is set when the index is `> ALLOWED_PORNOGRAPHY_LIKELIHOOD = 4`, which means **VERY_LIKELY only** (`common/app_constants.ts:209-216`, `:229`; `transcoding/app_transcoding.ts:447-462`).
  - The handler writes `contentTags`, `tags`, `explicit` and `blocked` (`:467-529`) and increments `contenttags/*` (`:531-564`).
  - **No GVI timestamp is used.** Any timestamp would be on the synthetic timeline anyway.
- GVI is deprecated and shuts down on 2027-09-14. Expause moves its primary signal elsewhere, and scenewise stays a complement (U1).

### 3.4 Encryption: what, when, where

- `triggerVideoEncryption` (`video_encryption/video_encryption.ts:7-35`):
  - Creates two Secret Manager secrets per media: the AES key `{EXPAUSE_MEDIA_CDN_VIDEO_SECRET_KEY_PREFIX}{mediaId}` and the IV `{EXPAUSE_MEDIA_CDN_IV_SECRET_KEY_PREFIX}{mediaId}`. Each holds 16 random bytes, XOR-masked with sha256(secretName) (`encryption/encryption_manager.ts:216-249`, `:38-50`).
  - Writes `encrypt_video/{uid}` = `{userId, mediaId, timestamp, iteration: -1}` with `merge: true` (`video_encryption/video_encryption.ts:18-31`). The document is keyed by **user**, not media. A second upload by the same user that finishes while the first is still encrypting overwrites `mediaId` (Expause issue E7). Two trigger chains then run on the second media's prefix and race on the same objects (section 10, E7).
- `onEncryptVideo` is a Firestore trigger on `encrypt_video/{id}` (`:44-108`). It fires as soon as that document is written. On each write it:
  - Lists up to `ENCRYPT_VIDEO_STORAGE_FILE_SIZE = 100` objects **directly** under `media/{uid}/{mediaId}/` in the **transcoder bucket**, with `delimiter: '/'` (`encryption/encryption_storage.ts:150-161`, `common/app_constants.ts:135`). Objects in sub-folders and objects in other buckets are never listed.
  - Processes them in a batch, sleeps 1 s, and re-fires itself by incrementing `iteration` (`video_encryption/video_encryption.ts:82-89`) until nothing is left. It then calls `completeContentProcessing` (`:98-103`), which sets `isProcessing: false` (`content/content_utils.ts:330`, `:378`).
- `manageEncryptVideoStorageBatch` (`encryption/encryption_storage.ts:15-148`), for **every** listed object:
  1. Downloads it (`:51`). Any error from here to the upload (including a `404` because the object vanished after the listing) sets `hasErrors` and `break`s the batch (`:140-144`). `onEncryptVideo` then deletes the `encrypt_video` document and marks the media `hasErrors: true`, leaving every remaining plaintext object unencrypted and unpublished (`video_encryption/video_encryption.ts:61-78`). The delete in step 5 is the only tolerant step (its own try/catch, `encryption_storage.ts:129-138`).
  2. For `.m3u8` files other than the two masters, inserts `#EXT-X-KEY:METHOD=AES-128,URI="hlsScheme://www.expause.com/{mediaId}",IV=0x1234567890abcdef1234567890abcdef` and rewrites `.m4s` references (regex `[a-zA-Z0-9_-]+\.m4s`, so no `/` in names) to absolute `{CDN_NAME}media/{uid}/{mediaId}/{name}.m4s` (`:73-105`, regex at `:96`).
  3. Encrypts the **whole file** with `aes-128-cbc` (Node default PKCS#7 padding), using the per-media Secret Manager key and IV. It does not use the constant IV in the playlist (`:108-113`, `encryption/encryption_manager.ts:287-299`). The call is not filtered by extension, so audio `.m4s` and init segments are encrypted too.
  4. Uploads the result to the **CDN bucket** at the **same object name** (`encryption/encryption_storage.ts:123-127`).
  5. **Deletes the plaintext original** from the transcoder bucket (`:129-138`).
- **Conclusion:** plaintext audio exists only in `gs://{TRANSCODER_BUCKET}/media/{uid}/{mediaId}/`, from Transcoder `SUCCEEDED` until the encryption batch reaches it. That starts right after `app_transcoding.ts:223`. Because of E5, E6 and E7, the transcoder bucket is **not** a guaranteed-deleted area. Scenewise must not rely on that either way.
- **Not encrypted:** the thumbnail and the `previewNNNN.jpeg` files in the CDN bucket (`transcoding/app_transcoding.ts:94-96`, `:148-150`).

### 3.5 Storage locations (user-generated video)

| What | Bucket | Path | Lifetime |
|---|---|---|---|
| Raw upload | `DEFAULT_BUCKET_NAME` | `{filePath}` (3 segments, 2nd = uid) | Deleted at the end of the success handler (`transcoding/app_transcoding.ts:241-244`) |
| Transcoder output (plaintext) | `TRANSCODER_BUCKET_NAME` | `media/{uid}/{mediaId}/` (flat) | Until the encryption loop encrypts it to the CDN and deletes it (section 3.4); restorable afterwards for the soft-delete window (E13) |
| Previews sprite sheet | transcoder | `media/{uid}/{mediaId}/previews.jpeg` (after rename) | Today: deleted at `:157`. Proposed: left in place, copied by the hook, deleted by the encryption loop without download (section 8.3) |
| Thumbnail, previews | `CDN_BUCKET_NAME` | `media/{uid}/{mediaId}/thumbnail.jpeg`, `previewNNNN.jpeg` | Permanent, plaintext |
| Encrypted segments, playlists, manifests | CDN | `media/{uid}/{mediaId}/{same name}` | Permanent, AES-128-CBC |
| **Proposed:** scenewise staging | new `SCENEWISE_STAGING_BUCKET` | `user_media/{uid}/{mediaId}/r{rev}/` | Deleted by Expause on terminal-record intake; 3-day lifecycle backstop (section 8.7) |

- Chat and community videos use the same pattern under `chat/{u1}/{u2}/{docId}/` and `community/{owner}/{msgId}/` (`common/app_constants.ts:70-93`), with the same `hasAudio` gating (`transcoding/chat_video_transcoding.ts:206`, `transcoding/community_video_transcoding.ts:217`).
- Only the user-generated path calls `analyzeVideo` (the sole caller is `transcoding/app_transcoding.ts:414`).

### 3.6 Existing Cloud Tasks usage

- `cloud_tasks/cloud_tasks_utils.ts` creates four kinds of HTTP-target task: auto-renew subscriptions, scheduled content, video-boost end and campaign end (`:6-135`). Each sends `POST` to `CLOULD_FUNCTIONS_URL + <functionName>` with a base64 JSON body and a `scheduleTime`. The queues are named in `common/app_constants.ts:2-5`.
- **None of them sets `oidcToken` or a task name, and the receiving handlers do no authentication in code.** For example, `onTaskPublishContent` is a bare `https.onRequest` that publishes whatever `contentId` it is sent (`content/on_task_publish_content.ts:4-8`), and `onTaskAutoRenewExclusiveSubscription` runs `handleUserSubscription(userId, peerId, true, true)` for any body (`user_subscriptions/on_task_auto_renew_exclusive_subscription.ts:4-8`). Because the tasks carry no token, the functions must accept unauthenticated invocations for scheduling to work. This is **inferred from code**: `setGlobalOptions({region: "europe-west1", preserveExternalChanges: true})` (`src/index.ts:12`) means the deployed IAM may differ from the repo, so the deployed `run.invoker` binding must be confirmed (Expause issue E8). The scenewise integration must not copy this pattern.
- Pub/Sub is already used for Transcoder completion (`transcoding/transcode_job_updated.ts:8-10`).

---

## 4. Input contract

The shapes below are pydantic v2 and illustrative. Q8a owns the concrete module (`service/http/schemas.py`). Scenewise has no Expause-specific schema.

### 4.0 Conventions

- **Time base.** All times are float seconds on the **presentation timeline of the output media**. 0 is the first presented sample after any trim and after edit lists and AAC priming are applied, which is the instant a player shows as 0:00. See section 5.4 for how scenewise normalises audio to it.
- **Versioning.**
  - `schema_version` is the major version of the contract. Within a major version, changes are **additive and optional only**.
  - **Inputs** are `extra="forbid"`: an unknown field fails with `invalid_request`, so typos and version skew fail loudly. With a readable `job_id` that is a terminal `failed` record and `200` (q8a §6.2 step 4); without one it is `422`.
  - **Outputs** are documented as "clients must ignore unknown fields". Pydantic's default `extra="ignore"` does this for Python clients [S25].
  - A breaking change is `schema_version: "2"`. The service accepts both versions for one deprecation window.
  - Every result carries `scenewise_version` and the per-stage model ids.
- **URI policy (security).** Requests name inputs by URI, and the service fetches them. That makes the service an SSRF target. Following OWASP [S21]:
  - `gs://{bucket}/…` is accepted only for buckets in `Settings.inputs.allowed_gcs_buckets`.
  - `https://` is accepted only for hosts in `Settings.inputs.allowed_https_hosts` (exact host match, port 443). Redirects are not followed. Each resolved address is checked, and loopback, private (RFC 1918, ULA), link-local (including the metadata address `169.254.169.254`) and unspecified ranges are refused. The client connects only to the validated address, which defends against DNS rebinding [S21].
  - `file://` and bare paths are accepted **only by the CLI / library entry point** (`Settings.inputs.allow_local_paths`). The HTTP service refuses them, whatever the configuration.
  - Every other scheme (`http`, `ftp`, ffmpeg protocols such as `concat:`, `data:`) is refused.
  - A refusal is an `InputError` with `code = "uri_not_allowed"`. It ends in a terminal `failed` record and a `200` (q8a §6.2 step 5), so it is never retried. URIs are never passed to ffmpeg/ffprobe directly. Scenewise fetches them through its `BlobStore` port into a local temp file first, so ffmpeg's own protocol handlers never see a remote URL.
- **Credentials** are scenewise configuration, never request fields.
- **Size.** The `POST` body is capped at 1 MiB (`413`, rejected before parsing, so no record). This is reachable only by direct callers: a Cloud Tasks body is at most 100 KB [S13]. Long lists are passed **by reference** (section 4.2).

### 4.1 Job request envelope

```python
class JobRequest(BaseModel, extra="forbid"):
    schema_version: Literal["1"]
    job_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,200}$")   # and not "." or ".." (q8a JobId, final)
        # caller-chosen idempotency key, also one GCS path segment; see 8.5. Expause: "um-{mediaId}-r{rev}"
    supersedes: str | None = None        # job_id this run replaces (re-processing); echoed in the result
    external_ref: dict[str, str] = {}    # opaque, echoed back
    stages: list[StageName]              # "captions" | "summary" | "chapters" | "moderation" | "labels"
    media: MediaInfo = MediaInfo()
    audio: AudioInput | None = None      # required if "captions" requested (may be kind="none")
    visual: VisualInput | None = None    # required if "moderation" or "labels" requested
    context: TextContext | None = None   # optional title/description/hashtags
    options: StageOptions = StageOptions()
    delivery: Delivery

class MediaInfo(BaseModel, extra="forbid"):
    duration_s: float | None = None      # output-timeline duration if known; scenewise re-probes
    has_audio: bool | None = None        # caller's belief; None = unknown, scenewise probes
    # future additive field (not in v1; sending it fails with invalid_request): video_start_s (5.4)

class TextContext(BaseModel, extra="forbid"):
    title: str | None = Field(None, max_length=1000)
    description: str | None = Field(None, max_length=10000)
    tags: list[str] = Field([], max_length=100)

class StageOptions(BaseModel, extra="forbid"):
    language_hint: str | None = None     # BCP-47, e.g. "en"
    labels_max: int = 20
    summary_max_chars: int = 500
    chapters_min_duration_s: float = 30.0
    include_words: bool = False          # also emit words.json (5.2)
    # future additive field (not in v1): hls_timestamp_map_mpegts (5.4)
```

Which input each stage needs:

| Stage | Needs | Also uses |
|---|---|---|
| captions | `audio` | `options.language_hint` |
| summary | transcript (from captions) and/or `visual` | `context` |
| chapters | transcript (from captions) and/or `visual` | `context` |
| moderation | `visual` | transcript, if captions ran |
| labels | `visual` | transcript, `context` |

Summary and chapters can run on visual input alone when there is no audio, at lower quality (see Q3).

### 4.2 Audio input

```python
class AudioFile(BaseModel, extra="forbid"):          # one video or audio file; ffmpeg probes and extracts audio
    kind: Literal["file"]
    uri: str
    mime: str | None = None

class AudioSegments(BaseModel, extra="forbid"):      # fMP4/CMAF: init + ordered media segments, stitched by scenewise
    kind: Literal["segments"]
    container: Literal["fmp4", "mpegts"] = "fmp4"
    init_uri: str | None = None          # required for fmp4
    # exactly one of the next two:
    segments: list[SegmentRef] | None = Field(None, max_length=200)   # inline, small jobs only
    segments_list_uri: str | None = None # JSON array of SegmentRef in the input bucket (by reference)

class SegmentRef(BaseModel, extra="forbid"):
    uri: str                             # absolute, or relative to the list/manifest location
    duration_s: float | None = None      # informative; timing comes from tfdt in fMP4

class AudioManifest(BaseModel, extra="forbid"):      # an HLS media/master playlist or DASH MPD; segments resolved by scenewise
    kind: Literal["manifest"]
    uri: str
    format: Literal["hls", "dash"]
    rendition: str | None = None         # e.g. "audio_480p_fmp4"; default = lowest-bandwidth audio

class NoAudio(BaseModel, extra="forbid"):            # caller knows there is no audio track
    kind: Literal["none"]
    reason: Literal["source_has_no_audio"] = "source_has_no_audio"

AudioInput = Annotated[AudioFile | AudioSegments | AudioManifest | NoAudio, Field(discriminator="kind")]
```

Rules:

- `segments` and `manifest` are always **stitched** into one track before ASR (section 6). The service never transcribes segments independently.
- Segment lists go **by reference** when they are long (`segments_list_uri` or `manifest`). The inline `segments` list is capped at 200 entries. A Cloud Tasks body is limited to 100 KB [S13]: a 90 min job has about 901 segments, which is about 90 KB as `gs://` URIs and several hundred KB as signed URLs.
- Every URI a manifest or list points to goes through the same URI policy (section 4.0). A playlist cannot be used to reach a host that is not on the allow-list.
- Encrypted inputs are **not accepted**. An `#EXT-X-KEY` other than `METHOD=NONE`, or an undecodable stream, fails the job with `input_encrypted`.
- If a `file` has no audio stream, scenewise treats it as `none` and reports this (section 9).

### 4.3 Visual input

The rule for every timed visual input: **time, grid and geometry are supplied explicitly. Scenewise never infers an interval, offset, grid or tile size from image sizes or counts.** A request that is inconsistent (for example a sheet not divisible into the stated tiles) fails with `invalid_sprite_grid` and is not retried.

```python
class VideoForFrames(BaseModel, extra="forbid"):     # scenewise samples frames itself; times come from the container
    kind: Literal["video"]
    uri: str                             # or a manifest URI with format
    format: Literal["file", "hls", "dash"] = "file"
    sampling: Literal["interval", "scene"] = "interval"
    interval_s: float = 2.0

class TimedFrame(BaseModel, extra="forbid"):
    uri: str
    t_s: float                           # presentation time of the frame

class Frames(BaseModel, extra="forbid"):             # arbitrary images with explicit times
    kind: Literal["frames"]
    frames: list[TimedFrame] = Field(max_length=2000)

class IntervalFrames(BaseModel, extra="forbid"):     # ordered thumbnails, one every interval_s
    kind: Literal["interval_frames"]
    uri_template: str                    # e.g. "gs://b/p/preview{index:04d}.jpeg"; by reference, no list
    count: int
    interval_s: float                    # required; index i ↔ t = start_offset_s + i * interval_s
    start_offset_s: float                # required, no default

class SpriteSheets(BaseModel, extra="forbid"):
    kind: Literal["sprite_sheet"]
    sheets: list[str] = Field(min_length=1, max_length=100)
        # explicit sheet URIs, in order (q8a domain SpriteSheets.sheets). No prefix form:
        # q8a's BlobStore has no list operation, and the producer knows the names anyway.
    grid: Grid                           # required: columns and rows per FULL sheet
    tile: TileSize                       # required: pixel size of one tile
    interval_s: float                    # required
    start_offset_s: float                # required (Transcoder: startTimeOffset, default 0)
    count: int | None = None             # total real tiles; None = tiles that fit each sheet's actual pixel size

class Grid(BaseModel, extra="forbid"):
    columns: int = Field(ge=1)
    rows: int = Field(ge=1)
    order: Literal["row_major"] = "row_major"

class TileSize(BaseModel, extra="forbid"):
    width: int = Field(ge=1)
    height: int = Field(ge=1)

VisualInput = Annotated[VideoForFrames | Frames | IntervalFrames | SpriteSheets, Field(discriminator="kind")]
```

### 4.4 Delivery

```python
class HttpCallback(BaseModel, extra="forbid"):
    kind: Literal["http"]
    url: str                             # must match Settings.delivery.allowed_callback_urls (prefix match)
    auth: Literal["hmac", "oidc"] = "hmac"
    key_id: str | None = None            # hmac: which configured secret to sign with
    audience: str | None = None          # oidc: REQUIRED when auth="oidc"; never defaulted

class NoNotify(BaseModel, extra="forbid"):           # the caller reads the job record (recommended for Expause)
    kind: Literal["none"]

class ArtifactSink(BaseModel, extra="forbid"):       # where result.json and captions.vtt are written
    uri_prefix: str | None = None        # e.g. gs://expause-scenewise-results/user_media/{uid}/{mediaId}/r{rev}/
                                         # None = {state_prefix}/{job_id}/ (q8a §6.2)
                                         # must be on the allow-list (writes are an exfiltration vector too)

class Delivery(BaseModel, extra="forbid"):
    notify: HttpCallback | NoNotify = NoNotify()
    artifacts: ArtifactSink = ArtifactSink()
```

- Results are always written as objects (`result.json`, `captions.vtt`), and the job record points at them (`result_uri`). There is no inline-only mode, because the record is the contract.
- The callback is q8a's `Notifier` port. It is a hint sent after the terminal record is written (section 8.6).
- Pub/Sub delivery is out of v1 (q8a §12).
- Secrets, the OIDC service account and the allow-lists are server configuration.

---

## 5. Output contract

### 5.1 Job record and result document

There are two documents, both in GCS (q8a §6.2):

- **`{state_prefix}/{job_id}/status.json`, the `JobRecord`.** Small, written with compare-and-swap, and returned as the `200` body of `POST /v1/jobs` and by `GET /v1/jobs/{id}`. Fields per q8a: `job_id`, `state` (`RUNNING` | `SUCCEEDED` | `PARTIAL` | `FAILED`; on the wire `running` | `retry_wait` | `succeeded` | `partial` | `failed`, where `retry_wait` is a `RUNNING` record whose lease has expired), `attempt`, `lease_until`, `request_digest`, `error_code`, `result_uri`, `updated_at`. Q1 asks for three more fields, `schema_version`, `scenewise_version` and `external_ref`, so that a consumer reading the record from an event can route it without parsing `result.json` (open question 13).
- **`{artifacts.uri_prefix or state_prefix/job_id}/a{attempt}/result.json`, the `JobResult`.** Written before the terminal record, and pointed to by `result_uri`. Artifact paths are attempt-scoped (q8a §6.2), so consumers must follow `result_uri` and never build the path themselves.

```python
class JobResult(BaseModel):              # outputs: clients ignore unknown fields
    schema_version: Literal["1"]
    scenewise_version: str               # e.g. "0.1.0"
    job_id: str
    supersedes: str | None
    external_ref: dict[str, str]
    status: Literal["succeeded", "partial", "failed"]
    error: ErrorInfo | None              # set when status == "failed" (job-level error)
    media: ProbedMedia | None            # None if the job failed before probing
    stages: StageResults
    timings_ms: dict[str, int]           # per stage, for cost tracking
    models: dict[str, str]               # stage -> model id + version actually used
    attempt: int                         # from the job record (q8a JobRecord.attempt)
    created_at: datetime; finished_at: datetime

class ErrorInfo(BaseModel):
    code: str                            # one of the codes below
    category: Literal["input", "retryable", "internal"]   # q8a §8
    retryable: bool                      # == (category == "retryable")
    message: str                         # human-readable, not for parsing
    stage: StageName | None = None

class ProbedMedia(BaseModel):
    duration_s: float
    has_audio: bool
    audio_source: Literal["file", "segments", "manifest", "none"]
    audio_start_offset_s: float          # first audio PTS removed during normalisation (5.4)
    visual_source: Literal["video", "frames", "interval_frames", "sprite_sheet"] | None
    frames_analyzed: int

class StageStatus(BaseModel):
    status: Literal["succeeded", "skipped", "failed"]
    reason: str | None = None            # SkipReason when skipped; error code when failed (q8a StageOutcome.reason);
                                         # the one allowed value on a succeeded stage is "no_speech" (captions, section 9)
    error: ErrorInfo | None = None       # when status == "failed"

class StageResults(BaseModel):
    captions: CaptionsResult | None = None
    summary: SummaryResult | None = None
    chapters: ChaptersResult | None = None
    moderation: ModerationResult | None = None
    labels: LabelsResult | None = None
```

**Error codes** are q8a's (§8), grouped by category. A code only ever appears in the body of a `200` (a terminal record) or of a `413`/`422`/`429`/`503` problem (and the `job_id_conflict` problem inside a `200` rejection, q8a §6.2 step 8).

| Category | Codes (q8a) | Q1 proposes adding | Where it lands |
|---|---|---|---|
| `input` (never retried) | `invalid_request`, `uri_not_allowed`, `job_id_conflict`, `corrupt_media`, `invalid_sprite_grid`, `input_encrypted`, `stage_unavailable`, `media_too_large`, `exceeds_push_budget`, `unsupported_media`, `manifest_unsupported` | `input_unavailable` (input 404, or 403 after in-attempt retries) | Before stages: terminal `failed` record + `200`. Inside a stage: that stage fails and the job is `partial` |
| `retryable` | `backend_unavailable`, `storage_unavailable`, `job_in_progress`; `CapacityError` (429) | — | Fails the attempt: the record is released and the response is `503`/`429` + `Retry-After`. After `max_attempts`, a terminal `failed` record with `attempts_exhausted` |
| `internal` (never retried) | `model_output_invalid`, `resource_exhausted`, `deadline_exceeded`, `invariant_violation`, `attempts_exhausted`, `unexpected` | — | Inside a stage: that stage fails and the job is `partial`. Otherwise: a terminal `failed` record + `200` |

| `SkipReason` | Meaning |
|---|---|
| `no_audio_stream` | No audio track (`audio.kind = "none"`, or the probe found none) |
| `no_speech` | Audio present, no speech detected (with `status = "succeeded"`, `cue_count = 0`) |
| `not_requested` | Stage not in `stages` |
| `dependency_failed` | A prerequisite failed (e.g. summary needed the transcript and no visual input was given) |

**Job status rules** (q8a §5, §8):
- `succeeded`: every requested stage succeeded or was skipped.
- `partial`: at least one requested stage failed.
- `failed`: a job-level error, raised before the stages run or when attempts are exhausted.
- Bad LLM JSON and GPU OOM are retried **inside the stage**. A stage failure never triggers a whole-job retry.
- Exactly one terminal record exists per `job_id`. There is no "upgrade" of a `partial` result under the same `job_id`. To re-run, the caller submits a new `job_id` (`rev + 1`, `supersedes`).

### 5.2 Captions: WebVTT plus a JSON descriptor

```python
class CaptionsResult(StageStatus):
    language: str | None                 # BCP-47 detected/used
    vtt_uri: str | None                  # {artifacts prefix}/captions.vtt
    words_uri: str | None                # when options.include_words
    cue_count: int = 0
    speech_seconds: float = 0.0
```

The VTT file follows W3C WebVTT [S11]:

- The file opens with the header `WEBVTT`.
- An optional `NOTE` block before the first cue carries the scenewise version and job id. Any `STYLE` block added later must also come before the first cue [S11].
- Cue times are on the presentation timeline (`HH:MM:SS.mmm --> HH:MM:SS.mmm`, with hours optional when zero and exactly 3 millisecond digits). Cue ids are optional and sequential.
- No `X-TIMESTAMP-MAP` by default (section 5.4).

```
WEBVTT

NOTE scenewise 0.1.0 job=um-abc123-r1 lang=en

1
00:00:00.480 --> 00:00:03.920
The old lighthouse stood at the edge of the cliff
```

Word-level timings are optional (`options.include_words`) as `words.json`, `[{"w": "lighthouse", "start_s": 1.02, "end_s": 1.51}]`. They are for search and chapters and are not part of the VTT.

### 5.3 Summary, chapters, moderation, labels (JSON)

```python
class SummaryResult(StageStatus):
    short: str | None                    # ≤ 1 sentence
    long: str | None                     # ≤ options.summary_max_chars
    language: str | None
    inputs_used: list[Literal["transcript", "frames", "context"]]

class Chapter(BaseModel):
    start_s: float
    end_s: float
    title: str
    summary: str | None = None

class ChaptersResult(StageStatus):
    chapters: list[Chapter]              # contiguous, sorted, cover [0, duration_s]

Likelihood = Literal["UNKNOWN", "VERY_UNLIKELY", "UNLIKELY", "POSSIBLE", "LIKELY", "VERY_LIKELY"]
    # same names and order as GVI / Expause's PORNOGRAPHY_LIKELIHOODS; integer index = list position

class Evidence(BaseModel):
    t_s: float
    source: Literal["frame", "transcript"]
    frame_index: int | None = None       # index into the resolved frame list (7.1)
    text: str | None = None              # transcript excerpt

class ModerationCategory(BaseModel):
    category: str                        # Q4 owns the list
    likelihood: Likelihood
    score: float                         # 0..1, model-native, for thresholds
    evidence: list[Evidence] = []

class ModerationResult(StageStatus):
    categories: list[ModerationCategory]
    max_likelihood: Likelihood
    # complement only (U1): no allow/block verdict

class Label(BaseModel):
    name: str
    confidence: float                    # 0..1
    segments: list[tuple[float, float]] = []   # presentation-time [start_s, end_s) where seen
    source: Literal["frames", "transcript", "both"]

class LabelsResult(StageStatus):
    labels: list[Label]                  # sorted by confidence desc, ≤ options.labels_max
```

- `Likelihood` uses GVI's names **including `UNKNOWN`**, in the same order as Expause's `PORNOGRAPHY_LIKELIHOODS` (`common/app_constants.ts:209-216`). The Expause adapter maps a value to its index without translation, so it can be compared with `ALLOWED_PORNOGRAPHY_LIKELIHOOD = 4` (`:229`). Q4 owns the category list.

### 5.4 Time alignment (AAC priming, offsets, HLS)

- **What was measured (local, [L1]; mechanism corrected in r3).** In the ffmpeg-made fMP4 HLS, the `#EXTINF` durations repeat `6.016000, 5.994667, 5.994667, 5.994667` (re-checked on a 60 s sine with the same build: `6.016, 5.994667 ×3, 6.016, 5.994667 ×3, 6.016, 5.994667, 0.021333`).
  - **Cause: AAC frame quantisation, not priming.** An AAC frame is 1024 samples, so 6 s at 48 kHz is 281.25 frames. The HLS muxer cuts at the first frame boundary at or after k × 6 s, so segments run 282/281/281/281 frames, i.e. 6.016000/5.994667 s. The 0.021333 s difference is one frame and would appear with zero priming.
  - **Priming is presented, not trimmed.** The `elst` box in ffmpeg's `init.mp4` is `entry_count=1, segment_duration=0, media_time=0, rate=1.0` (re-checked by reading the box bytes). The encoder's 1024 priming samples (about 21 ms of leading silence) therefore stay in the presented timeline.
  - The stitched `init + all segments` file reports `start: 0.000000` because the first fragment's `tfdt` is 0, not because of an edit list. `init + segment_2` alone reports `start: 12.010667`, which is 563 frames × 1024 / 48000, the cumulative cut point.
- **Rule (unchanged).** Scenewise decodes with edit lists applied and then subtracts the probed first audio presentation timestamp (`ProbedMedia.audio_start_offset_s`), so cue time 0 is presentation time 0. When the priming is presented (ffmpeg's `media_time = 0`), the remaining error against the video is at most the priming, about 21 ms at 48 kHz (1024 samples): below one video frame and not visible in captions. A future additive `media.video_start_s` (not in v1) would let a caller whose video starts at a non-zero PTS align to that instead.
- **Not verified for Transcoder output:** whether its first audio `tfdt` starts at 0, and whether its fMP4 init or standalone MP4 writes a non-zero `elst media_time` (which would trim the priming). This is open question 2. The rule above holds either way.
- **HLS packaging.** RFC 8216 §3.5: a WebVTT segment "SHOULD" carry `X-TIMESTAMP-MAP`. When it is absent, "the client MUST assume that the WebVTT cue time of 0 maps to an MPEG-2 timestamp of 0" [S10]. Scenewise emits a **sidecar** VTT (for `<track>` or a player API) **without** `X-TIMESTAMP-MAP`. If Expause later packages captions as an HLS `SUBTITLES` rendition (open question 6), it would pass a future additive `options.hls_timestamp_map_mpegts` (not in v1; the 90 kHz PTS of presentation 0 in its video segments), and scenewise writes `X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:<n>`.

---

## 6. Segment vs stitched captions

### 6.1 How the reference tools handle long audio

- **The Whisper encoder always consumes a 30 s window.**
  - `openai/whisper`: `CHUNK_LENGTH = 30`, `N_SAMPLES = 480000`, and `pad_or_trim` pads or trims "to N_SAMPLES, as expected by the encoder" [S3].
  - faster-whisper pads every window's mel features to 3000 frames (30 s) before encoding. Sequential path: `transcribe.py:1185`. Batched path: `transcribe.py:517`. Function: `audio.py:117-129` (commit `9fa78645`) [S4].
  - **So in Whisper-family models a 6 s segment costs a full 30 s encoder pass: 5× the encoder compute per second of audio.** Parakeet TDT (FastConformer), the default ASR (U4), does not pad to 30 s, so this compute penalty does not carry over (Q2).
- **faster-whisper sequential mode** seeks through the track window by window, without overlap, and by default conditions on the previous text (`condition_on_previous_text=True`, `transcribe.py:277`) [S4].
- **faster-whisper batched mode** runs Silero VAD and caps each speech chunk at `max_speech_duration_s = chunk_length` (30 s), with no overlap (`transcribe.py:396-425`). Chunks longer than that are split "at the timestamp of the last silence that lasts more than `min_silence_at_max_speech`" (98 ms), and "otherwise, they will be split aggressively just before `max_speech_duration_s`" (`vad.py:28-31`, `:47`). So cuts fall in silence **when a silence of at least 98 ms exists within the 30 s budget**, and mid-speech otherwise. Batched mode also forces `condition_on_previous_text=False` (`transcribe.py:549`) [S4][S5].
- **WhisperX** uses the same idea ("VAD Cut & Merge"). It reports a 12× speed-up from batching, and attributes drift, hallucination and repetition to sequential buffered transcription [S6].
- **Hugging Face chunking with stride, for CTC models (Wav2Vec2).** Chunks of `chunk_length_s` with a stride on each side of, by default, chunk/6. The edge output is discarded and the rest stitched. With 30 s chunks and 5 s strides each step advances 20 s, so the model is fed **1.5× the audio**. The authors say plain chunking degrades "around the chunking border", and that the strided result is not "100% the same" as whole-file inference [S7]. This blog covers CTC models. Whisper in `transformers` uses a different, sequence-level merge.

### 6.2 Measurement (indicative)

**Status: indicative, Whisper-specific.** It is one 104 s synthetic TTS clip, so it is not a benchmark. The script was recovered and re-run for this revision. Method, exactly:

- **Hardware and software:** Apple M4, CPU, Python 3.9 venv, faster-whisper 1.2.1, CTranslate2 4.8.2, `compute_type="int8"`, `cpu_threads=4`, `beam_size=1`, `language="en"`. The models were `base.en` and `small.en`. Before timing, one 5 s warm-up transcription ran in the same process (warm model, cold nothing else).
- **Input:** 104.26 s of English TTS (macOS `say`), reference text of **349 words** after normalisation. Encoded as AAC 192 kbps 48 kHz mono, then cut by ffmpeg's HLS muxer (`-hls_segment_type fmp4 -hls_time 6`) into **18 fMP4 segments plus an init segment**.
- **Audio prep:** each input is decoded by ffmpeg to 16 kHz mono float32 PCM.
  - Per-segment input: `init + segment_i`.
  - Stitched input: `init + all segments`.
- **Strategies:**
  1. **Stitched, sequential:** `model.transcribe(full, condition_on_previous_text=True)`, with VAD off (the faster-whisper default for sequential mode).
  2. **Stitched, batched + VAD:** `BatchedInferencePipeline.transcribe(full, batch_size=8)`, with VAD on (the batched default) and `condition_on_previous_text=False` (forced).
  3. **Per 6 s segment, independent:** a **sequential** `model.transcribe(segment, vad_filter=False)` call for each of the 18 segments, one after the other (**not batched**), and the texts joined.
  4. **Per 6 s segment, ±1.5 s overlap:** windows `[s0 − 1.5, s1 + 1.5]` cut from the stitched PCM, a sequential `transcribe(word_timestamps=True, vad_filter=False)` call on each, and a word kept if its midpoint lies in `[s0, s1)`.
- **WER:** word-level Levenshtein against the reference, after a simple normaliser (lowercase, every non-`[a-z0-9 ]` character → space, split on whitespace). It is **not** Whisper's `EnglishTextNormalizer`.
- **Runs:**
  - The original r1 table came from several invocations of the script. Their number was not recorded.
  - For r2, `base.en` was re-run **3 times**. WER was **identical in all runs** (decoding is deterministic at `beam_size=1`).
  - Wall times varied by up to 2.5×, because the machine was shared with other work. Wall times are therefore indicative only.
  - `small.en` was not re-run.

| Strategy | Audio fed | `base.en` errors / WER | `small.en` errors / WER | `base.en` wall (r1; r2 ×3) | `small.en` wall (r1) |
|---|---|---|---|---|---|
| Stitched, sequential (30 s windows) | 1.00× | 4 / 1.1 % | 6 / 1.7 % | 3.1–3.9 s; 8.1, 3.3, 4.4 s | 9.6 s |
| Stitched, batched + VAD (no overlap) | 1.00× | 3 / 0.9 % | 5 / 1.4 % | 2.1–2.8 s; 4.8, 2.2, 3.4 s | 6.1 s |
| Per 6 s segment, independent | 1.00× | 26 / 7.4 % | 45 / 12.9 % | 7.5–8.5 s; 13.7, 11.0, 11.0 s | 27.2 s |
| Per 6 s segment, ±1.5 s overlap | 1.49× | 4 / 1.1 % | 5 / 1.4 % | 8.8–11.2 s; 9.7, 14.0, 12.5 s | 33.8 s |

What the table shows:

- **Robust:** independent per-segment transcription adds about **22 errors (base.en) and 40 (small.en) on 17 internal boundaries**, about one or more per boundary, from cut words and lost context. This mechanism is model-independent.
- **Not distinguishable:** the two stitched modes differ by **one word** (3 vs 4, and 5 vs 6). They are tied on WER for this clip. They also differ in VAD and in conditioning on previous text, so this clip cannot separate those effects.
- **Overlap** restores accuracy, but feeds 49 % more audio (= (104.26 + 17 × 3) / 104.26).
- **Wall time (Whisper only, indicative):** paired within each run, per-segment independent was **2.7–5.0×** slower than stitched-batched (r1 range bounds 2.7–4.0; r2 runs 2.85, 5.0, 3.2; `small.en` 4.5), and overlap **2.0–6.4×** (r1 3.1–5.3; r2 2.0, 6.4, 3.7; `small.en` 5.5). The r1 invocations were not recorded individually, so their bounds pair the extremes of the two ranges. The cause is the 30 s padding (section 6.1). These ratios **do not apply to Parakeet**, whose per-segment cost was not measured (open question 9).
- The stitched track needs the whole audio track. That is no constraint here: inputs are VOD only, and with the design in section 8 the Transcoder produces one continuous file.

Caveats: synthetic TTS speech is cleaner than user video, there is one clip and one language, and the work was CPU only. The scripts and reference text live in the session scratchpad (`scratchpad/scripts/seg_vs_stitched.py`, `scratchpad/speech/ref.txt`). They should be committed under `bench/` when the scenewise repo gets code (Q8b owns the location).

### 6.3 Stitching fMP4 AAC segments with ffmpeg

What I verified locally with ffmpeg 7.1 (the imageio-ffmpeg static build) [L1]:

1. ffmpeg's HLS muxer (`-hls_segment_type fmp4 -hls_time 6`) wrote 4 segments plus `init.mp4` for 20 s of AAC, and 601 segments for 1 h.
2. `cat init.mp4 segment_*.m4s > stitched.mp4` decodes with no errors. Duration was 20.02 s for the 20 s source and 01:00:00.02 for the 1 h source.
3. Remuxing with `ffmpeg -i stitched.mp4 -c copy out.m4a` also works. So does reading the playlist directly with `ffmpeg -i audio.m3u8 -c copy out.m4a`.
4. Local cost for 1 h on an M4 disk: `cat` 0.05 s, `-c copy` remux 0.23 s, decode to 16 kHz mono WAV 1.19 s. This is **local disk only**. Fetching 601–901 objects from GCS costs far more and was not measured, which is why section 8 avoids stitching inside an Expause function.

Why this works: RFC 8216 §3.3 requires every fMP4 segment's Track Fragment Box to contain a `tfdt`. The init section is an `ftyp` and `moov` with `mvex`, and segments are `moof` plus `mdat` [S10]. Init followed by fragments is therefore a valid fragmented MP4, and timestamps survive stitching (see section 5.4 for frame quantisation and priming).

Not verified: that Google Transcoder's own audio fMP4 output stitches the same way (open question 2). It matters only for the `segments`/`manifest` path (backfill, other callers). The default Expause path uses the Transcoder's standalone MP4.

### 6.4 Recommendation

- Always feed ASR one continuous track: the Transcoder's standalone file for Expause, or scenewise's own stitch for segment and manifest inputs. Then run VAD-chunked ASR over the whole track (Q2 owns the chunking for Parakeet).
- Per-segment ASR is never used. Live input is out of scope.

---

## 7. Sprite sheet mapping

### 7.1 General rule (scenewise)

Given `columns` (C), `rows` (R), `tile` (W×H), `interval_s` (I) and `start_offset_s` (O), all **supplied by the caller**, take sheets in order and tiles in row-major order. For the global tile index `k`, from 0:

```
per_sheet = C * R
sheet     = k // per_sheet
r         = (k % per_sheet) // C
c         = k % C
t_k       = O + k * I                      # seconds, presentation timeline
crop      = (x = c * W, y = r * H, w = W, h = H)
```

- Validation: every sheet except the last must be exactly `C*W × R*H` pixels. The last sheet must be at most that size and a whole number of tiles in each dimension. Anything else fails with `invalid_sprite_grid`.
- Tile count: with `count`, tiles at index ≥ `count` are ignored. Without `count`, the last sheet contributes the tiles that fit its actual pixel size. **No blank-tile detection is done.** If a producer pads a partial sheet with blank tiles, the caller must send `count`.
- Scenewise resolves every visual input (video, frames, interval frames, sprites) into one internal list of `TimedFrame(t_s, image)`. `Evidence.frame_index` and `Label.segments` refer to that list and its `t_s`.
- A label seen in consecutive frames `k..m` is reported as `[t_k, t_m + I)`, clamped to `duration_s`.

### 7.2 Transcoder semantics [S1]

- `interval`: "Starting from `0s`, create sprites at regular intervals." `startTimeOffset` is "relative to the output file timeline" and defaults to 0.
- `columnCount`: "The maximum number of sprites per row in a sprite sheet", where 0 means no limit. `rowCount`: "The maximum number of rows per sprite sheet. When the sprite sheet is full, a new sprite sheet is created", where 0 means no limit.
- Sheet files are `{filePrefix}{10-digit zero-padded index}.jpeg`.
- Only one of `spriteWidthPixels` / `spriteHeightPixels` needs to be set, so that the aspect ratio is preserved.
- So for Expause, `t_k = k × I` with `O = 0`, on the **trimmed output** timeline.

### 7.3 Expause specifics: the sliced previews are not usable as timed frames

1. **Mis-slicing for every trimmed Flutter upload (confirmed; Expause issue E1).**
   - Job start computes `I` and `columnCount` from the **untrimmed** ffprobe duration (`transcoding/app_transcoding.ts:776-777`, `:810-811`).
   - Slicing recomputes both from `media.duration`. Flutter sets that to the **trimmed** length, `_cropMillisecondsTo - _cropMillisecondsFrom` (`lib/presentation/screens/publish/preview_content_screen.dart:194-201`; slicing at `transcoding/app_transcoding.ts:123-124`).
   - **Example:** a 120 s source trimmed to 50 s. Job start gives I = 10 s and C = 12, and the Transcoder takes sprites at 0, 10, 20, 30, 40 s of the trimmed output. Slicing gives I = 5 s and C = 10, so the sheet is cut into 10 tiles of the wrong width. Each `previewNNNN.jpeg` is a wrong crop, and its implied time is off by 2×.
   - Untrimmed uploads (all web uploads, because web sends `timeStartExpression: null`, `expause_web/src/domain/remappers/userMedia/userMediaRemapper.ts:142`) are exposed only to client-vs-probe duration differences.
   - **Contract consequence:** scenewise must never be given a frame list whose times or geometry Expause *infers* from `media.duration`. The adapter sends the **raw sheets** with `grid`, `tile`, `interval_s` and `start_offset_s` taken from the Transcoder job config.
2. **A second sheet is expected, not just possible (per [S1]; Expause issue E2).** Sprites at 0, I, 2I, … below the output duration D number `ceil(D/I)`. `columnCount = floor(D_source/I)` with `rowCount: 1`. Whenever `D mod I ≠ 0`, the last sprite starts `previews0000000001.jpeg`. `findStorageFile` takes only the first match (`storage/app_storage.ts:40`). The second sheet stays in the transcoder prefix and is encrypted and copied to the CDN by the encryption loop, unread. It still needs one real-job listing to confirm empirically (open question 3).
3. **`columnCount = 0` when D < I** (for example a 1 s clip with I = 2; Expause issue E3). The Transcoder reads 0 as "no limit". Slicing computes `tileWidth = floor(width / 0)`, so no previews are produced.
4. **`Math.floor(mediaDuration / 1000) ?? 15`** (`transcoding/app_transcoding.ts:123`) yields `NaN`, not 15, when `duration` is missing, because `??` never fires on `NaN`. In `computeSpriteSheetPreviewsParams(NaN)` every `<=` test is false, so the interval falls through to **60 s**, `columnCount = floor(NaN / 60) = NaN`, and `Array.from({length: NaN})` is empty: no previews (`:684-715`; Expause issue E4).
5. **Authoritative values for the adapter:** `onTranscodeJobSucceeded` already has the job config (`:47-50`), and the previews sheet is `spriteSheets[0]` (`:826-834`).
   - `interval` is a protobuf `Duration` that has been through `JSON.stringify`, so `seconds` may be a number, a string, or a stringified protobufjs `Long` object `{low, high, unsigned}` (for which `Number()` is `NaN`), and `nanos` may be present. Parse `seconds` as `typeof s === "object" && s !== null ? s.low + s.high * 2 ** 32 : Number(s ?? 0)`, add `(nanos ?? 0) / 1e9`, and reject a non-finite result (skip the job, log). `startTimeOffset` is parsed the same way (absent = 0).
   - `columnCount` and `rowCount` are taken as written in the config, not recomputed.
   - Tile size: `rowCount = 1`, so `tile.height` is the sheet height. `tile.width` is `spriteWidthPixels` when set (landscape). For portrait (`spriteHeightPixels` set), `tile.width` is the first sheet's width / `columnCount`. The first sheet is always full when `columnCount ≥ 1`, because `ceil(D/I) ≥ floor(D_source/I)` for untrimmed uploads. For trimmed uploads the output can have fewer sprites than `columnCount`, so the first sheet may be partial. Expause's adapter (built in Expause) therefore derives the portrait width as `sheet_height × source_aspect`, using the `resolution` and aspect it receives in the payload, and rounds to the even pixel count the Transcoder requires [S1]. For `columnCount = 0`, `grid.columns = count = 1`.
   - `count`: the adapter sends `ceil((D_out − O) / I)` when the output duration is known (the probed duration of `scenewise_audio.mp4`, or the trim from the job config's `editList`). Otherwise it omits `count`, and the geometry rule in section 7.1 applies.
6. **Chosen Expause visual input:** `sprite_sheet` over the **raw sheet(s)**, copied to staging and listed explicitly in `sheets` (section 8.3). The Transcoder's sprites are the same frames GVI sees today (before Expause's mis-slice), so the complement compares like with like. Option, later: `kind: "video"` over the lowest video rendition for denser sampling. This costs more vision compute and would need another standalone mux stream, whose billing is unverified.

---

## 8. Trigger and delivery

### 8.1 Constraints (verified)

| # | Constraint | Source |
|---|---|---|
| C1 | The success handler has a 180 s hard timeout, no retry, 1 GiB shared by up to 80 concurrent invocations, and already waits on GVI | `transcoding/transcode_job_updated.ts:8-17`; `video_analysis/video_analysis.ts:42-43` |
| C2 | Anything that throws or times out before `triggerVideoEncryption` leaves the media unencrypted and unpublished on the CDN | `transcoding/app_transcoding.ts:223-239` |
| C3 | Plaintext under `media/{uid}/{mediaId}/` (flat) is deleted within seconds to minutes after `:223` (but stays restorable for the bucket's soft-delete window, 7 days by default [S19], unless that is 0; E13). Sub-folders and other buckets are never touched. An object that disappears between the loop's listing and its download aborts encryption for the whole media (`hasErrors`, section 3.4) | `encryption/encryption_storage.ts:129-144`, `:150-161`; `video_encryption/video_encryption.ts:61-78` |
| C4 | Up to 90 min of video: about 901 audio segments, about 130 MB of AAC | section 3.1 item 6 |
| C5 | A Cloud Task body is at most 100 KB. A named task de-duplicates (`ALREADY_EXISTS`) while its name is retained: "up to 24 hours (or 9 days …)" after deletion or execution. That is an upper bound on retention, not a guaranteed de-duplication window, and a recently deleted name also blocks a deliberate re-create. Hashed names are recommended over sequential ones | [S13] |
| C6 | A Cloud Tasks HTTP dispatch succeeds on 2xx, retries everything else, backs off harder on 429/503, honours `Retry-After`, and has a dispatch deadline of 15 s–30 min | [S9] |
| C7 | Pub/Sub (`transcoder_topic`) is at-least-once and may redeliver after an ack | [S22] |
| C8 | Paywalled and early-access media are encrypted to protect them (`allowUnlock`, `unlockCharge`, `allowEarlyAccess`) | `transcoding/transcode_user_video.ts:61-63`, `:120-122` |

### 8.2 Options for getting plaintext audio to scenewise

| Option | Work in the 180 s handler | Delays publishing | Plaintext stays readable because | Verdict |
|---|---|---|---|---|
| **A.** Handler downloads 900 segments, `cat`s them, uploads `audio.m4a` (r1 default) | about 900 GETs + one 130 MB upload, through in-memory `/tmp` shared by 80 invocations | Yes, unbounded; a timeout blocks publishing entirely (C2) | it is copied out before `:223` | **Rejected** (C1, C2) |
| **B.** Handler runs GCS `compose` (≤32 sources per call [S16]) into one object | about 30 compose calls (29 + 1 for 901 segments) plus a listing; no bytes through the function | Yes, seconds, on the critical path | the composite is created before `:223` | Rejected as default: dozens of calls on the critical path for nothing B does better than E. The [S16] page shows only same-bucket examples, so cross-bucket compose is unverified |
| **C.** Scenewise reads the segments straight from the transcoder prefix | none | No | it is not: encryption deletes them within minutes (C3) | **Rejected**: a race that scenewise loses under any queueing |
| **D.** Encryption loop copies the lowest audio rendition's files to staging before its delete, and enqueues the task when the loop finishes; scenewise stitches from the staged playlist | none | Slightly: about 900 extra server-side copies spread across the loop's batches | it is copied before the loop deletes it | **Fallback.** No Transcoder change, but the trigger sits behind E7 (the `encrypt_video/{uid}` overwrite can drop it), more Expause code, and scenewise has to stitch |
| **E.** The Transcoder writes one extra **standalone audio MP4**. The handler copies it (and the raw sprite sheets) to staging, then enqueues; the encryption loop deletes the sources unread | 2–3 server-side copies + 1 `createTask`, under a hard budget | Yes, by the copy latency (one 130 MB same-location server-side rewrite; single request per [S17]; latency unmeasured, open question 11). Budget-capped | the copy lives outside the encryption prefix | **Chosen** |
| F. Delay encryption until scenewise is done | none | Yes, by the full AI latency | encryption waits | Rejected: publishing must not wait for AI |
| G. Scenewise decrypts from the CDN | none | No | not needed | Rejected for new media: it couples an open-source service to Expause's key scheme. Kept as an **adapter-side backfill** only (section 8.9) |

**Trade-off of E, stated plainly.**
- It costs one Transcoder config change, which applies to new jobs only, and a few hundred milliseconds to a few seconds on the publishing path. The exact time is unmeasured, and it is hard-capped.
- In return there is no stitching anywhere, there are no segment lists, and there is no race with encryption. Scenewise reads one file whenever its queue reaches the job, hours later if need be.
- The cost of the extra output is nil per the pricing page: in a job with any video elementary stream, the audio "counts as complimentary", and "the charge is based only on the video class" [S15].
- Risk: if the hook is skipped (budget exceeded, GCS error), that media gets no scenewise job. The encryption loop deletes `scenewise_audio.mp4` and the sheets unread either way (section 8.3 step 4). The reconciliation sweep in section 8.3, step 6, re-tries only media whose staging copies exist. Others need the backfill path.

**Optimisation to check (open question 11):** if the Transcoder accepts a `MuxStream.fileName` with a sub-folder (e.g. `scenewise/audio.mp4`), the file lands in `media/{uid}/{mediaId}/scenewise/`, which the flat, delimiter-`/` listing never sees (C3). The audio copy and its loop rule then become unnecessary, but the sub-folder must be deleted by Expause on intake (the loop never will). [S1] does not say whether `/` is allowed in `fileName`.

### 8.3 Chosen design (Expause side, to be built in Expause)

Scenewise contains no Expause code (`q8a-architecture-layout.md` §1.3). Everything in this section is built in Expause, against the generic contract in sections 4, 5 and 8.5.

1. **Job start** (`startTranscoderJob`, `transcoding/app_transcoding.ts:766-953`): if `hasAudio`, after the per-resolution loop add one mux stream:
   `{key: "scenewise_audio", container: "mp4", elementaryStreams: ["audio_{minRes}p"], fileName: "scenewise_audio.mp4"}`.
   It is **not** added to `manifests[*].muxStreams`. [S1] lists `mp4` as a standalone container, and `Manifest.muxStreams` lists only the keys "that should appear in this manifest".
2. **Success handler** (`onTranscodeJobSucceeded`). **Ordering rule: the hook only copies, and the encryption loop owns every delete in the transcoder prefix.**
   - **Remove the delete of `previews.jpeg` at `:157`** (one line). The sheet stays in the flat prefix until the encryption loop deletes it unread (step 4). `:157` is inside the outer `try` (`:45-223`), so any change there that could throw (a cross-bucket move is a rewrite plus a delete) would land in the catch at `:224-239` and skip encryption, the E6 outcome. Removing the call shrinks that failure surface instead of growing it.
   - Immediately before `triggerVideoEncryption` (`:223`), call `sceneWiseHook.submit(...)`, wrapped so that it **cannot throw and cannot exceed its budget**:
     - try/catch around everything, logging only;
     - a **15 s** budget enforced with an `AbortController`: the timer aborts it, every step checks `signal.aborted` before it starts, and the GCS and Cloud Tasks calls get a per-call timeout where the client supports one. `Promise.race` alone is not enough, because it does not cancel the losing promise;
     - the hook is skipped entirely if the handler has already used more than 120 s (measured from handler entry), so it never pushes the handler towards 180 s.
   - **Why copy-only is safe even after a timeout.** A copy that is still in flight when `:223` starts the encryption loop never removes an object, so the loop can never fail on a vanished object (section 3.4). The opposite race (the loop deletes a source before the copy reads it) makes only the copy fail: logged, no task enqueued, the media is published normally. Reconciliation does not re-try it (no staging copy); the backfill path can.
   - Rejected alternatives: moving in the hook (a late delete can trip the loop's `hasErrors` path, finding r2-6); moving at `:157` (unguarded, finding r2-5); enqueueing from the end of the encryption loop (option D, exposed to E7).
   - The hook does, in order, checking the abort signal before each step:
     1. List `previews*.jpeg` in the transcoder prefix (the renamed `previews.jpeg` plus any further sheet, E2; 1–2 objects in practice) and **copy** each to `gs://{SCENEWISE_STAGING}/user_media/{uid}/{mediaId}/r{rev}/sprites/`, keeping the order (`previews.jpeg` first, then `previews0000000001.jpeg`, …). The copied names go into `visual.sheets`.
     2. **Copy** `media/{uid}/{mediaId}/scenewise_audio.mp4` to `…/r{rev}/audio.mp4`. If it does not exist, there is no audio. This replaces parsing `master.m3u8`, which still works as a cross-check (`TYPE=AUDIO`, `:303-310`).
     3. Build a generic `JobRequest` (section 8.4) and `createTask` on queue `scenewise-jobs` with:
        - `name = sw-{hex(sha256(job_id))[:32]}`. The name is hashed, as C5 recommends.
        - `httpRequest: POST {SCENEWISE_URL}/v1/jobs`, with the JSON body.
        - `oidcToken: {serviceAccountEmail: SCENEWISE_INVOKER_SA, audience: SCENEWISE_ROOT_URL}`. The audience is **always set explicitly to the service root URL**. If it is left out, the default is the full target URI [S14], and Cloud Run does not accept that as `aud` (q8a §6.5).
        - `dispatchDeadline: 1800s` (q8a §6.3).

       `ALREADY_EXISTS` counts as success, which de-duplicates a redelivered Pub/Sub message (C7). This is the only place where it does: reconciliation uses its own names (step 6).
3. **Queue `scenewise-jobs`** (q8a §6.2, [S12]):
   - `maxAttempts: -1` and `maxRetryDuration: 12h`. **Scenewise's own attempt counter is authoritative**, so the queue never deletes a task before scenewise has written a terminal record.
   - `maxConcurrentDispatches ≤ max_instances × max_jobs`, so `429` is a safety net, not the normal path.
   - Back-off from `minBackoff` 10 s to `maxBackoff` 10 min.

   **The queue is the work queue.** Scenewise keeps no queue of its own. It has a non-blocking admission limiter (`429`) and a durable GCS job record (section 8.5).
4. **Encryption loop: one mandatory rule** (deploy it before, or with, the Transcoder change). In `manageEncryptVideoStorageBatch`, before the download at `encryption/encryption_storage.ts:51`, an object whose file name is `scenewise_audio.mp4` or matches `previews*.jpeg` (the renamed `previews.jpeg` and any further Transcoder sheet, E2) is **deleted and skipped**: no download, no encryption, no CDN upload, and the delete tolerates `404` (like the existing delete at `:129-138`). Without the rule the loop would download a 130 MB file into the function's memory-backed `/tmp` and publish an unused encrypted copy to the CDN. With it, the loop never touches the objects the hook reads, and the sources are gone as soon as the loop reaches them. Publishing (`isProcessing: false`) never waits for scenewise.
5. **Result intake:** section 8.6.
6. **Reconciliation (Expause, needed per q8a §6.2):** a daily scheduled function looks at media whose job has had no terminal record for more than N hours (default 6).
   - It calls `GET /v1/jobs/{job_id}`. A `404` means scenewise never received the job: re-enqueue it if the staging objects still exist. `running` or `retry_wait` means wait. A terminal record means the event was missed: ingest it.
   - This also covers the case q8a cannot cover itself: storage was unreachable on every attempt, so no record was ever written.
   - **Re-enqueue under a distinct task name**, e.g. `sw-{hex(sha256(job_id + ":recon:" + YYYY-MM-DD))[:32]}`. Re-using the original hashed name would fail: if the original task was deleted recently (for example `maxRetryDuration` ran out while storage was down, the very case this step exists for), its name is still retained for up to 24 h, `createTask` returns `ALREADY_EXISTS`, and treating that as success would silently do nothing. With the dated name, `ALREADY_EXISTS` means only that today's sweep already enqueued it. Scenewise's record (`job_id` + digest) remains the execution de-duplication, so a second delivery is harmless.
   - A deliberate re-run uses a new `rev`.
7. **Re-processing and backfill:** a new `rev` gives a new `job_id`, a new staging prefix and a new task name. The request sets `supersedes` to the previous `job_id`.

The Expause success handler stays O(1): two or three server-side copies, one short listing of `previews*`, and one enqueue, all inside the never-throw guard. It does no stitching, downloading or segment listing, and it never deletes or moves an object in the prefix the encryption loop lists.

### 8.4 The Cloud Task body (a generic `JobRequest`)

Expause builds the generic request itself (q8a §1.3). It holds references only. A typical body is about 1–2 KB, and even a 10 000-character description stays far under the 100 KB task limit [S13].

```json
{
  "schema_version": "1",
  "job_id": "um-M456-r1",
  "supersedes": null,
  "external_ref": {"kind": "user_media", "uid": "U123", "media_id": "M456", "rev": "1"},
  "stages": ["captions", "summary", "chapters", "moderation", "labels"],
  "media": {"has_audio": true},
  "audio": {"kind": "file", "uri": "gs://expause-scenewise-staging/user_media/U123/M456/r1/audio.mp4"},
  "visual": {"kind": "sprite_sheet",
             "sheets": ["gs://expause-scenewise-staging/user_media/U123/M456/r1/sprites/previews.jpeg",
                        "gs://expause-scenewise-staging/user_media/U123/M456/r1/sprites/previews0000000001.jpeg"],
             "grid": {"columns": 12, "rows": 1}, "tile": {"width": 1280, "height": 720},
             "interval_s": 10.0, "start_offset_s": 0.0, "count": 13},
  "context": {"title": "…", "description": "…", "tags": ["…"]},
  "options": {"language_hint": null},
  "delivery": {"notify": {"kind": "none"},
               "artifacts": {"uri_prefix": "gs://expause-scenewise-results/user_media/U123/M456/r1/"}}
}
```

- **`job_id = "um-{mediaId}-r{rev}"`.** It must match q8a's `JobId` rule `^[A-Za-z0-9._:-]{1,200}$` (not `.` or `..`), which keeps it safe as a GCS path segment. `mediaId` is **client-supplied when present** (`const mediaId = data.id ?? uuid()`, `transcoding/transcode_user_video.ts:41`) and not validated, so the adapter must check it against `^[A-Za-z0-9_-]{1,128}$` before building the `job_id` and the staging paths, and skip the job (logged) when it does not match. The same check protects the `{mediaId}` path segment in the staging and results buckets.
- **The visual fields come from the Transcoder job config.** `grid`, `tile`, `interval_s`, `start_offset_s` and `count` are computed by Expause's adapter as in section 7.3 item 5, and never from `media.duration`. `sheets` lists the staged copies in order (the example shows a 125 s upload: 12 columns in the first sheet, a 13th sprite in the second, E2).
- When there is no audio, `"audio": {"kind": "none"}` and `"media": {"has_audio": false}`.
- Both buckets must be on scenewise's `allowed_gcs_buckets`. Scenewise's service account needs read access to staging and write access to results.

### 8.5 Scenewise HTTP API (settled by q8a §6–§8)

**`POST /v1/jobs` is a synchronous Cloud Tasks push handler.** The request runs the job and returns when the job reaches a terminal state: succeeded, partial or failed. This follows Cloud Run's Cloud Tasks guide: return 200 "only after task processing is complete" (q8a §6.1). There is no `202 queued`.

**Job record** (q8a §6.2):
- The record is `{state_prefix}/{job_id}/status.json`, holding `state`, `attempt`, `lease_until`, `request_digest`, `error_code`, `result_uri` and `updated_at`.
- Every write is conditional on the generation that was read (GCS `ifGenerationMatch`; `0` = create only if absent). That makes each write a compare-and-swap.
- Results go to `{artifacts.uri_prefix or state_prefix/job_id}/a{attempt}/result.json` and `…/a{attempt}/captions.vtt` (attempt-scoped, so a fenced zombie attempt cannot overwrite the winner). The terminal record is written **after** the results, and its `result_uri` names the winning attempt's `result.json`.
- A failure record is always written before the final 200.

**Status codes** (q8a §8; problem bodies are RFC 9457 `application/problem+json` with `code`, `category` and `retryable` [S28]):

| Situation | Status |
|---|---|
| Job finished (succeeded, partial, or failed with a terminal record: input error, internal error, attempts exhausted, `exceeds_push_budget`) | **200** + `JobRecord`. A failure is in the body, not the status, so Cloud Tasks stops |
| Duplicate delivery of a job that is already terminal | **200** + the existing record (acknowledged) |
| Same `job_id`, different request (digest mismatch) | **200** + `{job_id, outcome: "rejected", problem: job_id_conflict}`. No record is written (the record belongs to the original request); logged at ERROR. A non-2xx would be retried for 12 h, conflicting every time |
| Body parses and has a usable `job_id`, but fails validation (schema, domain, URI policy) | **200** + terminal `failed` record with `invalid_request` (or `uri_not_allowed`). Validation runs inside the claim (q8a §6.2 step 4) |
| No usable `job_id` (not JSON, missing, or outside the pattern) | **422**. No record can be keyed. Cloud Tasks retries until `maxRetryDuration`, which is the signal for a broken producer; Expause's reconciliation finds the job (`404`) |
| Body over 1 MiB (direct callers only; a Cloud Task cannot exceed 100 KB) | **413**, before parsing, no record |
| Admission limiter full (`acquire_nowait` → `WouldBlock`) | **429** + `Retry-After` |
| Job still running under a live lease (`job_in_progress`), or another retryable error such as `storage_unavailable` | **503** + `Retry-After` (the remaining lease, for in-progress) |
| Crash / no response | Cloud Tasks retries, and lease expiry lets a later attempt take over |

**Time budget** (q8a §6.3):
- The Cloud Run request timeout and the Cloud Tasks `dispatchDeadline` are both 1800 s. Scenewise's own budget is `attempt_budget_s = 1500 s`.
- After probing, scenewise estimates the cost as duration × Σ stage cost factors. Media that will not fit is rejected up front with `exceeds_push_budget`, as a terminal, acknowledged failure.
- The deadline is cooperative: it is checked between stages, and ffmpeg gets `timeout = remaining`.
- Expause's maximum is 90 min (section 3.1). With Expause's chosen inputs it should fit: at most `5400 / 60 = 90` sprite frames (seconds of vision at q7's ≈165 ms per frame on 4 vCPU), Parakeet ASR at q7's RTFx 12.9 on 4 vCPU ≈ 420 s for 90 min (≈1020 s even at q7's low cross-check RTFx 5.3), and a hosted summary by default. Rejections become likely only with a local CPU LLM over a 90 min transcript or with dense `kind: "video"` sampling. The final numbers depend on the calibrated cost factors (q8a Q-11).
- **Settled (former open question 15):** the 1500 s budget and the up-front `exceeds_push_budget` stay. Expause records `exceeds_push_budget` as its own `scenewise.status` (not a generic failure), so rejections are countable. The Cloud Run jobs `:run` path (q8a §6.4) stays deferred until calibration shows a non-trivial rejection rate.

**Other endpoints:** `GET /v1/jobs/{job_id}` returns 200 + `JobRecord` (wire state `running` | `retry_wait` | `succeeded` | `partial` | `failed`, with `result_uri` when terminal), or 404. Nothing else in v1. Re-runs are new `job_id`s (`rev + 1`). There is no `retry` or `redeliver` endpoint, and no purge endpoint (section 8.7 shows why none is needed).

**Authentication:**
- IAM-only with OIDC: Cloud Run `--no-allow-unauthenticated`, Expause's task service account holds `roles/run.invoker`, and the platform verifies the token (q8a §6.5).
- In-app verification for self-hosting outside GCP is out of v1 (q8a Q-13).
- If it is added later, it must check `aud`, `iss`, `exp` and an `email` allow-list, and must pass `audience` explicitly: with google-auth's `verify_oauth2_token`, "If no audience is supplied, the audience is not checked" [S24].

**Errors.** Q1 uses q8a's categories and codes (q8a §8):
- `InputError`: `invalid_request`, `uri_not_allowed`, `corrupt_media`, `invalid_sprite_grid`, `input_encrypted`, `stage_unavailable`, `job_id_conflict`; `MediaTooLargeError`: `media_too_large`, `exceeds_push_budget`; `UnsupportedMediaError`: `unsupported_media`, `manifest_unsupported`. Their 413/415 classes apply only to non-push callers; on the push path every error with a keyed record answers `200` (q8a §8).
- `RetryableError`: `backend_unavailable`, `storage_unavailable`, `job_in_progress`, plus the `CapacityError` that gives 429.
- `InternalError`: `model_output_invalid`, `resource_exhausted`, `deadline_exceeded`, `invariant_violation`, `attempts_exhausted`, `unexpected`.

Q1 proposes one more `InputError` code, `input_unavailable` (open question 13); q8a's final list already has `uri_not_allowed`. `retryable` is derived from the category.

**Idempotency:**
- `job_id` + `request_digest` decide the outcome: a duplicate is acknowledged with the existing record, and a mismatch is a `200` rejection with `job_id_conflict` and no record.
- The Cloud Task name de-duplicates *enqueueing* (C5, C7). The record de-duplicates *execution*: a duplicate delivery while the job runs gets `503` until the lease ends, then the terminal `200`.
- `supersedes` links re-runs, and Expause keeps the result with the highest `rev`.

### 8.6 Results back to Expause

**Can Expause use the response body? No.** The response to a Cloud Tasks push goes to Cloud Tasks, not to the code that created the task. Cloud Tasks only passes the previous response *code* to the next attempt (`X-CloudTasks-TaskPreviousResponse`, q8a §6.1). The `200` body is only useful to a caller that calls `/v1/jobs` directly and waits, such as a CLI, a test, or the reconciliation `GET`.

**Recommendation: the GCS job record is the source of truth, and Expause learns about completion from a Cloud Storage event.**
- Put `state_prefix` and `artifacts.uri_prefix` in Expause-owned private buckets. Deploy an Expause function on `onObjectFinalized` for the bucket that holds `status.json`. Firebase fires it for every new object generation, "includ[ing] copying or rewriting an existing object" [S29].
- Trigger details (required):
  - **Location.** Expause functions are pinned to `europe-west1` (`src/index.ts:12`). Firebase warns that "a mismatch between locations can result in deployment failure" [S29], so the records bucket must be in a location compatible with `europe-west1` (an EU location also satisfies U3), and the function's location is set to match the bucket.
  - **Filter on the name.** The trigger fires for **every** object in the bucket, including `result.json`, `captions.vtt` and orphaned `a{n}/` artifacts. The handler returns at once unless the object name ends in `/status.json`. (Alternatively, records and artifacts go in separate buckets.)
  - **`retry: true`.** Event-driven functions are not retried by default: "if a function invocation terminates with an error, the function is not invoked again and the event is dropped"; with `retry: true` a 2nd-gen function is retried for up to 24 h [S31]. The handler is idempotent anyway, so retrying is safe. Without it, a failed intake is caught only by the daily reconciliation.
- The function reads `status.json`, returns at once unless the state is terminal, then reads the `result.json` that `result_uri` names (and the `captions.vtt` beside it). In a Firestore transaction it writes `users/{uid}/media/{mediaId}.scenewise` only if the `rev` is higher than the stored one, or equal with no stored terminal state.
- Eventarc delivery is at-least-once with no ordering guarantee [S30]. The handler is therefore idempotent on `(job_id, state)`, and it re-reads the record instead of trusting event order.
- Advantages over an HTTP callback:
  - Expause exposes no new inbound endpoint, which avoids repeating E8.
  - There are no callback secrets, and no retry schedule for scenewise to run outside a request. q8a runs no background work (q8a §6.1).
  - The terminal record is written after `result.json`, so an event can never point at a result that does not exist yet.
- Cost: one event per record write (RUNNING writes included), filtered by the first read.
- Missed events are caught by the reconciliation in section 8.3, step 6.

**Alternative: the HTTP callback (q8a's `Notifier` port).**
- With `delivery.notify = {kind: "http", url, auth}`, scenewise calls Expause after it writes the terminal record, inside the same request.
- The callback is a **hint**: the record is authoritative. A failed callback does not change the job's state or its `200`, and it is retried only briefly inside the request (bounded by the remaining budget). Reconciliation covers the rest.
- Auth on the callback:
  - When scenewise runs on GCP, it sends a Google ID token with `aud` = the callback URL [S23].
  - When it runs elsewhere, it signs per Standard Webhooks [S20]: `webhook-id` = `job_id`, `webhook-timestamp`, and `webhook-signature: v1,<base64 HMAC-SHA256(secret, id.timestamp.body)>`. The receiver allows ±5 min of clock skew, and two signatures are sent during key rotation.
  - Long-lived service-account keys are not used off GCP [S23].
- The receiving `onSceneWiseResult` must verify the call (not E8's pattern), use `webhook-id` as the idempotency key, and then read the record from GCS.
- Use the callback only if Expause wants lower latency than Eventarc gives, or if its storage lives outside GCP.

**Using the result.**
- Moderation stays advisory (U1) and never flips `blocked`. A disagreement can open a review item; that is a product decision. An example is scenewise `VERY_LIKELY` while the primary signal is at or below `LIKELY`, the real threshold at `common/app_constants.ts:229`.
- How the VTT is served, and whether it is encrypted, is open question 6.

### 8.7 Plaintext audio and derived-text lifecycle

The staged `audio.mp4` and sprite sheets are plaintext copies of paywalled and early-access media (C8). The transcript, VTT and summary are derived plaintext of the same content. Every copy lives in **Expause-owned buckets**, so Expause can delete all of it without any scenewise endpoint.

- **Staging bucket** `SCENEWISE_STAGING_BUCKET`:
  - Same location and storage class as the transcoder bucket, so the hook's copies are single-request rewrites [S17].
  - **Soft delete disabled**: retention 0. The default is 7 days [S19], which would keep "deleted" plaintext recoverable.
- **Transcoder bucket (requirement, E13):** soft delete must be **off (retention 0)** there too. "Soft delete is enabled by default for all buckets that support it, with a default retention duration of 7 days" [S19]. The copied sources, every plaintext segment and playlist the encryption loop deletes (`encryption/encryption_storage.ts:129-138`), and the sprite sheets all live and die in that bucket, so with the default they stay restorable for 7 days whatever staging does. Its current setting was not read: check it (`gcloud storage buckets describe` → `soft_delete_policy`) and set it to 0. The raw upload in the default bucket (deleted at `transcoding/app_transcoding.ts:241-244`) has the same exposure (open question 12).
  - Lifecycle rule `Delete` at `age ≥ 3` days as a backstop. Actions run asynchronously, with some lag [S18].
  - Uniform bucket-level access. Expause's function service account may create and delete objects. Scenewise's service account may only read.
- **Expause deletes a job's staging prefix** when its result intake sees the terminal record (section 8.6). The plaintext window is therefore queue wait + processing, with 3 days as the upper bound when something is stuck. Scenewise needs no delete permission.
- **Results and records** (`state_prefix`, `artifacts.uri_prefix`) go in Expause-owned private buckets, not the CDN bucket, until open question 6 decides how captions are served. Soft delete is off and the retention is Expause's choice. A lifecycle rule (e.g. 30 days) applies to the scenewise copies, once Expause has copied what it keeps into Firestore or its own paths.
- **Account deletion:** Expause's delete-account flow (`DELETE_ACCOUNT_*`, `common/app_constants.ts:132-140`) deletes:
  - `user_media/{uid}/` in staging and results;
  - `{state_prefix}/um-{mediaId}-r*/` for each of the user's media.

  Scenewise keeps no other copy.
- **Logs:** scenewise must not log transcript text or signed URIs. It logs only `job_id`, stage, timings and codes. Q8a §7.2 binds `job_id`/`stage`/`attempt` and does not state this rule; open question 13.

### 8.8 Backfill of existing videos

Existing media have only ciphertext in the CDN. The backfill runs **adapter-side, in Expause**:
1. Fetch the per-media key and IV from Secret Manager and unmask them with `shiftKeyBytes` (`encryption/encryption_manager.ts:38-50`).
2. Decrypt the **whole files**, init segment included, with AES-128-CBC and the **Secret Manager IV**. The `IV=0x1234567890abcdef…` written into the playlists (`encryption/encryption_storage.ts:78-79`) is not the IV used (`:108-113`), so a standard HLS AES-128 decryptor does not work.
3. Write the decrypted init and segments plus the playlist to staging, then submit with `audio.kind = "manifest"` (scenewise stitches) and `rev = 1`.

Whether to backfill at all is open question 7.

---

## 9. Audio-less videos

- **Expause side:**
  - The Transcoder config has no audio elementary stream, mux stream or manifest entry when `hasAudio` is false (`transcoding/app_transcoding.ts:910-935`; comment at `:910-914` on the `AudioMissing` failure). So no `scenewise_audio` mux stream is added either.
  - `hasAudio` is not persisted (`:793-799`; media doc at `transcoding/transcode_user_video.ts:86-138`).
  - The hook detects it by the absence of `scenewise_audio.mp4`. Cross-checks are the absence of `TYPE=AUDIO` in `master.m3u8` and of an `audio/mp4` AdaptationSet in `manifest.mpd`, which is the form Expause's own manifest parser expects (`:303-310`, `:369-380`).
  - `hasAudio` is computed from the client-supplied `dynamicUrl` (section 3.1), not from the object the Transcoder reads. The two normally agree. A mismatch makes the Transcoder job fail (`AudioMissing`) or drop the audio (Expause issue E12).
  - Suggestion (Expause): persist `hasAudio` at `startTranscoderJob` (E9).
- **Scenewise contract:**
  - `audio: {kind: "none"}`, or a `file` with no audio stream found by probing, gives `media.has_audio = false` and `captions = {status: "skipped", reason: "no_audio_stream"}` with **no VTT**.
  - Summary, chapters, labels and moderation still run on visual input. `summary.inputs_used` excludes `"transcript"`.
  - The job `status` stays `"succeeded"`: skipping captions is expected, not a failure.
  - **Audio present but no speech** (music, silence) is different: `captions = {status: "succeeded", reason: "no_speech", cue_count: 0}` (`no_speech` is the one `reason` allowed on a succeeded stage, section 5.1), with no VTT or a header-only VTT (Q2 decides).
  - Expause shows no caption track in both cases, but analytics can tell them apart.

---

## 10. Expause issues found (for later Expause tasks)

None of these is fixed here. Scenewise's contract is designed to be correct regardless of them.

| # | Issue | Evidence | Effect | What the scenewise contract requires / suggested fix |
|---|---|---|---|---|
| E1 | **Sprite mis-slicing for trimmed uploads.** Job start uses the untrimmed ffprobe duration for I and C. Slicing uses the trimmed `media.duration`. | `transcoding/app_transcoding.ts:776-777`, `:810-811` vs `:123-124`; `lib/presentation/screens/publish/preview_content_screen.dart:194-201` | Wrong crops and timestamps off by up to 2× in `previewNNNN.jpeg`. GVI analyses wrong crops | Contract: grid, tile, interval and offset are **supplied explicitly** from the Transcoder job config and never inferred (section 7.3). Fix: slice with `payload.config.spriteSheets[0]` values |
| E2 | **Second sprite sheet ignored.** `findStorageFile` takes the first match; a second sheet is expected whenever D mod I ≠ 0 | `storage/app_storage.ts:40`; [S1] | Last preview lost. Orphan sheet encrypted and copied to the CDN | The hook copies all `previews*` sheets and lists them in `sheets`; the loop rule deletes them unread (section 8.3). Fix: handle N sheets |
| E3 | `columnCount = 0` when D < I | `transcoding/app_transcoding.ts:707`, `:735` | The Transcoder reads 0 as "no limit". Slicing divides by 0, so no previews | The adapter sends `columns = 1`. Fix: `max(1, …)` |
| E4 | `Math.floor(mediaDuration / 1000) ?? 15` is `NaN`, never 15 | `transcoding/app_transcoding.ts:123` | When `duration` is missing the interval falls through to 60 s and `columnCount` is `NaN`, so no previews are produced (`:684-715`) | Fix: test `Number.isFinite` |
| E5 | `previewOutputFiles.length` throws when no sheet was found | `transcoding/app_transcoding.ts:116-138`, `:215` | Falls into the catch, so encryption is skipped (E6) | Fix: default `[]` |
| E6 | The catch path sets `isProcessing: false` but never starts encryption | `transcoding/app_transcoding.ts:224-239` | The media is "published" with no CDN segments. Plaintext stays in the transcoder bucket indefinitely | The scenewise hook must never throw (section 8.3). Fix: always reach `triggerVideoEncryption`, or a sweeper |
| E7 | `encrypt_video` is keyed by **uid**, written with `merge: true` | `video_encryption/video_encryption.ts:18-31` | Two close uploads by one user: the first media's remaining plaintext is orphaned and it may never reach `completeContentProcessing`. Also, the first chain's pending `iteration` increment re-fires against the overwritten document (`:82-89`), so **two trigger chains** run on the second media's prefix and race on the same objects. A download of an object the other chain already deleted trips the `hasErrors` path (`encryption/encryption_storage.ts:140-144`), which marks the second media `hasErrors: true` and stops its encryption (`video_encryption/video_encryption.ts:61-78`) | This is why the scenewise trigger is not in the encryption loop (option D). Fix: key by `mediaId` |
| E8 | Cloud Tasks HTTP handlers are unauthenticated `https.onRequest`, and tasks set no `oidcToken`. **Inferred from code**: `preserveExternalChanges: true` (`src/index.ts:12`) means the deployed IAM may differ; confirm the deployed `run.invoker` binding | `cloud_tasks/cloud_tasks_utils.ts:14-20`, `:46-52`, `:80-86`, `:114-120`; handlers `user_subscriptions/on_task_auto_renew_exclusive_subscription.ts:4-8`, `content/on_task_publish_content.ts:4-8`, `content/on_task_video_boost_end.ts:5`, `campaigns/on_campaign_end_task.ts:8` | If public, anyone who knows the URL can trigger them. **Highest impact: subscription auto-renewal** (`handleUserSubscription(userId, peerId, true, true)` for any posted ids); also content publishing, boost end and campaign end | The recommended intake is a Cloud Storage event, so there is no new inbound endpoint. If the optional callback is used, its handler must verify OIDC/HMAC (section 8.6). Fix: OIDC on tasks plus verification in handlers |
| E9 | `hasAudio` is not persisted | `transcoding/app_transcoding.ts:793-799` | Downstream must re-detect it | Suggestion: persist it with `resolution` |
| E10 | The HLS `#EXT-X-KEY` advertises a constant IV that differs from the real per-media IV, and init segments are encrypted too | `encryption/encryption_storage.ts:78-79`, `:108-113` | Standard HLS decryptors cannot play or decrypt. Presumably the player handles `hlsScheme://` itself (not verified) | Backfill must use the Secret Manager IV (section 8.8). Verify it is intended |
| E11 | The success handler has no retry and a 180 s timeout, and waits synchronously on GVI | `transcoding/transcode_job_updated.ts:8-17`; `video_analysis/video_analysis.ts:42-43` | A slow GVI call can kill post-processing, with the E6 outcome. No redelivery | The scenewise hook has a 15 s budget and skips above 120 s elapsed. Fix: move GVI to its own task |
| E12 | `ffprobe` runs on a **client-supplied URL** (`dynamicUrl`), unvalidated | `transcoding/transcode_user_video.ts:45`, `:149`; `transcoding/app_transcoding.ts:776`, `:582` (same in chat and community: `transcoding/transcode_chat_video.ts:74`, `transcoding/community_video_transcoding.ts:112`) | **Authenticated blind SSRF**: any signed-in user (the callable rejects calls without `request.auth`, `transcode_user_video.ts:20-25`) can make the function issue requests to arbitrary URLs, including internal ones. No file-read or response-exfiltration path was found: only width, height, duration and `hasAudio` are used and only `resolution` is persisted (`:793-799`), so at most a success/failure side channel leaks; the metadata server needs a `Metadata-Flavor` header ffprobe does not send. Also, the metadata (`hasAudio`, duration) may not describe the stored object | Scenewise never passes request URIs to ffmpeg (section 4.0). Fix: probe `gs://` input via a signed URL generated server-side, or the Transcoder's own metadata |
| E13 | **Plaintext stays restorable after deletion** unless soft delete is off on the transcoder bucket (and the default bucket for raw uploads). GCS enables 7-day soft delete by default [S19]; the buckets' settings were not read | `encryption/encryption_storage.ts:129-138`; `transcoding/app_transcoding.ts:157`, `:241-244`; [S19] | Every "deleted" plaintext segment, playlist, sprite sheet and raw upload of paywalled or early-access media (C8) can be restored for 7 days by anyone with restore permission | Requirement: transcoder bucket soft-delete retention 0 (section 8.7); staging too. Default bucket: open question 12 |

---

## 11. Review round 1 — resolution

Every finding was re-checked against the Expause code at `32ed0bf18` and against the cited sources on 2026-10-08. After the first r2 draft, Q8a settled the job contract: a synchronous push handler, a GCS job record, no Expause code in scenewise and no `ResultSink`. Rows 3, 7–10 and 13 describe the resolution as aligned with that contract. Q1's objections were open questions 14 and 15; both are closed in round 2. Rows 1, 7 and 14 are amended by round 2 (findings r2-1, r2-5 to r2-7): the hook now copies instead of moving, reconciliation uses a distinct task name, a `job_id` conflict is a `200` rejection rather than `409`, and the row-14 mechanism is frame quantisation, not priming.

| # | Sev. | Finding (short) | Resolution |
|---|---|---|---|
| 1 | design (high) | The hook is on the critical path; a timeout blocks encryption; "not delayed" is false | **Fixed.** Re-verified `:215-239` and `transcode_job_updated.ts:8-17` (and found `concurrency: 80` too). The hook is now O(1) (2–3 moves + 1 enqueue), with a 15 s `Promise.race`, skipped past 120 s elapsed, and never throws (section 8.3). The text states the publishing delay (section 8.2, E). Encryption-loop placement was considered (option D) and kept as the fallback, because E7 can drop its trigger |
| 2 | unsupported | The "about 1 s" `cat` inside the 180 s / 1 GiB function; max is 90 min | **Fixed.** Re-verified 5400 s (`remote_configs_defaults.dart:36`, `remoteConfigDefaults.ts:202`). Stitching in the handler is removed. The Transcoder writes a standalone audio MP4 (option E); compose is evaluated and not chosen (option B). The local `cat` timing is labelled local-disk only (section 6.3) |
| 3 | wrong | "Cloud Tasks … protects a self-hosted GPU box" | **Fixed.** Confirmed on the official reference [S9]: 2xx = done, and 429/503 bring higher back-off and `Retry-After`. The 202 premise is gone: per q8a's settled contract, `POST /v1/jobs` is a synchronous push handler that returns `200` only at a terminal state. Cloud Tasks *is* the work queue: its retries cover the work itself, and its `maxConcurrentDispatches` pacing does bound concurrent work. Scenewise adds a non-blocking admission limiter (`429`), a lease (`503` while running) and a durable GCS record (section 8.5) |
| 4 | unsupported | Mis-slicing is worse than stated | **Fixed.** Re-verified the Flutter trimmed duration and the web `null`. Section 7.3 item 1 has the example. The contract requires an explicit grid, tile, interval and offset; raw sheets are sent; recorded as E1; open question 4 answered |
| 5 | unsupported | The second sheet is expected per [S1]; `columnCount = 0` edge | **Fixed.** Re-read [S1] (`columnCount`/`rowCount` 0 = no limit). Section 7.3 items 2 and 3; E2, E3; open question 3 kept for empirical confirmation only |
| 6 | missing | Cloud Tasks 100 KB limit | **Fixed.** Confirmed [S13]. The task body carries a prefix reference (~1–2 KB) (section 8.4). `segments_list_uri` and `uri_template` provide by-reference lists, and inline lists are capped (sections 4.2, 4.3) |
| 7 | design | Idempotency and task naming; same id with a different body; re-processing | **Fixed.** `job_id = um-{mediaId}-r{rev}` (fits q8a's `JobId` rule), a hashed task name (C5 recommends hashed over sequential names), and q8a's `request_digest` giving duplicate → `200` with the existing record, mismatch → `409`. `supersedes` links re-runs (sections 8.4, 8.5) |
| 8 | missing | OIDC audience and verification by a non-GCP host; HMAC default; Expause handlers unauthenticated | **Fixed.** The default audience is the target URI [S14], so it is always set explicitly to the service root URL. Push authentication is IAM-only with OIDC, verified by Cloud Run (q8a §6.5); a future in-app verifier must pass `audience` [S24]. The optional callback uses OIDC on GCP and Standard-Webhooks HMAC elsewhere [S20][S23]. E8 recorded |
| 9 | design | Callback semantics unspecified | **Fixed differently.** The GCS job record is authoritative. Expause is told by a Cloud Storage finalize event (at-least-once [S30], so the handler is idempotent on `(job_id, state)`), with reconciliation through `GET` as the backstop. The callback is optional and only a hint, retried briefly inside the request. Results are always objects pointed to by the record (section 8.6) |
| 10 | design | No error object, free-text reasons, no POST codes | **Fixed.** `ErrorInfo{code, category, retryable, message, stage}` using q8a's categories and codes (Q1 proposes two more), a closed `SkipReason`, q8a's `POST` status table, and the partial/re-run rules (sections 5.1, 8.5) |
| 11 | design | No versioning policy | **Fixed.** Additive-only within a major version, inputs `extra="forbid"`, outputs "ignore unknown" (pydantic default `ignore` [S25]), `scenewise_version`, one deprecation window (section 4.0) |
| 12 | design (security) | `file://` and arbitrary `https://` | **Fixed.** Allow-listed `gs://` buckets and `https://` hosts only, with no redirects, resolved-IP checks and no `file://` in service mode [S21]. URIs are never handed to ffmpeg (section 4.0). Related Expause SSRF recorded as E12 |
| 13 | missing | Plaintext copy of paid content | **Fixed.** Staging bucket with soft delete off [S19], 3-day lifecycle [S18], restricted IAM (scenewise read-only), Expause deletes staging when it ingests the terminal record, records and results in Expause-owned buckets, and account deletion is a prefix delete in Expause (section 8.7). Linked to open question 6 |
| 14 | missing | AAC priming; time base; `X-TIMESTAMP-MAP` | **Fixed, with a correction to the reviewer's explanation.** Re-measured: segment 0 is 6.016000 s and later segments 5.994667 s, so the 0.021333 s difference is 1024 priming samples. `12.010667` is the cumulative decode time, not "512 samples of priming". The stitched file starts at 0.000 with the edit list applied. The requirement stands: presentation-timeline rule, `audio_start_offset_s`, optional `X-TIMESTAMP-MAP` (section 5.4, RFC 8216 §3.5 re-read) |
| 15 | unsupported | "Cuts fall in silence" is overstated; conditioning differs | **Fixed.** Re-read `vad.py:28-31`, `:47` and `transcribe.py:277`, `:549` at `9fa78645`. Section 6.1 reworded; section 6.2 notes the confound |
| 16 | unsupported | Experiment method under-specified | **Fixed.** The script was recovered and the method stated exactly (sequential per-segment, not batched, VAD off; batched stitched with `batch_size=8`; custom normaliser; warm-up). `base.en` re-run 3×: WER identical, wall time noisy. The whole experiment is labelled **indicative, Whisper-specific** (section 6.2) |
| 17 | minor | 0.9 vs 1.1 % is half a word | **Fixed.** Error counts added (3 vs 4 of 349); the two stitched modes are declared tied |
| 18 | minor | The speed penalty is Whisper-specific | **Fixed.** Section 1 and section 6 label the speed claims Whisper-family. "Stitch always" rests on boundaries and context. Parakeet (U4) noted |
| 19 | minor | HF chunking is a CTC method | **Fixed** (section 6.1) |
| 20 | missing | Backfill IV and init decryption | **Fixed** (section 8.8, E10) |
| 21 | minor | `encrypt_video/{uid}` overwrite | **Fixed.** Re-verified `:18-31`. Noted in section 3.4, E7, and as the reason against trigger option D |
| 22 | minor | ffprobe runs on `dynamicUrl` | **Fixed** (section 3.1). Escalated: it is client-supplied and unvalidated, recorded as E12 |
| 23 | minor | Parsing the protobuf `Duration` | **Fixed** (section 7.3 item 5) |
| 24 | minor | `UNKNOWN` missing; threshold example wrong | **Fixed.** `UNKNOWN` added and index-aligned with `PORNOGRAPHY_LIKELIHOODS`; example now "`VERY_LIKELY` vs ≤ `LIKELY`" (sections 5.3, 8.6) |
| 25 | minor | Cite the manifest parser for audio detection | **Fixed** (`:303-310`, `:369-380`, sections 3.2 and 9) |
| 26 | minor | File names / flat layout | **Fixed.** Flat layout recorded as implied by the encryption regex and listing (`encryption_storage.ts:96`, `:150-161`). Less relevant now, because the chosen path reads one named file. Open question 1 kept for the `segments`/backfill path |
| 27 | minor | STYLE block placement | **Fixed** (section 5.2) |

Reviewer's answers to open questions: **Q4 accepted** (answered, yes). **Q3 accepted** (on paper; empirical check remains). **Q5 accepted for duration** (90 min). Headroom is moot, because the handler no longer moves bytes through memory. **Q1 accepted** (flat layout, partly answered).

Rejected findings: **none outright.** Finding 14 is accepted in its requirement but its mechanism is corrected (see row 14).

---

## 11b. Review round 2 — resolution

Every finding of `reviews/q1-review-r2.md` was re-checked on 2026-10-08: the Expause code at `32ed0bf18` (read only), the cited Google and Firebase pages (Cloud Tasks `tasks.create` updated 2026-07-30; soft delete, Cloud Storage triggers and function retries updated 2026-10-07), and a local ffmpeg 7.1 reproduction of the AAC segment durations and `elst` box. Q1 was also aligned with the final q8a (job-id pattern, `job_id_conflict` as a `200` rejection, attempt-scoped artifact paths, `retry_wait`, `attempt`, error classes).

| # | Sev. | Finding (short) | Resolution |
|---|---|---|---|
| 1 | wrong | AAC "priming" explains the 6.016/5.994667 s segments; the edit list explains `start: 0` | **Fixed.** Reproduced: durations follow 282/281/281/281 AAC frames (frame quantisation), and ffmpeg's `elst` has `media_time = 0`, so priming is presented, not trimmed; `start: 0` comes from `tfdt = 0`. Timing rule kept with its ~21 ms bound (section 5.4); open question 2 now asks about a non-zero `elst media_time` in Transcoder output. r1 reviewer's "512 samples" stays rejected |
| 2 | unsupported | E12 "SSRF and local-file-read" | **Fixed.** Verified `request.auth` check (`transcode_user_video.ts:20-25`), only `resolution` persisted (`:793-799`), ffprobe at `app_transcoding.ts:582`. E12 is now an authenticated blind SSRF with no exfiltration path found; line ref corrected |
| 3 | minor | E8 rests on inference; auto-renewal is the worst handler | **Fixed.** Verified no `oidcToken` at all four task builders and `preserveExternalChanges: true` (`src/index.ts:12`). E8 and section 3.6 say "inferred from code; confirm the deployed `run.invoker` binding" and lead with subscription auto-renewal |
| 4 | minor | E4: interval falls through to 60 s | **Fixed** (section 7.3 item 4, E4), verified at `:684-715` |
| 5 | design | The `:157` move is outside the never-throw guard | **Fixed differently.** `:157`'s delete is removed instead of turned into a move; the sheets are copied inside the guarded hook, and the encryption loop deletes them unread (section 8.3 steps 2 and 4) |
| 6 | design | `Promise.race` does not cancel; a late move can trip the loop's `hasErrors` path | **Fixed, with the simplest safe ordering:** the hook never moves or deletes anything in the transcoder prefix, it only copies; the loop's `scenewise_*`/`previews*.jpeg` rule is **mandatory** and runs before download with a 404-tolerant delete; the budget uses an `AbortController` checked between steps. Verified the failure path (`encryption_storage.ts:51`, `:140-144`; `video_encryption.ts:61-78`). The sub-folder variant (open question 11) stays an optimisation |
| 7 | design | Task-name retention is "up to" 24 h; reconciliation re-enqueue can silently no-op | **Fixed.** Re-read `tasks.create`. C5 and section 1 say "retained for up to 24 h, no guaranteed window"; reconciliation uses `sw-{hash(job_id + ":recon:" + date)}`; `ALREADY_EXISTS` counts as success only for the hook's own name (section 8.3) |
| 8 | missing | Transcoder bucket's 7-day soft delete keeps plaintext restorable | **Fixed.** Re-read the soft-delete page. Requirement added (section 1, 8.7, C3), Expause issue **E13**; the default bucket's raw uploads are a user decision (open question 12) |
| 9 | missing | Storage trigger: location, name filter, retries | **Fixed.** Section 8.6 states the `europe-west1`-compatible bucket and matching function location, the `status.json` name filter, and `retry: true` (re-read [S29]; new [S31]) |
| 10 | design | `sheets_prefix` needs a `BlobStore.list` that q8a lacks; tile optionality | **Fixed** by choosing explicit `sheets: [...]` (sections 4.3, 8.3, 8.4); no `BlobStore.list` needed. **Tile part rejected:** the final q8a `SpriteGrid` has `tile_width: int; tile_height: int` (not optional), which matches Q1's required `tile` |
| 11 | minor | `media.video_start_s`, `options.hls_timestamp_map_mpegts` not in the schema | **Fixed** by marking both as future additive fields, not in v1 (sections 4.1, 5.4), so the v1 schema matches q8a's domain |
| 12 | minor | `skip_reason` vs `reason`; `no_speech` on a succeeded stage | **Fixed** (sections 5.1, 9) |
| 13 | minor | §3.5 says scenewise deletes staging | **Fixed** (Expause deletes on intake; 3-day backstop) |
| 14 | minor | Staging path inconsistent | **Fixed:** `user_media/{uid}/{mediaId}/r{rev}/` everywhere; account deletion uses `user_media/{uid}/` |
| 15 | minor | Wall-time ratio ranges | **Fixed:** 2.7–5.0× and 2.0–6.4×, paired within runs (section 6.2, section 1) |
| 16 | minor | protobufjs `Long` makes `Number()` NaN | **Fixed** (section 7.3 item 5): object form handled, non-finite result skips the job |
| 17 | minor | `mediaId` is client-supplied | **Fixed.** Verified `data.id ?? uuid()` (`transcode_user_video.ts:41`); the adapter validates it and skips the job on mismatch (section 8.4) |
| 18 | minor | Stale cross-references; 413 | **Fixed on Q1's side** (413 row for direct callers, section 4.0/8.5); the q8a-side items are listed in open question 13, since q8a is final |
| 19 | minor | E7 consequence understated | **Fixed** (E7 effect column; section 3.4) |

Reviewer's views on the disagreements: **open question 14 closed** (the final q8a already implements Q1's split: `200` + terminal `invalid_request` for keyable bodies, `422` only without a usable `job_id`). **Open question 15 closed** in favour of the reviewer's view (keep 1500 s; Expause records `exceeds_push_budget` as its own status; jobs path deferred until calibration).

Rejected: only the tile-optionality part of finding 10 (reason above).

---

## 12. Open questions

1. **Transcoder object names for the segment path** (backfill, other callers): the exact init segment and media playlist names under the flat prefix. Partly answered: the layout is flat (finding 26). The adapter parses the playlist rather than guessing.
2. **Transcoder audio timing:** does the standalone `scenewise_audio.mp4` (or the Transcoder's fMP4 init) write a **non-zero `elst media_time`**, i.e. trim the AAC priming, unlike ffmpeg's `media_time = 0` (section 5.4)? Do its first audio PTS and the fMP4 `tfdt` start at 0? Does Transcoder fMP4 stitch with `cat`? Check: `ffprobe -show_streams -show_entries stream=start_time` plus a dump of the `elst` box on one real job's outputs. The timing rule is correct either way; this only sizes the residual (0 or about 21 ms).
3. **Second previews sheet:** expected per [S1] whenever D mod I ≠ 0. Confirm by listing `previews*` for one real job. Also: is a partial last sheet narrower, or padded with blank tiles? (This decides whether `count` is mandatory.)
4. ~~Mis-slicing~~: **answered**, yes for every trimmed Flutter upload (E1).
5. ~~Handler headroom / max duration~~: **answered**, 90 min. The new hook moves no bytes through the function. Still worth measuring: p99 duration of `transcodeJobUpdated` today (Cloud Logging), to size the 120 s skip threshold.
6. **Captions serving:** should Expause encrypt the VTT (paid content), and will it serve a sidecar `<track>` or an HLS `SUBTITLES` rendition? The latter needs a WebVTT media playlist (RFC 8216 §4.3.4.2.1) and `X-TIMESTAMP-MAP` (section 5.4).
7. **Backfill:** decrypt adapter-side (section 8.8), or skip existing videos?
8. **Chat and community videos:** in scope? They have their own encryption loops and no GVI today.
9. **Parakeet per-segment penalty** (speed and WER) was not measured. Moot for the design, because a continuous track is mandatory; Q2 may want the number.
10. **Billing of the extra mux stream:** [S15] says audio in a job with video "counts as complimentary". Confirm on one invoice line or the SKU report that adding `scenewise_audio` changes nothing.
11. **Copy latency and the sub-folder shortcut:** measure a same-location server-side copy of a 130 MB object (90 min audio) from Cloud Functions, to confirm it fits the 15 s hook budget. Test whether `MuxStream.fileName` may contain `/` (that would remove the audio copy and its loop rule, section 8.2).
12. **Bucket settings to read before building (checks, plus one user decision):**
    - Staging location: one region with the transcoder bucket. Its location was not read; it must match for single-request rewrites [S17]. EU residency (U3) also applies. The records bucket must also be compatible with the `europe-west1` intake function (section 8.6).
    - Transcoder bucket soft delete: **requirement**, set retention to 0 (section 8.7, E13).
    - **User decision: soft delete on the default (upload) bucket.** Raw uploads are deleted at `transcoding/app_transcoding.ts:241-244` and stay restorable for 7 days under the default policy. *For retention 0:* the plaintext window of paid content then ends at deletion, consistent with the transcoder and staging buckets. *Against:* the default bucket likely holds other user files too, and turning soft delete off removes recovery from accidental deletes for all of them. A middle path is to move raw video uploads to their own bucket with retention 0. Scenewise's design works with any choice.
13. **Follow-ups for q8a (q8a is final; each is a user decision: accept into q8a's follow-ups, or leave as is).** None changes Q1's design.
    - The `InputError` code `input_unavailable` (input 404, or 403 after in-attempt retries). *For:* lets a consumer tell a missing staging object from a corrupt one. *Against:* one more code; `corrupt_media` or `invalid_request` could cover it.
    - `schema_version`, `scenewise_version` and `external_ref` in `JobRecord`. *For:* the Cloud Storage intake can route a record without reading `result.json`. *Against:* a larger record; Expause can derive routing from the `job_id` (`um-{mediaId}-r{rev}`) alone.
    - A stated rule that logs never contain transcript text or signed URIs (q8a §7.2 binds only `job_id`/`stage`/`attempt`).
    - Stale cross-references in q8a: §6.2's Expause key `expause:user_media:{mediaId}:r{rev}` (Q1 uses `um-{mediaId}-r{rev}`, which fits the same pattern); §6.5's "Outbound callbacks … (q1 §8.6)" is correct, but q8a §6.2's mention of Q1's 24 h callback schedule and Q-16 are obsolete (Q1 adopts best-effort callbacks plus reconciliation); §8's 413/415 note covers non-push callers, which Q1 §4.0/§8.5 now state.
    - Q-17's `sheets_prefix` item is resolved on Q1's side (explicit `sheets`, no `BlobStore.list`).
14. ~~Objection: `422` for schema-invalid bodies~~: **closed.** The final q8a parses the envelope first and validates the full body inside the claim, so a body with a readable `job_id` that fails validation gets a terminal `failed`/`invalid_request` record and `200`; only a body with no usable `job_id` gets `422` (q8a §6.2 steps 0 and 4, §8). That is exactly Q1's split; section 8.5's status table now matches it.
15. ~~Objection: 1500 s push budget vs 90 min~~: **closed** in favour of the round-2 reviewer's view. With sprite frames, Parakeet on CPU and a hosted summary, 90 min fits the budget even at q7's low CPU estimate (section 8.5). Kept: up-front `exceeds_push_budget`; Expause records it as its own `scenewise.status`; the jobs `:run` path stays deferred until calibration (q8a Q-11) shows a non-trivial rejection rate.
16. **Note on the 202 decision (no objection to the outcome).** q8a rejected `202` partly because background CPU needs instance-based billing. On GPU services instance-based billing is required anyway (q8a §6.1), so that argument is weaker there. The other argument decides it: a `202` would end Cloud Tasks' at-least-once retry for the actual work. Q1 adopts the synchronous handler.

---

## 13. Sources

All read 2026-10-08.

- [S1] Google Cloud Transcoder API, REST `JobConfig` (MuxStream `container` incl. standalone `mp4`/`mp3`/`ogg`/`vtt`, `fileName`; Manifest `muxStreams`; SpriteSheet `columnCount`/`rowCount` 0 = no limit, `interval`, `startTimeOffset`, sprite pixel fields; segment naming). https://docs.cloud.google.com/transcoder/docs/reference/rest/v1/JobConfig
- [S2] Google Cloud sample, "Create a job that generates a spritesheet with a variable number of images". https://docs.cloud.google.com/transcoder/docs/samples/transcoder-create-job-with-periodic-images-spritesheet
- [S3] openai/whisper `whisper/audio.py` (`CHUNK_LENGTH`, `N_SAMPLES`, `pad_or_trim`). https://raw.githubusercontent.com/openai/whisper/main/whisper/audio.py
- [S4] SYSTRAN/faster-whisper at commit `9fa78645d7913ff9d94d0907a2156526b19b4556`: `faster_whisper/transcribe.py` (277, 396-425, 517, 549, 1170-1185), `faster_whisper/audio.py` (117-129), `faster_whisper/vad.py` (28-31, 47). https://github.com/SYSTRAN/faster-whisper
- [S5] faster-whisper README (BatchedInferencePipeline; VAD on by default for batched mode). https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
- [S6] Bain et al., "WhisperX: Time-Accurate Speech Transcription of Long-Form Audio", arXiv:2303.00747. https://arxiv.org/abs/2303.00747
- [S7] Hugging Face blog, "Making automatic speech recognition work on large files with Wav2Vec2 in Transformers". https://huggingface.co/blog/asr-chunking
- [S8] Google Cloud Tasks, "Create HTTP target tasks" (OIDC token, roles). https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks
- [S9] Google Cloud Tasks REST reference, `projects.locations.queues.tasks` `HttpRequest` (2xx = success; "backs off on all errors", higher back-off on 429/503; `Retry-After` considered; `dispatchDeadline` 15 s–30 min, default 10 min). https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks
- [S10] RFC 8216, HTTP Live Streaming: §3.3 Fragmented MPEG-4; §3.5 WebVTT and `X-TIMESTAMP-MAP`; §4.3.4.2.1. https://www.rfc-editor.org/rfc/rfc8216
- [S11] W3C, WebVTT: The Web Video Text Tracks Format (Candidate Recommendation Draft, 20 May 2026). https://www.w3.org/TR/webvtt1/
- [S12] Google Cloud Tasks, "Configure Cloud Tasks queues" (`max_concurrent_dispatches`, rate and retry parameters). https://docs.cloud.google.com/tasks/docs/configuring-queues
- [S13] Google Cloud Tasks, `tasks.create` ("The maximum task size is 100KB"; explicit names de-duplicate with `ALREADY_EXISTS`; name reuse after up to 24 h / 9 days; hashed names recommended). https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks/create
- [S14] Google Cloud Tasks, `OidcToken` ("If not specified, the URI specified in target will be used" as audience). https://docs.cloud.google.com/tasks/docs/reference/rest/v2/OidcToken
- [S15] Google Cloud, Transcoder API pricing (audio-only output $0.005/min; Example 6: audio "counts as complimentary for video transcoding … the charge is based only on the video class"). https://cloud.google.com/transcoder/pricing
- [S16] Google Cloud Storage, "Compose objects" ("between 1 and 32 objects"; same-bucket examples only). https://docs.cloud.google.com/storage/docs/composing-objects
- [S17] Google Cloud Storage JSON API, `objects.rewrite` (single request when storage class unchanged and same location). https://docs.cloud.google.com/storage/docs/json_api/v1/objects/rewrite
- [S18] Google Cloud Storage, Object Lifecycle Management (`age`, `matchesPrefix`; actions are asynchronous). https://docs.cloud.google.com/storage/docs/lifecycle
- [S19] Google Cloud Storage, Soft delete (default 7 days; disable with retention 0). https://docs.cloud.google.com/storage/docs/soft-delete
- [S20] Standard Webhooks specification (`webhook-id`/`-timestamp`/`-signature`; `msg_id.timestamp.payload`; HMAC-SHA256 `v1`; retry schedule; multiple signatures for rotation). https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md
- [S21] OWASP, Server-Side Request Forgery Prevention Cheat Sheet (allow-lists, no redirects, resolved-IP checks incl. 169.254.169.254, DNS rebinding). https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- [S22] Google Cloud Pub/Sub, Subscription overview ("at-least-once delivery"; redelivery possible after ack). https://docs.cloud.google.com/pubsub/docs/subscription-overview
- [S23] Google Cloud Run, "Authenticating service-to-service" (ID tokens via libraries or metadata server; audience; Workload Identity Federation preferred off-GCP; keys "are a security risk"). https://docs.cloud.google.com/run/docs/authenticating/service-to-service
- [S24] google-auth, `google.oauth2.id_token` (`verify_oauth2_token(id_token, request, audience=None, …)`; "If no audience is supplied, the audience is not checked"). https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.id_token.html
- [S25] Pydantic, `ConfigDict.extra` (`'ignore'` default, `'forbid'`, `'allow'`). https://pydantic.dev/docs/validation/latest/api/pydantic/config/
- [S28] RFC 9457, Problem Details for HTTP APIs (July 2023). https://www.rfc-editor.org/rfc/rfc9457.html
- [S29] Firebase, "Cloud Storage triggers" (`onObjectFinalized`: "Sent when a new object (or a new generation of an existing object) is successfully created in the bucket"; copies and rewrites trigger it; `bucket` option). https://firebase.google.com/docs/functions/gcp-storage-events
- [S30] Google Cloud Eventarc overview ("At-least-once event delivery to targets … 24 hours" retention; no in-order guarantee). https://docs.cloud.google.com/eventarc/docs/overview
- [S31] Firebase, "Retry asynchronous functions" ("By default, if a function invocation terminates with an error, the function is not invoked again and the event is dropped"; `retry: true`; 2nd gen retry window 24 hours; updated 2026-10-07). https://firebase.google.com/docs/functions/retries
- [Q8a] `docs/research/q8a-architecture-layout.md` (final, 2026-10-08): §1.3 no consumer code; §6.1–6.5 synchronous push handler, GCS job record, deadlines, admission, IAM/OIDC; §8 error hierarchy and status mapping; §12 left out of v1.
- [L1] Local experiments, 2026-10-08, Apple M4. ffmpeg 7.1 (imageio-ffmpeg static build), faster-whisper 1.2.1, CTranslate2 4.8.2, `base.en`/`small.en`, int8. Script `seg_vs_stitched.py` and reference text are in the session scratchpad, not committed. The r2 re-run of `base.en` ×3 rebuilt the 18 segments byte-identically from the stored `init + segment_i` files (verified with `cmp`). The r3 check of AAC segment durations and the `elst` box used a 60 s 440 Hz sine, AAC 192 kbps, `-hls_segment_type fmp4 -hls_time 6`, same build.
