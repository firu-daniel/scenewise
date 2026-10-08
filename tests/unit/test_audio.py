import time
import wave

import pytest

from scenewise.app.audio import acquire_audio
from scenewise.domain.errors import UnsupportedMediaError
from scenewise.domain.inputs import (
    AudioFile,
    AudioManifest,
    AudioSegments,
    AudioSource,
    NoAudio,
)
from tests.fakes import CLIP, SILENT, FakeMediaTool, InMemoryBlobStore

FIXTURES = {"clip.mp4": CLIP, "silent.mp4": SILENT}


def _store() -> InMemoryBlobStore:
    store = InMemoryBlobStore()
    for name in FIXTURES:
        store.write(f"mem://in/{name}", b"media", content_type="video/mp4")
    return store


def _deadline() -> float:
    return time.monotonic() + 60


def test_file_with_audio_yields_one_track() -> None:
    media = FakeMediaTool(infos=FIXTURES)
    source = AudioFile(uri="mem://in/clip.mp4")
    with acquire_audio(
        source, store=_store(), media=media, deadline=_deadline()
    ) as acquired:
        assert acquired is not None
        assert acquired.media == CLIP
        assert acquired.track is not None
        with wave.open(str(acquired.track)) as track:
            assert (track.getframerate(), track.getnchannels()) == (16_000, 1)


def test_file_without_audio_stream_has_no_track() -> None:
    media = FakeMediaTool(infos=FIXTURES)
    source = AudioFile(uri="mem://in/silent.mp4")
    with acquire_audio(
        source, store=_store(), media=media, deadline=_deadline()
    ) as acquired:
        assert acquired is not None
        assert acquired.track is None


@pytest.mark.parametrize("source", [NoAudio(), None])
def test_no_audio_input(source: AudioSource | None) -> None:
    media = FakeMediaTool(infos=FIXTURES)
    with acquire_audio(
        source, store=_store(), media=media, deadline=_deadline()
    ) as acquired:
        assert acquired is None


@pytest.mark.parametrize(
    "source",
    [
        AudioSegments(
            container="fmp4", init_uri="i", segment_uris=("s",), list_uri=None
        ),
        AudioManifest(uri="mem://in/a.m3u8", rendition=None),
    ],
)
def test_segments_and_playlists_arrive_later(source: AudioSource) -> None:
    media = FakeMediaTool(infos=FIXTURES)
    with (
        pytest.raises(UnsupportedMediaError),
        acquire_audio(source, store=_store(), media=media, deadline=_deadline()),
    ):
        pass
