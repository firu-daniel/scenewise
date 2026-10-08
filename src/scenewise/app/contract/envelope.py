"""The lenient envelope, parsed before anything else so a record can be keyed."""

import hashlib
import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError

from scenewise.domain.jobs import JobId, job_id


@dataclass(frozen=True, slots=True, kw_only=True)
class Envelope:
    """The part of a request body that is read before validation."""

    job_id: JobId
    schema_version: str | None
    external_ref: tuple[tuple[str, str], ...] | None  # None: absent or not str -> str
    request_digest: str


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    schema_version: object = None
    external_ref: object = None


class _ExternalRef(BaseModel):
    model_config = ConfigDict(strict=True)

    ref: dict[str, str]


def request_digest(document: object) -> str:
    """The sha256 of the canonical JSON of a parsed request body."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _external_ref(value: object) -> tuple[tuple[str, str], ...] | None:
    try:
        ref = _ExternalRef.model_validate({"ref": value}).ref
    except ValidationError:
        return None
    return tuple(sorted(ref.items()))


def parse(raw: bytes) -> Envelope | None:
    """Read ``job_id``, ``schema_version`` and ``external_ref``; ``None`` if unkeyable.

    Only a body that is not a JSON object, or has no valid ``job_id``, gives ``None``;
    everything else is checked later, inside the claim.
    """
    try:
        document = json.loads(raw)
        envelope = _Envelope.model_validate(document)
        key = job_id(envelope.job_id)
    except (ValueError, ValidationError):  # JSONDecodeError is a ValueError
        return None
    version = envelope.schema_version
    return Envelope(
        job_id=key,
        schema_version=version if isinstance(version, str) else None,
        external_ref=_external_ref(envelope.external_ref),
        request_digest=request_digest(document),
    )
