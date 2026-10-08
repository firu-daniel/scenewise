# Review r1 of `q8c-reconciliation.md`

Reviewer: a fresh review agent. I did not write this file or review it before. Review date: **2026-10-08**.

## Method

- Read q8c in full. For every resolution, I opened the cited sections: q1 §4.0, §5.1–5.3, §9, OQ13; q2 §1, §4.2–4.5, §5.1–5.3, §6, §7; q3 §1, §7 table, OQ7; q4 summary and the refusal section; q5 §4, §6.1–6.3; q7 §1, §2.2, §2.5; q8a §1.4, §1.5, §4, §5, §6.2, §6.3, §7.1, §8, §9.1–9.5; q8b §1–§3, §6, §8, §11–§13, §15.1. Also `user-decisions.md`, `open-decisions.md` (D18–D23) and `ARCHITECTURE.md` (§17 and every ASR/extras/gates passage).
- **PyPI JSON** (2026-10-08), `/pypi/<name>[/<version>]/json`:
  - faster-whisper 1.2.1 `requires_dist` contains `onnxruntime<2,>=1.14` (hard), `av>=11`, `ctranslate2<5,>=4.0`.
  - sherpa-onnx 1.13.8 requires `sherpa-onnx-core==1.13.8`; cp310–cp314 wheels.
  - onnx-asr 0.12.0: only `numpy>=1.22.4` is hard; onnxruntime is in `cpu`, onnxruntime-gpu in `gpu`, huggingface-hub in `hub`.
  - onnxruntime 1.30.0 and onnxruntime-gpu 1.30.0: `requires_python >=3.11`.
  - numpy 2.5.3: `>=3.12`, uploaded 2026-09-06. Pillow 12.3.0: `>=3.10`, uploaded 2026-07-01.
  - anthropic 1.12.1: the `vertex` extra pulls `google-auth[requests]`. av 19.0.1 needs `>=3.12`.
  - These are still the latest versions of faster-whisper, sherpa-onnx, onnx-asr, numpy and onnxruntime.
- **Wheel contents** (downloaded into the scratchpad, listed only, never executed):
  - `sherpa_onnx_core-1.13.8-py3-none-manylinux2014_x86_64.whl` contains `sherpa_onnx/lib/libonnxruntime.so`.
  - Neither that wheel nor `sherpa_onnx-1.13.8-cp312-…manylinux…x86_64.whl` contains `py.typed` or `.pyi`. Both distributions ship files under `sherpa_onnx/`.
  - `onnx_asr-0.12.0-py3-none-any.whl` **does** contain `onnx_asr/py.typed`.
- **Source checks:**
  - faster-whisper 1.2.1 `audio.py`: `format="s16"` and `/ 32768.0`.
  - `transcribe.py`:
    - `detect_language(audio: Optional[np.ndarray] = None, …)` returns `(language, probability, all_language_probs)`. With `vad_filter=True` it **concatenates** the speech chunks (L1803–1806).
    - Word probability is `np.mean(text_token_probs[i:j])` (L1746–1749).
  - onnx-asr 0.12.0 `asr.py`: `TimestampedResult` has `timestamps`, `tokens` **and** `logprobs` ("Tokens logprob list"). The timestamped adapter passes `need_logprobs="yes"`.
- **k2-fsa CUDA wheels:**
  - https://k2-fsa.github.io/sherpa/onnx/cuda.html is a flat HTML list of links.
  - `sherpa_onnx-1.13.8+cuda13.cudnn9.onnxruntime1.28.2-cp312-cp312-linux_x86_64.whl` exists. I read its METADATA by HTTP range requests: `Name: sherpa_onnx`, with **no `Requires-Dist`**. It ships `sherpa_onnx/lib/libonnxruntime_providers_tensorrt.so` and other files, so it is a monolithic wheel.

Severity scale: **wrong** / **unsupported** / **design concern** / **missing** / **minor**.

## What holds (verified, no finding)

