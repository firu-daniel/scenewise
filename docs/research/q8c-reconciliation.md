# Q8 part C: reconciling the final findings before the skeleton

Research date: 2026-10-08. Scope: the conflicts that writing `ARCHITECTURE.md` (draft) surfaced in its §17 "Open items",
plus three items from the decision document (`docs/decisions/initial-research.md` §7.5) and the conflicts found while
reading. Every item proposes **one** design, with a short rationale, the alternatives rejected, and the concrete
signatures, extras and paths. Settled decisions override findings: U1–U12 and D2–D31 in
[user-decisions.md](user-decisions.md) ("ud" below).

Inputs: [q1](q1-input-contract.md), [q2](q2-captions.md), [q3](q3-summaries-chapters.md), [q4](q4-moderation.md),
[q5](q5-labels.md), [q7](q7-runtime-cost.md), [q8a](q8a-architecture-layout.md), [q8b](q8b-tooling-gates.md),
`ARCHITECTURE.md` (read only). External checks, all read 2026-10-08:

- [X1] PyPI JSON API, `https://pypi.org/pypi/<name>/<version>/json`: faster-whisper 1.2.1 `requires_dist` includes
  `onnxruntime<2,>=1.14` (a hard dependency, not an extra); sherpa-onnx 1.13.8 requires `sherpa-onnx-core==1.13.8`;
  onnx-asr 0.12.0 puts onnxruntime only in its `cpu`/`gpu` extras; onnxruntime 1.30.0 requires Python ≥3.11;
  Pillow latest 12.3.0 (2026-07-01, Python ≥3.10); numpy 2.5.3 (Python ≥3.12).
- [X2] Wheel contents, downloaded from PyPI: `sherpa_onnx_core-1.13.8-py3-none-macosx_11_0_arm64.whl` contains
  `sherpa_onnx/lib/libonnxruntime.dylib` (29,006,384 bytes, the bundled runtime); neither it nor
  `sherpa_onnx-1.13.8-cp312-cp312-macosx_11_0_arm64.whl` ships a `py.typed` or `.pyi` file.
- [X3] faster-whisper v1.2.1 `faster_whisper/audio.py`, https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/faster_whisper/audio.py:
  `decode_audio` resamples with `AudioResampler(format="s16", …)` and converts with `astype(np.float32) / 32768.0`;
  `transcribe.py` `detect_language(audio: Optional[np.ndarray] = None, …)`.
- [X4] Re-checked for review round 1: faster-whisper 1.2.1 `requires_dist` also hard-requires `av>=11`; anthropic
  1.12.1's `vertex` extra requires `google-auth[requests]<3,>=2`; onnx-asr v0.12.0 `src/onnx_asr/` contains
  `py.typed`, and `asr.py` `TimestampedResult` has `logprobs: list[float] | None` ("Tokens logprob list"), filled when
  the decoder is asked with `need_logprobs`.
- [X5] Re-checked for review round 2: faster-whisper v1.2.1 `transcribe.py` L394–423 and `vad.py` L186
  (`collect_chunks`); WhisperX `whisperx/vads/vad.py` `merge_chunks`; GitHub docs "Creating rulesets for a
  repository" (bypass actors and "For pull requests only").

---

## 0. Decisions at a glance

| # | Conflict | Decision |
|---|---|---|
| 1 | `SpeechRecognizer` shape | `transcribe(track: Path, segments: Sequence[TimeSpan], *, language: str) -> list[RecognizedSegment]`. The boundary is the one 16 kHz mono `pcm_s16le` WAV that `MediaTool.audio_track` already produces (now pinned in its contract), plus spans; adapters slice and convert to float32 and hand faster-whisper arrays, never paths. Out come tokens with absolute start, optional end hint and log-probability; `domain/captions.py` builds words and extends ends. Spans are merged VAD runs of up to 30 s (§2). `app` calls it in chunks of ≤300 s of span audio and checks the deadline between calls. |
| 2 | VAD, LID, segmentation, music tagger | Two new ports, `VoiceActivityDetector` (per-hop probabilities) and `LanguageIdentifier` (argmax + p per window; a window is a list of speech spans the adapter concatenates, never their envelope). Run detection, ≤30 s lowest-probability cuts, LID windows, the language rule and the merge of runs into ≤30 s recognition segments are pure functions in a new `domain/speech.py`. The three speech ports are bundled as `Speech` in `app/deps.py`. The music tagger gets no port until T1 (D22). |
| 3 | `asr` extra, GPU ASR | One `asr` extra: sherpa-onnx 1.13.8, onnx-asr 0.12.0, onnxruntime 1.30.0, faster-whisper 1.2.1, numpy 2.5.3. `asr-whisper` and the `ort-cpu`/`ort-cu130` selector pair are removed. **v1 ASR is CPU-only in both images**; the `-cuda` image accelerates vision only. GPU ASR is out of v1; its packaging route is to be researched. faster-whisper makes PyAV a transitive dependency (q8a §9.1 superseded); it is imported but never given input. |
| 4 | Missing ports | Labels (now): `ZeroShotLabeller.score(...) -> LabelScores` with cosines, the model's score transform and optional frame embeddings. Item 3: an `ImageGuard` port with its own HTTP adapter in `adapters/llm/`. Item 4: `scenewise calibrate` (CLI → `app/calibrate.py` → `domain/calibration.py`). |
| 5 | No-speech status | D23 confirmed: `status: "skipped"`, `reason: "no_speech"`, no VTT. In the domain a stage outcome is a tagged union `Succeeded \| Skipped(reason) \| LanguageSkipped(reason, report) \| Failed(error_code, detail)`; the wire `status`/`reason`/`error` are derived in `app/contract/mapping.py`, so a succeeded stage cannot carry a reason. v1 summaries are speech-based: `below_minimum` under about 40 transcript words; visual-only summaries arrive with a labeller (roadmap item 4). |
| 6 | Knock-on edits | Listed file by file in §6. |
| 7 | Further conflicts | Text-generation refusals, moderation's use of SigLIP, the q1 captions fields, the D9 fields at claim time, taxonomy YAML vs the `app` allow-list, the q5 wire shape, the Parakeet size in the model tier and others (§7). |
| 8 | q8b OQ7 / OQ12 / OQ13 | OQ7: Option A plus a ruleset bypass for the **Repository admin** role in "For pull requests only" mode, which in this personal-account repository is the maintainer alone (**user decision**); google-auth stays in `gcs`, with an import-based check; online zizmor stays nightly. None blocks the skeleton (§8). |

---

## 1. `SpeechRecognizer` shape

**Conflict.** q8a §4: `transcribe(audio: Path, *, language: str | None) -> Transcript`. q2 §6: "Input: 16 kHz mono
float32 segments. Output: tokens with start seconds, an optional end hint (sherpa-onnx: start + predicted TDT
duration), and log-probabilities". q2 §4.5 step 6 puts word grouping and end extension in scenewise. Ports are
stdlib-only (q8b §12, contract "Domain and ports: stdlib only"), so no numpy array can cross.

**Decision: the boundary is the whole-track WAV path plus the spans to decode.**

```python
# scenewise/ports.py
class SpeechRecognizer(Protocol):             # sherpa-onnx Parakeet (D20) | onnx-asr Parakeet | faster-whisper
    def transcribe(
        self, track: Path, segments: Sequence[TimeSpan], *, language: str
    ) -> list[RecognizedSegment]:
        """Decode each span of `track` (16 kHz mono pcm_s16le WAV from MediaTool.audio_track).

        Contract: one RecognizedSegment per input span, in input order; token times are absolute
        track seconds inside their span, non-decreasing; a token that starts a word begins with
        one space (adapters map SentencePiece "▁"); end_hint is None when the runtime has none.
        """
```

```python
# scenewise/domain/results.py  (new values; stdlib only)
@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    text: str                   # " the" starts a word; "re" continues one
    start: Seconds              # absolute track time
    end_hint: Seconds | None    # sherpa-onnx: start + predicted TDT duration (0–0.32 s, may equal start);
                                # onnx-asr: None; faster-whisper: its word end
    log_prob: float | None      # sherpa-onnx: ys_log_probs; onnx-asr: TimestampedResult.logprobs [X4];
                                # faster-whisper: log(max(word.probability, 1e-6)), one Token per Whisper word

@dataclass(frozen=True, slots=True, kw_only=True)
class RecognizedSegment:
    span: TimeSpan
    tokens: tuple[Token, ...]

@dataclass(frozen=True, slots=True, kw_only=True)
class Word:
    text: str
    span: TimeSpan              # end = extended end (below), never a raw end_hint
    log_prob: float | None      # mean of its tokens' log_prob; None if any token has none

# Transcript changes from q8a §5: words replace the bare text segments as the source of truth.
@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptSegment:
    span: TimeSpan
    words: tuple[Word, ...]
    @property
    def text(self) -> str: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class Transcript:
    language: str
    segments: tuple[TranscriptSegment, ...]
```

Pure core in `domain/captions.py`:

```python
def words(recognized: Sequence[RecognizedSegment], *, pauses: Sequence[TimeSpan],
          min_hold: Seconds) -> tuple[Word, ...]: ...
    # groups tokens at the leading-space boundary (q2 §4.5 step 6). A word's provisional end p is its last
    # token's end_hint, else the next token's start, else (last token of a segment) span.end. Then
    #   end = min(next_word.start, max(p, min(next_pause.start, start + min_hold)))
    # so extension never shortens a word and never overlaps the next one (no next word/pause ⇒ that term drops).
    # Both edge cases are hypothesis properties.
def transcript(recognized, *, pauses, language, min_hold) -> Transcript: ...
def cues(transcript: Transcript, *, layout: CueLayout = CueLayout()) -> tuple[Cue, ...]: ...
    # CueLayout(max_chars=42, max_lines=2, max_duration=7.0): keeps every sketch within max-args 5 (q8b §11)
def render_webvtt(cues: Sequence[Cue], *, note: str) -> str: ...
```

**Rationale.**
- The track already exists: `MediaTool.audio_track` yields one local 16 kHz mono WAV (q8a §4). Passing it with spans
  creates no per-segment temp files, which was q8a §9.3's objection to paths for frames. Memory stays bounded,
  because each adapter reads only the spans it decodes (≤30 s, §2). A 90-minute track is never held in memory.
- s16 loses nothing that matters: faster-whisper itself decodes to s16 and divides by 32768 [X3]. The adapters do the
  same (stdlib `wave` to read, then `numpy.frombuffer(..., "<i2").astype(np.float32) / 32768`). That gives the
  "float32 segments" of q2 §6 inside the adapter. Stdlib `wave` reads integer PCM only, so the `MediaTool.audio_track`
  docstring and its contract test pin `pcm_s16le`, 16 kHz, mono (§6.3 item 14).
- **faster-whisper gets arrays, never paths.** Passing a path or file object makes `faster_whisper.decode_audio` decode
  in-process with PyAV, which q8a §9.1 rejects for untrusted media. Both faster-whisper adapters pass only the float32
  arrays from `wav.read_span`. `WhisperModel.transcribe` decodes only when it is given something other than an
  `np.ndarray` (transcribe.py L875–876), so the `FasterWhisperRecognizer` contract suite patches
  `faster_whisper.transcribe.decode_audio` (the name bound by transcribe.py L19) to raise. `detect_language` has no
  decode path at all (ndarray or features only), so the `WhisperLanguageIdentifier` suite instead asserts that the
  model receives an `np.ndarray`.
- **Log-probabilities are confidence values, not likelihoods to sum.** `Word.log_prob` is a mean, so words of different
  token counts compare. The runtimes still differ: faster-whisper only exposes log(mean p) per word, which by Jensen's
  inequality is ≥ the mean token log-probability. Any threshold on it (q2 T3) is therefore set per runtime.
