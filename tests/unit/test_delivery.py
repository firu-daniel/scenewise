import json
from dataclasses import dataclass, field
from typing import override

import pytest

from scenewise.app.contract import mapping
from scenewise.app.contract.envelope import Envelope, parse
from scenewise.app.delivery import (
    DeliveryOutcome,
    DeliveryPolicy,
    Finished,
    TryLater,
    handle_delivery,
    job_prefix,
)
from scenewise.app.deps import Dependencies
from scenewise.domain.errors import RetryableError
from scenewise.domain.jobs import AttemptInfo, JobRecord, JobState
from scenewise.domain.time import Seconds
from scenewise.ports import WriteConflictError
from tests.fakes import (
    FIXTURE_INFOS,
    FakeMediaTool,
    InMemoryBlobStore,
    fake_dependencies,
)

NOW = 1_000_000.0
STATUS = "mem://state/j-1/status.json"
POLICY = DeliveryPolicy(state_prefix="mem://state", attempt_budget=Seconds(60))


def _info(max_attempts: int = 3) -> AttemptInfo:
    return AttemptInfo(now=NOW, lease=Seconds(100), max_attempts=max_attempts)


def _raw(**changes: object) -> bytes:
    body: dict[str, object] = {
        "schema_version": "1",
        "job_id": "j-1",
        "stages": ["audio"],
        "audio": {"kind": "file", "uri": "mem://in/clip.mp4"},
        "delivery": {},
    }
    body.update(changes)
    return json.dumps(body).encode()


def _envelope(raw: bytes) -> Envelope:
    envelope = parse(raw)
    assert envelope is not None
    return envelope


@dataclass
class ConflictingStore(InMemoryBlobStore):
    """Raises ``WriteConflictError`` on the listed write numbers (1-based)."""

    conflicts: set[int] = field(default_factory=set)
    writes: int = 0

    def __post_init__(self) -> None:
        super().__init__()

    @override
    def write(
        self,
        uri: str,
        data: bytes,
        *,
        content_type: str,
        if_generation: int | None = None,
    ) -> int:
        self.writes += 1
        if self.writes in self.conflicts:
            raise WriteConflictError(uri)
        return super().write(
            uri, data, content_type=content_type, if_generation=if_generation
        )


def _store(store: InMemoryBlobStore | None = None) -> InMemoryBlobStore:
    store = store or InMemoryBlobStore()
    for name in FIXTURE_INFOS:
        store.objects.pop(f"mem://in/{name}", None)
        InMemoryBlobStore.write(store, f"mem://in/{name}", b"m", content_type="x")
    return store


def _deliver(
    deps: Dependencies, raw: bytes | None = None, *, max_attempts: int = 3
) -> DeliveryOutcome:
    raw = raw or _raw()
    return handle_delivery(
        _envelope(raw), raw, deps=deps, info=_info(max_attempts), policy=POLICY
    )


def _record(store: InMemoryBlobStore) -> JobRecord:
    blob = store.read(STATUS)
    assert blob is not None
    return mapping.record_from_json(blob.data)


def _status(outcome: DeliveryOutcome) -> dict[str, object]:
    assert isinstance(outcome, Finished)
    status: dict[str, object] = json.loads(outcome.body)
    return status


def _seed(store: InMemoryBlobStore, *, attempt: int, lease_until: float) -> None:
    claim = JobRecord(
        job_id=_envelope(_raw()).job_id,
        state=JobState.RUNNING,
        attempt=attempt,
        lease_until=lease_until,
        request_digest=_envelope(_raw()).request_digest,
        error_code=None,
        result_uri=None,
        updated_at=NOW,
        schema_version="1",
        scenewise_version="0.1.0",
        external_ref=None,
    )
    store.write(STATUS, mapping.record_to_json(claim), content_type="application/json")


def test_job_prefix() -> None:
    assert job_prefix("mem://state/", "j") == "mem://state/j"


def test_first_delivery_runs_to_a_terminal_record() -> None:
    store = _store()
    status = _status(_deliver(fake_dependencies(store=store)))
    assert status["status"] == "succeeded"
    assert status["attempt"] == 1
    assert status["result_uri"] == "mem://state/j-1/a1/result.json"
    record = _record(store)
    assert record.state is JobState.SUCCEEDED
    assert "mem://state/j-1/a1/audio.wav" in store.objects


def test_artifacts_go_to_the_requested_prefix() -> None:
    store = _store()
    raw = _raw(delivery={"artifacts": {"uri_prefix": "mem://out/x"}})
    status = _status(_deliver(fake_dependencies(store=store), raw))
    assert status["result_uri"] == "mem://out/x/j-1/a1/result.json"


