import json
from typing import get_args, get_type_hints

import pytest
from pydantic import BaseModel

from scenewise.app.contract import mapping
from scenewise.app.contract.records import JobRecordV1
from scenewise.app.contract.requests import StageNameV1
from scenewise.app.contract.results import (
    ErrorInfoV1,
    JobResultV1,
    ProblemV1,
    StatusV1,
)
from scenewise.domain.errors import (
    Category,
    InputError,
    InternalError,
    JobIdConflictError,
)
from scenewise.domain.inputs import AudioFile, NoAudio
from scenewise.domain.jobs import (
    JobRecord,
    JobState,
    SkipReason,
    StageName,
    WireStatus,
    job_id,
)
from scenewise.domain.results import (
    Analysis,
    Failed,
    LanguageSkipped,
    Skipped,
    StageOutcome,
    Succeeded,
)
from scenewise.domain.speech import LanguageReport
from tests.fakes import CLIP


def _request(**changes: object) -> bytes:
    body: dict[str, object] = {
        "schema_version": "1",
        "job_id": "j-1",
        "external_ref": {"b": "2", "a": "1"},
        "stages": ["audio"],
        "audio": {"kind": "file", "uri": "mem://in/clip.mp4"},
        "delivery": {"artifacts": {"uri_prefix": "mem://out"}},
    }
    body.update(changes)
    return json.dumps(body).encode()


def test_to_domain() -> None:
    job = mapping.to_domain(_request())
    assert job.id == "j-1"
    assert job.spec.stages == {StageName.AUDIO}
    assert job.audio == AudioFile(uri="mem://in/clip.mp4")
    assert job.external_ref == (("a", "1"), ("b", "2"))
    assert job.artifacts_prefix == "mem://out"


def test_to_domain_audio_none_and_absent() -> None:
    assert mapping.to_domain(_request(audio={"kind": "none"})).audio == NoAudio()
    assert mapping.to_domain(_request(audio=None)).audio is None


@pytest.mark.parametrize(
    "raw",
    [
        _request(stages=[]),
        _request(stages=["dance"]),
        _request(extra_field=1),
        _request(schema_version="2"),
        _request(audio={"kind": "file", "uri": "x", "typo": 1}),
        b"{",
    ],
)
def test_to_domain_rejects(raw: bytes) -> None:
    with pytest.raises(InputError) as caught:
        mapping.to_domain(raw)
    assert caught.value.code == "invalid_request"


def test_to_domain_hides_input_values() -> None:
    with pytest.raises(InputError) as caught:
        mapping.to_domain(_request(audio={"kind": "file", "uri": 7}))
    assert "audio.file.uri" in caught.value.detail
    assert "7" not in caught.value.detail.replace("audio.file.uri", "")


def test_to_domain_maps_domain_value_errors() -> None:
    with pytest.raises(InputError) as caught:
        mapping.to_domain(_request(job_id=".."))
    assert caught.value.code == "invalid_request"


def _record(external_ref: tuple[tuple[str, str], ...] | None) -> JobRecord:
    return JobRecord(
        job_id=job_id("j-1"),
        state=JobState.SUCCEEDED,
        attempt=2,
        lease_until=10.0,
        request_digest="abc",
        error_code=None,
        result_uri="mem://out/a2/result.json",
        updated_at=5.0,
        scenewise_version="0.1.0",
        external_ref=external_ref,
    )


@pytest.mark.parametrize("ref", [None, (("a", "1"),)])
def test_record_round_trip(ref: tuple[tuple[str, str], ...] | None) -> None:
    record = _record(ref)
    assert mapping.record_from_json(mapping.record_to_json(record)) == record


def test_unreadable_record() -> None:
    with pytest.raises(InternalError) as caught:
        mapping.record_from_json(b'{"state": "nope"}')
    assert caught.value.code == "invariant_violation"


@pytest.mark.parametrize("ref", [None, (("a", "1"),)])
def test_status_json(ref: tuple[tuple[str, str], ...] | None) -> None:
    status = json.loads(mapping.status_json(_record(ref), now=20.0))
    assert status["status"] == "succeeded"
    assert status["result_uri"] == "mem://out/a2/result.json"
    assert status["external_ref"] == (None if ref is None else {"a": "1"})


