"""``handle_delivery()``: decide -> claim -> parse -> run -> publish -> record.

This module owns every write of the job record (ARCHITECTURE.md §7). Records are only
written under compare-and-swap: the claim's generation is the attempt's fencing token,
so an attempt whose lease expired cannot overwrite a later attempt's terminal record.
Callbacks (step 7's notify) arrive with the HTTP callback adapter.
"""

import time
from dataclasses import dataclass, replace
from typing import assert_never

import structlog

from scenewise import __version__
from scenewise.app.contract import mapping
from scenewise.app.contract.envelope import Envelope
from scenewise.app.deps import Dependencies
from scenewise.app.publish import publish
from scenewise.app.runner import run_job
from scenewise.domain.errors import InputError, RetryableError, ScenewiseError
from scenewise.domain.jobs import (
    RECORD_SCHEMA_VERSION,
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
)
from scenewise.domain.results import job_state
from scenewise.domain.time import Seconds
from scenewise.ports import WriteConflictError

log = structlog.get_logger(__name__)

JSON = "application/json"
RETRY_AFTER_CONFLICT = Seconds(30.0)  # another delivery won the claim or the record


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryPolicy:
    """Deployment settings the delivery protocol needs."""

    state_prefix: str
    attempt_budget: Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class Finished:
    """Answer 200 with ``body``: a job status, or a ``job_id_conflict`` rejection."""

    body: bytes


@dataclass(frozen=True, slots=True, kw_only=True)
class TryLater:
    """Answer 503 with ``Retry-After``; the queue redelivers."""

    error: RetryableError
    retry_after: Seconds


type DeliveryOutcome = Finished | TryLater


def job_prefix(state_prefix: str, job_id: str) -> str:
    """``{state_prefix}/{job_id}``: the record's folder and the default artifacts."""
    return f"{state_prefix.rstrip('/')}/{job_id}"


def artifacts_prefix(job: Job, state_prefix: str) -> str:
    """Where this job's artifacts go: always a folder of its own.

    A requested ``uri_prefix`` gets the job id appended, so one job can never write
    into another job's folder, and it may not point into the state prefix at all.
    The store's allow-list decides which other roots are writable.
    """
    if job.artifacts_prefix is None:
        return job_prefix(state_prefix, job.id)
    requested = job.artifacts_prefix.rstrip("/")
    state = state_prefix.rstrip("/")
    if requested == state or requested.startswith(f"{state}/"):
        detail = "artifacts may not be written under the state prefix"
        raise InputError(code="uri_not_allowed", detail=detail)
    return job_prefix(requested, job.id)


@dataclass(frozen=True, slots=True, kw_only=True)
class _Delivery:
    envelope: Envelope
    raw: bytes
    deps: Dependencies
    info: AttemptInfo
    policy: DeliveryPolicy

    @property
    def uri(self) -> str:
        return (
            f"{job_prefix(self.policy.state_prefix, self.envelope.job_id)}/status.json"
        )

    def write(self, record: JobRecord, *, if_generation: int) -> int:
        data = mapping.record_to_json(record)
        return self.deps.store.write(
            self.uri, data, content_type=JSON, if_generation=if_generation
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
        schema_version=RECORD_SCHEMA_VERSION,
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
            return _attempt(d, 1, generation=0)  # decide_attempt(None, ...) is Start(1)
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
                error = InputError(
                    code="job_id_conflict", detail="job id used for another request"
                )
                body = mapping.rejection_json(
                    envelope.job_id, error, status=409, title="Job id already used"
                )
                return Finished(body=body)
            case _:
                assert_never(decision)
