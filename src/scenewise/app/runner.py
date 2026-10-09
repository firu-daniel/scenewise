"""``run_job()``: compose the requested stages over the acquired inputs."""

import time
from typing import Literal

import structlog

from scenewise.app import stages
from scenewise.app.audio import AcquiredAudio, acquire_audio
from scenewise.app.deps import Dependencies
from scenewise.domain import plan
from scenewise.domain.errors import (
    InputError,
    InternalError,
    RetryableError,
    ScenewiseError,
)
from scenewise.domain.jobs import Job, SkipReason, StageName
from scenewise.domain.results import (
    Analysis,
    Failed,
    Outcome,
    Skipped,
    StageOutcome,
    Succeeded,
)

log = structlog.get_logger(__name__)


def remaining(deadline: float) -> float:
    """Seconds left before ``deadline`` (a ``time.monotonic()`` value)."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise InternalError(code="deadline_exceeded")
    return left


def _audio_stage(acquired: AcquiredAudio | None) -> tuple[Outcome, bytes | None]:
    if acquired is None or acquired.track is None:
        return Skipped(reason=SkipReason.NO_AUDIO_STREAM), None
    return Succeeded(), stages.audio(acquired.track)


def _dispatch(
    stage: StageName, acquired: AcquiredAudio | None
) -> tuple[Outcome, bytes | None]:
    match stage:
        case StageName.AUDIO:
            return _audio_stage(acquired)
        case _:
            detail = f"stage {stage.value} is enabled but not wired"
            raise InternalError(code="invariant_violation", detail=detail)


def _run_stage(
    stage: StageName, acquired: AcquiredAudio | None
) -> tuple[Outcome, bytes | None]:
    """Run one stage; anything but a retryable error fails this stage only (§9).

    A domain ``ValueError`` is an ``invariant_violation`` and any other exception is
    ``unexpected``, both internal; a ``RetryableError`` fails the attempt instead.
    """
    try:
        return _dispatch(stage, acquired)
    except RetryableError:
        raise
    except ScenewiseError as e:
        log.warning("stage_failed", code=e.code)
        category: Literal["input", "internal"] = (
            "input" if isinstance(e, InputError) else "internal"
        )
        return Failed(error_code=e.code, category=category, detail=e.detail), None
    except ValueError as e:
        log.warning("stage_failed", code="invariant_violation")
        failed = Failed(
            error_code="invariant_violation", category="internal", detail=str(e)
        )
        return failed, None
    except Exception:
        log.exception("stage_failed", code="unexpected")
        return Failed(error_code="unexpected", category="internal"), None


def run_job(job: Job, deps: Dependencies, *, deadline: float) -> Analysis:
    """Run every requested stage of ``job``; errors before the stages fail the job.

    A requested stage this deployment does not offer is
    ``InputError(code="stage_unavailable")``. The deadline is checked between stages.
    """
    if missing := plan.unavailable(job.spec.stages, deps.enabled_stages):
        names = ", ".join(stage.value for stage in missing)
        raise InputError(code="stage_unavailable", detail=f"not offered here: {names}")
    outcomes: list[StageOutcome] = []
    wav: bytes | None = None
    with (
        structlog.contextvars.bound_contextvars(job_id=job.id),
        acquire_audio(
            job.audio, store=deps.inputs, media=deps.media, deadline=deadline
        ) as acquired,
    ):
        for stage in plan.ordered(job.spec.stages):
            remaining(deadline)
            started = time.monotonic()
            with structlog.contextvars.bound_contextvars(stage=stage.value):
                outcome, produced = _run_stage(stage, acquired)
            wav = produced if stage is StageName.AUDIO else wav
            seconds = time.monotonic() - started
            outcomes.append(StageOutcome(stage=stage, outcome=outcome, seconds=seconds))
    return Analysis(
        job_id=job.id,
        media=None if acquired is None else acquired.media,
        outcomes=tuple(outcomes),
        audio_wav=wav,
    )
