"""``handle_delivery()``: decide -> claim -> parse -> run -> publish -> record.

This module owns every write of the job record (ARCHITECTURE.md §7). Records are only
written under compare-and-swap: the claim's generation is the attempt's fencing token,
so an attempt whose lease expired cannot overwrite a later attempt's terminal record.
Callbacks (step 7's notify) arrive with the HTTP callback adapter.
"""

import posixpath
import time
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Final, assert_never
from urllib.parse import unquote, urlsplit

import structlog

from scenewise import __version__
from scenewise.app.constants import JSON_MEDIA_TYPE
from scenewise.app.contract import mapping
from scenewise.app.contract.envelope import Envelope
from scenewise.app.deps import Dependencies
from scenewise.app.publish import publish
from scenewise.app.runner import run_job
from scenewise.domain.errors import (
    InputError,
    JobIdConflictError,
    RetryableError,
    ScenewiseError,
)
from scenewise.domain.jobs import (
    FIRST_ATTEMPT,
    AlreadyDone,
    AttemptInfo,
    Conflict,
    GiveUp,
    InProgress,
    Job,
    JobRecord,
    JobState,
    Start,
    decide_attempt,
    job_id,
)
from scenewise.domain.results import job_state
from scenewise.domain.time import Seconds
from scenewise.ports import ABSENT_GENERATION, BlobStore, WriteConflictError

log = structlog.get_logger(__name__)