def test_problem_and_rejection() -> None:
    error = JobIdConflictError()
    problem = mapping.problem(error, status=409, title="Conflict")
    assert (problem.code, problem.detail, problem.retryable) == (
        "job_id_conflict",
        "job_id_conflict",
        False,
    )
    rejection = json.loads(
        mapping.rejection_json("j-1", error, status=409, title="Conflict")
    )
    assert rejection["outcome"] == "rejected"
    assert rejection["problem"]["code"] == "job_id_conflict"


def _analysis(*outcomes: StageOutcome) -> Analysis:
    return Analysis(job_id=job_id("j-1"), media=CLIP, outcomes=outcomes)


def _outcome(outcome: Succeeded | Skipped | LanguageSkipped | Failed) -> StageOutcome:
    return StageOutcome(stage=StageName.AUDIO, outcome=outcome, seconds=0.25)


def _result(analysis: Analysis, audio_uri: str | None = None) -> dict[str, object]:
    raw = mapping.result_json(
        analysis, attempt=1, external_ref=(("a", "1"),), audio_uri=audio_uri
    )
    result: dict[str, object] = json.loads(raw)
    return result


def test_result_succeeded() -> None:
    result = _result(_analysis(_outcome(Succeeded())), "mem://out/a1/audio.wav")
    assert result["status"] == "succeeded"
    assert result["stages"] == {
        "audio": {
            "status": "succeeded",
            "reason": None,
            "error": None,
            "uri": "mem://out/a1/audio.wav",
        }
    }
    assert result["timings_ms"] == {"audio": 250}
    assert result["media"] == {"duration_s": 2.0, "has_audio": True, "has_video": True}


def test_result_skipped_and_failed() -> None:
    skipped = _result(_analysis(_outcome(Skipped(reason=SkipReason.NO_AUDIO_STREAM))))
    assert skipped["stages"] == {
        "audio": {
            "status": "skipped",
            "reason": "no_audio_stream",
            "error": None,
            "uri": None,
        }
    }
    language = LanguageSkipped(
        reason=SkipReason.LANGUAGE_UNKNOWN,
        report=LanguageReport(dominant=None, detected=("und",), partial=False),
    )
    assert _result(_analysis(_outcome(language)))["status"] == "succeeded"
    failed = _result(
        _analysis(_outcome(Failed(error_code="corrupt_media", category="input")))
    )
    assert failed["status"] == "partial"


def test_result_ignores_other_stages() -> None:
    captions = StageOutcome(stage=StageName.CAPTIONS, outcome=Succeeded(), seconds=0)
    result = _result(_analysis(captions))
    assert result["stages"] == {"audio": None}
    assert result["timings_ms"] == {"captions": 0}


def test_result_without_media_or_stages() -> None:
    result = _result(Analysis(job_id=job_id("j"), media=None, outcomes=()))
    assert result["media"] is None
    assert result["stages"] == {"audio": None}


def _field_values(model: type[BaseModel], name: str) -> set[str]:
    return set(get_args(model.model_fields[name].annotation))


def test_wire_stage_names_mirror_the_domain() -> None:
    assert set(get_args(StageNameV1.__value__)) == {s.value for s in StageName}


def test_wire_record_states_mirror_the_domain() -> None:
    assert _field_values(JobRecordV1, "state") == {s.value for s in JobState}


def test_wire_statuses_mirror_the_domain() -> None:
    assert set(get_args(StatusV1.__value__)) == set(get_args(WireStatus.__value__))


def test_wire_error_categories_mirror_the_domain() -> None:
    assert _field_values(ProblemV1, "category") == set(get_args(Category.__value__))
    # the wire also allows ``retryable``, which a failed stage never carries
    stage_categories = set(get_args(get_type_hints(Failed)["category"]))
    assert stage_categories <= _field_values(ErrorInfoV1, "category")


def test_wire_result_statuses_are_job_states() -> None:
    assert _field_values(JobResultV1, "status") <= {s.value for s in JobState}