- **Package facts [X1]–[X3]** are correct as stated. The onnxruntime / onnxruntime-gpu clash is real: both install the `onnxruntime` import package, and faster-whisper hard-requires the CPU distribution.
- **One CPU-only `asr` extra** is the right call:
  - faster-whisper is needed on every captions job for language ID (LID), so it cannot be optional;
  - onnx-asr is pure Python;
  - dropping `ort-*` removes the clash and the onnxruntime CUDA start-up probe;
  - numpy must be declared (deptry DEP003).
  - None of this contradicts U4, D12 or D20.
- **Item 8 is required, not just tidy.** Dropping the onnxruntime `ignore_imports` entry is necessary: `unmatched_ignore_imports_alerting = "error"` would fail import-linter once bootstrap stops importing onnxruntime. Adding `sherpa_onnx` to the `forbidden` contract is safe because `forbidden` tolerates absent packages (q8b §3).
- **The `SpeechRecognizer` shape** (`track: Path`, spans, `language`) works for all three runtimes:
  - sherpa-onnx `accept_waveform(16000, float32)`;
  - onnx-asr `recognize(ndarray | list[ndarray])`;
  - faster-whisper `transcribe(ndarray, language="en", word_timestamps=True)`, mapping each Whisper word (leading space included) to one `Token`.
- **The arithmetic is right:** 1.92 MB per 30 s of float32, 172.8 MB s16 for 90 min, 168,750 hops of 32 ms for 90 min, and 4.6M multiply-adds.
- **A per-hop probability VAD port is a sensible boundary.**
  - The lowest-probability cut needs per-hop values (q2 §4.2), and that is exactly why sherpa's VAD was rejected.
  - A 168,750-float tuple is about 5.4 MB of Python objects. A pure-Python pass over it takes milliseconds.
  - Returning runs instead would move the tunable policy into the adapter.
- **The new ports are the minimal set:**
  - `VoiceActivityDetector` and `LanguageIdentifier`, both model boundaries;
  - `ImageGuard`, a separate port because its input is an image and its output is logprobs;
  - `ZeroShotLabeller → LabelScores` and `TextGenerator → Generation`, both changes to existing ports.
  - `Speech` as one optional member is not ceremony: it enforces "no recogniser without its gate".
- **The status rule is consistent with the user decisions.** D23 (ud: `skipped` / `no_speech`, no VTT) is applied correctly. Removing q1's "succeeded + reason" exception is a pre-release change to an unshipped contract, and new `SkipReason` values plus `partial_language` / `detected_languages` are additive.
- **The 27 skeleton edits do not by themselves make any gate fail.** Every skeleton-level signature fits `max-args = 5` and `max-positional-args = 3`, and the mypy override list (item 5) matches the wheels. Exceptions are in findings 5, 9 and 19.

## Findings

### 1. LID windows are sent as envelopes, which feeds non-speech into Whisper

- **Claim (§2):** `speech.lid.identify(track, [envelope(g) for g in groups])`, where a group is "adjacent segments merged … spanning 3–30 s". The port docstring says "Windows are VAD speech only (q2 §4.4 step 1)".
- **Source:**
  - q2 §4.4 step 1: "Input: VAD speech only. Never run LID on the whole track". The reason given is that `detect_language` "always returns a label" on non-speech (music 0.21–0.33, silence "cy" 0.282).
  - The envelope of `[0–1 s, 20–22 s]` includes 19 s of music or silence, and that gap fills most of Whisper's single 30 s mel window.
  - faster-whisper's own `vad_filter` path **concatenates** the speech chunks before LID (transcribe.py L1803–1806); it does not use their envelope.
  - q8c's code therefore contradicts its own docstring.
- **Severity:** design concern.
- **Correction:**
  - Change the port to `identify(track, windows: Sequence[Sequence[TimeSpan]]) -> list[LanguageGuess]`. Each window is the speech spans of one group; the adapter reads them and concatenates them before `detect_language(vad_filter=False)`.
  - Let `lid_windows` bound the **speech** duration of a group to 3–30 s, not its envelope.
  - Drop the undefined `envelope()` helper.

### 2. `Skipped(plan.skip)` drops the data §5 and D21 require on a language skip