- **Chunked calls.** `app/stages.py` passes the merged segments (§2) in chunks of at most `SpeechPolicy.decode_chunk`
  (300 s of summed segment length, i.e. of audio the recogniser decodes) and checks the cooperative deadline between
  calls (q8a §6.3: one long native call cannot be interrupted). The contract already allows any subset of spans, and
  each adapter's batch memory stays bounded. Because segments are merged to up to 30 s, a chunk holds about 10–15
  segments, so one call is about 10–15 Parakeet segment decodes (about 23 s at q7's 12.9 RTFx on 4 vCPUs) or 10–15
  Whisper 30 s encoder passes. Call counts per job are in §2.
- The time contract (absolute seconds, input order) is the Liskov rule `ARCHITECTURE.md` §13 already states. It is
  checked by one contract suite for all three runtimes.
- `language` is required. Captions are English in v1 (q2 title, D19), and the LID gate (§2) decides which spans to send.
  Passing "en" also stops faster-whisper from auto-detecting the language per span.
- The domain owns word ends. A TDT duration "is a predicted frame advance, not a measured word end" (q2 §1, §4.5
  step 6), and onnx-asr has none (q2 §5.1). Making extension a pure function lets T2 (q2 §7) tune `min_hold`
  without touching an adapter.

**Rejected.**
- *PCM bytes per segment* (`AudioClip(start, sample_rate, samples: bytes)`): `app` would have to read and slice the
  WAV (I/O plus 1.9 MB of float32 per 30 s through `app`), and VAD would need the whole track as bytes (172 MB s16 for
  90 minutes).
- *One WAV path per segment*: this adds temp-file management, the reason q8a §9.3 rejected paths for frames.
- *Keeping `-> Transcript`*: the token log-probabilities, end hints and the word-building policy would disappear into
  each adapter, three times over.

---

## 2. Where VAD, the language-ID gate, segmentation and the music tagger live

**Conflict.** q2 §6: "VAD (scenewise's own Silero loop on pip onnxruntime), segmentation, the LID gate, the optional
music tagger and cue building live in scenewise, not in the adapters." They need onnxruntime, numpy and
faster-whisper, which the allow-list contracts ban from `domain`, `ports` and `app` (q8b §12). q8a has no port for them
(ARCHITECTURE §17).

**Decision: the models go behind two new ports; the policy is pure domain code.** "In scenewise, not in the adapters"
is read as "not inside the *ASR runtime* adapters". The models run in their own adapters, and every decision about
them is made in `domain/speech.py`.

```python
# scenewise/ports.py
class VoiceActivityDetector(Protocol):        # Silero v6.2 ONNX loop on pip onnxruntime (q2 §4.2)
    def speech_probabilities(self, track: Path) -> SpeechProbabilities:
        """P(speech) for every hop of the whole track, from t = 0; recurrent state lives in the call."""

class LanguageIdentifier(Protocol):           # faster-whisper `tiny` int8, detect_language(vad_filter=False) (q2 §4.4)
    def identify(self, track: Path, windows: Sequence[Sequence[TimeSpan]]) -> list[LanguageGuess]:
        """One argmax guess per window, in order. A window is the VAD speech spans of one group; the adapter
        reads and concatenates them (as faster-whisper's own vad_filter path does) and calls
        detect_language(audio=<ndarray>, vad_filter=False). The gaps between spans never reach Whisper
        (q2 §4.4 step 1)."""
```

```python
# scenewise/domain/speech.py  (new; stdlib only)
@dataclass(frozen=True, slots=True, kw_only=True)
class SpeechProbabilities:
    hop: Seconds                    # 0.032 s for Silero at 16 kHz (512-sample hop, q2 §4.2)
    values: tuple[float, ...]       # each in [0, 1]; ≈168,750 values for 90 min

@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageGuess:
    language: str                   # Whisper language code = BCP-47 primary subtag ("en", "de", "haw", "yue")
    probability: float

@dataclass(frozen=True, slots=True, kw_only=True)
class SpeechPolicy:                 # starting values; q2 T1–T4 tune them; settings group `captions`
    threshold: float = 0.5          # q2 §4.2
    neg_threshold: float = 0.35     # hysteresis, threshold − 0.15 as in onnx-asr (q2 §4.2 table)
    min_speech: Seconds = 0.25
    min_silence: Seconds = 0.1
    pad: Seconds = 0.03
    max_segment: Seconds = 30.0     # q2 §4.2, §4.5 step 3
    cut_search: Seconds = 5.0       # "the last few seconds before the cap" (q2 §4.2; q2 open question 4)
    no_speech_below: Seconds = 1.0  # q2 §4.5 step 2
    lid_window_min: Seconds = 3.0   # q2 §4.4 step 2
    lid_window_max: Seconds = 30.0
    lid_segment_min: Seconds = 1.0
    lid_p_min: float = 0.5          # q2 §4.4 step 4
    english_min: Seconds = 2.0      # q2 §4.4 step 5; D19
    merge_gap: Seconds = 2.0        # join runs across pauses shorter than this (see "Segmentation" below)
    decode_chunk: Seconds = 300.0   # summed segment length per SpeechRecognizer call, deadline checked between calls (§1)
    lid_chunk: int = 10             # LID windows per LanguageIdentifier call, deadline checked between calls

def speech_runs(probs: SpeechProbabilities, policy: SpeechPolicy) -> tuple[TimeSpan, ...]: ...
    # hysteresis runs; a pause of min_silence (0.1 s) or more ends a run, so ordinary speech gives runs of 1–3 s
def pieces(runs: Sequence[TimeSpan], probs: SpeechProbabilities, policy: SpeechPolicy) -> tuple[TimeSpan, ...]: ...
    # every run longer than max_segment is cut at the lowest-probability hop in [cap − cut_search, cap];
    # never a fixed offset. Shorter runs pass through unchanged.
def lid_windows(pieces: Sequence[TimeSpan], policy: SpeechPolicy) -> tuple[tuple[TimeSpan, ...], ...]: ...
    # adjacent pieces grouped into windows of 3–30 s of *speech* (summed piece lengths, not the envelope);
    # every piece is in exactly one window; a lone piece < lid_segment_min that cannot join one is "und"
def decide_language(windows, guesses: Sequence[LanguageGuess], policy: SpeechPolicy, *, target: str = "en") -> LanguagePlan: ...
def segments(stretches: Sequence[Sequence[TimeSpan]], policy: SpeechPolicy) -> tuple[TimeSpan, ...]: ...
    # within each stretch, join consecutive pieces while the gap to the next piece is < merge_gap and the
    # joined envelope stays ≤ max_segment; otherwise start a new segment. Never joins across stretches.
def chunks[T](items: Sequence[T], *, limit: float, size: Callable[[T], float]) -> tuple[tuple[T, ...], ...]: ...
    # consecutive items, summed size ≤ limit per chunk (an item larger than limit gets a chunk of its own);
    # used for recognition (size = span length, limit = decode_chunk) and LID (size = 1, limit = lid_chunk)

@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageReport:                                 # travels on success *and* on a language skip
    dominant: str | None                              # most speech seconds among confident windows; None ⇒ all "und"
    detected: tuple[tuple[str, Seconds], ...]         # language → speech seconds, incl. "und" (D21 flag)
    partial: bool                                     # some speech was dropped (q2 §4.4 step 5)

@dataclass(frozen=True, slots=True, kw_only=True)
class LanguagePlan:
    stretches: tuple[tuple[TimeSpan, ...], ...]       # target-language pieces, split wherever a dropped piece lay
                                                      # between them: what segments() may join
    skip: Literal[SkipReason.LANGUAGE_UNSUPPORTED, SkipReason.LANGUAGE_UNKNOWN] | None
    report: LanguageReport
```

**Segmentation: cut, then merge (review r2, finding 1).** `speech_runs` splits at every pause of 0.1 s or more, so
on its own it yields dozens of 1–3 s runs per minute. Sending those to the recogniser one by one would cost the Whisper
fallback a full 30 s encoder pass per 1–3 s span (q1 §6.1), about 10–30× the compute of 30 s windows, and would give
Parakeet isolated fragments without their neighbours' context. Both reference designs merge before decoding:

- WhisperX `merge_chunks` (`whisperx/vads/vad.py`, read 2026-10-08) joins consecutive VAD segments while the envelope
  stays within `chunk_size` (30 s), with no limit on the gap between them.
- faster-whisper 1.2.1 `BatchedInferencePipeline` runs VAD with `max_speech_duration_s=chunk_length` (30 s) and
  `min_silence_duration_ms=160`, then `collect_chunks(..., max_duration=chunk_length)` (`vad.py` L186) concatenates
  speech chunks up to 30 s of *speech*, dropping the gaps and remapping timestamps afterwards.

scenewise follows WhisperX's envelope merge, with one limit added: a gap of `merge_gap` (2 s) or more always starts a
new segment, so long music or silence never reaches the recogniser inside a segment. A gap below 2 s stays in the audio,
where faster-whisper's `hallucination_silence_threshold` (2.0 s, q2 §4.3) already covers it. The pipeline is:

1. `runs = speech_runs(probs)`: raw runs. `pauses = gaps(runs)` is taken here, so word-end extension and cue breaks
   still see every pause of 0.1 s or more (§1).
2. `pieces(runs)`: runs over 30 s are cut at the lowest-probability hop.
3. `lid_windows(pieces)` and `decide_language(...)`: LID sees only speech (the adapter concatenates the pieces of a
   window), as in r1.
4. `segments(plan.stretches)`: the kept pieces are merged into recognition segments of up to 30 s. A merge never
   crosses a dropped (non-English or `und`) piece, because `decide_language` returns the kept pieces as separate
   stretches wherever one was dropped.

Hypothesis properties of `segments`: every segment is ≤ `max_segment` long; every kept piece lies inside exactly one
segment; segments are ordered and do not overlap; no segment spans two stretches; inside a segment no gap is ≥
`merge_gap`.

*Rejected:* faster-whisper's concatenation. It splices speech across pauses, so every adapter would have to keep an
offset map and remap token times to honour the absolute-time contract (§1), and TDT durations at a splice would
straddle two unrelated stretches of audio. The envelope merge keeps the audio as it was spoken.

**Resulting call counts.** For S seconds of English speech in mostly continuous talk, merged segments are mostly
20–30 s long (shorter only where a pause of 2 s or more ends one), so a job has about S / 25 segments. For a 20-minute
talk that is about 45–50 segments instead of 400–1,200 raw runs:

| Runtime | Work per segment | 20 min of speech | `SpeechRecognizer` port calls (≤300 s each) |
|---|---|---|---|
| Parakeet (sherpa-onnx, onnx-asr) | one decode of ≤30 s of audio | ≈ 45–50 decodes; ≈ 1,200 s / 12.9 RTFx ≈ 95 s on 4 Cloud Run vCPUs (q7) | 4 (⌈1,200 / 300⌉), ≈ 23 s each |
| Whisper fallback (faster-whisper) | one 30 s encoder pass plus decoding | ≈ 45–50 encoder passes (≈ 400–1,200 unmerged) | 4 |

In general a job makes ⌈total segment length / 300 s⌉ recogniser calls (a 90-minute talk: about 18), and the
admission estimate (`exceeds_push_budget`) decides whether that fits the 1,500 s attempt budget. The deadline overshoot
is bounded by one call: about 23 s for Parakeet. For the fallback it depends on the model (`large-v3-turbo` on CPU is
not measured in q7) and is stated as unmeasured. LID is chunked the same way: at most `lid_chunk` = 10 windows per
`identify` call (about 10 × 0.4–0.9 s locally for `tiny`, q2 §4.4 step 3, ×2.5 on Cloud Run per q7 ≈ 10–23 s), with a
deadline check between calls (review r2, finding 6).

`"und"` (BCP 47 "undetermined") is the key for windows below `lid_p_min`, in the domain and on the wire.

The captions use case in `app/stages.py` is the shell that calls the ports in order:

```python
def transcribe(track: Path, *, speech: Speech, policy: SpeechPolicy,
               deadline: float) -> Transcribed | Skipped | LanguageSkipped:
    probs = speech.vad.speech_probabilities(track)
    runs = domain.speech.speech_runs(probs, policy)
    if domain.speech.total(runs) < policy.no_speech_below:
        return Skipped(reason=SkipReason.NO_SPEECH)                           # D23
    windows = domain.speech.lid_windows(domain.speech.pieces(runs, probs, policy), policy)
    guesses: list[LanguageGuess] = []
    for batch in domain.speech.chunks(windows, limit=policy.lid_chunk, size=lambda _: 1):
        check_deadline(deadline)
        guesses += speech.lid.identify(track, batch)
    plan = domain.speech.decide_language(windows, guesses, policy)
    if plan.skip is not None:
        return LanguageSkipped(reason=plan.skip, report=plan.report)          # §5: report kept on the skip
    segs = domain.speech.segments(plan.stretches, policy)                    # merged, ≤ max_segment
    recognized: list[RecognizedSegment] = []
    for chunk in domain.speech.chunks(segs, limit=policy.decode_chunk, size=lambda s: s.end - s.start):
        check_deadline(deadline)        # the runner's monotonic-budget check; raises its timeout error (q8a §6.3)
        recognized += speech.recognizer.transcribe(track, chunk, language="en")
    return Transcribed(transcript=captions.transcript(recognized, pauses=gaps(runs), language="en", min_hold=...),
                       language=plan.report)
```

```python
# scenewise/app/deps.py
@dataclass(frozen=True, slots=True, kw_only=True)
class Speech:                         # the captions stage needs all three, so they travel together
    vad: VoiceActivityDetector
    lid: LanguageIdentifier
    recognizer: SpeechRecognizer

# Dependencies.asr: SpeechRecognizer | None  →  Dependencies.speech: Speech | None
```

Adapters (all in the one `adapters/asr/` kind, so they may share a helper without breaking the `independence`
contract):

| File | Implements | Library |
|---|---|---|
| `adapters/asr/wav.py` | `read_span(track, span) -> np.ndarray[float32]` (stdlib `wave` + numpy, ÷32768) | numpy |
| `adapters/asr/silero_vad.py` | `VoiceActivityDetector` (the ~40-line loop; vendored from onnx-asr `models/silero.py`, MIT, with its notice, or written fresh; q2 §4.2) | onnxruntime, `providers=["CPUExecutionProvider"]` (q2 §5.1) |
| `adapters/asr/whisper_lid.py` | `LanguageIdentifier` | faster_whisper |
| `adapters/asr/sherpa_parakeet.py` | `SpeechRecognizer` (primary, D20) | sherpa_onnx |
| `adapters/asr/onnx_asr_parakeet.py` | `SpeechRecognizer` (tested second, D20) | onnx_asr |
| `adapters/asr/faster_whisper.py` | `SpeechRecognizer` (fallback, U4). `transcribe(array, language="en", vad_filter=False, word_timestamps=True, condition_on_previous_text=False)`; q2 §4.3's other thresholds kept (`hallucination_silence_threshold` 2.0 needs `word_timestamps`). `vad_filter=False` because the spans are already VAD-cut and merged (§2 "Segmentation"); the pauses under 2 s left inside a span are covered by `hallucination_silence_threshold`. Word times are clamped into their span, since DTW times can spill over | faster_whisper |

**Music tagger.** It gets no port and no module in v1. D22 says music handling waits for T1 and a licence check. When
it is added, it becomes `AudioTagger.music_scores(track, spans) -> list[float]` in
`adapters/asr/sherpa_tagger.py`, in chunks of ≤10 s (q2 §6.2). The energy gate and the `[music]` / flag decision go in
`domain/speech.py` (q2 §1: digital silence scored "Music" 0.33–0.37). Added after T1, once D22 is resolved.

**Rationale.**
- This follows `ARCHITECTURE.md` §14: a Protocol where "an I/O or model boundary … needs a fake because the real thing is
  slow, nondeterministic or costly". Both models qualify, and the segmentation policy, which is the part q2 says must be
  tunable (open question 4), becomes unit-testable with fakes and hypothesis, with no onnxruntime in the PR tier.
- VAD returns probabilities, not runs, because the ≤30 s cut needs the probability per hop (q2 §4.2). That is also the
  reason q2 rejected sherpa-onnx's VAD.
- LID returns the argmax only. The rule uses only the argmax and p (q2 §4.4 step 4), and the full distribution would
  be dead data.
- `Speech` as one optional member keeps "None ⇒ the stage is not offered" as a single check (q8a §4) and makes it
  impossible to wire a recogniser without its gate.

**Rejected.**
- *VAD and LID inside each ASR adapter*: cue boundaries would depend on the runtime, the very thing q2 §4.2 rules out
  ("keeps cue boundaries independent of the runtime"), and the code would be repeated in three adapters.
- *One `SpeechFrontEnd` port that returns English segments*: the tunable policy would move into an adapter, testable
  only with the models installed.
- *Allowing numpy in `app`*: it breaks the allow-list (q8b §12) for about 50 lines of arithmetic that work fine over
  tuples. 168k floats per 90 minutes is small.

---

## 3. The `asr` extra and the GPU ASR path

**Facts.**
- sherpa-onnx's PyPI wheels are CPU-only and bundle their own onnxruntime 1.28.2 (q2 §5.1, §5.2 [S54]; [X2]).
- Silero needs pip onnxruntime 1.30.0 (q2 §5.2).
- faster-whisper is required on every captions job for the LID gate (q2 §4.4), but q8a §9.4 puts it in an optional
  `asr-whisper` extra.
- **faster-whisper 1.2.1 hard-requires `onnxruntime`** [X1], while q8a's `ort-cu130` selector installs
  `onnxruntime-gpu`. Both distributions provide the same `onnxruntime` import package, so an
  `asr + ort-cu130` environment would contain both. That is a packaging inference; it was not re-tested here.
- D12: no CUDA 12 image, faster-whisper runs on CPU.
- q7 §1–§2 recommends the Cloud Run CPU service; q7's table says "LID and VAD stay on the CPU in the GPU image".

**Decision: one CPU-only `asr` extra; no ORT selector pair; v1 ASR runs on CPU in both images.**

| Extra | Contents (pyproject floor = locked version, following q8a §9.4's `>=` style; uv.lock pins exactly) | Source |
|---|---|---|
| (base) | `pydantic>=2.13`, `pydantic-settings>=2.15`, `structlog>=26.1`, `httpx>=0.28`, **`pillow>=12.3`** (D3) | q8a §9.4; [X1] |
| `service` | `fastapi>=0.142`, `uvicorn>=0.54` | q8a §9.4 |
| **`asr`** | `sherpa-onnx>=1.13.8` (pulls `sherpa-onnx-core==1.13.8`), `onnx-asr>=0.12.0` (no `[hub]`, no `[cpu]`), `onnxruntime>=1.30.0`, `faster-whisper>=1.2.1` (pulls ctranslate2 4.8.2), `numpy>=2.5.3` | q2 §5.2; D20 |
| `llm-anthropic` | `anthropic[vertex]>=1.12` | U5 |
| `vision` | `open-clip-torch>=3.3`, `timm>=1.0.17` (Pillow removed, D3) | q8a §9.4 |
| `gcs` | `google-cloud-storage>=3.16`, `google-auth` | q8a §9.4; §8 below |
| `torch-cpu` / `torch-cu130` | `torch>=2.14`, `torchvision>=0.29`, routed per q8a §9.4 | unchanged |
| ~~`asr-whisper`~~, ~~`ort-cpu`~~, ~~`ort-cu130`~~ | removed | this item |

- **onnx-asr goes into `asr`, without `[hub]`.** It is pure Python on numpy (q2 §5.1; [X1]), so the second runtime
  stays a configuration switch (`SCENEWISE_ASR__BACKEND=onnx-asr`) in every image, and CI runs both on the same fixtures
  (q2 §5.1). `[hub]` is dropped because weights are baked and verified by sha256, and nothing downloads at run time
  (q2 §5.2, §6.2). `[cpu]` is dropped because `asr` lists onnxruntime itself.
- **numpy is declared** because the adapters import it, and deptry reports imports of transitive-only packages
  (DEP003).
- **Images** (q7 §2.5, one Dockerfile):
  - `-cpu` = `--extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cpu`.
  - `-cuda` = the same with `--extra torch-cu130`. Its ASR, VAD and LID run on CPU, and only the vision models use
    the GPU.
- **Settings.** `asr.backend: "sherpa-onnx" | "onnx-asr" | "faster-whisper" | "none"` (replacing q8a §7.1's
  `"parakeet" | …`, which named a model, not a runtime). There is no `device` for ASR in v1. bootstrap drops its
  onnxruntime `CUDAExecutionProvider` probe (q8a §9.4); only the torch probe stays.
- **Rationale.** It removes the onnxruntime/onnxruntime-gpu clash. The ASR stack is about 19 CPU-s per video (q7 §2)
  and the default deployment is CPU (q7 §1, U6). No sherpa-onnx GPU throughput has been measured (q2 §5.1). It is
  also one extra fewer for adopters to get wrong.
- **PyAV becomes a transitive dependency.** faster-whisper 1.2.1 hard-requires `av>=11` [X4], so every image with
  `asr` ships PyAV and its bundled FFmpeg libraries. This supersedes q8a §9.1's "PyAV is not even a transitive
  dependency". PyAV is also *loaded*: `faster_whisper/__init__.py` imports `faster_whisper.audio`, which runs
  `import av` at module load, so PyAV and its bundled FFmpeg libraries are mapped into the service process whenever a
  faster-whisper adapter is constructed (every captions deployment, because of LID). q8a's objection was to in-process
  *decoding* of untrusted media, and that still never happens: **PyAV is imported but never given input.** The rule in
  §1 (faster-whisper adapters pass decoded arrays, never paths or file objects) keeps `decode_audio` unused; the
  recogniser contract suite enforces it, and `detect_language` has no decode path. ffmpeg stays the only decoder. The bundled FFmpeg licence joins the NOTICE review
  (§6.3 item 21).
- **GPU ASR is out of v1; its packaging route is to be researched** if a GPU deployment or the L4 job mode is built
  (q7 §1). Constraint for that research: pip `onnxruntime` is always present (faster-whisper), so the route must not
  install `onnxruntime-gpu` next to it. Pointers from review r1, not re-verified here: k2-fsa publishes CUDA builds
  of sherpa-onnx as one monolithic `sherpa_onnx-…+cuda13…` wheel with no `Requires-Dist` (no CUDA
  `sherpa-onnx-core`), listed on a flat HTML page rather than a PEP 503 index, so it is not the torch mechanism.
- **Rejected.**
  - *onnx-asr + onnxruntime-gpu on GPU* (q2 §6.2's suggestion): faster-whisper's hard `onnxruntime` dependency [X1]
    puts both ORT distributions in one environment.
  - *Keeping `asr-whisper` separate* (decision doc §7.5, side B): captions would need two extras to work, and the
    error message would point at the fallback.
  - *Keeping `ort-*` for Silero*: Silero is about 0.07 s per 30 s on one CPU thread (q2 §4.2), so GPU buys nothing.

---

## 4. Ports the stage findings need but q8a lacks

### 4.1 Labels: scores, embeddings and calibration inputs (port changed now; implemented with roadmap item 4)

q5 needs four things from the labelling pass:
- the frame-max **cosine** for the uncalibrated z-score (q5 §6.1 principle 5);
- the model **score** (SigLIP `sigmoid(logit_scale · cos + logit_bias)`) for calibrated thresholds (q5 §6.2
  "Scoring");
- `model_id` and `preprocess`, to match calibration entries (q5 §6.1 principle 4);
- optional frame embeddings for the opt-in `mean_l2` video embedding (q5 §4).

q8a's `scores(...) -> list[list[float]]` carries none of these except a score.

```python
# scenewise/domain/labels.py
@dataclass(frozen=True, slots=True, kw_only=True)
class LabelScores:
    model_id: str                                   # e.g. "hf-hub:timm/ViT-B-16-SigLIP2"
    preprocess: str                                 # e.g. "squash-224"
    cosines: tuple[tuple[float, ...], ...]          # [frame][label]
    score_transform: tuple[float, float] | None     # (logit_scale, logit_bias) for SigLIP; None ⇒ score = cosine
    embeddings: tuple[tuple[float, ...], ...] | None  # [frame], L2-normalised; only when requested

# scenewise/ports.py — replaces q8a's ZeroShotLabeller.scores
class ZeroShotLabeller(Protocol):             # SigLIP 2 via open_clip
    def score(self, frames: Sequence[Frame], prompts: Sequence[Sequence[str]], *,
              embeddings: bool = False) -> LabelScores:
        """prompts[i] = the expanded `templates × prompts` of label i (expanded in domain/labels.py).
        The adapter averages and L2-normalises each label's text embeddings and caches them by the prompt tuple."""
```

`domain/labels.py` gains `frame_scores()` (applies the transform), `select()` (calibrated threshold or z ≥ z_min,
`top_k` = the request's `labels_max` or else the taxonomy's `top_k`, q5 §6.1, §7.5) and `video_embedding()` (`mean_l2`, q5 §4). All the arithmetic is pure.

*Rejected:* a separate `ImageEmbedder` port plus pure-Python dot products. That is about 4.6M multiply-adds per video
(200 labels × 30 frames × 768) in the interpreter. The port would split for no consumer.

### 4.2 Moderation tier 2: the guard model (sketch; added with roadmap item 3)

This also answers decision-doc item (a). q4's recommendation: a promptable guard on ambiguous or flagged frames
returning "renormalised P(yes)", with Shieldstral-1.0-3B or ShieldGemma 2 4B as candidates; Nemotron is dropped by
D24. q7 §3 places it "in its out-of-process llama.cpp server". The model choice stays open for item 3 (decision doc
§7.5).

```python
# scenewise/ports.py   (added with roadmap item 3)
class ImageGuard(Protocol):                   # guard VLM behind an OpenAI-compatible server
    def p_yes(self, frame: Frame, policies: Sequence[str]) -> list[float]:
        """Per policy question, P(yes) renormalised over the yes/no tokens, 0..1 (q4 tier 2). Not calibrated."""

# Dependencies.guard: ImageGuard | None
# domain/moderation.py: ambiguous(frames, scores, band) -> frames to escalate; p_yes → Likelihood bucket (q4 mapping table)
```

- **Wiring: its own port and its own adapter, `adapters/llm/openai_guard.py`, not the `TextGenerator` adapter.** The
  contracts differ:
  - input: an image (JPEG-encoded with Pillow, which is a base dependency after D3) plus a policy;
  - output: a probability read from `logprobs`/`top_logprobs` of a single yes/no token, not text.

  Pushing both through `TextGenerator` would add an image field and a logprobs mode to every text back end and a parse
  step to `app`. The adapter sits in the `llm` kind because both talk to the same kind of server. It may share a small
  private HTTP helper (`adapters/llm/_openai_http.py`) with `openai_compat.py` without breaking the `independence`
  contract, which works at the kind level (q8b §12).
- The server runs as a separate process (llama.cpp `llama-server` or vLLM), following q3/q8a's rule of no in-process
  llama-cpp-python (q8a §9.4). It adds no new Python dependency (httpx).
- **To verify with item 3**: that the chosen server returns `top_logprobs` for image + text chat requests with the
  candidate's GGUF and vision projector. Not checked here.
- The Claude third opinion (q4 Summary 3) also needs images. With item 3, `TextRequest` gains
  `images: tuple[Frame, ...] = ()`, encoded by the LLM adapters. It needs no new port.

### 4.3 `scenewise calibrate` and the threshold sidecar (sketch; added with roadmap item 4)

U10: uncalibrated labels are for shadow comparison only, and "one `scenewise calibrate` run is part of the Expause
integration". Following q5 §6.2 "Scoring" point 4:

```text
scenewise calibrate --taxonomy taxonomies/expause-interests.toml \
                    --labels labels.csv --frames frames.csv \
                    [--target-precision 0.9] [--min-positives 20]
```

| File | Role |
|---|---|
| `service/cli.py` | the `calibrate` subcommand: parses arguments into a `CalibrationRequest`, gets a `CalibrationDeps` from `bootstrap.calibration_deps(settings)`, calls the use case. Local paths only (`allow_local_paths`, q1 §4.0) |
| `app/deps.py` | `CalibrationDeps(store: BlobStore, images: ImageReader, labeller: ZeroShotLabeller)`: the three ports the use case needs, all required. The full `Dependencies` is not used, because its `media` and `notifier` are required and irrelevant here |
| `app/calibrate.py` | `CalibrationRequest(taxonomy_uri, labels_uri, frames_uri, target_precision=0.9, min_positives=20)`, a frozen dataclass; `calibrate(request, *, deps: CalibrationDeps) -> CalibrationEntry`: reads the CSVs and taxonomy through `BlobStore`, frames through `ImageReader`, scores through `ZeroShotLabeller.score`, then writes `<taxonomy>.calibrations.json` through `BlobStore.write` |
| `app/contract/taxonomy.py` | Pydantic models for the taxonomy file and the sidecar (`schema_version: 1`, `entries[]`, q5 §6.2), with `to_domain()` |
| `domain/calibration.py` | `fit_threshold(pos, neg, *, target_precision) -> float \| None`, `k_range(...)`, `entry_matches(entry, *, serving: ServingSetup)` with `ServingSetup(model_id, taxonomy_hash, preprocess, score_stat)` |
| `domain/labels.py` | `taxonomy_hash()` over labels + templates (q5 §6.1 principle 3) |

---

## 5. No-speech status (D23), and the q1 rule change

**Confirmed: D23 stands.** Audio is present and VAD finds no speech, so the result is
`captions = {status: "skipped", reason: "no_speech", cue_count: 0, vtt_uri: null}`, and no VTT is written (not even a
header-only file). The job state is unaffected, because a skipped stage never makes a job partial (q8a §5). This
supersedes q1 §5.1 (the `StageStatus` comment and the `SkipReason` table row "with `status = "succeeded"`") and q1 §9
("`captions = {status: "succeeded", reason: "no_speech", cue_count: 0}` … with no VTT or a header-only VTT").

**The rule that replaces q1's exception.** The status decides which `reason` values are allowed:

| `status` | `reason` | Other fields |
|---|---|---|
| `succeeded` | always `null` (q1's single exception is removed) | stage outputs; for captions `partial_language` / `detected_languages` may be set (§7.3) |
| `skipped` | exactly one closed `SkipReason`: `not_requested`, `no_audio_stream`, `no_speech`, `language_unsupported`, `language_unknown`, `dependency_failed`, `below_minimum` | no artifact; `error = null`. On `language_unsupported` / `language_unknown` only, captions also carries `language` (the dominant detected language, `null` when all windows were `und`) and `detected_languages`, both informational (q2 §4.4 step 5, D21) |
| `failed` | the error code (q8a §8 / `ARCHITECTURE.md` §9 list), equal to `error.code` | `error: ErrorInfo` |

- `language_unsupported` / `language_unknown` come from q2 §4.4 step 5 (less than about 2 s of English, D19).
- `below_minimum` covers U7's thresholds, read with q3's visual fall-through:
  - **chapters**: skipped when the video is shorter than 120 s or the validator yields fewer than 3 chapters. This
    supersedes q3's "Omit (`chapters: []`)" in its "Minimum length" table (§9).
  - **summary (v1): speech-based.** Skipped when there is no transcript or it has fewer than about 40 words
    (U7, `summary_min_words = 40`, configurable). Otherwise it succeeds with `inputs_used = ["transcript"]`, plus
    `"context"` when the request's `context` was put in the prompt. `inputs_used` never contains `"frames"` in v1. The
    test is a pure `domain/summary.py::summary_basis(words: int) -> Basis | None` (`None` ⇒ `below_minimum`).
  - **chapters (v1)** likewise take only the transcript (and `context`): no transcript ⇒ `below_minimum`.
  - **Why not q3's visual fall-through in v1 (review r2, finding 2).** q3's rule is "labels cover ≥3 distinct scenes
    or there is on-screen text". v1 has neither signal: no OCR stage exists, scene detection is out of v1 (D10;
    `ARCHITECTURE.md` §14), and labels come from roadmap item 4, which ships after summaries (item 2). A rule built on
    inputs that do not exist yet cannot be tested, and q3 feeds the model *labels*, not frames, which `TextRequest`
    cannot carry before item 3 (§4.2). So audio-less and no-speech videos get `summary: skipped / below_minimum` in v1.
    This narrows q1 §9 ("summary … still run[s] on visual input"; §9 below) and is put to the user as OQ-B below.
  - **Visual-only summaries arrive with a configured labeller (roadmap item 4).** Item 4 defines then, with tests:
    the concrete label-based rule (a starting point from r2: at least 3 distinct emitted non-moderation labels, each
    the top label on at least one frame, over a stdlib `VisualEvidence(labels, frames_covered)`; on-screen text
    stays out until an OCR signal exists); whether summary runs the labeller itself when `labels` was not requested
    (decision doc Q7 orders it "after captions and labels"); and the `inputs_used` value, where an additive
    `"labels"` literal is preferred to reusing `"frames"`, because labels, not frames, are what the model sees.
    `summary_basis` then gains its `visual` argument.
  - It is one reason, because the caller's reaction is the same in each case.

**Domain shape: a tagged union, not a validated `reason` field.** `SkipReason` is a `StrEnum`, so
`SkipReason | str | None` would be just `str | None` to mypy. The domain therefore makes invalid combinations
unrepresentable, and the wire fields are derived:

```python
# scenewise/domain/results.py  (replaces q8a §5's StageOutcome.status/reason)
class SkipReason(StrEnum): ...                       # the seven values above; lives in domain/jobs.py

@dataclass(frozen=True, slots=True, kw_only=True)
class Succeeded: ...                                 # stage results live in Analysis, as in q8a §5

@dataclass(frozen=True, slots=True, kw_only=True)
class Skipped:
    reason: Literal[SkipReason.NOT_REQUESTED, SkipReason.NO_AUDIO_STREAM, SkipReason.NO_SPEECH,
                    SkipReason.DEPENDENCY_FAILED, SkipReason.BELOW_MINIMUM]

@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageSkipped:                               # captions only; carries the report (§2)
    reason: Literal[SkipReason.LANGUAGE_UNSUPPORTED, SkipReason.LANGUAGE_UNKNOWN]
    report: LanguageReport

@dataclass(frozen=True, slots=True, kw_only=True)
class Failed:
    error_code: str                                  # a code from ARCHITECTURE.md §9
    detail: str = ""                                 # ScenewiseError.detail → ErrorInfo.message; never transcript text (D8)

type Outcome = Succeeded | Skipped | LanguageSkipped | Failed

@dataclass(frozen=True, slots=True, kw_only=True)
class StageOutcome:                                  # q8a §5, `status` and `reason` replaced by `outcome`
    stage: StageName
    outcome: Outcome
    seconds: float
```

mypy narrows `Literal` enum members, so `Skipped(reason=SkipReason.LANGUAGE_UNKNOWN)` and a `LanguageSkipped` without a
report are type errors; the pairing in the §5 table holds by construction (review r2, finding 7). `__post_init__`
still checks the reason at run time, for values built from untyped data.

`app/contract/mapping.py` matches exhaustively (`assert_never`) and writes the wire `status`, `reason`, `error`
(`ErrorInfo.code` from `error_code`, `message` from `detail`) and, for `LanguageSkipped`, `language` and
`detected_languages`. The wire shape stays q1's apart from §7.3's fields.
The job-state rule (any `Failed` ⇒ partial or failed; `Skipped` and `LanguageSkipped` never, q8a §5) matches on the variant. Stage functions return `T | Skipped` (captions: `| LanguageSkipped`) and raise for
failures, as before; `run_job` wraps the result with the stage name and timing.

---

## 6. Edits to apply when building the skeleton

### 6.1 `pyproject.toml` (q8a §9.4 project tables and q8b §11–§12 tool tables)

1. `[project] dependencies`: add `"pillow>=12.3"` (D3; [X1]).
2. `[project.optional-dependencies]`: replace `asr`, delete `asr-whisper`, `ort-cpu` and `ort-cu130`, and remove
   `"pillow"` from `vision` (§3 table).
3. `[tool.uv] conflicts`: keep only `[{ extra = "torch-cpu" }, { extra = "torch-cu130" }]`.
4. `[tool.ruff] line-length = 88` (U11).
5. `[[tool.mypy.overrides]] ignore_missing_imports`: add `"sherpa_onnx.*"` (no `py.typed` [X2]). The list becomes
   onnxruntime, faster_whisper, ctranslate2, sherpa_onnx, open_clip, torchvision, google.cloud. onnx_asr needs no
   override: the 0.12.0 wheel ships `py.typed` [X4].
6. `[tool.coverage.report] omit`: delete the line `"src/scenewise/adapters/media/images.py"` (D3). `adapters/asr/*`
   stays omitted, since the `test` job syncs `--extra service` only (D4).
7. `[tool.deptry.package_module_name_map]`: delete `onnxruntime-gpu = "onnxruntime"`; nothing installs it any more.
   `sherpa-onnx` and `sherpa-onnx-core` both ship files under `sherpa_onnx/` [X2]; if deptry attributes the import to
   the undeclared core package on the first sync, map `sherpa-onnx = ["sherpa_onnx"]`.
8. import-linter "Driving side imports no ML or cloud SDK": add `"sherpa_onnx"` to `forbidden_modules` and delete the
   `ignore_imports` entry `"scenewise.service.bootstrap -> onnxruntime"`. The torch probe stays.

### 6.2 Scripts and CI (q8b §13)

9. `scripts/check_lock.sh`: replace `asr=$(reqs --extra service --extra asr --extra ort-cu130)` with
   `asr=$(reqs --extra service --extra asr)`. Keep the no-torch assertion with its message changed to
   "FAIL: asr pulls torch", and add
   `if grep -qE "^onnxruntime-gpu==" <<<"$asr"; then echo "FAIL: asr pulls onnxruntime-gpu"; exit 1; fi`.
10. `ci.yml` `static` and `extended.yml` `models`: `uv sync --extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cpu`
    (drops `--extra asr-whisper --extra ort-cpu`).
11. Add q2's T4 to `models` in full (q2 §7): on linux/amd64, load pip onnxruntime, sherpa-onnx and faster-whisper in
    one process in both import orders; run one fixture through Silero, LID and both Parakeet adapters; record peak
    RSS; fail on a golden-file diff or on peak RSS above the instance budget.
11a. **`tests/models.lock` and the model cache** (§7.6): each entry becomes repo, revision, file list and full sha256
    per file; `fetch_models.py` downloads the listed files with `hf_hub_download` (not whole snapshots, so the
    2.4 GB fp32 files in the onnx-asr repo are never fetched) and verifies each hash. Silero is pinned through its
    byte-identical HF mirror `istupakov/silero-vad-onnx@b3e3ee3` `silero_vad.onnx`, checked against the upstream
    sha256 `1a153a22…88e3` (q2 §4.2), since the GitHub tag cannot be fetched that way.
12. `Dockerfile`: the image extras from §3.

### 6.3 Source (q8a §4–§8, `ARCHITECTURE.md` §2–§9)

13. **D2**: `WriteConflict` → `WriteConflictError` in `ports.py`, the `BlobStore` docstring, `app/delivery.py`, the
    contract suites (q8b §6 table: "`WriteConflict` on create-if-absent / on a stale generation") and `tests/fakes.py`.
    No other exception name trips N818: every class in q8a §8 already ends in `Error`.
14. **Ports**: add `VoiceActivityDetector` and `LanguageIdentifier`, replace `SpeechRecognizer` (§1), change
    `ZeroShotLabeller` (§4.1), and change `TextGenerator.generate` to return `Generation` (§7.1). The `MediaTool.audio_track` docstring and its contract test pin `pcm_s16le`, 16 kHz,
    mono (§1). That makes 10 ports; `ImageGuard` is the 11th with item 3. With per-port contract
    docstrings, `ports.py` will reach q8a's ≈200-line split point early. Start it as `ports/` (one module per port kind:
    `storage.py`, `media.py`, `speech.py`, `text.py`, `vision.py`, `notify.py`, plus `__init__.py` re-exports) if the
    first draft exceeds 200 lines.
15. **Domain**: new `domain/speech.py` (§2: `pieces`, `lid_windows`, `decide_language`, `segments` with the merge,
    generic `chunks`); `domain/results.py` gains `Token`, `RecognizedSegment`, `Word` and `Generation` and changes
    `TranscriptSegment` (§1, §7.1); `SkipReason` in `domain/jobs.py`; `StageOutcome` carries
    `outcome: Succeeded | Skipped | LanguageSkipped | Failed` instead of `status`/`reason` (§5);
    `domain/summary.py::summary_basis(words)` (§5); `app/contract/mapping.py` derives the wire fields.
15a. **Taxonomies (item 4)**: `StageOptions.labels_taxonomy: str | None = None` and the bootstrap read path (§7.5).
16. **`app/deps.py`**: `asr: SpeechRecognizer | None` → `speech: Speech | None` (§2). `enabled_stages` derives
    `CAPTIONS` from `speech`.
17. **JobRecord (D9)**, in `domain/jobs.py`:
    ```python
    class JobRecord:  # q8a §5 fields, plus:
        schema_version: str                               # record format major version, "1"; set by the writer
        scenewise_version: str                            # version of the writer, from scenewise.__version__
        external_ref: tuple[tuple[str, str], ...] | None  # None ⇒ absent or unreadable in the body
    ```
    `app/contract/envelope.py` parses `external_ref` leniently, next to `job_id` and `schema_version`: a valid
    `dict[str, str]` is kept, anything else gives `None` and never an error. That lets the claim write (step 4, before
    the full parse) and an `invalid_request` terminal record still carry it (q1 §5.1 open question 13). The wire
    `JobStatusV1` adds the same three fields. `decide_attempt` ignores them.
18. **`max_jobs`**: `Settings.service.max_jobs: PositiveInt = 1`, a single default with no device-dependent value.
    GPU deployments set `SCENEWISE_SERVICE__MAX_JOBS=2` explicitly (q8a §6.3 "2 on GPU … 1 on small CPU instances";
    q7 §2 `max_jobs = 1`). Cloud Run `--concurrency` is set equal to it in the deploy config.
19. **413**: `Settings.service.max_body_bytes: int = 1_048_576`. `service/http/push.py` rejects a `Content-Length`
    over the limit, or a streamed body that passes limit + 1 bytes, **before** the Envelope parse, with
    `MediaTooLargeError("request_too_large")`, rendered by `problems.py` as 413 problem+json. No record is written.
    Add the row "Body over 1 MiB (direct callers only) → 413, before parsing, no record" to the q8a §8 status table
    (`ARCHITECTURE.md` §7 already has it; q1 §4.0, §8.5). `request_too_large` joins the 413-class codes of `MediaTooLargeError` in `src/scenewise/domain/errors.py` (item 20); the `ARCHITECTURE.md` §9 text is item 25.1.
20. **Errors**: add `model_refused` to `InternalError`'s codes (§7.1) and `request_too_large` to `MediaTooLargeError`'s
    codes. `input_unavailable` (D7) is already in `ARCHITECTURE.md` §9.
21. **NOTICE**: Parakeet (U4), Silero, Whisper tiny/large-v3-turbo and onnx-asr's MIT notice if its Silero loop is
    vendored (q2 §5.3). Review the licence of the FFmpeg libraries bundled in PyAV's wheels, which every `asr` image
    now ships (§3; not checked here).

### 6.4 `ARCHITECTURE.md` text (for its author)

Complete after review r2 (finding 4): every passage of `ARCHITECTURE.md` (2026-10-08 draft, 763 lines) that this file
contradicts, by section and line, with the old text and its replacement. Items 22–31 from round 1 are folded in (their
numbers are kept in brackets); r1 item 23's "the JobRecord fields" is dropped, because lines 317–318 already have them.

**§1 At a glance**

- **22.1** L48, "Heavy dependencies": "No torch in the base install or in an ASR-only image. Model runtimes sit behind extras
  plus two accelerator selector pairs." → "No torch in the base install or in the `asr` extra. Model runtimes sit
  behind extras plus one accelerator selector pair (`torch-cpu` / `torch-cu130`); ASR runs on CPU in every image."
  Evidence: add "q8c §3".

**§2 Layout**

- **22.2** L78 `check_lock.sh`: "asserts torch routing per selector and a torch-free ASR resolution" → "asserts torch routing
  per selector, and no torch and no `onnxruntime-gpu` in `service + asr`".
- **22.3** L79 `fetch_models.py`: "downloads the pinned tiny models for the model tier (to be written)" → "downloads the files
  listed in `tests/models.lock` with `hf_hub_download` and verifies each sha256 (to be written)".
- **22.4** L87 `models.lock`: "repo id + revision of each tiny test model; the CI model-cache key" → "repo, revision, file
  list and per-file sha256 of every model the model tier loads (≈ 1.4 GB, q8c §7.6); the CI model-cache key".
- **22.5** L99 `jobs.py`: add `SkipReason` after `StageName`.
- **22.6** L100 `results.py`: → "Token, RecognizedSegment, Word, Transcript, Cue, Summary, Generation, Chapter, moderation and
  label results, the StageOutcome union, Analysis".
- **22.7** L103 `captions.py`: "Transcript → cues (line breaking, merge, split); render_webvtt()" → "tokens → words (word-end
  extension) → Transcript; Transcript → cues (line breaking, merge, split); render_webvtt()".
- **22.8** New line after L103: `speech.py  # VAD runs, ≤30 s cuts, LID windows, the language rule, segment merge, chunks`.
- **22.9** L105 `summary.py`: add "`summary_basis()`".
- **22.10** L108 `labels.py`: "prompt set; top-k and threshold selection over scores" → "prompt set; frame_scores(), select()
  (calibrated threshold or z ≥ z_min, top_k), video_embedding(), taxonomy_hash()".
- **22.11** New line (item 4): `calibration.py  # fit_threshold(), k_range(), entry_matches(), ServingSetup`.
- **22.12** New line under `app/contract/` (item 4): `taxonomy.py  # TOML taxonomy and JSON calibration sidecar models`.
- **22.13** L119 `deps.py`: "Dependencies: frozen dataclass of port implementations" → "Dependencies and Speech (port
  bundles); CalibrationDeps for `scenewise calibrate`".
