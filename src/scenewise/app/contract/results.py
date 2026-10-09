"""Output documents: the result, the job status, problems and rejections (q1 §5).

Outputs are documented as "clients ignore unknown fields": later stages add fields,
never remove them, within ``schema_version`` "1".
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from scenewise.app.constants import SCHEMA_VERSION_V1, SchemaVersionV1

type StatusV1 = Literal["running", "retry_wait", "succeeded", "partial", "failed"]


class _Output(BaseModel):
    model_config = ConfigDict(frozen=True)


class ErrorInfoV1(_Output):
    """A job or stage error."""

    code: str
    category: Literal["input", "retryable", "internal"]
    retryable: bool
    message: str
    stage: str | None = None


class ProbedMediaV1(_Output):
    """What scenewise found in the media."""

    duration_s: float
    has_audio: bool
    has_video: bool


class StageStatusV1(_Output):
    """How one stage ended."""

    status: Literal["succeeded", "skipped", "failed"]
    reason: str | None = None
    error: ErrorInfoV1 | None = None


class AudioStageV1(StageStatusV1):
    """The audio stage: the normalised track, 16 kHz mono ``pcm_s16le`` WAV."""

    uri: str | None = None


class StageResultsV1(_Output):
    """One entry per requested stage."""

    audio: AudioStageV1 | None = None


class JobResultV1(_Output):
    """``result.json``, written under the attempt's artifact prefix."""

    schema_version: SchemaVersionV1 = SCHEMA_VERSION_V1
    scenewise_version: str
    job_id: str
    external_ref: dict[str, str]
    status: Literal["succeeded", "partial"]
    media: ProbedMediaV1 | None
    stages: StageResultsV1
    timings_ms: dict[str, int]
    attempt: int


class JobStatusV1(_Output):
    """The answer of ``POST /v1/jobs`` and ``GET /v1/jobs/{id}``."""

    schema_version: SchemaVersionV1 = SCHEMA_VERSION_V1
    scenewise_version: str
    job_id: str
    status: StatusV1
    attempt: int
    error_code: str | None
    result_uri: str | None
    updated_at: float
    external_ref: dict[str, str] | None


class ProblemV1(_Output):
    """An RFC 9457 problem with scenewise's extension members."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    category: Literal["input", "retryable", "internal", "configuration"]
    retryable: bool


class RejectionV1(_Output):
    """A delivery that was refused without writing a record (``job_id_conflict``)."""

    job_id: str
    outcome: Literal["rejected"] = "rejected"
    problem: ProblemV1