- **Claim:**
  - §2: `if plan.skip is not None: return Skipped(plan.skip)`.
  - §5: "For `language_unsupported`, `captions.language` holds the dominant detected language". §7.3 adds `detected_languages`.
- **Source:**
  - q2 §4.4 step 5: "Set `language_unsupported: <dominant language>`".
  - D21: unknown windows are "dropped and flagged".
  - `Skipped` carries only a reason, so the dominant language and `plan.detected` are lost exactly in the skip cases. `LanguagePlan` also has no `dominant` field.
- **Severity:** missing.
- **Correction:**
  - Return `Skipped(reason, language_plan: LanguagePlan | None)`, or one `CaptionsOutcome` that always carries the plan.
  - Add `dominant: str | None` to `LanguagePlan`.
  - State that `detected_languages` is filled on `skipped / language_*` too. Under §5's table that means `skipped` may carry these two informational fields besides `reason`.

### 3. §7.6 caches "the one large model", but §3, D20 and q8b need more

- **Claim (§7.6):** "the `models` job caches the pinned Parakeet int8 export as the one large model … Silero … and Whisper `tiny` … are already small."
- **Source:**
  - q8c §3: "CI runs both [sherpa-onnx and onnx-asr] on the same fixtures (q2 §5.1)".
  - D20: "onnx-asr tested second".
  - q2 §5.2: onnx-asr uses a **different** export, `istupakov/parakeet-tdt-0.6b-v2-onnx`, with its own 652 MB int8 encoder.
  - q8b §6 table: the `SpeechRecognizer` contract runs against "parakeet and faster-whisper (`model`)". The faster-whisper fallback's large-v3-turbo is about 1.6 GB.
  - So the plan as written either cannot run the second runtime or must download another 0.65–2.3 GB.
- **Severity:** wrong (internally inconsistent with §3 and D20).
- **Correction:**
  - Cache both Parakeet exports, about 1.3 GB together, keyed on `tests/models.lock`.
  - Run `FasterWhisperRecognizer`'s contract with `tiny`: the adapter is model-agnostic, and `tiny` is already cached for LID.
  - State the cache size against GitHub's 10 GB per-repo cache limit.

### 4. `below_minimum` for summaries misstates U7 / q3 and would skip summaries of silent videos

- **Claim (§5):** "a summary needs more than about 40 transcript words".
- **Source:**
  - q3 §1: "Emit a summary only when the transcript has at least about 40 words, **or when visual labels are rich enough**". The q3 thresholds table says, below 40 words, "fall through to the visual rule".
  - q1 §9: for audio-less videos, "Summary, chapters, labels and moderation still run on visual input".
  - q8a §5: SUMMARY needs "a transcript or visual input".
  - Applied literally, the rule skips every summary of a no-audio or no-speech video.
- **Severity:** wrong (unfaithful to the cited finding).
- **Correction:** `below_minimum` applies to the summary only when the transcript has 40 words or fewer **and** no visual input (or the visual rule fails). Also record in §9 that `skipped / below_minimum` for chapters supersedes q3's "Omit (`chapters: []`)".

### 5. Two §4.3 signatures would fail the ruff gate as written (item 4 sketch, not the skeleton)

- **Claim (§4.3):**
  - `calibrate(taxonomy_uri, labels_uri, frames_uri, *, deps, target_precision, min_positives)`;
  - `entry_matches(entry, model_id, taxonomy_hash, preprocess, score_stat)`.
- **Source:** q8b §11 sets `max-args = 5` (PLR0913 counts keyword-only parameters too) and `max-positional-args = 3` (PLR0917), and `src/` has no per-file exemption. `calibrate` has 6 parameters, and `entry_matches` has 5 positional ones.
- **Severity:** minor (a roadmap-item-4 sketch; not one of the 27 skeleton edits).
- **Correction:** `calibrate(request: CalibrationRequest, *, deps)` with a frozen dataclass, and `entry_matches(entry, *, serving: ServingSetup)`.

### 6. The later GPU-ASR route names the wrong packages and the wrong index type

