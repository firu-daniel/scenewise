"""The error categories (ARCHITECTURE.md §9).

Leaf classes exist only where the HTTP mapping differs. The ``code`` is what a caller
acts on; ``detail`` is human-readable and never contains transcript text or signed URIs.
"""

from typing import ClassVar, Literal

type Category = Literal["input", "retryable", "internal", "configuration"]


class ScenewiseError(Exception):
    """Base of every error scenewise raises on purpose."""

    category: ClassVar[Category] = "internal"

    def __init__(self, code: str = "internal", detail: str = "") -> None:
        """Keep the machine-readable ``code`` and a human-readable ``detail``."""
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail

    @property
    def retryable(self) -> bool:
        """Whether a later attempt may succeed."""
        return self.category == "retryable"


class InputError(ScenewiseError):
    """The caller must change the request; never retried.

    Codes: invalid_request, uri_not_allowed, input_unavailable, corrupt_media,
    invalid_sprite_grid, input_encrypted, stage_unavailable, job_id_conflict.
    """

    category: ClassVar[Category] = "input"


class MediaTooLargeError(InputError):
    """413 class: media_too_large, exceeds_push_budget, request_too_large."""


class UnsupportedMediaError(InputError):
    """415 class: unsupported_media, manifest_unsupported."""


class RetryableError(ScenewiseError):
    """Transient: backend_unavailable, storage_unavailable, job_in_progress."""

    category: ClassVar[Category] = "retryable"


class CapacityError(RetryableError):
    """429, from admission only."""


class InternalError(ScenewiseError):
    """Ours; a retry will not help.

    Codes: model_output_invalid, model_refused, resource_exhausted, deadline_exceeded,
    invariant_violation, attempts_exhausted, unexpected.
    """

    category: ClassVar[Category] = "internal"


class ConfigurationError(ScenewiseError):
    """Start-up only; the process exits non-zero."""

    category: ClassVar[Category] = "configuration"
