# Review r2 (final round): q1-input-contract.md (revision r2)

Reviewer: a fresh review agent that neither wrote nor previously reviewed the file. Date: 2026-10-08.
- Expause code was re-read at HEAD `32ed0bf18` (2026-09-22), read only. Paths are relative to `/Users/daniel/Work/expause/cloud_functions/functions/src/functions/` unless they start with `lib/` or `expause_web/`.
- External pages were fetched on 2026-10-08. Their "last updated" stamps are given where the page shows one.
- Local check: ffmpeg 7.1 (the same imageio-ffmpeg static build as [L1]). I also read the stored experiment files in the session scratchpad (`scripts/seg_vs_stitched.py`, `speech/`, `rerun/`).

Severity scale (same as r1): **wrong**, **unsupported**, **missing**, **design concern**, **minor**.

Overall: the r2 revision resolves 26 of the 27 round-1 findings correctly. It is consistent with q8a's settled contract: a synchronous push handler, a GCS record with a lease, and IAM/OIDC. Its Expause code reading is again accurate almost everywhere.
- One new technical claim is **wrong**: the AAC "priming" explanation in §5.4 and in resolution row 14.
- One security claim is overstated: E12, "local-file-read".
- The rest are design gaps in the new Expause hook: an unguarded `:157` move, a non-cancelling `Promise.race`, and task-name reuse in reconciliation. There is also one mismatch with q8a's ports: `sheets_prefix` needs a list operation that `BlobStore` does not have.

## Findings

1. **"segment 0's `#EXTINF` is 6.016000 s and later segments are 5.994667 s … 1024 samples at 48 kHz, the AAC encoder priming … the stitched file reports `start: 0.000000`, because ffmpeg applies the init segment's edit list. The edit list also explains the priming."** (§5.4; resolution row 14)
   → What the evidence shows:
   - **The doc's own stored playlist** (`scratchpad/speech/hls/audio.m3u8`) reads `6.016000, 5.994667, 5.994667, 5.994667, 6.016000, …` repeating, then `2.226333`. Later segments are **not** all 5.994667 s: every fourth one is 6.016 s.
   - I reproduced this on a 60 s sine with the same ffmpeg 7.1 build and `-hls_segment_type fmp4 -hls_time 6`. The pattern was the same: `6.016, 5.994667 ×3, 6.016, 5.994667 ×3, 6.016, 5.994667, 0.021333`.
   - **The cause is frame quantisation, not priming.** 6 s at 48 kHz is 281.25 AAC frames of 1024 samples. The HLS muxer cuts at the first frame at or after k × 6 s, so segments run 282/281/281/281 frames. 282 frames is 6.016 s and 281 frames is 5.994667 s. The 0.021333 s difference is one frame, and it would appear with zero priming.
   - **The init segment's edit list does not shift for priming.** The `elst` box in my init.mp4 is `entry_count=1, segment_duration=0, media_time=0, rate=1.0`. So ffmpeg's fMP4 output keeps the 1024 priming samples in the presented timeline, and `start: 0.000000` comes from `tfdt` = 0, not from an edit list.
   - `init + segment_2` → `start: 12.010667` was reproduced. It is 563 frames × 1024 / 48000, the cumulative cut point.

   → **wrong**

   → Correction:
   - In §5.4 and resolution row 14, replace the mechanism with: "AAC frames are 1024 samples, so 6 s segments alternate 282/281 frames (6.016/5.994667 s). ffmpeg's fMP4 init has `elst media_time = 0`, so the encoder's 1024-sample priming is *presented* (about 21 ms of leading silence), not trimmed."
   - The rule itself (subtract the first presented audio PTS, with error ≤ about 21 ms) still stands, and the r1 reviewer's "512 samples" stays rejected.
   - Open question 2 should also ask whether the Transcoder's MP4 writes a non-zero `elst media_time`.

2. **E12: "`ffprobe` runs on a client-supplied URL … SSRF and local-file-read vector through ffprobe protocols"** (§10; also §3.1)
   → What the code does:
   - `dynamicUrl` is taken unvalidated from callable data (`transcoding/transcode_user_video.ts:45`). It is passed at `:149` to `getVideoMetadata`, which calls `ffmpeg.ffprobe(inputPath)` at `transcoding/app_transcoding.ts:582` (the doc says `:581`). So server-side fetches of arbitrary URLs are real (SSRF).
   - **The caller must be signed in.** The callable rejects requests without `request.auth` (`transcode_user_video.ts:20-25`), so this is not anonymous.
   - **No probe output is returned to the caller.** Only width, height, duration and `hasAudio` are used, and only `resolution = min(w, h)` is persisted (`app_transcoding.ts:793-799`). Errors are logged.
   - A `file:` path or an HLS playlist that points at local files therefore yields no contents to the attacker. At most it leaks a blind success/failure side channel.
   - The GCE metadata server needs a `Metadata-Flavor: Google` header, which ffprobe does not send from a bare URL. Metadata theft is therefore not shown either.

   → **unsupported** (overstated)

   → Correction: "authenticated blind SSRF (any signed-in user can make the function issue requests to arbitrary URLs, including internal ones); no file-read or response exfiltration path was found". Fix the line to `:582`. The proposed fix (probe a server-generated signed URL of the stored object) stands.