- **Claim (§3):**
  - "Add an `asr-cuda13` selector that routes `sherpa-onnx`/`sherpa-onnx-core` to the `+cuda13` builds on k2-fsa's wheel index through `[tool.uv.sources]` plus an explicit `[[tool.uv.index]]`, the same mechanism as torch".
  - "This keeps the bundled-runtime model".
- **Source (checked):**
  - The k2-fsa page is a flat HTML list of links (wheels hosted on `huggingface.co/csukuangfj2/sherpa-onnx-wheels`), not a PEP 503 simple index like PyTorch's.
  - The CUDA build is one monolithic `sherpa_onnx-1.13.8+cuda13.cudnn9.onnxruntime1.28.2` wheel with **no `Requires-Dist`**. There is no CUDA `sherpa-onnx-core`.
  - So it is not "the same mechanism as torch". Routing `sherpa-onnx-core` has nothing to route to; the core dependency simply disappears under that extra. "Keeps the bundled runtime" is still true.
- **Severity:** wrong (detail; not v1).
- **Correction:**
  - Use `[[tool.uv.index]] name = "sherpa-cuda", url = "https://k2-fsa.github.io/sherpa/onnx/cuda.html", format = "flat", explicit = true`, and route **only** `sherpa-onnx` under the extra.
  - Add a `check_lock.sh` assertion that `sherpa-onnx-core` is absent and `sherpa-onnx==…+cuda13…` is present under it.
  - Note that the wheel expects CUDA 13 and cuDNN 9 from the image (not verified here).

### 7. Folding faster-whisper into `asr` makes PyAV a permanent dependency, and q8c does not say so

- **Claim:** §3 puts faster-whisper in the one `asr` extra, and the §9 table lists no change to q8a §9.1.
- **Source:**
  - q8a §9.1 rejects in-process decoding of untrusted media, and says: "With Parakeet/onnx-asr as the ASR default, PyAV is not even a transitive dependency. faster-whisper's `av>=11` applies only to the `asr-whisper` extra".
  - faster-whisper 1.2.1 hard-requires `av>=11` (PyPI). av 19.0.1 ships wheels with FFmpeg bundled.
  - `faster_whisper.decode_audio` decodes **in-process** whenever a path or file object is passed to `transcribe` or `detect_language`.
- **Severity:** missing.
- **Correction:**
  - Record in §9 that q8a §9.1's statement is superseded.
  - Add a rule (and a contract-test assertion) that the faster-whisper adapters pass only `np.ndarray` audio from `wav.read_span`, never a path.
  - Add the licence of av's bundled FFmpeg libraries to the NOTICE review list in item 21, since every image now ships them (not verified here).

### 8. OQ7 Option A with "no bypass" and a sole code owner blocks the maintainer's own gate PRs

- **Claim (§8):** "`@firu-daniel` (D5) is the only code owner, and the ruleset requires code-owner review with no bypass."
- **Source:**
  - q8b OQ7, Option A "Against": "every gate-config PR the maintainer writes needs a second identity's approval or a temporary bypass".
  - On GitHub, a pull request author cannot approve their own PR. A sole code owner who authors a gate change can therefore never satisfy "Require review from Code Owners" without bypass.
  - q8c recommends Option A but drops this cost and gives no workaround.
- **Severity:** design concern.
- **Correction:** keep Option A, but specify one of these:
  - the maintainer's account (never the bot) is on the ruleset bypass list in "pull requests only" mode, so the bypass is visible on the PR; or
  - all gate-file changes are authored by the bot and approved by the maintainer.
- State the choice in the repository-setup step.

### 9. §6.4 misses several `ARCHITECTURE.md` passages that the decisions invalidate

- **Claim:** items 22–27 list §4, §5, §6, §8, §12 and §17.
- **Source (`ARCHITECTURE.md`, read-only):** these passages also contradict q8c:
  - §2 tree, line 131: `asr/` "one module per runtime behind SpeechRecognizer". It now also holds `wav.py`, `silero_vad.py` and `whisper_lid.py`.
  - §13 table, lines 582–586: "Every `SpeechRecognizer` returns ordered, absolute-time segments"; "bootstrap constructs the adapter with `model=…, device=…`". There is no ASR `device` in v1.
  - §12, line 566: the onnxruntime providers probe.
  - §16 gate table:
    - line 696: "bootstrap's two start-up probes (onnxruntime, torch)";
    - line 705: lock routing "no torch in `service + asr + ort-cu130`";
    - line 706: deptry "maps `onnxruntime-gpu`".
  - §15, line 664: the contract-suite list needs the VAD and LID suites (§7.7).