- **22.14** New line under `app/` (item 4): `calibrate.py  # CalibrationRequest; calibrate(request, *, deps)`.
- **22.15** [r1 28] L131–132 `asr/`: → "speech adapters: `wav.py` (span reader), `silero_vad.py`, `whisper_lid.py`, and one
  module per `SpeechRecognizer` runtime (`sherpa_parakeet.py`, `onnx_asr_parakeet.py`, `faster_whisper.py`)".
- **22.16** New lines under `llm/` (item 3): `openai_guard.py  # ImageGuard over an OpenAI-compatible server` and
  `_openai_http.py  # private HTTP helper shared with openai_compat.py`.
- **22.17** L149 `cli.py`: add "; `scenewise calibrate` (item 4, local paths only)".

**§4 Ports**

- **22.18** [r1 22] L216: "There are eight." → "There are ten (`ImageGuard` is the eleventh, with roadmap item 3)."
- **22.19** L237 `audio_track` comment: "16 kHz mono WAV." → "16 kHz mono `pcm_s16le` WAV, pinned by its contract test."
- **22.20** [r1 22] L244–245: replace the `SpeechRecognizer` block with q8c §1's, and add `VoiceActivityDetector` and
  `LanguageIdentifier` from q8c §2.
- **22.21** L247–248: `def generate(self, request: TextRequest) -> str: ...` → `-> Generation: ...` (q8c §7.1).
- **22.22** L253–254: `def scores(self, frames, labels) -> list[list[float]]` → q8c §4.1's
  `def score(self, frames, prompts, *, embeddings: bool = False) -> LabelScores`.
