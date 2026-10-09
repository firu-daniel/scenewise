"""Wire <-> domain: ``to_domain()`` for requests, ``*_json()`` for every document."""

from typing import Literal, assert_never

from pydantic import ValidationError

from scenewise import __version__
from scenewise.app.constants import SCHEMA_VERSION_V1
from scenewise.app.contract.records import JobRecordV1
from scenewise.app.contract.requests import AudioFileV1, JobRequestV1, NoAudioV1
from scenewise.app.contract.results import (
    AudioStageV1,
    ErrorInfoV1,
    JobResultV1,
    JobStatusV1,
    ProbedMediaV1,
    ProblemV1,
    RejectionV1,
    StageResultsV1,
)
from scenewise.domain.errors import InputError, InternalError, ScenewiseError
from scenewise.domain.inputs import AudioFile, AudioSource, NoAudio
from scenewise.domain.jobs import (
    Job,
    JobRecord,
    JobSpec,
    JobState,
    StageName,
    job_id,
    wire_status,
)
from scenewise.domain.media import MediaInfo
from scenewise.domain.results import (
    Analysis,
    Failed,
    LanguageSkipped,
    Skipped,
    StageOutcome,
    Succeeded,
    job_state,
)
from scenewise.domain.time import MS_PER_SECOND


def _validation_summary(error: ValidationError) -> str:
    """Field paths and messages only: input values may hold URIs (D8)."""
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc']) or '<body>'}: {e['msg']}"
        for e in error.errors(include_input=False, include_url=False)
    )


def _audio(audio: AudioFileV1 | NoAudioV1 | None) -> AudioSource | None:
    match audio:
        case AudioFileV1(uri=uri):
            return AudioFile(uri=uri)
        case NoAudioV1():
            return NoAudio()
        case None:
            return None
        case _:
            assert_never(audio)


def to_domain(raw: bytes) -> Job:
    """Validate a request body; any problem is ``invalid_request`` (``InputError``)."""
    try:
        request = JobRequestV1.model_validate_json(raw)
        return Job(
            id=job_id(request.job_id),
            spec=JobSpec(stages=frozenset(StageName(s) for s in request.stages)),
            audio=_audio(request.audio),
            external_ref=tuple(sorted(request.external_ref.items())),
            artifacts_prefix=request.delivery.artifacts.uri_prefix,
        )
    except ValidationError as e:
        raise InputError(code="invalid_request", detail=_validation_summary(e)) from e
    except ValueError as e:
        raise InputError(code="invalid_request", detail=str(e)) from e


def record_to_json(record: JobRecord) -> bytes:
    """Serialise a job record for ``status.json``."""
    ref = record.external_ref
    return (
        JobRecordV1(
            schema_version=SCHEMA_VERSION_V1,
            scenewise_version=record.scenewise_version,
            job_id=record.job_id,
            state=record.state.value,
            attempt=record.attempt,
            lease_until=record.lease_until,
            request_digest=record.request_digest,
            error_code=record.error_code,
            result_uri=record.result_uri,
            updated_at=record.updated_at,
            external_ref=None if ref is None else dict(ref),
        )
        .model_dump_json()
        .encode()
    )


def record_from_json(data: bytes) -> JobRecord:
    """Read ``status.json``; an unreadable record is an invariant violation."""
    try:
        doc = JobRecordV1.model_validate_json(data)
    except ValidationError as e:
        raise InternalError(
            code="invariant_violation", detail="unreadable job record"
        ) from e
    ref = doc.external_ref
    return JobRecord(
        job_id=job_id(doc.job_id),
        state=JobState(doc.state),
        attempt=doc.attempt,
        lease_until=doc.lease_until,
        request_digest=doc.request_digest,
        error_code=doc.error_code,
        result_uri=doc.result_uri,
        updated_at=doc.updated_at,
        scenewise_version=doc.scenewise_version,
        external_ref=None if ref is None else tuple(sorted(ref.items())),
    )


def status_json(record: JobRecord, now: float) -> bytes:
    """The job status a caller sees for ``record`` at ``now``."""
    ref = record.external_ref
    return (
        JobStatusV1(
            scenewise_version=record.scenewise_version,
            job_id=record.job_id,
            status=wire_status(record, now),
            attempt=record.attempt,
            error_code=record.error_code,
            result_uri=record.result_uri,
            updated_at=record.updated_at,
            external_ref=None if ref is None else dict(ref),
        )
        .model_dump_json()
        .encode()
    )


def problem(error: ScenewiseError, *, status: int, title: str) -> ProblemV1:
    """An RFC 9457 problem body for ``error``."""
    return ProblemV1(
        title=title,
        status=status,
        detail=error.detail or error.code,
        code=error.code,
        category=error.category,
        retryable=error.retryable,
    )


def rejection_json(
    job: str, error: ScenewiseError, *, status: int, title: str
) -> bytes:
    """The 200 body of a delivery that was refused without a terminal record."""
    body = problem(error, status=status, title=title)
    return RejectionV1(job_id=job, problem=body).model_dump_json().encode()


type _StageFields = tuple[
    Literal["succeeded", "skipped", "failed"], str | None, ErrorInfoV1 | None
]


def _stage_fields(outcome: StageOutcome) -> _StageFields:
    match outcome.outcome:
        case Succeeded():
            return "succeeded", None, None
        case Skipped(reason=reason) | LanguageSkipped(reason=reason):
            return "skipped", reason.value, None
        case Failed(error_code=code, category=category, detail=detail):
            error = ErrorInfoV1(
                code=code,
                category=category,
                retryable=False,
                message=detail or code,
                stage=outcome.stage.value,
            )
            return "failed", code, error
        case _:
            assert_never(outcome.outcome)


def _media(media: MediaInfo | None) -> ProbedMediaV1 | None:
    if media is None:
        return None
    return ProbedMediaV1(
        duration_s=media.duration, has_audio=media.has_audio, has_video=media.has_video
    )


def result_json(
    analysis: Analysis,
    *,
    attempt: int,
    external_ref: tuple[tuple[str, str], ...],
    audio_uri: str | None,
) -> bytes:
    """``result.json`` for one attempt; ``audio_uri`` is where the track was put."""
    stages = StageResultsV1()
    for outcome in analysis.outcomes:
        if outcome.stage is StageName.AUDIO:
            status, reason, error = _stage_fields(outcome)
            audio = AudioStageV1(
                status=status, reason=reason, error=error, uri=audio_uri
            )
            stages = StageResultsV1(audio=audio)
    state = job_state(analysis.outcomes)
    return (
        JobResultV1(
            scenewise_version=__version__,
            job_id=analysis.job_id,
            external_ref=dict(external_ref),
            status="partial" if state is JobState.PARTIAL else "succeeded",
            media=_media(analysis.media),
            stages=stages,
            timings_ms={
                o.stage.value: round(o.seconds * MS_PER_SECOND)
                for o in analysis.outcomes
            },
            attempt=attempt,
        )
        .model_dump_json(indent=2)
        .encode()
    )
