"""In-memory fakes of the ports the skeleton uses; each passes its contract suite."""

import io
import tempfile
import time
import wave
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from scenewise.app.deps import Dependencies
from scenewise.domain.errors import InputError, InternalError
from scenewise.domain.jobs import StageName
from scenewise.domain.media import RGB24_BYTES_PER_PIXEL, Frame, MediaInfo, Tile
from scenewise.domain.time import Seconds
from scenewise.ports import Blob, WriteConflictError

SAMPLE_RATE = 16_000


@dataclass(frozen=True, slots=True)
class _Object:
    data: bytes
    generation: int
    content_type: str


class InMemoryBlobStore:
    """A ``BlobStore`` in a dict; only URIs under ``prefix`` are allowed."""

    def __init__(self, *, prefix: str = "mem://") -> None:
        self.prefix = prefix
        self.objects: dict[str, _Object] = {}

    def _check(self, uri: str) -> None:
        if not uri.startswith(self.prefix):
            raise InputError(code="uri_not_allowed", detail="outside the store")

    @contextmanager
    def materialise(self, uri: str) -> Iterator[Path]:
        self._check(uri)
        found = self.objects.get(uri)
        if found is None:
            raise InputError(code="input_unavailable", detail="no such object")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / uri.rsplit("/", 1)[-1]
            path.write_bytes(found.data)
            yield path

    def read(self, uri: str) -> Blob | None:
        self._check(uri)
        found = self.objects.get(uri)
        return (
            None
            if found is None
            else Blob(data=found.data, generation=found.generation)
        )

    def write(
        self,
        uri: str,
        data: bytes,
        *,
        content_type: str,
        if_generation: int | None = None,
    ) -> int:
        self._check(uri)
        found = self.objects.get(uri)
        current = 0 if found is None else found.generation
        if if_generation is not None and if_generation != current:
            raise WriteConflictError(uri)
        self.objects[uri] = _Object(data, current + 1, content_type)
        return current + 1


def wav_bytes(seconds: float) -> bytes:
    """A silent 16 kHz mono pcm_s16le WAV of ``seconds``."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(b"\0\0" * round(seconds * SAMPLE_RATE))
    return buffer.getvalue()


class FakeMediaTool:
    """A ``MediaTool`` that knows its media by file name, or fails with ``error``."""

    def __init__(
        self, *, infos: Mapping[str, MediaInfo], error: Exception | None = None
    ) -> None:
        self.infos = dict(infos)
        self.error = error

    def probe(self, path: Path) -> MediaInfo:
        if self.error is not None:
            raise self.error
        try:
            return self.infos[path.name]
        except KeyError as e:
            raise InputError(code="corrupt_media", detail=path.name) from e

    @contextmanager
    def audio_track(self, parts: Sequence[Path], *, deadline: float) -> Iterator[Path]:
        if deadline <= time.monotonic():
            raise InternalError(code="deadline_exceeded")
        infos = [self.probe(part) for part in parts]
        if not all(info.has_audio for info in infos):
            raise InputError(code="corrupt_media", detail="no audio stream")
        with tempfile.TemporaryDirectory() as tmp:
            track = Path(tmp) / "track.wav"
            track.write_bytes(wav_bytes(sum(info.duration for info in infos)))
            yield track

    def video_frames(
        self,
        path: Path,
        times: Sequence[Seconds],
        *,
        max_side: int,
        deadline: float,
    ) -> Iterator[Frame]:
        if deadline <= time.monotonic():
            raise InternalError(code="deadline_exceeded")
        info = self.probe(path)
        if info.width is None or info.height is None:
            raise InputError(code="corrupt_media", detail="no video stream")
        scale = min(1.0, max_side / max(info.width, info.height))
        width, height = round(info.width * scale), round(info.height * scale)
        for t in times:
            if t > info.duration:
                raise InputError(code="corrupt_media", detail="no frame")
            size = width * height * RGB24_BYTES_PER_PIXEL
            yield Frame(timestamp=t, width=width, height=height, rgb=b"\x80" * size)


class FakeImageReader:
    """An ``ImageReader`` that returns grey frames of each tile's size."""

    def __init__(self, *, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def read(self, path: Path, tiles: Sequence[Tile], *, max_side: int) -> list[Frame]:
        if not path.read_bytes().startswith(b"\x89PNG"):
            raise InputError(code="corrupt_media", detail="unreadable image")
        frames: list[Frame] = []
        for tile in tiles:
            w, h = (
                (self.width, self.height)
                if tile.rect is None
                else (tile.rect.width, tile.rect.height)
            )
            scale = min(1.0, max_side / max(w, h))
            w, h = max(1, round(w * scale)), max(1, round(h * scale))
            rgb = b"\x80" * (w * h * RGB24_BYTES_PER_PIXEL)
            frames.append(Frame(timestamp=tile.timestamp, width=w, height=h, rgb=rgb))
        return frames


CLIP = MediaInfo(
    duration=Seconds(2), has_audio=True, has_video=True, width=160, height=120
)
SILENT = MediaInfo(
    duration=Seconds(2), has_audio=False, has_video=True, width=160, height=120
)
TONE = MediaInfo(duration=Seconds(2), has_audio=True, has_video=False)
FIXTURE_INFOS = {"clip.mp4": CLIP, "silent.mp4": SILENT, "tone.m4a": TONE}


def fake_dependencies(
    *,
    store: InMemoryBlobStore | None = None,
    inputs: InMemoryBlobStore | None = None,
    media: FakeMediaTool | None = None,
    enabled: frozenset[StageName] = frozenset({StageName.AUDIO}),
) -> Dependencies:
    """Dependencies over fakes, with the fixture media known by name.

    Inputs come from ``store`` unless a separate ``inputs`` store is given.
    """
    store = store or InMemoryBlobStore()
    return Dependencies(
        store=store,
        inputs=inputs or store,
        media=media or FakeMediaTool(infos=FIXTURE_INFOS),
        images=FakeImageReader(width=160, height=120),
        enabled_stages=enabled,
    )
