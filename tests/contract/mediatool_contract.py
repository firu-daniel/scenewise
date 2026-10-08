"""The ``MediaTool`` contract (ports.MediaTool docstring), shared by every tool."""

import time
import wave
from pathlib import Path

import pytest

from scenewise.domain.errors import InputError, InternalError
from scenewise.domain.time import Seconds
from scenewise.ports import MediaTool


def _later() -> float:
    return time.monotonic() + 60


class MediaToolContract:
    """Subclass and provide the ``media`` fixture; media comes from ``fixtures_dir``."""

    def test_probe_video_with_audio(self, media: MediaTool, fixtures_dir: Path) -> None:
        info = media.probe(fixtures_dir / "clip.mp4")
        assert (info.has_audio, info.has_video) == (True, True)
        assert (info.width, info.height) == (160, 120)
        assert info.duration == pytest.approx(2.0, abs=0.1)

    def test_probe_video_without_audio(
        self, media: MediaTool, fixtures_dir: Path
    ) -> None:
        info = media.probe(fixtures_dir / "silent.mp4")
        assert (info.has_audio, info.has_video) == (False, True)

    def test_probe_audio_only(self, media: MediaTool, fixtures_dir: Path) -> None:
        info = media.probe(fixtures_dir / "tone.m4a")
        assert (info.has_audio, info.has_video, info.width) == (True, False, None)

    def test_probe_garbage(self, media: MediaTool, tmp_path: Path) -> None:
        garbage = tmp_path / "garbage.mp4"
        garbage.write_bytes(b"\x00\x01not media" * 100)
        with pytest.raises(InputError) as caught:
            media.probe(garbage)
        assert caught.value.code == "corrupt_media"

    def test_audio_track_is_16k_mono_s16(
        self, media: MediaTool, fixtures_dir: Path
    ) -> None:
        with media.audio_track([fixtures_dir / "tone.m4a"], deadline=_later()) as track:
            with wave.open(str(track)) as wav:
                assert wav.getframerate() == 16_000
                assert wav.getnchannels() == 1
                assert wav.getsampwidth() == 2  # pcm_s16le
                seconds = wav.getnframes() / wav.getframerate()
            assert seconds == pytest.approx(2.0, abs=0.1)
        assert not track.exists()

    def test_audio_track_after_the_deadline(
        self, media: MediaTool, fixtures_dir: Path
    ) -> None:
        past = time.monotonic() - 1
        with (
            pytest.raises(InternalError) as caught,
            media.audio_track([fixtures_dir / "tone.m4a"], deadline=past),
        ):
            pass
        assert caught.value.code == "deadline_exceeded"

    def test_video_frames(self, media: MediaTool, fixtures_dir: Path) -> None:
        times = [Seconds(0.0), Seconds(0.5), Seconds(1.5)]
        frames = list(
            media.video_frames(
                fixtures_dir / "clip.mp4", times, max_side=80, deadline=_later()
            )
        )
        assert [f.timestamp for f in frames] == times
        assert {(f.width, f.height) for f in frames} == {(80, 60)}

    def test_video_frames_never_upscale(
        self, media: MediaTool, fixtures_dir: Path
    ) -> None:
        (frame,) = media.video_frames(
            fixtures_dir / "clip.mp4", [Seconds(1)], max_side=1000, deadline=_later()
        )
        assert (frame.width, frame.height) == (160, 120)
