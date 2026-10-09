"""The HTTP routes."""

import time
from http import HTTPStatus
from typing import Final, cast

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from scenewise.app.constants import JSON_MEDIA_TYPE
from scenewise.app.delivery import job_status
from scenewise.domain.errors import (
    InternalError,
    JobNotFoundError,
    RetryableError,
    ScenewiseError,
)
from scenewise.service.http import push as push_handler
from scenewise.service.http.problems import problem_response
from scenewise.service.http.state import ServiceState

log = structlog.get_logger(__name__)
router = APIRouter()

RETRY_AFTER_STORAGE_S: Final = 5.0  # the job store failed transiently on a status read


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
    try:
        body = job_status(
            job,
            store=state.deps.store,
            state_prefix=state.settings.service.state_prefix,
            now=time.time(),
        )
    except RetryableError as e:
        return problem_response(e, retry_after=RETRY_AFTER_STORAGE_S)
    except ScenewiseError as e:  # an unreadable record: problem+json, never bare 500
        log.warning("status_unreadable", code=e.code)
        return problem_response(e)
    except Exception:
        log.exception("status_unreadable", code="unexpected")
        return problem_response(InternalError(code="unexpected"))
    if body is None:
        return problem_response(JobNotFoundError(detail="no such job"))
    return Response(content=body, media_type=JSON_MEDIA_TYPE)


@router.get("/healthz")
def healthz(request: Request) -> JSONResponse:
    """Liveness: 503 while a job thread has outlived budget + grace."""
    overdue = _state(request).watchdog.overdue(time.monotonic())
    if overdue:
        return JSONResponse(
            {"status": "hung", "jobs": overdue},
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    return JSONResponse({"status": "ok"})


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    """Start-up: ready once the lifespan built every dependency."""
    stages = sorted(_state(request).deps.enabled_stages)
    return JSONResponse({"status": "ready", "stages": stages})