- **Severity:** missing.
- **Correction:** add §2, §13, §15 and §16 to §6.4, with the replacement text from §3, §6.1 items 7–9 and §7.7.

### 10. §7.5 does not reconcile q1's `Label` with q5's label object

- **Claim (§7.5):** "`LabelsResult` echoes `taxonomy {id, version, hash}` and `model.id` … and carries `calibrated` per label and an optional `video_embedding`." Also `labels_max` (exists) = `top_k`.
- **Source:**
  - q1 §5.3: `Label{name, confidence, segments, source: frames|transcript|both}`.
  - q5 §6.2: `{id, name, path, score_max, score_mean, frames, calibrated}`, plus an optional `external_id` echo.
  - The two shapes differ in five fields.
  - q5 §6.2 also puts a default `top_k` in the taxonomy file ("only `top_k` may be overridden" per request). q1's `labels_max` has a request default, so the taxonomy value could never apply.
- **Severity:** missing.
- **Correction:**
  - Define the v1 `Label` explicitly, e.g. `id, name, path, confidence (= score_max), score_mean, calibrated, external_id?`, and drop or defer `segments` and `source`, since q5 has no transcript labels.
  - Make `labels_max: int | None = None`, so that `None` means the taxonomy's `top_k`.

### 11. Log-probabilities: the semantics differ by runtime, and onnx-asr is under-reported

- **Claim (§1):**
  - `Token.log_prob` is "per token (sherpa-onnx ys_log_probs); faster-whisper: log(word.probability)";
  - `Word.log_prob` is the "sum over its tokens";
  - onnx-asr is left implicit as `None`, by analogy with `end_hint`.
- **Source:**
  - faster-whisper's `word.probability` is the **mean** of token probabilities (transcribe.py L1746–1749). log(mean p) is not comparable with a sum of token log-probabilities. A zero probability gives −inf.
  - onnx-asr 0.12.0 returns per-token `logprobs` (`TimestampedResult.logprobs`, `need_logprobs="yes"`).
- **Severity:** minor.
- **Correction:**
  - Define `Word.log_prob` as the **mean** per-token log-probability, a confidence value comparable across runtimes. q2 T3 compares mean token log-probabilities anyway.
  - The faster-whisper adapter maps `log(max(p, 1e-6))`.
  - Map onnx-asr's `logprobs`. Only `end_hint` is `None` for onnx-asr.

### 12. The word-end rule is ambiguous at its edges

- **Claim (§1):** the provisional end is "its last token's end_hint, else the next token's start". It "is then extended to the start of the next pause … or to start + min_hold, whichever is earlier, and never past the next word."
- **Source:**
  - Read literally, "whichever is earlier" can *shorten* a word whose provisional end is later than `start + min_hold`.
  - The last token of a `RecognizedSegment` with `end_hint=None` (onnx-asr) has no next token.
  - q2 §4.5 step 6 only says "extended to the next pause or a minimum hold".
- **Severity:** minor.
- **Correction:**
  - `end = min(next_word.start, max(provisional, min(next_pause_start, start + min_hold)))`.
  - For the last token of a segment without an `end_hint`, the provisional end is `span.end`.
  - Make both cases hypothesis properties.

### 13. `StageOutcome.reason: SkipReason | str | None` is `str | None` to the type checker

- **Claim (§5):** "`StageOutcome.reason` is typed `SkipReason | str | None` and validated in `__post_init__` against the table."
- **Source:**
  - `SkipReason` is a `StrEnum`, so the union collapses to `str | None` for mypy. The status/reason coupling becomes a runtime check in a codebase whose gates rely on mypy strict and `exhaustive-match` (q8b §11).
  - q8a §5 and §8 already carry the error separately (`error_code`, `ErrorInfo`).