- **22.23** After L257 (item 3): the `ImageGuard` sketch from q8c §4.2, marked "added with roadmap item 3".
- **22.24** L268–269: "every `SpeechRecognizer` returns segments in absolute seconds, in order and not overlapping" → "every
  `SpeechRecognizer` returns one `RecognizedSegment` per input span, in input order, with token times absolute,
  inside the span and non-decreasing".
- **22.25** [r1 22] L270–271: delete the "**Open:**" bullet.
- **22.26** L281: `asr: SpeechRecognizer | None` → `speech: Speech | None`; add the `Speech(vad, lid, recognizer)` dataclass
  after the block, a `guard: ImageGuard | None` member "(item 3)", and one sentence: "`scenewise calibrate` gets
  `CalibrationDeps(store, images, labeller)` instead, because `media` and `notifier` are irrelevant to it (q8c §4.3)."

**§5 Domain types**

- **23.1** L313: add `class SkipReason(StrEnum): NOT_REQUESTED, NO_AUDIO_STREAM, NO_SPEECH, LANGUAGE_UNSUPPORTED,
  LANGUAGE_UNKNOWN, DEPENDENCY_FAILED, BELOW_MINIMUM`.
- **23.2** L324: `Transcript(language, segments: tuple[TranscriptSegment, ...])` → add before it
  `Token(text, start, end_hint, log_prob); RecognizedSegment(span, tokens); Word(text, span, log_prob)` and
  `TranscriptSegment(span, words)  # text is derived`.
