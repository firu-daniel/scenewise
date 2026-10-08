# Review r2 of `q8c-reconciliation.md`

Reviewer: a fresh review agent. I did not write this file or review it before. Review date: **2026-10-08**.

## Method

- Read q8c in full, including "Review round 1 — resolution", and r1's 24 findings. Checked each resolution against the
  text it points to.
- Sources re-read for the new or changed design: q1 §4.1 (`StageOptions`), §5.1 (`JobResult`, `ErrorInfo`,
  `StageStatus`, `SkipReason`), §5.3 (`Label`, `LabelsResult`), §6.1 (Whisper 30 s padding); q2 §4.2–§4.5, §5.1–§5.2;
  q3 "Summary and recommendation", "Minimum length", "Frame labels as input"; q5 §1, §6.1–§6.2; q8a §5 (`StageOutcome`,
  `TextRequest`); q8b §6 (model tier, tiny-model table); `user-decisions.md`; `docs/decisions/initial-research.md`
  (Q3, Q7, §7.5 table); `ARCHITECTURE.md` (all 17 sections, line by line against §6.4); `ROADMAP.md` §0–§2.
- **faster-whisper v1.2.1 source** (raw.githubusercontent.com, tag v1.2.1):
  - `transcribe.py` L19: `from faster_whisper.audio import decode_audio, pad_or_trim`. So
    `faster_whisper.transcribe.decode_audio` is the right patch target.
  - `WhisperModel.transcribe(audio: Union[str, BinaryIO, np.ndarray], language=…, word_timestamps=…, vad_filter=…,
    condition_on_previous_text=…, hallucination_silence_threshold=…)`. L875–876:
    `if not isinstance(audio, np.ndarray): audio = decode_audio(...)`. An ndarray skips PyAV decoding entirely.
  - `detect_language(self, audio: Optional[np.ndarray] = None, features=None, vad_filter=False, …,
    language_detection_segments=1, language_detection_threshold=0.5) -> (language, probability, all_probs)`
    (L1768). It has **no** decode branch: it takes arrays or features only. With `vad_filter=True` it concatenates
    speech chunks (`collect_chunks` + `np.concatenate`), as q8c says.
  - `faster_whisper/__init__.py` L1 imports `faster_whisper.audio`, whose L15 is `import av`.
- **GitHub docs** (WebFetch, 2026-10-08):
  - "Creating rulesets for a repository": eligible bypass actors are "Repository admins, organization owners, and
    enterprise owners", "The maintain or write role, or custom repository roles based on the write role", "Teams",
    "GitHub Apps", "Dependabot". Individual users are not listed; the dialog searches for "the role, team, or app".
    "For pull requests only" exists: "The selected actor is now required to open a pull request", which leaves "a clear
    trail of their changes in the pull request and audit log".
  - "Managing rulesets for a repository": Rule Insights (Settings → Rules → Insights) lists "Actions where someone has
    bypassed one or more rulesets", filterable by actor.

Severity scale: **wrong** / **unsupported** / **design concern** / **missing** / **minor**.

## Round-1 resolutions: verified

All 24 are resolved as the resolution table says. Exceptions are noted in findings 1, 2, 3 and 4 below.

- **1 (LID envelopes).** Fixed. `identify(track, windows: Sequence[Sequence[TimeSpan]])` matches faster-whisper's own
  concatenation (L1803–1806). `lid_windows` bounds speech seconds, not the envelope.
- **2 (language skip data).** Fixed. `LanguageReport` travels on `Skipped`, and the §5 table allows `language` and
  `detected_languages` on `skipped / language_*`.
- **3 (model cache).** Fixed; see "What holds".
- **4 (visual-only summaries).** The rule now matches q3's table, but its inputs are not defined for v1 (finding 2).
- **5, 17 (signatures, `CalibrationDeps`).** Fixed.
- **6 (GPU-ASR route).** Narrowed correctly to "out of v1, to be researched".
- **7 (PyAV).** Fixed. The arrays-only rule is feasible in 1.2.1 (Method). One precision point is in finding 10.
- **8 (OQ7).** The cost is now stated, but A′ names a bypass actor type GitHub does not offer (finding 3).
- **9 (`ARCHITECTURE.md` list).** Items 26 and 28–31 were added, but the list is still incomplete (finding 4).
- **10–24.** Fixed as stated. `Word.log_prob` is a mean, and the Jensen remark is correct (log is concave). The word-end
  formula never shortens a word and never overlaps the next one. `"und"` is used throughout. The refusal path is
  stated. Decoding is chunked. T4 is copied in full. The `check_lock.sh` message is fixed. Silero is pinned through its
  HF mirror. The OQ12 import-based check is in place. The onnx_asr `py.typed` is verified. The `pcm_s16le` pin is in
  place. The fallback settings are restated.

