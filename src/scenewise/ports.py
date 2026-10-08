"""Every seam to I/O and models, on one screen (ARCHITECTURE.md §4).

Ports are synchronous: model work blocks, and each job runs in one worker thread. Each
docstring is the port's behavioural contract, which one shared contract suite per port
checks against every implementation.
"""

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scenewise.domain.jobs import Callback
from scenewise.domain.labels import LabelScores
from scenewise.domain.media import Frame, MediaInfo, Tile
from scenewise.domain.results import (
    FrameModeration,
    Generation,
    RecognizedSegment,
    TextRequest,
)
from scenewise.domain.speech import LanguageGuess, SpeechProbabilities
from scenewise.domain.time import Seconds, TimeSpan


class WriteConflictError(Exception):
    """A create-if-absent or generation precondition failed."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Blob:
    """An object's bytes and its store-assigned compare-and-swap token."""

    data: bytes
    generation: int


class BlobStore(Protocol):
    """Objects addressed by URI (local files | GCS | https read-only).

    Contract: ``read`` of an absent object is ``None``. ``write`` returns the new
    generation, always > 0; ``if_generation=0`` writes only if the object is absent,
    any other value only if it is the current generation, else ``WriteConflictError``.
    A URI outside the store's allow-list is ``InputError("uri_not_allowed")``; a
    missing input in ``materialise`` is ``InputError("input_unavailable")``.
    """

    def materialise(self, uri: str) -> AbstractContextManager[Path]:
        """Yield a local file with the object's bytes, valid inside the context."""
        ...

    def read(self, uri: str) -> Blob | None:
        """Return the object, or ``None`` if it is absent."""
        ...

    def write(
        self,
        uri: str,
        data: bytes,
        *,
        content_type: str,
        if_generation: int | None = None,
    ) -> int:
        """Write the object, optionally under a generation precondition."""
        ...


class MediaTool(Protocol):
    """ffmpeg and ffprobe; never given a URL, only local files.

    Contract: ``audio_track`` concatenates ``parts`` and extracts ONE 16 kHz mono
    ``pcm_s16le`` WAV, valid inside the context. ``video_frames`` yields one frame per
    time, in order, with the longer side <= ``max_side``. Undecodable input is
    ``InputError("corrupt_media")``; running out of time is
    ``InternalError("deadline_exceeded")``. ``deadline`` is a ``time.monotonic()``
    value.
    """

    def probe(self, path: Path) -> MediaInfo:
        """Describe the media in ``path``."""
        ...

    def audio_track(
        self, parts: Sequence[Path], *, deadline: float
    ) -> AbstractContextManager[Path]:
        """Yield the extracted WAV track of the concatenated parts."""
        ...

    def video_frames(
        self,
        path: Path,
        times: Sequence[Seconds],
        *,
        max_side: int,
        deadline: float,
    ) -> Iterator[Frame]:
        """Decode the frames shown at ``times``."""
        ...


class ImageReader(Protocol):
    """Still images (Pillow).

    Contract: one RGB frame per tile, in order, longer side <= ``max_side``.
    """

    def read(self, path: Path, tiles: Sequence[Tile], *, max_side: int) -> list[Frame]:
        """Cut ``tiles`` out of the image in ``path``."""
        ...


class VoiceActivityDetector(Protocol):
    """Silero VAD (roadmap item 1)."""

    def speech_probabilities(self, track: Path) -> SpeechProbabilities:
        """P(speech) for every hop of the whole track, from t = 0."""
        ...


class LanguageIdentifier(Protocol):
    """faster-whisper ``tiny`` language ID (roadmap item 1)."""

    def identify(
        self, track: Path, windows: Sequence[Sequence[TimeSpan]]
    ) -> list[LanguageGuess]:
        """One argmax guess per window, in order; gaps never reach the model."""
        ...


class SpeechRecognizer(Protocol):
    """Parakeet on sherpa-onnx or onnx-asr, or faster-whisper (roadmap item 1)."""

    def transcribe(
        self, track: Path, segments: Sequence[TimeSpan], *, language: str
    ) -> list[RecognizedSegment]:
        """One segment per span, in order; token times absolute and non-decreasing."""
        ...


class TextGenerator(Protocol):
    """Claude Haiku, an OpenAI-compatible server, or a fallback pair (item 2)."""

    def generate(self, request: TextRequest) -> Generation:
        """Answer one request; a refusal is ``refused=True``, never an exception."""
        ...


class ImageModerator(Protocol):
    """The tier-1 moderation classifier (roadmap item 3)."""

    def score(self, frames: Sequence[Frame]) -> list[FrameModeration]:
        """One result per frame, in order; scores in ``[0, 1]``."""
        ...


class ZeroShotLabeller(Protocol):
    """SigLIP 2 through open_clip (roadmap items 3 and 4)."""

    def score(
        self,
        frames: Sequence[Frame],
        prompts: Sequence[Sequence[str]],
        *,
        embeddings: bool = False,
    ) -> LabelScores:
        """Cosines of every frame against every label's prompts."""
        ...


class Notifier(Protocol):
    """HTTP callbacks; delivery logs and swallows a failure."""

    def notify(self, body: bytes, *, callback: Callback, idempotency_key: str) -> None:
        """Send the pre-serialised ``body`` unchanged; raise ``RetryableError``."""
        ...
