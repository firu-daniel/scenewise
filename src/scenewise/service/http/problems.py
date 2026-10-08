"""RFC 9457 problem responses with the members ``code``, ``category``, ``retryable``.

The 413 and 415 classes apply to direct callers; on the push path every error with a
keyed record is answered 200 by ``app.delivery`` (Cloud Tasks retries every non-2xx).
"""

import math
from http import HTTPStatus

from fastapi.responses import Response

from scenewise.app.contract import mapping
from scenewise.domain.errors import (
    CapacityError,
    InputError,
    MediaTooLargeError,
    RetryableError,
    ScenewiseError,
    UnsupportedMediaError,
)

PROBLEM_JSON = "application/problem+json"
# HTTPStatus.UNPROCESSABLE_CONTENT exists only from Python 3.13.
UNPROCESSABLE_CONTENT = 422


def http_status(error: ScenewiseError) -> int:
    """The HTTP status of an error that is answered as a problem."""
    match error:
        case CapacityError():
            return HTTPStatus.TOO_MANY_REQUESTS
        case RetryableError():
            return HTTPStatus.SERVICE_UNAVAILABLE
        case MediaTooLargeError():
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        case UnsupportedMediaError():
            return HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        case InputError():
            return UNPROCESSABLE_CONTENT
        case _:
            return HTTPStatus.INTERNAL_SERVER_ERROR


def problem_response(
    error: ScenewiseError,
    *,
    retry_after: float | None = None,
    status: int | None = None,
) -> Response:
    """Render ``error`` as a problem, with ``Retry-After`` when given."""
    status = status or http_status(error)
    body = mapping.problem(error, status=status, title=HTTPStatus(status).phrase)
    headers = (
        {} if retry_after is None else {"Retry-After": str(math.ceil(retry_after))}
    )
    return Response(
        content=body.model_dump_json(),
        status_code=status,
        media_type=PROBLEM_JSON,
        headers=headers,
    )
