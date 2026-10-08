"""Jobs, job records and the pure attempt state machine (ARCHITECTURE.md §7)."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NewType, assert_never

from scenewise.domain.inputs import AudioSource, VisualSource
from scenewise.domain.time import Seconds

JobId = NewType("JobId", str)

JOB_ID_PATTERN = r"^[A-Za-z0-9._:-]{1,200}$"
_JOB_ID = re.compile(JOB_ID_PATTERN)
RECORD_SCHEMA_VERSION = "1"


def job_id(value: str) -> JobId:
    """Validate ``value`` as a job id: safe as one path segment."""
    if not _JOB_ID.fullmatch(value) or value in {".", ".."}:
        msg = f"invalid job id {value!r}"
        raise ValueError(msg)
    return JobId(value)


class StageName(StrEnum):
    """The stages a request may ask for; the values are the wire names.

    ``AUDIO`` is the skeleton's one wired stage: it publishes the normalised audio
    track. The other stages arrive with roadmap items 1-4.
    """

    AUDIO = "audio"
    CAPTIONS = "captions"
    SUMMARY = "summary"
    CHAPTERS = "chapters"
    MODERATION = "moderation"
    LABELS = "labels"


class SkipReason(StrEnum):
    """Why a requested stage produced nothing without failing."""

    NOT_REQUESTED = "not_requested"
    NO_AUDIO_STREAM = "no_audio_stream"
    NO_SPEECH = "no_speech"
    LANGUAGE_UNSUPPORTED = "language_unsupported"
    LANGUAGE_UNKNOWN = "language_unknown"
    DEPENDENCY_FAILED = "dependency_failed"
    BELOW_MINIMUM = "below_minimum"


@dataclass(frozen=True, slots=True, kw_only=True)
class Callback:
    """Where to notify the caller; ``url`` is already allow-listed."""

    url: str
    auth: Literal["hmac", "oidc"]
    key_id: str | None = None
    audience: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class JobSpec:
    """What to compute."""

    stages: frozenset[StageName]


@dataclass(frozen=True, slots=True, kw_only=True)
class Job:
    """A validated request."""

    id: JobId
    spec: JobSpec
    audio: AudioSource | None
    visual: VisualSource | None = None
    external_ref: tuple[tuple[str, str], ...] = ()
    callback: Callback | None = None
    artifacts_prefix: str | None = None


class JobState(StrEnum):
    """The state stored in a job record."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class JobRecord:
    """The durable job record, ``{state_prefix}/{job_id}/status.json``."""

    job_id: JobId
    state: JobState
    attempt: int
    lease_until: float  # epoch seconds
    request_digest: str
    error_code: str | None
    result_uri: str | None
    updated_at: float  # epoch seconds
    schema_version: str
    scenewise_version: str
    external_ref: tuple[tuple[str, str], ...] | None  # None: absent or unreadable


@dataclass(frozen=True, slots=True, kw_only=True)
class AttemptInfo:
    """The facts ``decide_attempt`` needs besides the record."""

    now: float  # epoch seconds
    lease: Seconds
    max_attempts: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Start:
    """Claim the record and run attempt ``attempt``."""

    attempt: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AlreadyDone:
    """The job is terminal; answer with its record."""

    record: JobRecord


@dataclass(frozen=True, slots=True, kw_only=True)
class InProgress:
    """Another attempt holds a live lease."""

    retry_after: Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class GiveUp:
    """The last attempt's lease expired and no attempt is left."""

    attempt: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Conflict:
    """The job id was used before with a different request."""

    existing_digest: str


type Decision = Start | AlreadyDone | InProgress | GiveUp | Conflict


def decide_attempt(
    record: JobRecord | None, request_digest: str, info: AttemptInfo
) -> Decision:
    """Decide what one delivery of a request does, from the stored record."""
    if record is None:
        return Start(attempt=1)
    if record.request_digest != request_digest:
        return Conflict(existing_digest=record.request_digest)
    if record.state is not JobState.RUNNING:
        return AlreadyDone(record=record)
    if record.lease_until > info.now:
        return InProgress(retry_after=Seconds(record.lease_until - info.now))
    if record.attempt < info.max_attempts:
        return Start(attempt=record.attempt + 1)
    return GiveUp(attempt=record.attempt)


type WireStatus = Literal["running", "retry_wait", "succeeded", "partial", "failed"]


def wire_status(record: JobRecord, now: float) -> WireStatus:
    """The status a caller sees; a running record with an expired lease waits."""
    match record.state:
        case JobState.RUNNING:
            return "running" if record.lease_until > now else "retry_wait"
        case JobState.SUCCEEDED:
            return "succeeded"
        case JobState.PARTIAL:
            return "partial"
        case JobState.FAILED:
            return "failed"
        case _:
            assert_never(record.state)
