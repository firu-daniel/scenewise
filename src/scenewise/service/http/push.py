"""``POST /v1/jobs``: body limit, envelope, admission, then the delivery in a thread."""

import functools
import time
from typing import Final, assert_never

import anyio
import structlog
from fastapi import Request
from fastapi.responses import Response

from scenewise.app.constants import JSON_MEDIA_TYPE
from scenewise.app.contract import envelope as envelopes
from scenewise.app.contract import mapping
from scenewise.app.contract.envelope import Envelope
from scenewise.app.delivery import Finished, Rejected, TryLater, handle_delivery
from scenewise.domain.errors import (
    CapacityError,
    InputError,
    InternalError,
    MediaTooLargeError,
    RetryableError,
    ScenewiseError,
)
from scenewise.domain.jobs import AttemptInfo
from scenewise.domain.time import Seconds
from scenewise.service.http.problems import (
    http_status,
    problem_response,
    problem_title,
)
from scenewise.service.http.state import ServiceState

log = structlog.get_logger(__name__)

RETRY_AFTER_BUSY_S: Final = 30.0
_TASK_HEADERS: Final = (  # (request header, log context key)
    ("x-cloudtasks-taskname", "task_name"),
    ("x-cloudtasks-taskretrycount", "transport_retry"),
    ("x-cloud-trace-context", "trace"),
)


async def read_body(request: Request, *, limit: int) -> bytes:
    """Read at most ``limit`` bytes; more is ``MediaTooLargeError``, before parsing."""
    too_large = MediaTooLargeError(
        code="request_too_large", detail=f"body over {limit} bytes"
    )
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > limit:
        raise too_large
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_large
        chunks.append(chunk)
    return b"".join(chunks)


def _rejected(job: str, error: ScenewiseError) -> Response:
    """200 + problem: a non-retryable failure must not start a retry loop."""
    status = http_status(error)
    body = mapping.rejection_json(
        job, error, status=status, title=problem_title(error, status)
    )
    return Response(content=body, media_type=JSON_MEDIA_TYPE)


def _log_context(request: Request) -> dict[str, str]:
    return {
        key: request.headers[header].split("/")[0]
        for header, key in _TASK_HEADERS
        if header in request.headers
    }


async def _admitted(state: ServiceState, envelope: Envelope, raw: bytes) -> Response:
    """Run the delivery in a worker thread and map every outcome (§9)."""
    try:
        with state.watchdog.watch(envelope.job_id):
            service = state.settings.service
            info = AttemptInfo(
                now=time.time(),
                lease=Seconds(service.lease_s),
                max_attempts=service.max_attempts,
            )
            deliver = functools.partial(
                handle_delivery,
                envelope,
                raw,
                deps=state.deps,
                info=info,
                policy=state.policy,
            )
            outcome = await anyio.to_thread.run_sync(deliver)
    except RetryableError as e:
        return problem_response(e, retry_after=RETRY_AFTER_BUSY_S)
    except ScenewiseError as e:  # e.g. an unreadable job record
        log.warning("delivery_rejected", code=e.code)
        return _rejected(envelope.job_id, e)
    except Exception:
        log.exception("delivery_rejected", code="unexpected")
        return _rejected(envelope.job_id, InternalError(code="unexpected"))
    match outcome:
        case Finished(body=body):
            return Response(content=body, media_type=JSON_MEDIA_TYPE)
        case Rejected(error=error):
            return _rejected(envelope.job_id, error)
        case TryLater(error=error, retry_after=retry_after):
            return problem_response(error, retry_after=retry_after)
        case _:
            assert_never(outcome)


async def push(request: Request, state: ServiceState) -> Response:
    """Answer one delivery (ARCHITECTURE.md §7, steps 1-2; the rest is in ``app``)."""
    try:
        raw = await read_body(request, limit=state.settings.service.max_body_bytes)
    except MediaTooLargeError as e:
        return problem_response(e)
    envelope = envelopes.parse(raw)
    if envelope is None:
        return problem_response(
            InputError(code="invalid_request", detail="no usable job_id")
        )
    with structlog.contextvars.bound_contextvars(**_log_context(request)):
        try:
            state.limiter.acquire_nowait()
        except anyio.WouldBlock:
            busy = CapacityError(
                code="capacity_exceeded", detail="all job slots are busy"
            )
            return problem_response(busy, retry_after=RETRY_AFTER_BUSY_S)
        try:
            return await _admitted(state, envelope, raw)
        finally:
            state.limiter.release()
