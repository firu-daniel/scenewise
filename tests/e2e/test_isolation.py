"""Review r1, finding 1: one request must not read or overwrite another job's files."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scenewise.service.config import InputSettings, ServiceSettings, Settings
from scenewise.service.http.app import create_app

pytestmark = pytest.mark.e2e


def _client(state: Path, *, local_roots: tuple[Path, ...] = ()) -> TestClient:
    settings = Settings(
        inputs=InputSettings(local_roots=local_roots),
        service=ServiceSettings(
            state_prefix=state.as_uri(), artifact_roots=(state.parent / "artifacts",)
        ),
    )
    return TestClient(create_app(settings))


def _job(job_id: str, audio_uri: str, prefix: str | None = None) -> dict[str, object]:
    return {
        "schema_version": "1",
        "job_id": job_id,
        "stages": ["audio"],
        "audio": {"kind": "file", "uri": audio_uri},
        "delivery": {"artifacts": {"uri_prefix": prefix}} if prefix else {},
    }


@pytest.fixture
def victim(inputs: Path, tmp_path: Path) -> Path:
    """The state directory after job ``victim`` succeeded."""
    state = tmp_path / "state"
    with _client(state, local_roots=(inputs,)) as client:
        body = _job("victim", (inputs / "clip.mp4").as_uri())
        assert client.post("/v1/jobs", json=body).json()["status"] == "succeeded"
    return state


def test_cross_job_read_is_refused(victim: Path) -> None:
    stolen = (victim / "victim" / "a1" / "audio.wav").as_uri()
    for roots in ((), (victim.parent,)):  # none, and a root that contains the state
        with _client(victim, local_roots=roots) as client:
            status = client.post("/v1/jobs", json=_job(f"thief{len(roots)}", stolen))
        assert (status.json()["status"], status.json()["error_code"]) == (
            "failed",
            "uri_not_allowed",
        )


@pytest.mark.parametrize(
    ("prefix", "job"),
    [
        ("{state}/victim", "attacker"),
        ("{state}", "attacker"),
        ("{state}/../state/victim", "attacker"),
        ("{root}/artifacts/../state/victim", "attacker"),
        ("{root}/./state/victim", "attacker"),
        ("{root}//state/victim", "attacker"),
        ("{root}/artifacts/%2E%2E/state/victim", "attacker"),
        ("file://localhost{state_path}/victim", "attacker"),
        # The state directory is ``{root}/state``, so job ``state`` lands on it.
        ("{root}", "state"),
        ("{root}/artifacts/..", "state"),
    ],
)
def test_cross_job_overwrite_is_refused(
    victim: Path, inputs: Path, prefix: str, job: str
) -> None:
    result = victim / "victim" / "a1" / "result.json"
    before = result.read_bytes()
    before_tree = set(victim.rglob("*"))
    uri = prefix.format(
        state=victim.as_uri(), root=victim.parent.as_uri(), state_path=victim.as_posix()
    )
    with _client(victim, local_roots=(inputs,)) as client:
        body = _job(job, (inputs / "tone.m4a").as_uri(), uri)
        status = client.post("/v1/jobs", json=body).json()
    assert (status["status"], status["error_code"]) == ("failed", "uri_not_allowed")
    assert result.read_bytes() == before
    assert json.loads(before)["job_id"] == "victim"
    assert not (victim / "victim" / "a1" / "attacker").exists()
    assert not (victim / "a1").exists()
    created = {
        p.relative_to(victim).as_posix() for p in set(victim.rglob("*")) - before_tree
    }
    record = {
        job,
        f"{job}/status.json",
        f"{job}/.status.json.meta.json",
        f"{job}/.status.json.lock",
    }
    assert created <= record


def test_a_symlink_into_the_state_prefix_is_refused(victim: Path, inputs: Path) -> None:
    artifacts = victim.parent / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "link").symlink_to(victim / "victim")
    with _client(victim, local_roots=(inputs,)) as client:
        body = _job(
            "attacker", (inputs / "tone.m4a").as_uri(), (artifacts / "link").as_uri()
        )
        status = client.post("/v1/jobs", json=body).json()
    assert (status["status"], status["error_code"]) == ("failed", "uri_not_allowed")
    assert not (victim / "victim" / "attacker").exists()


def test_artifacts_under_an_artifact_root_are_job_scoped(
    victim: Path, inputs: Path
) -> None:
    prefix = (victim.parent / "artifacts" / "media-1").as_uri()
    with _client(victim, local_roots=(inputs,)) as client:
        body = _job("job-2", (inputs / "tone.m4a").as_uri(), prefix)
        status = client.post("/v1/jobs", json=body).json()
    assert status["status"] == "succeeded"
    assert status["result_uri"] == f"{prefix}/job-2/a1/result.json"


def test_artifacts_outside_every_root_are_refused(
    victim: Path, inputs: Path, tmp_path: Path
) -> None:
    prefix = (tmp_path / "elsewhere").as_uri()
    with _client(victim, local_roots=(inputs,)) as client:
        body = _job("job-3", (inputs / "tone.m4a").as_uri(), prefix)
        status = client.post("/v1/jobs", json=body).json()
    assert (status["status"], status["error_code"]) == ("failed", "uri_not_allowed")