RECORD_FILE_NAME: Final = "status.json"
# another delivery won the claim or the record
RETRY_AFTER_CONFLICT: Final = Seconds(30.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryPolicy:
    """Deployment settings the delivery protocol needs."""

    state_prefix: str
    attempt_budget: Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class Finished:
    """The job reached an answerable state; ``body`` is its status document."""

    body: bytes


@dataclass(frozen=True, slots=True, kw_only=True)
class Rejected:
    """Refused without writing a record; the HTTP layer renders ``error``."""

    error: InputError


@dataclass(frozen=True, slots=True, kw_only=True)
class TryLater:
    """Not finished yet: the request should be delivered again after ``retry_after``."""

    error: RetryableError
    retry_after: Seconds


type DeliveryOutcome = Finished | Rejected | TryLater


def job_prefix(state_prefix: str, job: str) -> str:
    """``{state_prefix}/{job}``: the record's folder and the default artifacts."""
    return f"{state_prefix.rstrip('/')}/{job}"


def record_uri(state_prefix: str, job: str) -> str:
    """``{state_prefix}/{job}/status.json``: where the job record lives."""
    return f"{job_prefix(state_prefix, job)}/{RECORD_FILE_NAME}"


def job_status(
    job: str, *, store: BlobStore, state_prefix: str, now: float
) -> bytes | None:
    """The status document of job ``job`` at ``now``; ``None`` when there is none.

    A string that is not a valid job id names no job. A store failure propagates as
    the store raised it; an unreadable record is ``invariant_violation``.
    """
    try:
        key = job_id(job)
    except ValueError:
        return None
    blob = store.read(record_uri(state_prefix, key))
    if blob is None:
        return None
    return mapping.status_json(mapping.record_from_json(blob.data), now)


def _location(uri: str) -> tuple[str, str, PurePosixPath]:
    """``(scheme, host, path)`` of ``uri``, normalised for comparison only.

    URI-level only: case of scheme and host, ``localhost`` for ``file`` (RFC 8089
    §2), percent-escapes, dot segments and repeated slashes. No symlink is followed.
    A string ``urlsplit`` cannot parse yields an empty scheme, which matches no
    real prefix.
    """
    try:
        parts = urlsplit(uri)
    except ValueError:
        return ("", "", PurePosixPath("/"))
    host = parts.netloc.lower()
    if parts.scheme == "file" and host == "localhost":
        host = ""
    path = unquote(parts.path) or "/"
    # normpath keeps exactly two leading slashes
    path = posixpath.normpath("/" + path.lstrip("/"))
    return (parts.scheme, host, PurePosixPath(path))


def _shape_refusal(requested: str) -> str | None:
    """Why ``requested`` cannot be a prefix, or ``None`` when its shape is fine.

    ``?`` and ``#`` are tested on the raw string: ``urlsplit`` drops an empty
    query or fragment, and the store reads only the path, so every job would share
    one file.
    """
    if "?" in requested or "#" in requested:
        return "artifacts uri_prefix may not carry a query or fragment"
    try:
        path = unquote(urlsplit(requested).path)
    except ValueError:
        return "artifacts uri_prefix is not a valid URI"
    if path and not path.startswith("/"):
        return "artifacts uri_prefix must have an absolute path"
    return None


def artifacts_prefix(job: Job, state_prefix: str) -> str:
    """Where this job's artifacts go: always a folder of its own.

    A requested ``uri_prefix`` gets the job id appended, so one job can never write
    into another job's folder. The job folder ``{uri_prefix}/{job_id}`` - not just
    the requested prefix - is compared with the state prefix after both are
    normalised (scheme and host case, ``localhost``, percent-escapes, dot segments,
    repeated slashes) and may not lie at or under it, so a parent of the state
    directory plus a job id equal to its basename is refused too. Queries,
    fragments and relative paths are refused. The caller's own spelling is
    returned. Symlinks and which other roots are writable are the output store's
    concern.
    """
    if job.artifacts_prefix is None:
        return job_prefix(state_prefix, job.id)
    shape = _shape_refusal(job.artifacts_prefix)
    if shape is not None:
        raise InputError(code="uri_not_allowed", detail=shape)
    folder = job_prefix(job.artifacts_prefix.rstrip("/"), job.id)
    scheme, host, path = _location(folder)
    state_scheme, state_host, state_path = _location(state_prefix)
    if (scheme, host) == (state_scheme, state_host) and path.is_relative_to(state_path):
        detail = "artifacts may not be written under the state prefix"
        raise InputError(code="uri_not_allowed", detail=detail)
    return folder


@dataclass(frozen=True, slots=True, kw_only=True)
class _Delivery:
    envelope: Envelope
    raw: bytes
    deps: Dependencies
    info: AttemptInfo
    policy: DeliveryPolicy

    @property
    def uri(self) -> str:
        return record_uri(self.policy.state_prefix, self.envelope.job_id)

    def write(self, record: JobRecord, *, if_generation: int) -> int:
        data = mapping.record_to_json(record)
        return self.deps.store.write(
            self.uri, data, content_type=JSON_MEDIA_TYPE, if_generation=if_generation
        )

    def answer(self, record: JobRecord) -> Finished:
        return Finished(body=mapping.status_json(record, self.info.now))


def _in_progress(retry_after: Seconds) -> TryLater:
    return TryLater(
        error=RetryableError(code="job_in_progress"), retry_after=retry_after
    )


def _terminal(
    claim: JobRecord, state: JobState, *, error_code: str | None = None
) -> JobRecord:
    return replace(claim, state=state, error_code=error_code, updated_at=time.time())


def _run(d: _Delivery, claim: JobRecord) -> JobRecord:
    """Parse, run and publish; every error but a retryable one ends the job."""
    try:
        job = mapping.to_domain(d.raw)
        deadline = time.monotonic() + d.policy.attempt_budget
        analysis = run_job(job, d.deps, deadline=deadline)
        result_uri = publish(
            analysis,
            store=d.deps.store,
            prefix=artifacts_prefix(job, d.policy.state_prefix),
            attempt=claim.attempt,
            external_ref=job.external_ref,
        )
    except RetryableError:
        raise
    except ScenewiseError as e:
        log.warning("job_failed", code=e.code, category=e.category)
        return _terminal(claim, JobState.FAILED, error_code=e.code)
    except Exception:
        log.exception("job_failed", code="unexpected")
        return _terminal(claim, JobState.FAILED, error_code="unexpected")
    return replace(
        _terminal(claim, job_state(analysis.outcomes)), result_uri=result_uri
    )


def _finish(d: _Delivery, final: JobRecord, *, token: int) -> DeliveryOutcome:
    try:
        d.write(final, if_generation=token)
    except WriteConflictError:
        log.warning("attempt_superseded")
        return _in_progress(RETRY_AFTER_CONFLICT)
    log.info("job_finished", state=final.state.value, error_code=final.error_code)
    return d.answer(final)


def _release(
    d: _Delivery, claim: JobRecord, error: RetryableError, *, token: int
) -> TryLater:
    """Hand the job back: the record reads ``retry_wait`` until the next delivery."""
    log.warning("attempt_released", code=error.code)
    released = replace(claim, lease_until=d.info.now, updated_at=time.time())
    try:
        d.write(released, if_generation=token)
    except WriteConflictError:
        log.warning("attempt_superseded")
    return TryLater(error=error, retry_after=RETRY_AFTER_CONFLICT)


def _attempt(d: _Delivery, attempt: int, *, generation: int) -> DeliveryOutcome:
    claim = JobRecord(
        job_id=d.envelope.job_id,
        state=JobState.RUNNING,
        attempt=attempt,
        lease_until=d.info.now + d.info.lease,
        request_digest=d.envelope.request_digest,
        error_code=None,
        result_uri=None,
        updated_at=d.info.now,
        scenewise_version=__version__,
        external_ref=d.envelope.external_ref,
    )
    try:
        token = d.write(claim, if_generation=generation)
    except WriteConflictError:
        return _in_progress(RETRY_AFTER_CONFLICT)
    with structlog.contextvars.bound_contextvars(attempt=attempt):
        try:
            final = _run(d, claim)
        except RetryableError as e:
            if attempt < d.info.max_attempts:
                return _release(d, claim, e, token=token)
            final = _terminal(claim, JobState.FAILED, error_code="attempts_exhausted")
        return _finish(d, final, token=token)


def _give_up(d: _Delivery, record: JobRecord, *, generation: int) -> DeliveryOutcome:
    final = _terminal(record, JobState.FAILED, error_code="attempts_exhausted")
    try:
        d.write(final, if_generation=generation)
    except WriteConflictError:
        return _in_progress(RETRY_AFTER_CONFLICT)
    return d.answer(final)


def handle_delivery(
    envelope: Envelope,
    raw: bytes,
    *,
    deps: Dependencies,
    info: AttemptInfo,
    policy: DeliveryPolicy,
) -> DeliveryOutcome:
    """Handle one delivery of a request whose envelope parsed."""
    d = _Delivery(envelope=envelope, raw=raw, deps=deps, info=info, policy=policy)
    with structlog.contextvars.bound_contextvars(job_id=envelope.job_id):
        blob = deps.store.read(d.uri)
        if blob is None:
            # no record: decide_attempt would start the first attempt
            return _attempt(d, FIRST_ATTEMPT, generation=ABSENT_GENERATION)
        record = mapping.record_from_json(blob.data)
        generation = blob.generation
        decision = decide_attempt(record, envelope.request_digest, info)
        match decision:
            case Start(attempt=attempt):
                return _attempt(d, attempt, generation=generation)
            case AlreadyDone(record=done):
                return d.answer(done)
            case InProgress(retry_after=retry_after):
                return _in_progress(retry_after)
            case GiveUp():
                return _give_up(d, record, generation=generation)
            case Conflict():
                log.error("job_id_conflict")
                return Rejected(
                    error=JobIdConflictError(detail="job id used for another request")
                )
            case _:
                assert_never(decision)