## What holds (verified, no finding)

- **`Succeeded | Skipped | Failed` against q1's wire contract.** q1's `StageStatus` has exactly three statuses
  (`succeeded | skipped | failed`), a `reason` and an `ErrorInfo`. The union maps onto them one to one, and q8a's
  `StageOutcome.reason` already carried the error code for `failed`. Removing q1's single "succeeded + `no_speech`"
  exception is consistent with D23. The added `SkipReason` values and the two captions fields are additive within
  `schema_version "1"`. `assert_never` in `mapping.py` fits mypy's `exhaustive-match` gate.
- **Speech-only LID input** is right, and it is feasible: `detect_language(audio=<ndarray>, vad_filter=False)` with
  the default `language_detection_segments=1` reads the first 30 s of the concatenated array. `lid_window_max = 30 s`
  of speech therefore fits exactly one Whisper window.
- **Arrays to faster-whisper.** Feasible as specified (Method). `hallucination_silence_threshold` needs
  `word_timestamps=True`, which is set.
- **Models cache.** The listed sizes match q2 §5.1–§5.2: about 652 MB for each int8 encoder, `tiny` model.bin 75.5 MB
  plus tokenizer (q8b §6 table), Silero about 2 MB, and the hf-internal-testing CLIP/SigLIP models at 2.9 + 5.1 MB.
  The sum is about 1.4 GB, well under the 10 GB per-repository cache. Running the fallback contract with `tiny` is
  sound, because the adapter is model-agnostic.
- **The `Label` object** matches q5 §6.2's example field for field (`id`, `name`, `path` root-first ending in `id`,
  `score_max`, `score_mean`, `frames`, `calibrated`, and an optional `external_id`). The `1–100` range matches q5's
  `top_k`. `labels_max: int | None = None` ⇒ taxonomy `top_k` is the right way to let q5's per-request override work.
- **Chunked recogniser calls.** The number of *port calls* is small: at most 1500 s / 300 s = 5 calls per job within
  the push budget. Their overhead is negligible. Parakeet at about 12.9 RTFx on 4 Cloud Run vCPUs (q7) takes about
  23 s per 300 s chunk, which bounds the deadline overshoot for the primary. The real cost question is the number of
  *spans* inside each call (finding 1).
- **Ruff limits.** Every new sketch signature fits `max-args = 5` and `max-positional-args = 3`, whether or not
  `self` counts:
  - `transcribe(self, track, segments, *, language)`;
  - `identify(self, track, windows)`;
  - `score(self, frames, prompts, *, embeddings)`;
  - `segments(runs, probs, policy)`;
  - `decide_language(groups, guesses, policy, *, target)`;
  - `transcript(recognized, *, pauses, language, min_hold)`;
  - app `transcribe(track, *, speech, policy, deadline)`;
  - `calibrate(request, *, deps)`;
  - `entry_matches(entry, *, serving)`;
  - `summary_basis(words, visual)`.

  Dataclass constructors (`CalibrationRequest`, `ServingSetup`, `SpeechPolicy`) are generated, so PLR0913 does not
  apply to them.

## Findings

### 1. `segments()` never merges VAD runs, so the recogniser gets many short spans

- **Claim (§2):**
  - `segments(runs, probs, policy)`: "every run longer than max_segment is cut". Nothing merges runs.
  - `SpeechPolicy.min_silence = 0.1` s, so every pause of 100 ms or more starts a new run.
  - §1: "each adapter reads only the spans it decodes (≤30 s)". `decode_chunk` bounds the call by 300 s of *speech*.
