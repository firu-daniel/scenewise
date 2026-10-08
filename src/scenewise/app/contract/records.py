"""The stored form of the job record, ``status.json``."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from scenewise.domain.jobs import JOB_ID_PATTERN


class JobRecordV1(BaseModel):
    """One job's durable record; written only under compare-and-swap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    scenewise_version: str
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    state: Literal["running", "succeeded", "partial", "failed"]
    attempt: int = Field(ge=1)
    lease_until: float
    request_digest: str
    error_code: str | None
    result_uri: str | None
    updated_at: float
    external_ref: dict[str, str] | None
