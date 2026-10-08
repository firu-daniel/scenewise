import pytest

from scenewise.domain.errors import (
    CapacityError,
    ConfigurationError,
    InputError,
    InternalError,
    MediaTooLargeError,
    RetryableError,
    ScenewiseError,
)


@pytest.mark.parametrize(
    ("error", "category", "retryable"),
    [
        (InputError(code="invalid_request"), "input", False),
        (MediaTooLargeError(code="request_too_large"), "input", False),
        (RetryableError(code="storage_unavailable"), "retryable", True),
        (CapacityError(code="capacity_exceeded"), "retryable", True),
        (InternalError(code="unexpected"), "internal", False),
        (ConfigurationError(code="ffmpeg_unavailable"), "configuration", False),
    ],
)
def test_categories(error: ScenewiseError, category: str, retryable: bool) -> None:
    assert error.category == category
    assert error.retryable is retryable


def test_message_carries_code_and_detail() -> None:
    assert str(ScenewiseError()) == "internal"
    assert str(InputError(code="corrupt_media", detail="bad header")) == (
        "corrupt_media: bad header"
    )
