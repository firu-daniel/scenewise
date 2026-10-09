"""``JobRequestV1``: the request body of ``POST /v1/jobs`` (q1 §4).

Inputs are ``extra="forbid"``, so a typo or version skew fails loudly. Only the inputs
the skeleton can run are here: an audio file or no audio. Segment lists and HLS
playlists (item 1), visual inputs (items 3-4), stage options and HTTP callbacks join
this module with the features that use them.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from scenewise.app.constants import SchemaVersionV1
from scenewise.domain.jobs import JOB_ID_PATTERN

type StageNameV1 = Literal[
    "audio", "captions", "summary", "chapters", "moderation", "labels"
]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AudioFileV1(_Input):
    """One video or audio file."""

    kind: Literal["file"]
    uri: str = Field(min_length=1)
    mime: str | None = None


class NoAudioV1(_Input):
    """The caller knows there is no audio track."""

    kind: Literal["none"]
    reason: Literal["source_has_no_audio"] = "source_has_no_audio"


type AudioInputV1 = Annotated[AudioFileV1 | NoAudioV1, Field(discriminator="kind")]


class NoNotifyV1(_Input):
    """The caller reads the job record instead of receiving a callback."""

    kind: Literal["none"]


class ArtifactSinkV1(_Input):
    """Where artifacts go; ``None`` is ``{state_prefix}/{job_id}``."""

    uri_prefix: str | None = Field(default=None, min_length=1)


class DeliveryV1(_Input):
    """How results reach the caller."""

    notify: NoNotifyV1 = NoNotifyV1(kind="none")
    artifacts: ArtifactSinkV1 = ArtifactSinkV1()


class JobRequestV1(_Input):
    """One job."""

    schema_version: SchemaVersionV1
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    supersedes: str | None = None
    external_ref: dict[str, str] = Field(default_factory=dict)
    stages: list[StageNameV1] = Field(min_length=1)
    audio: AudioInputV1 | None = None
    delivery: DeliveryV1
