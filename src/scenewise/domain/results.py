"""Stage outputs, stage outcomes and the job's analysis.

The transcript, cue, summary, chapter and label values join this module with the
stages that produce them (roadmap items 1-4); the values here are the ones a port or
the wired audio stage already needs.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from scenewise.domain.jobs import JobId, JobState, SkipReason, StageName
from scenewise.domain.media import MediaInfo
from scenewise.domain.speech import LanguageReport
from scenewise.domain.time import Seconds, TimeSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    """One recogniser token; a token that starts a word begins with a space."""

    text: str
    start: Seconds  # absolute track time
    end_hint: Seconds | None
    log_prob: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RecognizedSegment:
    """The tokens recognised in one input span."""

    span: TimeSpan
    tokens: tuple[Token, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TextRequest:
    """A prompt for a text generator; the JSON schema travels as text."""

    system: str
    prompt: str
    json_schema: str | None
    max_tokens: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Generation:
    """A text generator's answer, with the model that actually answered."""

    text: str
    model: str
    refused: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ModerationScore:
    """One category's score in ``[0, 1]``."""

    category: str
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class FrameModeration:
    """Every category's score for one frame."""

    timestamp: Seconds
    scores: tuple[ModerationScore, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Succeeded:
    """The stage produced its result; the result itself lives in ``Analysis``."""


type SkipReasonGeneral = Literal[
    SkipReason.NOT_REQUESTED,
    SkipReason.NO_AUDIO_STREAM,
    SkipReason.NO_SPEECH,
    SkipReason.DEPENDENCY_FAILED,
    SkipReason.BELOW_MINIMUM,
]


@dataclass(frozen=True, slots=True, kw_only=True)
class Skipped:
    """The stage had nothing to work on."""

    reason: SkipReasonGeneral


@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageSkipped:
    """Captions only: the speech was not in a supported language."""

    reason: Literal[SkipReason.LANGUAGE_UNSUPPORTED, SkipReason.LANGUAGE_UNKNOWN]
    report: LanguageReport


@dataclass(frozen=True, slots=True, kw_only=True)
class Failed:
    """The stage failed with an error code from ARCHITECTURE.md §9.

    A retryable error never fails a stage (it fails the attempt), so the category is
    input or internal.
    """

    error_code: str
    category: Literal["input", "internal"]
    detail: str = ""


type Outcome = Succeeded | Skipped | LanguageSkipped | Failed


@dataclass(frozen=True, slots=True, kw_only=True)
class StageOutcome:
    """How one requested stage ended, and how long it took."""

    stage: StageName
    outcome: Outcome
    seconds: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Analysis:
    """Everything one job produced."""

    job_id: JobId
    media: MediaInfo | None  # None when there was nothing to probe
    outcomes: tuple[StageOutcome, ...]
    audio_wav: bytes | None = None  # the audio stage's 16 kHz mono pcm_s16le track


def job_state(outcomes: Iterable[StageOutcome]) -> JobState:
    """``PARTIAL`` if any stage failed, else ``SUCCEEDED``; a skip is not a failure."""
    failed = any(isinstance(o.outcome, Failed) for o in outcomes)
    return JobState.PARTIAL if failed else JobState.SUCCEEDED