- **23.3** L325: `Summary(text, model)` → keep, with the comment "model = Generation.model of the back end that answered";
  add `Generation(text, model, refused)`.
- **23.4** L326: `Label(name, score)` → `LabelScores(model_id, preprocess, cosines, score_transform, embeddings)` and
  `Label(id, name, path, score_max, score_mean, frames, calibrated, external_id)` (q8c §4.1, §7.5).
- **23.5** L327: `TextRequest(...)` unchanged in v1; add the comment "gains `images: tuple[Frame, ...] = ()` with item 3".
- **23.6** [r1 23] L328: `StageOutcome(stage, status, reason, seconds)` → `StageOutcome(stage, outcome: Succeeded | Skipped |
  LanguageSkipped | Failed, seconds)`, with `Failed(error_code, detail)`.
- **23.7** New lines: `# domain/speech.py` with `SpeechProbabilities`, `LanguageGuess`, `SpeechPolicy`, `LanguageReport`,
  `LanguagePlan` (q8c §2).
- **23.8** L332–334: "summary and chapters need a transcript or visual input" → "summary and chapters need a transcript in
  v1; without one, or under about 40 words for the summary, they are `skipped` / `below_minimum` (visual-only
  summaries come with labels, roadmap item 4)".
- **23.9** L335–336: after "(D23)" add "Too little English speech gives `language_unsupported` or `language_unknown`, with
  the detected languages kept on the result (D19, D21)."