- **Severity:** design concern (small).
- **Correction:**
  - Model the domain outcome as a tagged union: `Succeeded | Skipped(reason: SkipReason, …) | Failed(error: ErrorRef)`.
  - Let `app/contract/mapping.py` derive the wire `status`, `reason` and `error`. The wire shape stays exactly q1's, and invalid combinations become unrepresentable instead of validated.

### 14. Language codes: "ISO 639-1" and the `"unknown"` key

- **Claim (§2, §7.3):**
  - `LanguageGuess.language` is "ISO 639-1 as faster-whisper returns it";
  - `detected_languages` keys include `"unknown"`.
- **Source:**
  - Whisper's language set includes `haw` and `yue` (three-letter codes), so it is not purely ISO 639-1.
  - q1 §5.2 types `CaptionsResult.language` as "BCP-47". BCP 47's code for an undetermined language is `und`; `"unknown"` is not a valid tag.
- **Severity:** minor.
- **Correction:** say "Whisper language code (BCP-47 primary subtag)" and use `"und"` for unknown windows on the wire.

### 15. Refusals: `FallbackTextGenerator` behaviour is not stated

- **Claim (§7.1):** `generate(...) -> Generation(text, model, refused)`; "never retried automatically (D18)".
- **Source:**
  - q8a §1.4 / §4: `FallbackTextGenerator(primary, secondary)` wraps two back ends.
  - D18 (ud): "No automatic refusal fallback in v1".
  - q3 says "A refused response may not match the schema [S4]", so `app/llm_output.py` must not try to parse it.
- **Severity:** minor.
- **Correction:**
  - State that `FallbackTextGenerator` returns a refused `Generation` as is (it falls through only on `RetryableError` / unavailability).
  - State that the stage checks `refused` before any JSON parse or repair retry, so a refusal never triggers the repair prompt.

### 16. Whole-list `transcribe` defeats the cooperative deadline the new shape makes possible

- **Claim:**
  - §1/§2: `speech.recognizer.transcribe(track, plan.segments, language="en")`, one call for all segments.
  - q8a §6.3: the cooperative deadline "cannot interrupt one long native call (the whole-file `transcribe()` is one call)".
- **Source:** with span input, `app` can now check the deadline between calls. q8c passes every segment of a 90-minute track at once, which also leaves batch memory to each adapter.
- **Severity:** minor.
- **Correction:** `app/stages.py` calls `transcribe` on chunks of segments (for example up to 5 min of audio per call) and checks the deadline between chunks. The port contract already allows any subset, because it returns one result per span.

### 17. The `calibrate` CLI wiring does not match `Dependencies`

- **Claim (§4.3):** `service/cli.py` "builds `Dependencies` (`labeller` and `images` only)", and `app/calibrate.py` "reads the CSVs and taxonomy through `BlobStore`".
- **Source:** q8a §4's `Dependencies` has required, non-optional `store`, `media` and `notifier`, and the use case itself needs `store`.
- **Severity:** minor.
- **Correction:** have `calibrate` take `store`, `images` and `labeller` explicitly, built by a small `bootstrap.calibration_deps(settings)`, or build the full `Dependencies`. Do not say "only".

### 18. Item 11 narrows q2's T4

- **Claim (item 11):** "load onnxruntime, sherpa-onnx and faster-whisper in one process, in both import orders".
- **Source:** q2 T4 also requires running "one fixture through Silero, LID and both ASR adapters", recording peak RSS, and failing on a golden-file diff or on RSS over the instance budget.
- **Severity:** minor.
- **Correction:** copy T4 in full into the `models` job.

### 19. Leftovers in `check_lock.sh` and `models.lock`

- **Claims:**
  - item 9 keeps "the no-torch assertion" without changing its message ("asr + ort-cu130 pulls torch");
  - §7.6 says Silero is "already small".