- **Source:**
  - With 100 ms minimum silence, ordinary speech produces runs of one to a few seconds: dozens per minute.
  - q1 §6.1: "in Whisper-family models a 6 s segment costs a full 30 s encoder pass". The faster-whisper fallback
    (q2 §4.3, `transcribe(array, …)` once per span) therefore pays a 30 s encoder pass per 1–3 s span: roughly 10–30×
    the compute of merged 30 s windows.
  - A 300 s speech chunk of 1–2 s spans is 150–300 Whisper windows in one uninterruptible port call. That defeats the
    deadline rationale of §1 for the fallback runtime.
  - q1 §6.1 also cites WhisperX "VAD Cut & **Merge**" and faster-whisper's batched pipeline, which merge speech up to
    30 s. Both reference designs merge.
  - For Parakeet, decoding isolated 1 s fragments drops cross-fragment acoustic and language context. That is
    unmeasured, but it is the opposite of q2's "segments of about 30 s or less", which reads as a cap, not a target
    of 1 s.
- **Severity:** design concern.
- **Correction:**
  - Make `segments()` cut *and merge*: join consecutive runs whose gap is below a `merge_gap` (for example 1–2 s) until
    `max_segment` is reached, then cut at the lowest-probability hop as now.
  - Keep `pauses = gaps(runs)` from the un-merged runs, so word-end extension and cue breaks still see every pause.
  - Add one hypothesis property: no merged segment exceeds `max_segment`, and every run lies inside exactly one segment.
  - With merging, the existing ≤300 s `decode_chunk` bounds compute for every runtime.

### 2. The summary's "visual rule" depends on signals v1 does not produce

- **Claim (§5):** summary is `below_minimum` when the transcript has fewer than about 40 words **and** "the labels do
  not cover at least 3 distinct scenes and there is no on-screen-text signal". The test is
  `summary_basis(words, visual) -> Basis | None`, and a visual-only summary reports `inputs_used = ["frames"]`.
- **Source:**
  - q3's table wording is "labels cover ≥3 distinct scenes or there is on-screen text". But scenewise has no OCR
    stage, and no scene detection in v1 (D10; `ARCHITECTURE.md` §14 "scene-based frame sampling" left out). q3's
    chapter rule also leans on "scene-change detection".
  - The labels the rule needs come from the labels stage, which is roadmap item 4. Summaries are item 2 (ROADMAP).
    q8c does not say what `visual` is, whether summary runs the labeller when the caller did not request `labels`, or
    what happens before item 4 ships.
  - q3 feeds *labels* to the LLM (`VISUAL LABELS (automatic, may be wrong)`), not frames. `TextRequest` has no images
    until item 3 (§4.2). `inputs_used = ["frames"]` is the nearest q1 literal, but it does not describe what was sent.
- **Severity:** design concern (the rule is faithful to q3 but not implementable as written).
- **Correction:**
  - Define `visual` for v1 as a stdlib value built from labels that the labeller actually emits, for example
    `VisualEvidence(labels: tuple[str, ...], frames_covered: int)`. State a concrete rule: for example at least 3
    distinct emitted non-moderation labels, each the top label on at least one frame. Drop "on-screen text" until an
    OCR signal exists, and say so.
  - State that, with no labeller configured (and before item 4), a summary below 40 words is `skipped / below_minimum`.
  - State whether summary invokes the labeller itself when `labels` was not requested. The decision doc Q7 implies it
    runs "after captions and labels".
  - Note that `inputs_used = ["frames"]` means "derived from frames (labels)". Alternatively, add a `"labels"` literal
    now, as an additive wire value.

### 3. OQ7 A′ names a bypass actor GitHub does not offer

- **Claim (§8):** "Its bypass list holds the maintainer's account only (never the bot), in 'pull requests only' mode,
  so a bypass happens on a PR, is shown there, and appears in the ruleset's insights."
- **Source (GitHub docs, read 2026-10-08):**
  - Eligible bypass actors are roles (repository admin, maintain, write, custom roles based on write), teams, GitHub
    Apps and Dependabot. Individual user accounts are not an actor type.
  - "For pull requests only" exists and leaves a trail "in the pull request and audit log".
  - Rule Insights lists bypasses, filterable by actor.