**§6 Stages**

- **24.1** [r1 24] L361 Captions row: ports → `MediaTool`, `VoiceActivityDetector`, `LanguageIdentifier`,
  `SpeechRecognizer`; pure core → add `domain/speech.py`; "What runs" → add "speech merged into ≤30 s segments".
- **24.2** L362 Summary/chapters row: "a summary only above about 40 transcript words (U7, configurable)" → "a summary only
  from about 40 transcript words; below that, or without speech, summary and chapters are `skipped` /
  `below_minimum` (U7, configurable). Visual-only summaries arrive with labels (roadmap item 4)." And "No automatic
  fallback on refusal" → "A refusal fails the stage with `model_refused` and is never retried (D18)". Ports:
  `TextGenerator` (returns `Generation`).
- **24.3** [r1 24] L363 Moderation row: ports → `ImageModerator`, `ZeroShotLabeller`, and `ImageGuard` (item 3).
- **24.4** L364 Labels row: "over an adopter-supplied taxonomy" → "over an adopter-supplied TOML taxonomy (`labels_taxonomy`;
  `labels_max` overrides its `top_k`); calibrated thresholds from `scenewise calibrate`". Pure core: add
  `domain/calibration.py`.

**§8 Concurrency**

- **25** [r1 25] L437: "default 1 on CPU, 2 on GPU" → "default 1; GPU deployments set 2". L443–444: "Models on one GPU share
  one lock" applies to vision only (ASR is CPU-only in v1).

**§9 Errors**

- **25.1** L471: `MediaTooLargeError … # media_too_large, exceeds_push_budget` → add `request_too_large`.
- **25.2** L476: `InternalError … # model_output_invalid, …` → add `model_refused`.

**§10 Configuration**

- **25.3** L500–502 groups: `asr` (discriminated on `backend`) → "`asr` (`backend`: `sherpa-onnx` | `onnx-asr` |
  `faster-whisper` | `none`; no device in v1)"; add a `captions` group (the `SpeechPolicy` fields, q8c §2) and a
  `labels` group (`taxonomy_path`, replacing q5's `SCENEWISE_TAXONOMY_PATH`, and `z_min`); `service` adds
  `max_body_bytes`; `llm` adds the U7 thresholds (`summary_min_words`, `chapters_min_seconds`,
  `chapters_min_count`).

**§11 ffmpeg and §14 left out**

- **25.4** L527–528: after "PyAV (in-process decoding, unkillable threads) … are rejected." add "PyAV is still installed and
  imported by faster-whisper, but scenewise never gives it input: every faster-whisper call receives decoded arrays
  (q8c §1, §3)."
- **25.5** L635–636: "PyAV" → "PyAV as a decoder (installed with faster-whisper, never given input)".

**§12 Extras**

- **26** [r1 26] L549–558: replace the table with q8c §3's (rows `asr-whisper` and `ort-cpu` / `ort-cu130` deleted; `gcs`
  row: "whether google-auth moves is **open**" → "google-auth stays here; bootstrap checks the import (q8c §8)").
  L560–563: "The selectors are split by runtime, so an ASR-only image (`--extra service --extra asr --extra
  ort-cu130`) pulls no torch. Each pair is a uv `conflicts` entry." → "There is one selector pair, a uv `conflicts`
  entry; `service + asr` pulls no torch and no `onnxruntime-gpu`." L564–566: drop "shared by the default ASR
  runtime" and "onnxruntime's providers and"; bootstrap checks only `torch.version.cuda` for `device=cuda`.

**§13 Principles**

- **29** [r1 29] L582 Single-responsibility cell: "`domain/captions.py` only turns a `Transcript` into cues and WebVTT" →
  "`domain/captions.py` only turns recognised tokens into words and a `Transcript` into cues and WebVTT;
  `domain/speech.py` owns the speech policy". L584 Liskov row → "Every `SpeechRecognizer` returns one
  `RecognizedSegment` per span, tokens in absolute time inside the span; every `VoiceActivityDetector` returns
  per-hop values in [0, 1]; checked by shared contract suites". L586 dependency-inversion row → "`bootstrap`
  constructs each adapter with its model path (plus `device` and `lock` for vision; ASR has no device in v1)".

**§15 Testing**

- **30** [r1 30] L656 Model row: "Real adapters with tiny pinned models, cached" → "Real adapters with the models pinned
  in `tests/models.lock` (two Parakeet int8 exports, Whisper `tiny`, Silero, tiny vision models; ≈ 1.4 GB),
  cached". L662–666 contract bullet: add `VoiceActivityDetector`, `LanguageIdentifier`, the `pcm_s16le` pin on
  `MediaTool.audio_track`, the recogniser "never calls `decode_audio`" assertion and the LID "receives an
  `np.ndarray`" assertion (q8c §1, §7.7). L671–672: "**No large model downloads.** The model tier uses tiny models
  pinned in `tests/models.lock`, an `actions/cache` keyed on that file, and offline mode" → "**No downloads at test
  time.** The model tier loads only files pinned with sha256 in `tests/models.lock`, fetched once by
  `scripts/fetch_models.py` into an `actions/cache` keyed on that file (≈ 1.4 GB of GitHub's 10 GB), and runs
  offline". Add a bullet: "q2's T4 (three runtimes in one process, both import orders, peak RSS) runs in the
  `models` job."

**§16 Gates**

- **31** [r1 31] L687 Types: "`ignore_missing_imports` only for six untyped heavy libraries" → "… for seven untyped heavy
  libraries (onnxruntime, faster_whisper, ctranslate2, sherpa_onnx, open_clip, torchvision, google.cloud)". L696
  driving side → "except bootstrap's torch start-up probe". L704 lock → "with its one conflict pair". L705 lock
  routing → "no torch and no `onnxruntime-gpu` in `service + asr`". L706 dependency hygiene → drop "maps
  `onnxruntime-gpu`; ". L712–714: add "and q8c §6.1" to the decisions to apply.

**§17 Open items**

- **27** [r1 27] L722–737: delete the first five "Architecture gaps" bullets (resolved in q8c §1–§4); keep "Music handling".
  L747: OQ12 → resolved (q8c §8). L748: OQ7 → "user decision, q8c §8". L750: drop "online zizmor in the merge gate
  (OQ13)" (resolved, q8c §8). Add the open questions of q8c's round-2 resolution.

### 6.5 `ROADMAP.md` text (review r2, finding 9)

- **32** §0, L35–36: "Model dependencies are pinned in extras (`asr`, `asr-whisper`, `llm-anthropic`, `vision`, `gcs`, plus
  CPU/CUDA selector pairs)" → "(`asr`, `llm-anthropic`, `vision`, `gcs`, plus one CPU/CUDA torch selector pair)".
- **33** §2, L80: "A summary is emitted only above about 40 transcript words." → "A summary is emitted only from about 40
  transcript words; below that, or without speech, it is skipped (`below_minimum`). Visual-only summaries arrive with
  labels (item 4)."
- **34** §4: add "Defines the label-based rule for visual-only summaries (q8c §5)" to the item's scope.

---

## 7. Other conflicts found

### 7.1 Refusals have no channel through `TextGenerator`

q3 says to "Handle refusal as a distinct outcome", D18 says to log and measure the refusal rate, and q4 says a Claude
refusal is "a signal to escalate" and to log "the model that actually answered". q8a's
`generate(request) -> str` can carry neither. `Summary.model` has no source either once `FallbackTextGenerator` picks a
back end.

**Decision:**

```python
class Generation:  text: str; model: str; refused: bool    # domain/results.py
class TextGenerator(Protocol):
    def generate(self, request: TextRequest) -> Generation: ...
```

The Anthropic adapter sets `refused = (stop_reason == "refusal")`. In summary and chapters, a refusal fails the stage
with `InternalError("model_refused")` and is logged with `stop_details.category`. It is never retried automatically
(D18):
- `FallbackTextGenerator` returns a refused `Generation` unchanged; it falls through to the secondary only on
  `RetryableError` or an unavailable primary.
- The stage checks `refused` before any JSON parse, so a refusal (which may not match the schema, q3) never triggers
  `app/llm_output.py`'s repair retry.

### 7.2 Moderation tier 1 also needs the zero-shot labeller

q4 Summary 1 scores violence, gore and weapons with "SigLIP 2 zero-shot prompts", and q7 §2 shares it with labels. q8a
and `ARCHITECTURE.md` §6 give moderation only `ImageModerator`.

**Decision:** no new port. `moderate()` takes `moderator` (Freepik, `sexual`) and, when present, `labeller` with a
moderation prompt set from `domain/moderation.py`. If `labeller` is None, those categories are absent from the report,
and their absence is reported, not hidden.

### 7.3 q1's `CaptionsResult` lacks q2's language fields

q2 §4.4 step 5 sets `partial_language` and lists "the detected languages and their durations", and D21 says unknown
windows are flagged. q1 §5.2 has neither field.

**Decision:** two additive v1 fields: `partial_language: bool = False` and `detected_languages: dict[str, float] = {}`
(seconds per Whisper language code, including `"und"` for windows below `lid_p_min`; BCP 47's "undetermined", since
q1 §5.2 types `language` as BCP-47). They are filled on success and on `skipped / language_*` (§5). These are additive
within `schema_version "1"` (q1 §4.0).

### 7.4 q5's taxonomy is YAML, but `app` may import only pydantic and structlog

q5 §6.1 uses YAML (`SCENEWISE_TAXONOMY_PATH`, a hand-edited file), and the `app` allow-list (q8b §12) admits no YAML
parser.

**Decision:** taxonomy files are **TOML**, parsed with stdlib `tomllib` in `app/contract/taxonomy.py` and validated by
Pydantic. Hand-edited, comments allowed, no new dependency. The sidecar stays JSON (q5 §6.2). q5's YAML example maps
one to one (`[[labels]]` tables).

**Read path.** `service/bootstrap.py` reads the files under `labels.taxonomy_path` (a file or a directory, q5 §6.1
point 2) at start-up, parses them with `app/contract/taxonomy.py`, and passes the parsed domain taxonomies, keyed by id,
into the labels use case. `app` does no file I/O of its own. A malformed taxonomy is a `ConfigurationError`, so a bad
revision never becomes ready. `scenewise calibrate` instead reads its one `--taxonomy` through `BlobStore` (§4.3),
because it takes a URI per run.

*Rejected:* PyYAML parsed in `service`. It adds a base dependency, and loading would split across two layers.
*Rejected:* the labels stage reading taxonomies through `BlobStore` per job. It re-parses on every job and turns a
configuration error into a per-job failure.

### 7.5 q5's request and response shape is not the wire contract

q5 §6.2's request (`video_id`, `inputs`, `outputs`, `taxonomy`, `top_k`) is a sketch. The contract is q1's
(`JobRequest` with `stages` and `options`).

**Decision:** map it into `StageOptions`:
- `labels_taxonomy: str | None = None` (the taxonomy id). `None` is valid only when exactly one taxonomy is
  configured; otherwise a request for `labels` without it is `InputError("invalid_request")`. A request that does not
  ask for labels never needs it (q1's `StageOptions` fields all have defaults);
- `labels_max: int | None = None` (1–100), replacing q1's `= 20`. `None` means the taxonomy's `top_k` (q5 §6.2: only
  `top_k` may be overridden per request), so the taxonomy default can apply;
- `video_embedding: bool = False`.

q1 §5.3's `Label{name, confidence, segments, source}` is replaced by q5's object:

```python
class Label(BaseModel):                    # app/contract, wire v1
    id: str                                # taxonomy label id
    name: str
    path: list[str]                        # ancestor ids, root first, ending with id
    score_max: float                       # ranking key; a model score, not a probability (q5 principle 6)
    score_mean: float
    frames: int                            # frames scored (K)
    calibrated: bool
    external_id: str | None = None         # echoed from the taxonomy

