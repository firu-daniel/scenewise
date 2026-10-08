import json
import time
import wave
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from fastapi.testclient import TestClient

from scenewise.app.contract import mapping
from scenewise.app.contract.envelope import parse
from scenewise.domain.jobs import JobRecord, JobState
from scenewise.service.config import InputSettings, ServiceSettings, Settings
from scenewise.service.http.app import create_app

if TYPE_CHECKING:
    from scenewise.service.http.state import ServiceState

pytestmark = pytest.mark.e2e


@pytest.fixture
def state(tmp_path: Path) -> Path:
    return tmp_path / "state"


@pytest.fixture
def client(inputs: Path, state: Path) -> Iterator[TestClient]:
    settings = Settings(
        inputs=InputSettings(local_roots=(inputs,)),
        service=ServiceSettings(state_prefix=state.as_uri()),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _job(inputs: Path, name: str = "clip.mp4", **changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1",
        "job_id": "um-1-r1",
        "external_ref": {"media": "1"},
        "stages": ["audio"],
        "audio": {"kind": "file", "uri": (inputs / name).as_uri()},
        "delivery": {},
    }
    body.update(changes)
    return body


def test_job_runs_to_a_terminal_record(
    client: TestClient, inputs: Path, state: Path
) -> None:
    response = client.post("/v1/jobs", json=_job(inputs))
    assert response.status_code == 200
    status = response.json()
    assert (status["status"], status["attempt"]) == ("succeeded", 1)
    assert status["external_ref"] == {"media": "1"}
    assert status["result_uri"] == (state / "um-1-r1" / "a1" / "result.json").as_uri()
    result = json.loads((state / "um-1-r1" / "a1" / "result.json").read_text())
    assert result["stages"]["audio"]["status"] == "succeeded"
    with wave.open(str(state / "um-1-r1" / "a1" / "audio.wav")) as track:
        assert (track.getframerate(), track.getnchannels()) == (16_000, 1)
    assert client.get("/v1/jobs/um-1-r1").json() == status
    assert client.post("/v1/jobs", json=_job(inputs)).json() == status  # duplicate


def test_video_without_audio(client: TestClient, inputs: Path) -> None:
    status = client.post("/v1/jobs", json=_job(inputs, "silent.mp4")).json()
    assert status["status"] == "succeeded"


def test_job_id_reused_for_another_request(client: TestClient, inputs: Path) -> None:
    client.post("/v1/jobs", json=_job(inputs))
    response = client.post("/v1/jobs", json=_job(inputs, "tone.m4a"))
    assert response.status_code == 200
    assert response.json()["problem"]["code"] == "job_id_conflict"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"stages": ["captions"]}, "stage_unavailable"),
        ({"stages": []}, "invalid_request"),
        ({"audio": {"kind": "file", "uri": "file:///etc/passwd"}}, "uri_not_allowed"),
        (
            {"audio": {"kind": "file", "uri": "https://example.com/a.mp4"}},
            "uri_not_allowed",
        ),
    ],
)
def test_bad_requests_end_in_a_failed_record(
    client: TestClient, inputs: Path, changes: dict[str, object], code: str
) -> None:
    body = _job(inputs)
    body.update(changes)
    response = client.post("/v1/jobs", json=body)
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["error_code"]) == (
        "failed",
        code,
    )


def test_corrupt_media_fails_the_job(client: TestClient, inputs: Path) -> None:
    status = client.post("/v1/jobs", json=_job(inputs, "broken.mp4")).json()
    assert (status["status"], status["error_code"]) == ("failed", "corrupt_media")


def test_no_usable_job_id_is_422(client: TestClient) -> None:
    response = client.post("/v1/jobs", content=b'{"job_id": "a/b"}')
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid_request"


def test_body_over_the_limit_is_413(client: TestClient) -> None:
    response = client.post("/v1/jobs", content=b"x" * 1_048_577)
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/v1/jobs/nope").status_code == 404
    assert client.get("/v1/jobs/a%20b").status_code == 404  # not a valid job id


def test_get_of_an_unknown_job_writes_nothing(client: TestClient, state: Path) -> None:
    before = sorted(state.rglob("*")) if state.exists() else []
    assert client.get("/v1/jobs/never-seen").status_code == 404
    after = sorted(state.rglob("*")) if state.exists() else []
    assert after == before


def test_unreadable_record(client: TestClient, inputs: Path, state: Path) -> None:
    (state / "um-1-r1").mkdir(parents=True)
    (state / "um-1-r1" / "status.json").write_bytes(b"{not a record")
    response = client.post("/v1/jobs", json=_job(inputs))
    assert response.status_code == 200  # never a retried 5xx (ARCHITECTURE.md §9)
    assert response.json()["outcome"] == "rejected"
    assert response.json()["problem"]["code"] == "invariant_violation"
    status = client.get("/v1/jobs/um-1-r1")
    assert status.status_code == 500
    assert status.headers["content-type"] == "application/problem+json"
    assert status.json()["code"] == "invariant_violation"


def test_probes(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready", "stages": ["audio"]}


def test_streamed_body_over_the_limit_is_413(client: TestClient) -> None:
    chunks = iter([b"x" * 600_000, b"x" * 600_000])
    response = client.post("/v1/jobs", content=chunks)
    assert response.status_code == 413


def test_full_admission_is_429(inputs: Path, state: Path) -> None:
    settings = Settings(
        inputs=InputSettings(local_roots=(inputs,)),
        service=ServiceSettings(state_prefix=state.as_uri()),
    )
    app = create_app(settings)
    with TestClient(app) as client:
        limiter = cast("ServiceState", app.state.scenewise).limiter
        portal = client.portal
        assert portal is not None
        token = object()
        portal.call(limiter.acquire_on_behalf_of, token)
        try:
            response = client.post("/v1/jobs", json=_job(inputs))
        finally:
            portal.call(limiter.release_on_behalf_of, token)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"


def test_live_lease_is_503(client: TestClient, inputs: Path, state: Path) -> None:
    body = _job(inputs)
    raw = json.dumps(body).encode()
    envelope = parse(raw)
    assert envelope is not None
    claim = JobRecord(
        job_id=envelope.job_id,
        state=JobState.RUNNING,
        attempt=1,
        lease_until=time.time() + 600,
        request_digest=envelope.request_digest,
        error_code=None,
        result_uri=None,
        updated_at=time.time(),
        schema_version="1",
        scenewise_version="0.1.0",
        external_ref=None,
    )
    (state / "um-1-r1").mkdir(parents=True)
    (state / "um-1-r1" / "status.json").write_bytes(mapping.record_to_json(claim))
    response = client.post("/v1/jobs", content=raw)
    assert response.status_code == 503
    assert response.json()["code"] == "job_in_progress"
    assert int(response.headers["retry-after"]) > 500
    assert client.get("/v1/jobs/um-1-r1").json()["status"] == "running"


def test_storage_down_is_503(inputs: Path, tmp_path: Path) -> None:
    (tmp_path / "blocked").write_bytes(b"")
    settings = Settings(
        inputs=InputSettings(local_roots=(inputs,)),
        service=ServiceSettings(state_prefix=(tmp_path / "blocked" / "s").as_uri()),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/jobs", json=_job(inputs))
        assert response.status_code == 503
        assert response.json()["code"] == "storage_unavailable"
        assert client.get("/v1/jobs/um-1-r1").status_code == 404