3. **E8: "Cloud Tasks HTTP handlers are unauthenticated … Anyone who knows the URL can trigger e.g. content publishing"**
   → What the code shows:
   - All four task kinds set only a `Content-Type` header and no `oidcToken` (`cloud_tasks/cloud_tasks_utils.ts:14-20`, `:46-52`, `:80-86`, `:114-120`).
   - The handlers do no checks: `content/on_task_publish_content.ts:4-8`, `content/on_task_video_boost_end.ts:5`, `campaigns/on_campaign_end_task.ts:8`, `user_subscriptions/on_task_auto_renew_exclusive_subscription.ts:4-8`.
   - Since the tasks carry no token, the functions must accept unauthenticated invocations for scheduling to work at all. **But** `setGlobalOptions({…, preserveExternalChanges: true})` (`src/index.ts:12`) means the deployed IAM, and any queue-level `httpTarget` auth override, may differ from the code. Neither can be seen in the repo.
   - The impact is wider than "publishing": one of these handlers is subscription auto-renewal (`handleUserSubscription(userId, peerId, true, true)`).

   → **minor** (the claim is very likely correct, but it rests on inference)

   → State "inferred from code; confirm the deployed `run.invoker` binding". List the auto-renewal handler as the highest-impact one.

4. **E4: "`Math.floor(mediaDuration / 1000) ?? 15` … NaN interval and columns when `duration` is missing"**
   → `computeSpriteSheetPreviewsParams(NaN)`: `NaN ?? 15` is `NaN`, every `<=` test is false, so the interval falls through to **60 s**, and `columnCount = Math.floor(NaN/60) = NaN` (`transcoding/app_transcoding.ts:687-708`). `Array.from({length: NaN})` is empty, so no previews are produced.

   → **minor**

   → Change it to "interval falls to 60 s, columns NaN, so no previews".

5. **"At `:157`, replace the delete of `previews.jpeg` with a move to `gs://{SCENEWISE_STAGING}/…`" while "the hook … cannot throw and cannot exceed its budget"** (§8.3 step 2)
   → `:157` is inside the outer `try` (`app_transcoding.ts:45-223`), not inside the guarded hook.
   - A cross-bucket move is a rewrite plus a delete. Any error there (IAM, location mismatch, a transient 5xx) jumps to the catch at `:224-239`, which skips `triggerVideoEncryption`. That is exactly the E6 outcome that the hook design was meant to prevent.
   - Today's plain `delete()` has a smaller failure surface.

   → **design concern**

   → Keep the `:157` delete as is, or wrap the move in the same never-throw guard. Better: move all sheets inside the guarded hook (they are listed there anyway for E2), and let `:157` delete only if the hook has not moved the sheet.

6. **"`Promise.race` against a 15 s timer … so it never pushes the handler towards 180 s"; "if the hook is skipped … the encryption loop then encrypts `scenewise_audio.mp4` into the CDN as an unused object (harmless)"** (§8.2 E, §8.3)
   → `Promise.race` does not cancel the losing promise. After a timeout, the move of `scenewise_audio.mp4` (copy, then delete) can still be in flight when `triggerVideoEncryption` (`:223`) starts the loop.
   - The loop lists the flat prefix (`encryption/encryption_storage.ts:150-161`), then calls `download()` on each object (`:51`).
   - If the object disappears between the list and the download, the outer catch sets `hasErrors = true` and `break`s (`:140-144`). `onEncryptVideo` then deletes the `encrypt_video` doc and marks the media `hasErrors: true`, **leaving all remaining plaintext unencrypted and unpublished** (`video_encryption/video_encryption.ts:61-78`).
   - The reverse order can also happen: the loop downloads and deletes the source before the move's delete, so the move fails noisily.

   → **design concern**

   → Fixes:
   - Make the encryption-loop rule for `scenewise_*` objects **mandatory, not optional**. It should skip such objects *before* download (no download, no delete, or a delete that tolerates 404), so the loop can never trip over them.
   - Alternatively, write the mux stream into a sub-folder (open question 11), which the delimiter-`/` listing never sees.
   - Pass an `AbortSignal` or timeout to the GCS calls instead of relying on `Promise.race` alone.