- **Severity:** wrong (the mechanism; the recommendation itself stands).
- **Correction:**
  - Put the **Repository admin** role on the bypass list, in "For pull requests only" mode.
  - In a personal-account repository, the owner (`@firu-daniel`) is the only admin. The bot is added as a
    collaborator, which never carries admin. A GitHub App is installed with contents/pull-requests write but no
    administration permission. So "maintainer only" holds through the role.
  - If the repository moves to an organisation, "Repository admin" also covers organisation owners. Say that the
    bypass then widens to them.
  - The visibility claims hold: the PR shows the bypass, and so do the audit log and Rule Insights.
  - Rulesets are free on public repositories, which scenewise is.

### 4. The §6.4 `ARCHITECTURE.md` edit list is still not mechanically complete

- **Claim:** items 22–31 cover the `ARCHITECTURE.md` changes.
- **Source:** `ARCHITECTURE.md`, read line by line. These passages contradict q8c and appear in no item:
  - **§1 table**, "Heavy dependencies": "No torch … in an ASR-only image … two accelerator selector pairs". There is
    now one pair and no ASR-only image (§3).
  - **§2 tree:**
    - missing `domain/speech.py` and, for item 4, `domain/calibration.py`, `app/calibrate.py`,
      `app/contract/taxonomy.py`;
    - the `service/cli.py` comment needs `calibrate`;
    - `scripts/fetch_models.py` says "tiny models", and `tests/models.lock` says "repo id + revision of each tiny test
      model". Both are wrong after item 11a and §7.6;
    - `domain/captions.py` "Transcript → cues" now also builds words from tokens.
  - **§4:**
    - `TextGenerator.generate -> str` → `-> Generation` (§7.1);
    - `ZeroShotLabeller.scores` → `score(...) -> LabelScores` (§4.1);
    - the `audio_track` comment "16 kHz mono WAV" → `pcm_s16le`;
    - the bullet "every `SpeechRecognizer` returns segments in absolute seconds, in order and not overlapping";
    - the `Dependencies` block, `asr: SpeechRecognizer | None` → `speech: Speech | None` (item 16 edits only the
      source).
    - Item 22 names only the port count, `SpeechRecognizer` and the two new ports.
  - **§5:**
    - `Label(name, score)`, `TextRequest`, `Summary(text, model)` (whose `model` now comes from `Generation`), and the
      new `Generation` and `LabelScores` values;
    - the bullet "summary and chapters need a transcript or visual input" should name `below_minimum`;
    - item 23's "the JobRecord fields" is already present (lines 317–318), so drop it.
  - **§6 table:**
    - the Summary/chapters row still says "a summary only above about 40 transcript words". It needs the visual
      fall-through, `skipped / below_minimum` for both, and refusal → `model_refused`;
    - the Labels row needs the TOML taxonomy and `labels_max`;
    - item 24 changes only the Captions and Moderation ports.
  - **§9:** `model_refused` in `InternalError` codes; `request_too_large` in `MediaTooLargeError`. Items 19–20 are
    source edits, and item 19's "§9" is ambiguous between q8a and `ARCHITECTURE.md`.
  - **§10:** the `asr` group's backend values (§7.9), the new `captions` settings group (`SpeechPolicy`, §2),
    `service.max_body_bytes` (item 19), and the taxonomy path / `z_min` settings.
  - **§11 and §14:** "PyAV … rejected" and "Deliberately left out: … PyAV" need the note that PyAV is now a transitive,
    never-used dependency (§3).
  - **§15:** the Model tier row ("tiny pinned models") and the bullet "**No large model downloads.** The model tier uses
    tiny models" directly contradict §7.6's 1.4 GB cache. Item 30 touches only the contract-suite list.
  - **§16:** the Types row "`ignore_missing_imports` only for six untyped heavy libraries" → seven (item 5 adds
    `sherpa_onnx`).
- **Severity:** missing.
- **Correction:** extend §6.4 with one item per passage above, quoting the old text and giving the replacement, as
  items 25 and 31 already do.

### 5. Source item 14 omits the `TextGenerator` port change

- **Claim (item 14):** "add `VoiceActivityDetector` and `LanguageIdentifier`, replace `SpeechRecognizer` (§1), change
  `ZeroShotLabeller` (§4.1)".
- **Source:** §7.1 changes `TextGenerator.generate` to return `Generation`, and adds `Generation` to
  `domain/results.py`. Neither item 14 nor item 15 lists it.
- **Severity:** minor.
- **Correction:** add the `TextGenerator` change to item 14 and `Generation` to item 15.

### 6. LID runs as one unbounded port call

