"""``acquire_audio()``: an audio source becomes probed media and one WAV track."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from scenewise.domain.errors import UnsupportedMediaError
from scenewise.domain.inputs import (
    AudioFile,
    AudioManifest,
    AudioSegments,
    AudioSource,
    NoAudio,
)
from scenewise.domain.media import MediaInfo
from scenewise.ports import BlobStore, MediaTool


@dataclass(frozen=True, slots=True, kw_only=True)
class AcquiredAudio:
    """The probed input and, when it has an audio stream, its extracted track."""

    media: MediaInfo
    track: Path | None  # 16 kHz mono pcm_s16le WAV; valid inside the context


@contextmanager
def acquire_audio(
    source: AudioSource | None,
    *,
    store: BlobStore,
    media: MediaTool,
    deadline: float,
) -> Iterator[AcquiredAudio | None]:
    """Fetch the input through the store, probe it and extract the track once.

    ffmpeg only ever sees the local file the store materialised (ARCHITECTURE.md §11).
    Yields ``None`` when the request has no audio input.
    """
    match source:
        case AudioFile(uri=uri):
            with store.materialise(uri) as path:
                info = media.probe(path)
                if not info.has_audio:
                    yield AcquiredAudio(media=info, track=None)
                    return
                with media.audio_track([path], deadline=deadline) as track:
                    yield AcquiredAudio(media=info, track=track)
        case AudioSegments() | AudioManifest():
            detail = "segment lists and playlists arrive with roadmap item 1"
            raise UnsupportedMediaError(code="unsupported_media", detail=detail)
        case NoAudio() | None:
            yield None
        case _:
            assert_never(source)