class LabelsResult(StageStatus):
    model: ModelRef                        # {id}
    taxonomy: TaxonomyRef                  # {id, version, hash}
    labels: list[Label]                    # sorted by score_max desc, ≤ effective top_k
    video_embedding: list[float] | None = None
```

`confidence` is dropped because q5 says the scores are not probabilities. `segments` and `source` are dropped: v1 has
no transcript labels, and per-frame presence can return later as an additive field. The transcript embedding (q5 point 4) gets no port until Expause's
recommender consumes vectors (q5 OQ11).

### 7.6 The Parakeet model is not a "tiny" test model

The q8b §6 model tier is built on tiny pinned models with an `actions/cache`, but the primary ASR weights are 652 MB
(q2 §5.2). No tiny NeMo TDT export with durations was found or checked.

**Decision:** the `models` job caches every model it actually loads, keyed on `tests/models.lock` (§6.3 item 11a):

| Model | Used by | Size |
|---|---|---|
| `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` @ 1ab9323 (int8 encoder, decoder, joiner, tokens) | `sherpa_parakeet` contract, T4 | ≈ 0.66 GB |
| `istupakov/parakeet-tdt-0.6b-v2-onnx` @ 0bbb45a, int8 files only | `onnx_asr_parakeet` contract (D20), T4 | ≈ 0.66 GB |
| `Systran/faster-whisper-tiny` @ d90ca5f | `whisper_lid` contract **and** the `faster_whisper` recogniser contract | ≈ 78 MB |
| `istupakov/silero-vad-onnx` @ b3e3ee3, `silero_vad.onnx` | `silero_vad` contract, T4 | ≈ 2 MB |
| the q8b §6 tiny vision models | vision contracts | < 10 MB |

About 1.4 GB in all, well inside GitHub's 10 GB per-repository cache. `large-v3-turbo` (≈1.6 GB) is **not** used in
CI: the fallback adapter is model-agnostic, so its contract runs with `tiny`; turbo is pinned only in the image's
weights layer. The recogniser contract in the PR tier runs against the fake.

### 7.7 q8b's contract-test example uses the old signature

q8b §6 has `recognizer.transcribe(speech_wav, language=None).segments` and imports `adapters.asr.parakeet`.

**Decision:** rewrite the example for §1:
- `transcribe(speech_wav, [TimeSpan(0, d)], language="en")`;
- one `RecognizedSegment` per span, tokens inside the span and non-decreasing;
- the adapter is imported from `scenewise.adapters.asr.sherpa_parakeet`.

Add `VoiceActivityDetectorContract` (values in [0, 1]; `len ≈ duration / hop`; silence fixture ⇒ max below threshold)
and `LanguageIdentifierContract` (one guess per window, in order, p in [0, 1]; a window of two spans with music between them
gives the same guess as the spans alone; splitting the windows over two calls gives the same guesses as one call). The
`FasterWhisperRecognizer` suite asserts that `faster_whisper.transcribe.decode_audio` is never called; the
`WhisperLanguageIdentifier` suite asserts that the model receives an `np.ndarray`, because `detect_language` has no
decode path to patch (§1).

### 7.8 q7 assumes onnxruntime-gpu and GPU ASR in the `-cuda` image

q7 §2.5 lists onnxruntime-gpu in `-cuda`, and its L4 captions column assumes ASR "drops to about 2 s" on an L4.

**Decision:** under §3 the `-cuda` image runs ASR on CPU. This affects only the L4 job mode, which v1 does not build
(U6). q7's CPU numbers and recommendation are unchanged.

### 7.9 q8a §7.1's ASR backend names

**Decision:** replace `backend: "parakeet" | "faster-whisper" | "none"` with
`backend: "sherpa-onnx" | "onnx-asr" | "faster-whisper" | "none"` (§3).

---

## 8. q8b open questions missing from `open-decisions.md`

These are decision-doc item (b). None of them blocks the skeleton.

| q8b | Recommendation | Blocks the skeleton? |
|---|---|---|
| **OQ7: CODEOWNERS identity model** | **Option A plus a logged bypass for the Repository admin role (the maintainer alone). User decision** (see below). | **No.** The `.github/CODEOWNERS` file is identical under every option. The ruleset and the bot identity must exist before agents first push gate changes (decision doc §7.5: Part 2 repository setup). |
| **OQ12: where google-auth goes** | **Leave it in `gcs` (current).** Expause runs on GCP with the `gcs` extra anyway (q7 §1), callbacks are optional for Expause (decision doc §7.5), and HMAC callbacks need no google-auth. Note that `llm-anthropic` also brings it: `anthropic[vertex]` requires `google-auth[requests]` [X4]. So bootstrap does not check which extra was selected; with `callback_auth = oidc` it imports `google.oauth2.id_token` and turns an `ImportError` into `ConfigurationError("callback_auth = oidc needs google-auth; install scenewise[gcs]")` (q8a §1.5 rule 4). Revisit with an `oidc` extra only if an off-GCP adopter asks for OIDC callbacks without `gcs`. | **No.** It is a placement in the extras table; `adapters/notify/google_id_token.py` exists either way (q8b §15.1). |
| **OQ13: online zizmor in the merge gate** | **No. Keep offline zizmor in `static` and online zizmor in the nightly `supply-chain` job (current).** Online checks depend on GitHub's API and upstream advisories. In the merge gate an outage or a new advisory would fail unrelated PRs, against q8b's deterministic-gate principle. The nightly run fails visibly. The window before it runs is covered twice: Dependabot's 14-day cooldown (q8b §13) for its own pin bumps, and code-owner review (OQ7) for any other PR that edits `uses:` pins in `.github/`. The maintainer's own bypassed gate PRs (OQ7) are covered only by the maintainer and the next nightly run. | **No.** |

**OQ7 in detail.** On GitHub a pull-request author cannot approve their own PR, so with a sole code owner
(`@firu-daniel`, D5) and "require review from Code Owners", the maintainer's own gate-file PRs can never satisfy the
rule. q8b's Option A states this cost ("needs a second identity's approval or a temporary bypass"); The first version of this section dropped it.

**How a ruleset bypass works** (GitHub docs, "Creating rulesets for a repository" and "Managing rulesets for a
repository", read 2026-10-08). The eligible bypass actors are roles ("Repository admins, organization owners, and
enterprise owners"; "The maintain or write role, or custom repository roles based on the write role"), teams, GitHub
Apps and Dependabot. **A single user account is not an actor type**; the dialog searches for "the role, team, or app".
In "For pull requests only" mode, "The selected actor is now required to open a pull request", which leaves a trail in
the pull request and the audit log, and Rule Insights (Settings → Rules → Insights) lists every bypass, filterable by
actor. Rulesets are available on public repositories, which scenewise is. Round 1's "the maintainer's account only" is
therefore not a setting GitHub offers (review r2, finding 3); the same effect comes from the admin role:

| | **A′ (recommended): Option A + admin-role bypass** | **B: routing only** |
|---|---|---|
| Setup | Agents push from a bot collaborator account (write role, never admin) or a GitHub App with contents and pull-requests write but no administration permission. The ruleset requires code-owner review on the default branch. Its bypass list holds **one actor, the Repository admin role, in "For pull requests only" mode**; the bot's role or App is never on it. In this personal-account repository the owner (`@firu-daniel`) is the only admin, so only the maintainer can bypass, and only by merging a PR. | Agents use the maintainer's credentials; CODEOWNERS only marks gate files in the PR view. No ruleset bypass is needed, because nothing is enforced. |
| For | An agent's change to a gate file cannot merge without the maintainer's approval, which is the threat q8b §4.2 names (this repository is built by agents). The maintainer's own gate PRs merge without a second person, and each such merge shows on the PR, in the audit log and in Rule Insights. | No bot identity to manage; nothing to bypass. |
| Against | A bot account or App to create, scope and maintain. The maintainer's own gate changes get no second review (as in any one-person repo), and a compromised maintainer session can bypass (visibly). If the repository moves to an organisation, "Repository admin" also covers the organisation owners, so the bypass widens to them; the ruleset must then be reviewed. Anyone later given admin on the repository can also bypass. | CODEOWNERS enforces nothing: an agent PR can weaken a gate or the workflow that runs the gates and merge with no extra step. |

Recommendation: **A′**, because it keeps the one property that matters (agents cannot merge gate edits unseen) at the
cost of a bot identity, and the admin role is exactly the maintainer while the repository stays personal and no one
else is made admin. Either way add the nightly `codeowners/errors` check (q8b OQ7) once the repo exists. **This is a
user decision** (OQ-A in the round-2 resolution): it fixes who holds which credentials, which only the maintainer can
choose.

---

## 9. What this changes in other findings (for the record; those files are not edited)

| File | Section | Superseded by |
|---|---|---|
| q8a | §4 `SpeechRecognizer`, `ZeroShotLabeller`, `TextGenerator`, `WriteConflict`; port count 8 | §1, §2, §4.1, §7.1, D2 |
| q8a | §1.4 `adapters/asr/{parakeet,faster_whisper}.py` | §2 adapter table |
| q8a | §5 `Transcript`, `TranscriptSegment`, `JobRecord`, `StageOutcome.status`/`reason` | §1, §5, §6.3 item 17 |
| q8a | §9.1 "PyAV is not even a transitive dependency" | §3 (PyAV bullet), §1 (arrays-only rule) |
| q8a | §4 `Dependencies` as the only wiring object (calibrate gets `CalibrationDeps`) | §4.3 |
| q8a | §6.3 `max_jobs` defaults; §8 status table without 413 | §6.3 items 18–19 |
| q8a | §7.1 `asr` backend names; §9.4 extras, `ort-*` selectors, ASR-only GPU image, onnxruntime CUDA probe | §3, §7.9 |
| q8b | §11 `line-length`, mypy overrides, coverage `omit`, deptry map; §12 service contract; §13 sync lines and `check_lock.sh`; §6 recogniser example | §6.1–§6.2, §7.7 |
| q1 | §5.1 `StageStatus` comment and `SkipReason` table; §9 no-speech bullet; §5.2 `CaptionsResult` | §5, §7.3 |
| q1 | §5.3 `Label`, `LabelsResult`; `labels_max: int = 20` | §7.5 |
| q3 | "Minimum length" table, chapters "Omit (`chapters: []`)"; the "Visual-only description" row in v1 | §5 (`skipped / below_minimum`; visual-only summaries deferred to roadmap item 4) |
| q1 | §9 "Summary, chapters, labels and moderation still run on visual input" (summary and chapters only, in v1) | §5 |
| q2 | §6 port shape; §6.2 "onnx-asr with onnxruntime-gpu may be the simpler adapter"; §4.3 `vad_filter=True` for the fallback; §4.2 segmentation without a merge step | §1, §3, §2 adapter table, §2 "Segmentation" |
| q5 | §6.1 YAML taxonomy and `SCENEWISE_TAXONOMY_PATH`; §6.2 request/response sketch | §7.4, §7.5, item 25.3 |
| q7 | §2.5 `-cuda` contents | §7.8 |

---

## Review round 1 — resolution

Review: [reviews/q8c-review-r1.md](reviews/q8c-review-r1.md). Re-checked before fixing: the q2/q3/q5/q1/q8a/q8b
passages each finding cites, and [X4] (PyPI JSON for faster-whisper 1.2.1 and anthropic 1.12.1; onnx-asr v0.12.0
source tree and `asr.py`). The k2-fsa CUDA wheel details (finding 6) were not re-verified; they are recorded only as
pointers for later research. No finding was rejected.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | design concern | LID fed envelopes, not speech | **Fixed.** `identify(track, windows: Sequence[Sequence[TimeSpan]])`; the adapter concatenates the spans; `lid_windows` bounds speech seconds; `envelope()` removed; contract property added (§2, §7.7). |
| 2 | missing | Language skip loses dominant language and durations | **Fixed.** `LanguageReport(dominant, detected, partial)` in `LanguagePlan`; `Skipped(reason, language)`; the §5 table allows `language` and `detected_languages` on `skipped / language_*`. |
| 3 | wrong | Model cache holds only one large model | **Fixed.** §7.6 lists every cached model: both Parakeet int8 exports, faster-whisper `tiny` (LID and the fallback recogniser contract), Silero via its HF mirror; ≈1.4 GB; `large-v3-turbo` not in CI. |
| 4 | wrong | `below_minimum` would skip visual-only summaries | **Fixed.** Summary is skipped only when the transcript is under ~40 words **and** q3's visual rule fails; chapters' `skipped` supersedes q3's `chapters: []` (§5, §9). |
| 5 | minor | `calibrate` / `entry_matches` exceed ruff argument limits | **Fixed.** `calibrate(request: CalibrationRequest, *, deps)`, `entry_matches(entry, *, serving: ServingSetup)`; `cues()` takes a `CueLayout` too (§1, §4.3). |
| 6 | wrong | GPU-ASR route names wrong packages / index type | **Fixed by narrowing.** GPU ASR is stated as out of v1 with its route to be researched; the reviewer's observations are kept as unverified pointers (§3). |
| 7 | missing | PyAV now a transitive dependency | **Fixed.** q8a §9.1 marked superseded; rule: faster-whisper adapters pass arrays, never paths, enforced by a contract test; FFmpeg-in-av licence added to NOTICE review (§1, §3, item 21, §9). |
| 8 | design concern | Sole code owner cannot approve own gate PRs | **Fixed.** Cost stated; A′ (Option A + maintainer-only, PR-mode, visible bypass) recommended against Option B, with both sides; **marked a user decision** (§8). |
| 9 | missing | `ARCHITECTURE.md` edit list incomplete | **Fixed.** Items 26 (§12 probe bullet), 28 (§2), 29 (§13), 30 (§15), 31 (§16 probes, lock, lock routing, deptry) added. |
| 10 | missing | q1 `Label` vs q5 label object; `top_k` vs `labels_max` | **Fixed.** v1 `Label` = q5's object (`confidence`, `segments`, `source` dropped, reasons given); `labels_max: int \| None = None` ⇒ taxonomy `top_k` (§7.5, §4.1). |
| 11 | minor | Log-prob semantics differ by runtime; onnx-asr has logprobs | **Fixed.** Per-runtime sources stated (onnx-asr `logprobs` [X4]); `Word.log_prob` = mean; faster-whisper `log(max(p, 1e-6))`; thresholds per runtime (§1). |
| 12 | minor | Word-end rule ambiguous | **Fixed.** `end = min(next_word.start, max(p, min(next_pause.start, start + min_hold)))`; last token without `end_hint` uses `span.end`; both are hypothesis properties (§1). |
| 13 | design concern | `SkipReason \| str \| None` collapses to `str \| None` | **Fixed.** Domain `Outcome = Succeeded \| Skipped \| Failed` inside `StageOutcome`; wire fields derived in `app/contract/mapping.py` (§5, items 15, 23). |
| 14 | minor | "ISO 639-1" and `"unknown"` | **Fixed.** "Whisper language code (BCP-47 primary subtag)"; `"und"` everywhere (§2, §7.3). |
| 15 | minor | `FallbackTextGenerator` refusal behaviour unstated | **Fixed.** Refusals pass through unchanged; `refused` checked before any parse or repair retry (§7.1). |
| 16 | minor | Whole-list `transcribe` defeats deadline checks | **Fixed.** `app` decodes in ≤300 s chunks (`SpeechPolicy.decode_chunk`, `domain.speech.chunks`) with a deadline check between calls (§1, §2). |
| 17 | minor | `calibrate` wiring vs `Dependencies` | **Fixed.** `CalibrationDeps(store, images, labeller)` from `bootstrap.calibration_deps(settings)` (§4.3). |
| 18 | minor | Item 11 narrows T4 | **Fixed.** T4 copied in full (item 11). |
| 19 | minor | `check_lock.sh` message; Silero not fetchable by `snapshot_download` | **Fixed.** Message → "asr pulls torch"; `models.lock` gains file lists and sha256, Silero pinned via `istupakov/silero-vad-onnx@b3e3ee3` against the upstream hash (items 9, 11a). |
| 20 | minor | `anthropic[vertex]` brings google-auth | **Fixed.** Verified [X4]; bootstrap checks the import, not the extra (§8 OQ12). |
| 21 | minor | onnx_asr typing already settled | **Fixed.** Verified `py.typed` [X4]; no override (item 5). |
| 22 | minor | s16 not in the `MediaTool` contract | **Fixed.** `audio_track` docstring and contract test pin `pcm_s16le`, 16 kHz, mono (§1, items 14, 30). |
| 23 | minor | Fallback recogniser settings | **Fixed.** `vad_filter=False`, `word_timestamps=True`, `condition_on_previous_text=False`, `language="en"`, q2's other thresholds kept, word times clamped (§2 adapter table, §9). |
| 24 | minor | OQ13 cooldown covers only Dependabot | **Fixed.** Code-owner review covers other `uses:` edits; the gap left by the maintainer's own bypassed PRs is stated (§8). |

**User decisions raised by this round:** OQ7 (A′ vs B, §8).

---

## Review round 2 — resolution

Review: [reviews/q8c-review-r2.md](reviews/q8c-review-r2.md). This is the last review round. Re-checked before fixing,
all on 2026-10-08:

- GitHub docs, "Creating rulesets for a repository": the bypass actor list (roles, teams, Apps, Dependabot; no
  individual users) and "For pull requests only" (finding 3).
- faster-whisper v1.2.1 `transcribe.py` L394–423 (`BatchedInferencePipeline`: VAD with `max_speech_duration_s=30`,
  `min_silence_duration_ms=160`, then `collect_chunks(..., max_duration=30)`) and `vad.py` L186 (`collect_chunks`
  concatenates speech up to 30 s). WhisperX `whisperx/vads/vad.py` `merge_chunks` (envelope merge up to `chunk_size`,
  no gap limit). Finding 1.
- `ARCHITECTURE.md`, all 763 lines, against this file (finding 4); `ROADMAP.md` §0, §2, §4 (finding 9); q1 §5.3, §9;
  q3 "Minimum length"; U7, D10.

No finding was rejected.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | design concern | `segments()` never merges VAD runs | **Fixed.** The cut is now `pieces()`, and `segments(stretches, policy)` merges consecutive kept pieces across gaps < `merge_gap` (2 s) up to `max_segment` (30 s), never across a dropped piece. Pauses still come from the raw runs. WhisperX's envelope merge is followed; faster-whisper's concatenation is rejected with reasons. Call counts stated: about S / 25 segments and ⌈length / 300 s⌉ port calls (a 20-minute talk: about 45–50 Parakeet decodes or Whisper encoder passes instead of 400–1,200, in 4 calls). Hypothesis properties listed (§1, §2). |
| 2 | design concern | Summary's visual rule depends on signals v1 lacks | **Fixed by narrowing.** v1 summaries (and chapters) are transcript-based: `below_minimum` with no transcript or under about 40 words (U7); `inputs_used = ["transcript"]` (plus `"context"`), never `"frames"`; `summary_basis(words)`. Visual-only summaries, their concrete label rule, whether summary runs the labeller, and an additive `"labels"` literal are defined with roadmap item 4. Chosen because summaries (item 2) ship before labels (item 4), v1 has no OCR and no scene detection (D10), and an untestable rule would be dead code. The narrowing of q1 §9 is put to the user as OQ-B (§5, §9). |
| 3 | wrong | OQ7 A′ names a bypass actor GitHub does not offer | **Fixed.** The bypass actor is the **Repository admin** role in "For pull requests only" mode, which is the maintainer alone in this personal repository; the bot is a write collaborator or an App without administration permission. The widening to organisation owners after a move to an organisation is stated. Both options are restated for the user (§8, OQ-A). |
| 4 | missing | `ARCHITECTURE.md` edit list incomplete | **Fixed.** §6.4 rewritten as a line-by-line list over every section: §1 L48; §2 (tree lines incl. the new files); §4 (port count, `audio_track`, `TextGenerator`, `ZeroShotLabeller`, `ImageGuard`, the contract bullet, `Dependencies`); §5 (types, prerequisite bullet); §6 (all four rows); §8; §9 codes; §10 settings; §11/§14 PyAV; §12; §13; §15 model tier and "no large model downloads"; §16 (seven untyped libraries and r1's items); §17. r1 item 23's JobRecord edit is dropped. |
| 5 | minor | Item 14 omits the `TextGenerator` change | **Fixed.** Item 14 changes `TextGenerator.generate` to return `Generation`; item 15 adds `Generation`. |
| 6 | minor | LID runs as one unbounded port call | **Fixed.** `identify` is called over batches of `lid_chunk` = 10 windows with a deadline check between calls; the contract suite checks that split calls give the same guesses (§2, §7.7). |
| 7 | minor | Union less strict than claimed; `Failed` drops detail | **Fixed.** `Skipped.reason` and the new `LanguageSkipped(reason, report)` take `Literal` subsets of `SkipReason`, so a language report can travel only on a language skip; `Failed(error_code, detail)` fills `ErrorInfo.message` (D8 applies) (§5). |
| 8 | minor | `labels_taxonomy` required; read path unstated | **Fixed.** `labels_taxonomy: str \| None = None`, valid only with exactly one configured taxonomy; bootstrap reads and parses the taxonomy files at start-up and passes them to `app`; `calibrate` reads through `BlobStore` (§7.4, §7.5). |
| 9 | minor | `ROADMAP.md` not in the knock-on lists | **Fixed.** §6.5, items 32–34. |
| 10 | minor | PyAV is loaded in-process | **Fixed.** "PyAV is imported but never given input"; the `decode_audio` patch stays on `faster_whisper.transcribe.decode_audio`, in the recogniser suite only; the LID suite asserts an `np.ndarray` (§1, §3, §7.7). |

### Open questions (user decisions)

None of them blocks the skeleton.

- **OQ-A (q8b OQ7): how CODEOWNERS binds.**
  - *A′ (recommended):* agents push as a bot collaborator (write role) or a GitHub App without administration
    permission; the ruleset requires code-owner review, with the Repository admin role (the maintainer alone) as the
    only bypass actor, in "For pull requests only" mode. For: agents cannot merge gate edits without the maintainer;
    the maintainer's own gate PRs still merge, visibly (PR, audit log, Rule Insights). Against: a bot identity to
    manage; the maintainer's own gate PRs get no second review; the bypass widens to organisation owners, or to anyone
    later made admin, if that ever happens.
  - *B:* agents use the maintainer's credentials and CODEOWNERS only marks gate files. For: nothing to set up.
    Against: nothing is enforced; an agent PR can weaken a gate and merge.
- **OQ-B: summaries for videos without enough speech in v1.**
  - *Speech-only v1 (recommended):* a summary needs about 40 transcript words; audio-less and no-speech videos get
    `summary: skipped / below_minimum` until labels ship (roadmap item 4), when a tested label-based rule adds
    visual-only summaries. For: every v1 rule is testable with signals v1 produces, and summaries ship on schedule.
    Against: it narrows q1 §9, so Expause's music-only and silent videos have no summary in v1.
  - *Visual summaries in v1:* pull the labeller and a minimal taxonomy forward into the summaries item, so q3's
    fall-through applies from the start. For: q1 §9 holds, and no-speech videos get a description. Against: summaries
    then depend on the `vision` extra, SigLIP and a taxonomy, which moves most of roadmap item 4 into item 2, and the
    label rule would be fixed before item 4's evaluation set exists.

The values `merge_gap` (2 s), `lid_chunk` (10) and `summary_min_words` (40) are starting points, tuned by q2 T1–T3 and
U7's real-sample tuning; they are not user decisions.
