"""The HTTP routes."""

import time
from http import HTTPStatus
from typing import cast

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from scenewise.app.contract import mapping
from scenewise.app.delivery import job_prefix
from scenewise.domain.errors import (
    InputError,
    InternalError,
    RetryableError,
    ScenewiseError,
)
from scenewise.domain.jobs import job_id
from scenewise.service.http import push as push_handler
from scenewise.service.http.problems import problem_response
from scenewise.service.http.state import ServiceState

log = structlog.get_logger(__name__)
router = APIRouter()


def _state(request: Request) -> ServiceState:
    return cast("ServiceState", request.app.state.scenewise)


@router.post("/v1/jobs")
async def post_job(request: Request) -> Response:
    """Run a job to a terminal state (a Cloud Tasks push target)."""
    return await push_handler.push(request, _state(request))


@router.get("/v1/jobs/{job}")
def get_job(job: str, request: Request) -> Response:
    """The job's status, from its record."""
    state = _state(request)
    missing = InputError(code="job_not_found", detail="no such job")
    not_found = problem_response(missing, status=HTTPStatus.NOT_FOUND)
    try:
        key = job_id(job)
    except ValueError:
        return not_found
    uri = f"{job_prefix(state.settings.service.state_prefix, key)}/status.json"
    try:
        blob = state.deps.store.read(uri)
        if blob is None:
            return not_found
        body = mapping.status_json(mapping.record_from_json(blob.data), time.time())
    except RetryableError as e:
        return problem_response(e, retry_after=5)
    except ScenewiseError as e:  # an unreadable record: problem+json, never bare 500
        log.warning("status_unreadable", code=e.code)
        return problem_response(e)
    except Exception:
        log.exception("status_unreadable", code="unexpected")
        return problem_response(InternalError(code="unexpected"))
    return Response(content=body, media_type="application/json")


@router.get("/healthz")
def healthz(request: Request) -> JSONResponse:
    """Liveness: 503 while a job thread has outlived budget + grace."""
    overdue = _state(request).watchdog.overdue(time.monotonic())
    if overdue:
        return JSONResponse({"status": "hung", "jobs": overdue}, status_code=503)
    return JSONResponse({"status": "ok"})


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    """Start-up: ready once the lifespan built every dependency."""
    stages = sorted(_state(request).deps.enabled_stages)
    return JSONResponse({"status": "ready", "stages": stages})