7. **"The hashed task name makes re-enqueueing idempotent within 24 h" and "`ALREADY_EXISTS` counts as success"** (§8.3 steps 2.3 and 6; C5)
   → `tasks.create` (last updated 2026-07-30) says: "The IDs of deleted tasks are not immediately available for reuse. It can take **up to** 24 hours (or 9 days …) for the task ID to be released." https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks/create
   - So 24 h is an upper bound on name *retention*, not a guaranteed dedupe window. A duplicate after release is not caught. That is harmless here, because the job record de-duplicates execution.
   - The real problem is the reverse case. Reconciliation (step 6) re-enqueues with the **same** hashed name after a `404`. If the original task was deleted recently (for example `maxRetryDuration` ran out while storage was down, which is exactly the case step 6 exists for), the call returns `ALREADY_EXISTS`. Step 2.3 treats that as success, so the re-enqueue silently does nothing.

   → **design concern**

   → Fixes:
   - Reword C5: names are retained for up to 24 h, with no guaranteed window.
   - Reconciliation must use a distinct name, for example `sw-{hash(job_id + ":recon:" + date)}`. Scenewise's record (digest plus state) remains the execution dedupe.

8. **Plaintext lifecycle: "Soft delete disabled" on staging** (§8.7; C3: "plaintext … is deleted within seconds to minutes after `:223`")
   → GCS: "Soft delete is enabled by default for all buckets that support it, with a default retention duration of 7 days … To disable soft delete, you set the retention duration to 0" (https://docs.cloud.google.com/storage/docs/soft-delete, updated 2026-10-07).
   - The **move source** (`scenewise_audio.mp4` and the sprite sheets in the transcoder bucket) is deleted there. So is every plaintext segment the encryption loop deletes (`encryption_storage.ts:129-138`).
   - Unless the transcoder bucket already has soft delete off (its configuration was not read), all of that plaintext stays restorable for 7 days. Turning soft delete off on staging alone does not shorten the plaintext window.

   → **missing**

   → Add to §8.7 and open question 12: check the soft-delete policy of the transcoder bucket, and set it to 0 if needed. Record the current exposure as an Expause issue (E13).

9. **Result intake via `onObjectFinalized` on the bucket that holds `status.json`** (§8.6)
   → The Firebase doc (updated 2026-10-07) confirms that finalize fires on "a new object (or a new generation …) … includes copying or rewriting" (https://firebase.google.com/docs/functions/gcp-storage-events). The same page adds: "A mismatch between locations can result in deployment failure … specify the function location so that it matches the bucket/trigger location."
   - Expause functions are pinned to `europe-west1` (`src/index.ts:12`).
   - Eventarc is at-least-once with no ordering, and retention is 24 h (https://docs.cloud.google.com/eventarc/docs/overview, updated 2026-10-07). That is correctly cited.
   - Unstated points:
     - (a) the results/state bucket must be in a location compatible with `europe-west1` (EU residency, U3, agrees);
     - (b) the trigger fires for **every** object in the bucket, so `result.json` and `captions.vtt` also fire unless the records live in their own bucket; the handler must filter on the `status.json` name;
     - (c) Firebase event functions do not retry on failure unless `retry: true` is set, so a failed intake is caught only by the daily reconciliation.

   → **missing** (minor in impact)

   → Add these three points to §8.6.

10. **`SpriteSheets.sheets_prefix` ("sheets = prefix + 10-digit index + .jpeg, sorted")**, used in the Expause body (§4.3, §8.4)
    → q8a's `BlobStore` port has `materialise`, `read` and `write`, and **no list** (q8a §4). q8a's domain `SpriteSheets` holds `sheets: tuple[str, ...]` (q8a §5). As written, scenewise cannot resolve a prefix except by probing names one by one with `read` until it gets `None`.
    - Also, q8a's `SpriteGrid.tile_width/tile_height` are `int | None`, while Q1's `tile` is required.

    → **design concern** (consistency with q8a)

    → Either add `list(prefix)` to `BlobStore` (q8a open question 13 list), or have Expause send an explicit `sheets: [...]`. The hook moves the sheets itself, so it knows their names; this is the simpler choice. Align the tile optionality.

11. **`media.video_start_s` and `options.hls_timestamp_map_mpegts`** (§5.4)
    → Neither field exists in `MediaInfo` or `StageOptions` (§4.1). Inputs are `extra="forbid"`, so a caller sending them gets `422`.

    → **minor**

    → Add both as optional fields, or mark them as future additive fields.

12. **§9: `captions = {status: "skipped", skip_reason: "no_audio_stream"}` and `{status: "succeeded", skip_reason: "no_speech"}`**
    → The schema field is `StageStatus.reason` (§5.1), described as "SkipReason when skipped".
    - `skip_reason` does not exist.
    - A `succeeded` stage carrying a SkipReason contradicts the field comment.

    → **minor**

    → Use `reason`, and state that `no_speech` is allowed as `reason` on a succeeded stage, or give it its own field.

13. **§3.5 table: staging is "Deleted by scenewise at job end"**
    → §8.7 says that scenewise is read-only on staging and that Expause deletes the prefix on intake. The two sections contradict each other.

    → **minor**

    → Fix §3.5 to "Deleted by Expause on terminal-record intake; 3-day lifecycle backstop".

14. **Staging path `expause/user_media/{uid}/{mediaId}/r{rev}/`** (§3.5) vs `…/user_media/{uid}/{mediaId}/r1/` (§8.3, §8.4, §8.7 account-deletion prefix)
    → **minor**. Pick one. The account-deletion prefix must match it exactly.

15. **"per-segment independent was 2.7–5.1× slower than stitched-batched across all runs, and overlap 3.0–6.5×"** (§6.2)
    → Paired within each run from the table:
    - per-segment: r1 range 2.7–4.0, r2 runs 13.7/4.8 = 2.85, 11.0/2.2 = 5.0, 11.0/3.4 = 3.2, `small.en` 4.5. That is **2.7–5.0**.
    - overlap: r1 range 3.1–5.3, r2 runs 9.7/4.8 = **2.0**, 14.0/2.2 = 6.4, 12.5/3.4 = 3.7, `small.en` 5.5. That is **2.0–6.4**.

    The r2 re-run's claims were verified: `seg_vs_stitched.py` matches the stated method (warm-up, sequential per-segment with VAD off, batched with `batch_size=8`, custom normaliser); `ref.txt` has 349 words; the 18 segments and `init.mp4` in `rerun/hls` are byte-identical to `speech/hls` (checked with `cmp`, pairing by index, because the file names differ: `segment_…` vs `seg…`).

    → **minor**

    → Correct the ranges. The conclusion is unaffected.

16. **"Parse it as `Number(seconds ?? 0) + (nanos ?? 0) / 1e9`"** (§7.3 item 5)
    → If the Node client returns `seconds` as a protobufjs `Long`, `JSON.stringify` turns it into `{low, high, unsigned}`, and `Number()` of that object is `NaN`.

    → **minor**

    → Handle the object form: `typeof s === "object" ? s.low + s.high * 2**32 : Number(s)`. Or read the interval from the job config Expause itself built (the adapter knows `previewsIntervalSeconds` at job start).

17. **"Expause media ids are UUIDs or Firestore ids, so they fit [`[A-Za-z0-9_-]{1,128}`]"** (§8.4)
    → `const mediaId = data.id ?? uuid()` (`transcoding/transcode_user_video.ts:41`). The id is **client-supplied** when present, and it is not validated.

    → **minor**

    → The adapter must validate `mediaId` against the pattern, and hash it or skip the job when it does not match.

18. **Cross-document references**
    → q8a still says "Idempotency key: … (Expause: `mediaId`, q1 §8.1)" (q8a §6.2) and "Outbound callbacks … (q1 §8.2)" (q8a §6.5). Both are stale: Q1 now uses `um-{mediaId}-r{rev}` and §8.6.
    - q8a §8 annotates `MediaTooLargeError` as "413", while both documents map every `InputError` after keying to a `200` terminal record.
    - Q1 §4.0 introduces `413` for a body over 1 MiB, which has no row in either status table. It is unreachable through Cloud Tasks (100 KB cap) but reachable for direct callers.

    → **minor**

    → Q1 open question 13 should also list these: q8a §6.5 → q1 §8.6, and the 413 row or annotation.

19. **E7 consequence understated** (§3.4, §10)
    → Besides orphaning the first media, the overwrite makes **two trigger chains** run on the second media's prefix. The first chain's pending `iteration` increment re-fires against the overwritten doc (`video_encryption/video_encryption.ts:82-89`). The two chains then race on the same objects, and a download of an object already deleted by the other chain trips the `hasErrors` path (finding 6), which marks the media `hasErrors: true` and stops encryption.

    → **minor**

    → Add this to the E7 "Effect" column.

## Verified as correct (brief)

- **Round-1 resolutions**:
  - Rows 1–13 and 15–27 are correctly resolved. Spot checks: `concurrency: 80`, no retry, 180 s (`transcode_job_updated.ts:8-17`); `:215` throw and `:223`/`:224-239` (`app_transcoding.ts`); 5400 s on both clients; Flutter trimmed duration (`preview_content_screen.dart:194-201`).
  - Row 14 is wrong in mechanism (finding 1). Rows 1 and 7 are fixed but leave the gaps in findings 5–7.
- **Transcoder billing for the extra stream (supported):** pricing Example 6: "manifest2 (audio1) … the audio stream is generated from the video input and counts as complimentary for video transcoding. If the job has any video elementary stream, the charge is based only on the video class" (https://cloud.google.com/transcoder/pricing, fetched 2026-10-08).
  - Q1's mux reuses an existing AAC elementary stream in a job with video, so it is covered by that rule.
  - No example shows a standalone `mp4` mux specifically, so open question 10's invoice check is the right residual.
- **JobConfig:** `container` "Supported standalone file formats: mp4 mp3 ogg vtt"; `Manifest.muxStreams` "that should appear in this manifest"; `fileName` defaults to key plus extension. Nothing says whether `/` is allowed (open question 11 is correct).
- **Cloud Tasks:** "The maximum task size is 100KB"; `ALREADY_EXISTS` de-duplication; hashed names recommended over sequential ones (create page, updated 2026-07-30).
- **GCS:** soft delete is 7 days by default and disabled with 0. Lifecycle actions run asynchronously, and rule changes take up to 24 h (https://docs.cloud.google.com/storage/docs/lifecycle, updated 2026-10-07).
- **Expause code, E1–E3, E5, E6, E9–E11:** correct at the cited lines.
  - E1: `:123-124` vs `:776-777`, `:810-811`.
  - E2: `storage/app_storage.ts:40` (first match).
  - E3: `:707`, `:735`; with D < 2 s, `columnCount = 0`, `tileWidth = Infinity`, and the empty filter fails, which is caught at `:132`, so there are no previews.
  - E5: `:116-138` and `:215`.
  - E6: `:224-239`.
  - E9: `:793-799`.
  - E10: `encryption_storage.ts:78-79` with the IV constant; whole-file encryption at `:113` → `encryption_manager.ts:288`.
  - E11: as cited.
  - E7's core claim is correct (`video_encryption.ts:18-31`).
- **Budget arithmetic:** 15 s budget + 120 s skip threshold = at most about 135 s, which leaves at least 45 s for `triggerVideoEncryption` (two Secret Manager creates and one Firestore write). That is reasonable. The skip threshold should still be sized from p99 logs (open question 5).

## Views on the two recorded disagreements

- **Open question 14 (422 for schema-invalid bodies): the evidence supports Q1.**
  - Cloud Tasks retries every non-2xx until `maxRetryDuration` (12 h here), and a validation failure is deterministic.
  - q8a's own `InputError` list includes `invalid_request`, and its own rule says an `InputError` gets a terminal record and `200` (q8a §6.2 step 5, §8). The 422 row contradicts that rule for every body whose `job_id` can be read.
  - q8a's reconciliation makes it worse. After 12 h the task is deleted, `GET` returns `404`, and Expause re-enqueues the same broken body, or silently does nothing (finding 7).
  - Recommendation: adopt Q1's split. A body that parses and has a valid `job_id` gets a terminal `failed`/`invalid_request` record and `200`. Only unparseable bodies, or bodies without a usable `job_id`, get `422`.
- **Open question 15 (1500 s push budget vs 90 min): the evidence leans to q8a for Expause's chosen inputs.** Q1's procedural ask is still cheap and worth adopting.
  - With sprite sheets, a 90 min video yields at most `5400/60 = 90` frames (E1 table), so vision is seconds (SigLIP about 66 ms per frame).
  - ASR on CPU: q7 prices captions at $0.0027 per 5 min at $0.000116 per wall-second, about 23 s per 5 min, so about 7 min for 90 min.
  - The summary is hosted (Haiku) by default.
  - Even at the 2× CPU uncertainty q7 flags, the total stays under 1500 s.
  - Budget rejections become likely only with a local CPU LLM summarising a 90 min transcript, or with `kind: "video"` dense sampling.
  - Recommendation: keep q8a's up-front `exceeds_push_budget`, record it as a distinct `scenewise.status` in Expause, and tie the jobs `:run` path to the calibration result (q8a Q-11), as Q1 asks.

## Count

wrong 1 · unsupported 1 · missing 2 · design concern 4 · minor 11 (total 19)