- **Source:** q8b §6 keys `models.lock` on HF repo and revision, and `fetch_models.py` uses `snapshot_download`. q2 §5.2 pins Silero from **GitHub** (`snakers4/silero-vad` tag v6.2), which `snapshot_download` cannot fetch.
- **Severity:** minor.
- **Correction:**
  - Fix the message to "asr pulls torch".
  - Pin Silero in `models.lock` through its byte-identical HF mirror `istupakov/silero-vad-onnx@b3e3ee3` (q2 §4.2), checking the same sha256, or extend `fetch_models.py` to download GitHub files by URL and sha256.

### 20. OQ12: `anthropic[vertex]` already brings google-auth

- **Claim (§8, OQ12):** leave google-auth in `gcs`; "bootstrap raises `ConfigurationError("callback_auth = oidc needs scenewise[gcs]")` when the extra is missing".
- **Source:** anthropic 1.12.1's `vertex` extra requires `google-auth[requests]<3,>=2` (PyPI). An install with `llm-anthropic` but without `gcs` therefore has google-auth, so OIDC works and an import-based check never fires.
- **Severity:** minor (the recommendation still holds).
- **Correction:** note this, and base the check on `import google.oauth2.id_token` succeeding, not on whether the `gcs` extra was selected.

### 21. Item 5's "re-check onnx_asr's typing" is already settled

- **Claim (item 5):** "Re-check onnx_asr's typing once the adapter exists (q8b §1 says it is typed)."
- **Source:** the `onnx_asr-0.12.0` wheel contains `onnx_asr/py.typed` (checked).
- **Severity:** minor.
- **Correction:** state it as verified; onnx_asr needs no override.

### 22. The s16 WAV format is assumed but not part of the `MediaTool` contract

- **Claim (§1):** the track is a "16 kHz mono s16 WAV from MediaTool.audio_track", and `wav.py` reads it with stdlib `wave`.
- **Source:**
  - q8a §4's `audio_track` docstring says only "16 kHz mono WAV".
  - Stdlib `wave` reads only integer PCM (`WAVE_FORMAT_PCM`; `WAVE_FORMAT_EXTENSIBLE` from 3.12). A float or other codec change in the ffmpeg adapter would break every speech adapter.
- **Severity:** minor (a missing knock-on edit).
- **Correction:** add to items 14/22 that the `MediaTool.audio_track` docstring and its contract test pin `pcm_s16le`, 16 kHz, mono.

### 23. The fallback recogniser's decoding settings conflict with q2 §4.3 and are not restated

- **Claim:** §2 lists `adapters/asr/faster_whisper.py` as the fallback `SpeechRecognizer` with no settings.
- **Source:**
  - q2 §4.3 recommends `vad_filter=True` for the fallback, but under q8c it decodes spans that scenewise's VAD already cut. That is the same "second VAD adds nothing" case q2 §4.4 step 1 states for LID.
  - Word timestamps are needed to fill `Token`s.
  - Whisper's DTW word times can fall slightly outside a span, which breaks the "inside their span" contract.
- **Severity:** minor.
- **Correction:**
  - Specify `vad_filter=False`, `word_timestamps=True`, `condition_on_previous_text=False` and `language="en"`.
  - The adapter clamps word times into the span.
  - Keep q2's other §4.3 thresholds.

### 24. OQ13 rationale: the cooldown covers only Dependabot

- **Claim (§8, OQ13):** "Dependabot's 14-day cooldown (q8b §13) leaves room to act before a pin bump lands."
- **Source:** the cooldown applies only to Dependabot PRs. A pin edited by an agent or by hand in a workflow merges with only offline zizmor, and the online checks (impostor commits, ref confusion) see it at the next nightly run.
- **Severity:** minor (the recommendation stands).
- **Correction:** add that a gate-file PR changing `uses:` pins is CODEOWNERS-reviewed (§13), which covers the window the cooldown does not.

## Summary

| Severity | Count | Findings |
|---|---|---|
| wrong | 3 | 3, 4, 6 |
| unsupported | 0 | — |
| design concern | 3 | 1, 8, 13 |
| missing | 4 | 2, 7, 9, 10 |
| minor | 14 | 5, 11, 12, 14–24 |
