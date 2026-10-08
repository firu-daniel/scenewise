from scenewise.domain.jobs import JobState, SkipReason, StageName
from scenewise.domain.results import (
    Failed,
    Skipped,
    StageOutcome,
    Succeeded,
    job_state,
)


def _outcome(outcome: Succeeded | Skipped | Failed) -> StageOutcome:
    return StageOutcome(stage=StageName.AUDIO, outcome=outcome, seconds=0.1)


def test_a_skip_is_not_a_failure() -> None:
    skipped = Skipped(reason=SkipReason.NO_AUDIO_STREAM)
    assert job_state([_outcome(Succeeded()), _outcome(skipped)]) is JobState.SUCCEEDED
    assert job_state([]) is JobState.SUCCEEDED


def test_any_failure_is_partial() -> None:
    failed = Failed(error_code="corrupt_media", category="input")
    assert job_state([_outcome(Succeeded()), _outcome(failed)]) is JobState.PARTIAL