@pytest.mark.parametrize("prefix", ["mem://state", "mem://state/other-job"])
def test_artifacts_never_go_under_the_state_prefix(prefix: str) -> None:
    store = _store()
    raw = _raw(delivery={"artifacts": {"uri_prefix": prefix}})
    status = _status(_deliver(fake_dependencies(store=store), raw))
    assert (status["status"], status["error_code"]) == ("failed", "uri_not_allowed")
    assert not any(uri.startswith("mem://state/other-job") for uri in store.objects)


def test_duplicate_is_answered_from_the_record() -> None:
    store = _store()
    deps = fake_dependencies(store=store)
    first = _status(_deliver(deps))
    writes = len(store.objects)
    assert _status(_deliver(deps)) == first
    assert len(store.objects) == writes


def test_same_job_id_other_request_is_rejected_without_a_record() -> None:
    store = _store()
    deps = fake_dependencies(store=store)
    _deliver(deps)
    before = store.objects[STATUS]
    rejection = _status(_deliver(deps, _raw(stages=["audio", "audio"])))
    assert rejection["outcome"] == "rejected"
    assert store.objects[STATUS] == before


def test_live_lease_is_in_progress() -> None:
    store = _store()
    _seed(store, attempt=1, lease_until=NOW + 40)
    outcome = _deliver(fake_dependencies(store=store))
    assert isinstance(outcome, TryLater)
    assert outcome.error.code == "job_in_progress"
    assert outcome.retry_after == Seconds(40)


def test_expired_lease_runs_the_next_attempt() -> None:
    store = _store()
    _seed(store, attempt=1, lease_until=NOW - 1)
    status = _status(_deliver(fake_dependencies(store=store)))
    assert (status["status"], status["attempt"]) == ("succeeded", 2)


def test_give_up_after_the_last_attempt() -> None:
    store = _store()
    _seed(store, attempt=3, lease_until=NOW - 1)
    status = _status(_deliver(fake_dependencies(store=store)))
    assert (status["status"], status["error_code"]) == ("failed", "attempts_exhausted")


def test_give_up_loses_the_race() -> None:
    store = _store(ConflictingStore(conflicts={2}))  # 1: seed, 2: give-up
    _seed(store, attempt=3, lease_until=NOW - 1)
    outcome = _deliver(fake_dependencies(store=store))
    assert isinstance(outcome, TryLater)


def test_claim_lost_to_another_delivery() -> None:
    store = _store(ConflictingStore(conflicts={1}))  # 1: claim
    outcome = _deliver(fake_dependencies(store=store))
    assert isinstance(outcome, TryLater)
    assert outcome.error.code == "job_in_progress"


def test_invalid_body_with_a_job_id_ends_failed() -> None:
    store = _store()
    status = _status(_deliver(fake_dependencies(store=store), _raw(stages=[])))
    assert (status["status"], status["error_code"]) == ("failed", "invalid_request")
    assert status["result_uri"] is None


def test_stage_not_offered_ends_failed() -> None:
    store = _store()
    raw = _raw(stages=["captions"])
    status = _status(_deliver(fake_dependencies(store=store), raw))
    assert status["error_code"] == "stage_unavailable"


def test_unexpected_exception_ends_failed() -> None:
    store = _store()
    media = FakeMediaTool(infos=FIXTURE_INFOS, error=RuntimeError("bug"))
    status = _status(_deliver(fake_dependencies(store=store, media=media)))
    assert status["error_code"] == "unexpected"


@pytest.mark.parametrize("conflicts", [set(), {2}])  # 1: claim, 2: release
def test_retryable_error_releases_the_attempt(conflicts: set[int]) -> None:
    store = _store(ConflictingStore(conflicts=conflicts))
    media = FakeMediaTool(
        infos=FIXTURE_INFOS, error=RetryableError(code="storage_unavailable")
    )
    outcome = _deliver(fake_dependencies(store=store, media=media))
    assert isinstance(outcome, TryLater)
    assert outcome.error.code == "storage_unavailable"
    record = _record(store)
    assert record.state is JobState.RUNNING
    assert record.lease_until == (NOW + 100 if conflicts else NOW)


def test_retryable_error_on_the_last_attempt_ends_failed() -> None:
    store = _store()
    media = FakeMediaTool(
        infos=FIXTURE_INFOS, error=RetryableError(code="backend_unavailable")
    )
    deps = fake_dependencies(store=store, media=media)
    status = _status(_deliver(deps, max_attempts=1))
    assert status["error_code"] == "attempts_exhausted"


def test_fenced_attempt_does_not_overwrite_the_record() -> None:
    # 1: claim, 2: audio.wav, 3: result.json, 4: terminal record
    store = _store(ConflictingStore(conflicts={4}))
    outcome = _deliver(fake_dependencies(store=store))
    assert isinstance(outcome, TryLater)
    assert _record(store).state is JobState.RUNNING
