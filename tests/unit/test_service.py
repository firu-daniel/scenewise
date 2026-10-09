import time

import pytest
from pydantic import ValidationError

from scenewise.domain.errors import (
    CapacityError,
    ConfigurationError,
    InputError,
    JobIdConflictError,
    JobNotFoundError,
    MediaTooLargeError,
    RetryableError,
    ScenewiseError,
    UnsupportedMediaError,
)
from scenewise.service.config import ServiceSettings, Settings
from scenewise.service.http.health import Watchdog
from scenewise.service.http.problems import http_status, problem_title


def test_watchdog_reports_only_overdue_jobs() -> None:
    watchdog = Watchdog(limit_s=10)
    with watchdog.watch("a"), watchdog.watch("b"):
        now = time.monotonic()
        assert watchdog.overdue(now) == []
        assert watchdog.overdue(now + 11) == ["a", "b"]
    assert watchdog.overdue(time.monotonic() + 100) == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (CapacityError(code="capacity_exceeded"), 429),
        (RetryableError(code="job_in_progress"), 503),
        (MediaTooLargeError(code="request_too_large"), 413),
        (UnsupportedMediaError(code="unsupported_media"), 415),
        (InputError(code="invalid_request"), 422),
        (JobIdConflictError(), 409),
        (JobNotFoundError(), 404),
        (ConfigurationError(code="store_unavailable"), 500),
        (ScenewiseError(), 500),
    ],
)
def test_http_status(error: ScenewiseError, status: int) -> None:
    assert http_status(error) == status


def test_problem_title_is_the_status_phrase_unless_the_error_has_one() -> None:
    conflict = JobIdConflictError()
    assert problem_title(conflict, 409) == "Job id already used"
    assert problem_title(JobNotFoundError(), 404) == "Not Found"


def test_timing_invariant() -> None:
    assert ServiceSettings().lease_s == 1920
    with pytest.raises(ValidationError, match="dispatch_deadline_s"):
        ServiceSettings(attempt_budget_s=1700)


def test_settings_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCENEWISE_SERVICE__MAX_JOBS", "2")
    monkeypatch.setenv("SCENEWISE_MEDIA__FFMPEG", "/opt/ffmpeg")
    settings = Settings()
    assert settings.service.max_jobs == 2
    assert settings.media.ffmpeg == "/opt/ffmpeg"
    assert settings.service.state_prefix.startswith("file://")
