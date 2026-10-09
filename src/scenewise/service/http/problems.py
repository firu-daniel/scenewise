"""RFC 9457 problem responses with the members ``code``, ``category``, ``retryable``.

The 413 and 415 classes apply to direct callers; on the push path every non-retryable
error with a keyed ``job_id`` is answered 200 by ``push`` (Cloud Tasks retries every
non-2xx), with the status below inside the body.
"""

import math
from http import HTTPStatus
from typing import Final

from fastapi.responses import Response

from scenewise.app.contract import mapping
from scenewise.domain.errors import (
    CapacityError,
    InputError,
    JobIdConflictError,
    JobNotFoundError,
    MediaTooLargeError,
    RetryableError,
    ScenewiseError,
    UnsupportedMediaError,
)

PROBLEM_JSON: Final = "application/problem+json"
# HTTPStatus.UNPROCESSABLE_CONTENT exists only from Python 3.13.
UNPROCESSABLE_CONTENT: Final = 422


# Error class -> status, first match wins: a leaf comes before its parent class.
_STATUSES: Final[tuple[tuple[type[ScenewiseError], int], ...]] = (
    (CapacityError, HTTPStatus.TOO_MANY_REQUESTS),
    (RetryableError, HTTPStatus.SERVICE_UNAVAILABLE),
    (MediaTooLargeError, HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
    (UnsupportedMediaError, HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
    (JobIdConflictError, HTTPStatus.CONFLICT),
    (JobNotFoundError, HTTPStatus.NOT_FOUND),
    (InputError, UNPROCESSABLE_CONTENT),
)


def http_status(error: ScenewiseError) -> int:
    """The HTTP status of an error that is answered as a problem."""
    return next(
        (status for cls, status in _STATUSES if isinstance(error, cls)),
        HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def problem_title(error: ScenewiseError, status: int) -> str:
    """The problem ``title``: the status phrase, unless the error has its own."""
    match error:
        case JobIdConflictError():
            return "Job id already used"
        case _:
            return HTTPStatus(status).phrase


def problem_response(
    error: ScenewiseError,
    *,
    retry_after: float | None = None,
    status: int | None = None,
) -> Response:
    """Render ``error`` as a problem, with ``Retry-After`` when given."""
    status = status or http_status(error)
    body = mapping.problem(error, status=status, title=problem_title(error, status))
    headers = (
        {} if retry_after is None else {"Retry-After": str(math.ceil(retry_after))}
    )
    return Response(
        content=body.model_dump_json(),
        status_code=status,
        media_type=PROBLEM_JSON,
        headers=headers,
    )