- **Claim (§2):** `speech.lid.identify(track, groups)` is called once for all groups. Only recognition is chunked
  "because one long native call cannot be interrupted".
- **Source:**
  - q2 §4.4 step 3: `tiny` took 0.4–0.9 s per window locally. q7 scales M4 timings by about 2.5 on Cloud Run.
  - A long, speech-dense video gives one window per ≤30 s of speech, so LID can take minutes in one call with no
    deadline check.
- **Severity:** minor.
- **Correction:** run `identify` over `chunks` of windows too, with the same `check_deadline` between calls. The
  contract (one guess per window, in order) already allows that.

### 7. The outcome union is slightly less strict than claimed, and `Failed` drops the detail

- **Claim (§5):** "makes invalid combinations unrepresentable"; `Failed(error_code: str)`.
- **Source:**
  - `Skipped(reason=NO_SPEECH, language=<report>)` is still representable, although the §5 table allows `language`
    only on `language_*`.
  - q1's `ErrorInfo` has `message` (and `stage`). `ScenewiseError` carries a `detail` (`ARCHITECTURE.md` §9), which
    `Failed` drops.
- **Severity:** minor.
- **Correction:**
  - Either split out `LanguageSkipped(reason: Literal[...], report: LanguageReport)`, or check the pairing in
    `Skipped.__post_init__` and soften "unrepresentable".
  - Give `Failed` a `detail: str`, so `mapping.py` can fill `ErrorInfo.message` (subject to D8's no-transcript rule).

### 8. `labels_taxonomy: str` is required, and the taxonomy read path is unstated

- **Claim (§7.5):** `labels_taxonomy: str` in `StageOptions`. §7.4 parses TOML in `app/contract/taxonomy.py`.
- **Source:**
  - q1 `StageOptions` fields all have defaults, so a required field would make every request name a taxonomy, even one
    that does not ask for labels.
  - q5 §6.1 point 2 loads taxonomies from `SCENEWISE_TAXONOMY_PATH` (a file or directory). `app` performs no file I/O
    except through ports.
- **Severity:** minor.
- **Correction:**
  - Use `labels_taxonomy: str | None = None`. `None` is valid only when exactly one taxonomy is configured; otherwise
    a request for `labels` without it is `invalid_request`.
  - State that `service` (bootstrap) reads the taxonomy files and passes bytes or parsed models to `app`. The other
    option is that `app` reads them through `BlobStore`, as `calibrate` does.

### 9. `ROADMAP.md` is not in the knock-on lists

- **Claim:** §6 and §9 list the files that change.
- **Source:**
  - `ROADMAP.md` §0: "Model dependencies are pinned in extras (`asr`, `asr-whisper`, …, plus CPU/CUDA selector
    pairs)".
  - `ROADMAP.md` §2: "A summary is emitted only above about 40 transcript words".
- **Severity:** minor.
- **Correction:** add a `ROADMAP.md` line to §6.4 (or a new §6.5): one `asr` extra, one torch selector pair, and the
  summary visual fall-through.

### 10. "PyAV never decodes" holds, but PyAV is still loaded in-process

- **Claim (§3):** the arrays-only rule "keeps `decode_audio` unused … ffmpeg stays the only decoder". The contract
  tests patch `faster_whisper.transcribe.decode_audio` to raise.
- **Source:**
  - `faster_whisper/__init__.py` imports `faster_whisper.audio`, which runs `import av` at module load. PyAV and its
    bundled FFmpeg libraries are therefore mapped into the service process whenever an ASR adapter is constructed,
    even though no untrusted byte reaches them.
  - `detect_language` has no decode path at all (ndarray or features only). The "never called" assertion therefore
    tests something only for the recogniser.
- **Severity:** minor (the security argument stands; the wording should be exact).
- **Correction:**
  - Say "PyAV is imported but never given input".
  - Keep the patch on `faster_whisper.transcribe.decode_audio`, which is the correct bound name (transcribe.py L19).
  - Assert it only in the `FasterWhisperRecognizer` suite. The LID suite can instead assert that it passes an
    `np.ndarray`.

## Summary

| Severity | Count | Findings |
|---|---|---|
| wrong | 1 | 3 |
| unsupported | 0 | — |
| design concern | 2 | 1, 2 |
| missing | 1 | 4 |
| minor | 6 | 5–10 |
