import time
from pathlib import Path

import pytest

from scenewise.app import stages
from scenewise.app.runner import remaining, run_job
from scenewise.domain.errors import InputError, InternalError, RetryableError
from scenewise.domain.inputs import AudioFile, NoAudio
from scenewise.domain.jobs import Job, JobSpec, SkipReason, StageName, job_id
from scenewise.domain.results import Failed, Skipped, Succeeded
from tests.fakes import CLIP, FakeMediaTool, InMemoryBlobStore, fake_dependencies


def _job(name: str = "clip.mp4", *stages: StageName) -> Job:
    return Job(
        id=job_id("j-1"),
        spec=JobSpec(stages=frozenset(stages or {StageName.AUDIO})),
        audio=AudioFile(uri=f"mem://in/{name}"),
    )


def _store() -> InMemoryBlobStore:
    store = InMemoryBlobStore()
    for name in ("clip.mp4", "silent.mp4", "broken.mp4"):
        store.write(f"mem://in/{name}", b"media", content_type="video/mp4")
    return store


def _deadline() -> float:
    return time.monotonic() + 60


def test_audio_stage_produces_the_track() -> None:
    analysis = run_job(_job(), fake_dependencies(store=_store()), deadline=_deadline())
    assert analysis.media == CLIP
    (outcome,) = analysis.outcomes
    assert outcome.stage is StageName.AUDIO
    assert outcome.outcome == Succeeded()
    assert outcome.seconds >= 0
    assert analysis.audio_wav is not None
    assert analysis.audio_wav.startswith(b"RIFF")


def test_no_audio_stream_skips_the_stage() -> None:
    deps = fake_dependencies(store=_store())
    analysis = run_job(_job("silent.mp4"), deps, deadline=_deadline())
    assert analysis.outcomes[0].outcome == Skipped(reason=SkipReason.NO_AUDIO_STREAM)
    assert analysis.audio_wav is None


def test_no_audio_input_skips_without_media() -> None:
    job = Job(
        id=job_id("j"),
        spec=JobSpec(stages=frozenset({StageName.AUDIO})),
        audio=NoAudio(),
    )
    analysis = run_job(job, fake_dependencies(), deadline=_deadline())
    assert analysis.media is None
    assert analysis.outcomes[0].outcome == Skipped(reason=SkipReason.NO_AUDIO_STREAM)


def test_stage_not_offered_fails_the_job() -> None:
    with pytest.raises(InputError) as caught:
        run_job(
            _job("clip.mp4", StageName.CAPTIONS),
            fake_dependencies(store=_store()),
            deadline=_deadline(),
        )
    assert caught.value.code == "stage_unavailable"


def test_enabled_but_unwired_stage_fails_that_stage_only() -> None:
    enabled = frozenset({StageName.AUDIO, StageName.CAPTIONS})
    deps = fake_dependencies(store=_store(), enabled=enabled)
    job = _job("clip.mp4", StageName.AUDIO, StageName.CAPTIONS)
    analysis = run_job(job, deps, deadline=_deadline())
    audio, captions = analysis.outcomes
    assert audio.outcome == Succeeded()
    assert captions.outcome == Failed(
        error_code="invariant_violation",
        category="internal",
        detail="stage captions is enabled but not wired",
    )


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ValueError("bad span"), "invariant_violation"),
        (RuntimeError("bug"), "unexpected"),
    ],
)
def test_other_errors_in_a_stage_fail_that_stage(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    def broken(_track: Path) -> bytes:
        raise error

    monkeypatch.setattr(stages, "audio", broken)
    analysis = run_job(_job(), fake_dependencies(store=_store()), deadline=_deadline())
    outcome = analysis.outcomes[0].outcome
    assert isinstance(outcome, Failed)
    assert (outcome.error_code, outcome.category) == (code, "internal")


def test_retryable_error_in_a_stage_fails_the_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_track: Path) -> bytes:
        raise RetryableError(code="storage_unavailable")

    monkeypatch.setattr(stages, "audio", unavailable)
    with pytest.raises(RetryableError):
        run_job(_job(), fake_dependencies(store=_store()), deadline=_deadline())


def test_errors_before_the_stages_fail_the_job() -> None:
    deps = fake_dependencies(store=_store())
    with pytest.raises(InputError) as caught:
        run_job(_job("broken.mp4"), deps, deadline=_deadline())
    assert caught.value.code == "corrupt_media"


def test_deadline() -> None:
    assert remaining(time.monotonic() + 10) > 0
    with pytest.raises(InternalError):
        remaining(time.monotonic() - 1)
    deps = fake_dependencies(
        store=_store(), media=FakeMediaTool(infos={"clip.mp4": CLIP})
    )
    with pytest.raises(InternalError) as caught:
        run_job(_job(), deps, deadline=time.monotonic() - 1)
    assert caught.value.code == "deadline_exceeded"
