"""The error categories (ARCHITECTURE.md §9).

Leaf classes exist only where the HTTP mapping differs. The ``code`` is what a caller
acts on; ``detail`` is human-readable and never contains transcript text or signed URIs.

The codes are a closed vocabulary, one ``Literal`` per class: every constructor takes
only its own class's codes (``JobIdConflictError`` has exactly one and takes none), so
mypy rejects a misspelt code and a code raised through the wrong class. The
code strings reach the wire unchanged (``ErrorInfoV1.code``, the problem ``code``), so
renaming one is a wire-contract change.
"""

from typing import ClassVar, Literal

type Category = Literal["input", "retryable", "internal", "configuration"]

type InputCode = Literal[  # InputError itself; the leaves below have their own
    "invalid_request",
    "uri_not_allowed",
    "input_unavailable",
    "corrupt_media",
    "invalid_sprite_grid",
    "input_encrypted",
    "stage_unavailable",
]
type MediaTooLargeCode = Literal[
    "media_too_large", "exceeds_push_budget", "request_too_large"
]
type UnsupportedMediaCode = Literal["unsupported_media", "manifest_unsupported"]
type JobIdConflictCode = Literal["job_id_conflict"]
type JobNotFoundCode = Literal["job_not_found"]
type RetryableCode = Literal[
    "backend_unavailable", "storage_unavailable", "job_in_progress"
]
type CapacityCode = Literal["capacity_exceeded"]
type InternalCode = Literal[
    "internal",
    "model_output_invalid",
    "model_refused",
    "resource_exhausted",
    "deadline_exceeded",
    "invariant_violation",
    "attempts_exhausted",
    "unexpected",
]
type ConfigurationCode = Literal[
    "stage_unavailable", "store_unavailable", "ffmpeg_unavailable", "ffmpeg_too_old"
]
type ErrorCode = (
    InputCode
    | MediaTooLargeCode
    | UnsupportedMediaCode
    | JobIdConflictCode
    | JobNotFoundCode
    | RetryableCode
    | CapacityCode
    | InternalCode
    | ConfigurationCode
)


class ScenewiseError(Exception):
    """Base of every error scenewise raises on purpose; internal when raised bare."""

    category: ClassVar[Category] = "internal"

    def __init__(self, *, code: InternalCode = "internal", detail: str = "") -> None:
        """Keep the machine-readable ``code`` and a human-readable ``detail``."""
        self._init(code, detail)

    def _init(self, code: ErrorCode, detail: str) -> None:
        """The one initialiser; each class's ``__init__`` narrows ``code`` first."""
        Exception.__init__(self, f"{code}: {detail}" if detail else code)
        self.code: ErrorCode = code
        self.detail = detail

    @property
    def retryable(self) -> bool:
        """Whether a later attempt may succeed."""
        return self.category == "retryable"


class InputError(ScenewiseError):
    """The caller must change the request; never retried (codes: ``InputCode``)."""

    category: ClassVar[Category] = "input"

    def __init__(self, *, code: InputCode, detail: str = "") -> None:
        """An input error with one of the ``InputCode`` codes."""
        self._init(code, detail)


class MediaTooLargeError(InputError):
    """413 class (codes: ``MediaTooLargeCode``)."""

    def __init__(self, *, code: MediaTooLargeCode, detail: str = "") -> None:
        """A too-large input with one of the ``MediaTooLargeCode`` codes."""
        self._init(code, detail)


class UnsupportedMediaError(InputError):
    """415 class (codes: ``UnsupportedMediaCode``)."""

    def __init__(self, *, code: UnsupportedMediaCode, detail: str = "") -> None:
        """An unsupported input with one of the ``UnsupportedMediaCode`` codes."""
        self._init(code, detail)


class JobIdConflictError(InputError):
    """409 class: ``job_id_conflict``, a job id reused for a different request."""

    def __init__(self, *, detail: str = "") -> None:
        """The one ``job_id_conflict`` error."""
        self._init("job_id_conflict", detail)


class JobNotFoundError(InputError):
    """404 class: ``job_not_found``, no record exists for the job id."""

    def __init__(self, *, detail: str = "") -> None:
        """The one ``job_not_found`` error."""
        self._init("job_not_found", detail)


class RetryableError(ScenewiseError):
    """Transient; a later attempt may succeed (codes: ``RetryableCode``)."""

    category: ClassVar[Category] = "retryable"

    def __init__(self, *, code: RetryableCode, detail: str = "") -> None:
        """A transient error with one of the ``RetryableCode`` codes."""
        self._init(code, detail)


class CapacityError(RetryableError):
    """429, from admission only (codes: ``CapacityCode``)."""

    def __init__(self, *, code: CapacityCode, detail: str = "") -> None:
        """A full admission limiter: ``capacity_exceeded``."""
        self._init(code, detail)


class InternalError(ScenewiseError):
    """Ours; a retry will not help (codes: ``InternalCode``)."""

    category: ClassVar[Category] = "internal"

    def __init__(self, *, code: InternalCode, detail: str = "") -> None:
        """An internal error with one of the ``InternalCode`` codes."""
        self._init(code, detail)


class ConfigurationError(ScenewiseError):
    """Start-up only; the process exits non-zero (codes: ``ConfigurationCode``)."""

    category: ClassVar[Category] = "configuration"

    def __init__(self, *, code: ConfigurationCode, detail: str = "") -> None:
        """A start-up error with one of the ``ConfigurationCode`` codes."""
        self._init(code, detail)
