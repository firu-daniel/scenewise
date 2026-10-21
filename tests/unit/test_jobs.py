import pytest
from hypothesis import given
from hypothesis import strategies as st

from scenewise.domain.jobs import (
    AlreadyDone,
    AttemptInfo,
    Conflict,
    GiveUp,
    InProgress,
    JobRecord,
    JobState,
    Start,
    decide_attempt,
    job_id,
    wire_status,
)
from scenewise.domain.time import Seconds

NOW = 1_000_000.0
INFO = AttemptInfo(now=NOW, lease=Seconds(1920), max_attempts=3)


def _record(
    *,
    state: JobState = JobState.RUNNING,
    attempt: int = 1,
    lease_until: float = NOW + 10,
) -> JobRecord:
    return JobRecord(
        job_id=job_id("job-1"),
        state=state,
        attempt=attempt,
        lease_until=lease_until,
        request_digest="d1",
        error_code=None,
        result_uri=None,
        updated_at=NOW - 10,
        scenewise_version="0.1.0",
        external_ref=None,
    )


@pytest.mark.parametrize("value", ["a", "um-123-r4", "A.b_c:d-e", "x" * 200])
def test_job_id_accepts(value: str) -> None:
    assert job_id(value) == value


@pytest.mark.parametrize(
    "value", ["", ".", "..", "a/b", "a b", "x" * 201, "é", "%2e%2e", "a\\b"]
)
def test_job_id_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="invalid job id"):
        job_id(value)


@given(st.from_regex(r"\A[A-Za-z0-9._:-]{1,200}\Z"))
def test_job_id_accepts_the_pattern(value: str) -> None:
    if value in {".", ".."}:
        return
    assert job_id(value) == value


def test_no_record_starts_attempt_one() -> None:
    assert decide_attempt(None, "d1", INFO) == Start(attempt=1)


def test_other_digest_conflicts() -> None:
    assert decide_attempt(_record(), "d2", INFO) == Conflict(existing_digest="d1")


@pytest.mark.parametrize(
    "state", [JobState.SUCCEEDED, JobState.PARTIAL, JobState.FAILED]
)
def test_terminal_is_already_done(state: JobState) -> None:
    record = _record(state=state)
    assert decide_attempt(record, "d1", INFO) == AlreadyDone(record=record)


def test_live_lease_is_in_progress() -> None:
    assert decide_attempt(_record(), "d1", INFO) == InProgress(retry_after=Seconds(10))


def test_expired_lease_starts_the_next_attempt() -> None:
    record = _record(lease_until=NOW, attempt=2)
    assert decide_attempt(record, "d1", INFO) == Start(attempt=3)


def test_expired_last_attempt_gives_up() -> None:
    record = _record(lease_until=NOW - 1, attempt=3)
    assert decide_attempt(record, "d1", INFO) == GiveUp(attempt=3)


@given(st.floats(min_value=-5, max_value=5, allow_nan=False))
def test_lease_boundary(offset: float) -> None:
    lease_until = NOW + offset
    decision = decide_attempt(_record(lease_until=lease_until), "d1", INFO)
    if lease_until > NOW:
        assert isinstance(decision, InProgress)
        assert decision.retry_after == lease_until - NOW
    else:
        assert decision == Start(attempt=2)


@pytest.mark.parametrize(
    ("state", "lease_until", "expected"),
    [
        (JobState.RUNNING, NOW + 1, "running"),
        (JobState.RUNNING, NOW, "retry_wait"),
        (JobState.SUCCEEDED, NOW, "succeeded"),
        (JobState.PARTIAL, NOW, "partial"),
        (JobState.FAILED, NOW, "failed"),
    ],
)
def test_wire_status(state: JobState, lease_until: float, expected: str) -> None:
    assert wire_status(_record(state=state, lease_until=lease_until), NOW) == expected
