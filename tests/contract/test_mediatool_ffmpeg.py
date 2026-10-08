import time
from pathlib import Path

import pytest

from scenewise.adapters.media.ffmpeg import FfmpegMediaTool, find_binaries, scaled_size
from scenewise.domain.errors import ConfigurationError, InputError, InternalError
from scenewise.domain.time import Seconds
from tests.contract.mediatool_contract import MediaToolContract


@pytest.fixture
def ffmpeg_tool(ffmpeg_binaries: tuple[str, str]) -> FfmpegMediaTool:
    ffmpeg, ffprobe = find_binaries(
        ffmpeg=ffmpeg_binaries[0], ffprobe=ffmpeg_binaries[1], min_major=6
    )
    return FfmpegMediaTool(ffmpeg=ffmpeg, ffprobe=ffprobe)


class TestFfmpegMediaTool(MediaToolContract):
    @pytest.fixture
    def media(self, ffmpeg_tool: FfmpegMediaTool) -> FfmpegMediaTool:
        return ffmpeg_tool


def test_find_binaries_missing() -> None:
    with pytest.raises(ConfigurationError) as caught:
        find_binaries(ffmpeg="/nonexistent/ffmpeg", ffprobe="ffprobe", min_major=6)
    assert caught.value.code == "ffmpeg_unavailable"


def test_find_binaries_too_old(ffmpeg_binaries: tuple[str, str]) -> None:
    ffmpeg, ffprobe = ffmpeg_binaries
    with pytest.raises(ConfigurationError) as caught:
        find_binaries(ffmpeg=ffmpeg, ffprobe=ffprobe, min_major=999)
    assert caught.value.code == "ffmpeg_too_old"


def test_find_binaries_unreadable_version(ffmpeg_binaries: tuple[str, str]) -> None:
    # ffprobe answers -version with "ffprobe version …", ffmpeg's pattern still matches,
    # so use a binary that prints no version at all.
    with pytest.raises(ConfigurationError) as caught:
        find_binaries(ffmpeg="true", ffprobe=ffmpeg_binaries[1], min_major=6)
    assert caught.value.code == "ffmpeg_unavailable"


@pytest.mark.parametrize(
    ("size", "expected"),
    [((1920, 1080), (448, 252)), ((100, 50), (100, 50)), ((1, 5000), (1, 448))],
)
def test_scaled_size(size: tuple[int, int], expected: tuple[int, int]) -> None:
    assert scaled_size(*size, 448) == expected


def test_audio_track_concatenates_parts(
    ffmpeg_tool: FfmpegMediaTool, fixtures_dir: Path, tmp_path: Path
) -> None:
    data = (fixtures_dir / "tone.m4a").read_bytes()
    parts = [tmp_path / "part0", tmp_path / "part1"]
    parts[0].write_bytes(data[:1000])
    parts[1].write_bytes(data[1000:])
    with ffmpeg_tool.audio_track(parts, deadline=time.monotonic() + 60) as track:
        assert track.stat().st_size > 60_000  # ~2 s at 32 kB/s


def test_audio_track_of_a_file_without_audio(
    ffmpeg_tool: FfmpegMediaTool, fixtures_dir: Path
) -> None:
    with (
        pytest.raises(InputError) as caught,
        ffmpeg_tool.audio_track(
            [fixtures_dir / "silent.mp4"], deadline=time.monotonic() + 60
        ),
    ):
        pass
    assert caught.value.code == "corrupt_media"


@pytest.mark.parametrize("budget", [-1.0, 0.005])  # spent before / during the run
def test_timeout_is_deadline_exceeded(
    ffmpeg_tool: FfmpegMediaTool, fixtures_dir: Path, budget: float
) -> None:
    with (
        pytest.raises(InternalError) as caught,
        ffmpeg_tool.audio_track(
            [fixtures_dir / "tone.m4a"], deadline=time.monotonic() + budget
        ),
    ):
        pass
    assert caught.value.code == "deadline_exceeded"


def test_frame_past_the_end(ffmpeg_tool: FfmpegMediaTool, fixtures_dir: Path) -> None:
    frames = ffmpeg_tool.video_frames(
        fixtures_dir / "clip.mp4",
        [Seconds(30)],
        max_side=64,
        deadline=time.monotonic() + 60,
    )
    with pytest.raises(InputError, match="no frame"):
        next(frames)


def test_frames_of_audio_only(ffmpeg_tool: FfmpegMediaTool, fixtures_dir: Path) -> None:
    frames = ffmpeg_tool.video_frames(
        fixtures_dir / "tone.m4a",
        [Seconds(0)],
        max_side=64,
        deadline=time.monotonic() + 60,
    )
    with pytest.raises(InputError, match="no video stream"):
        next(frames)


@pytest.mark.parametrize(
    ("output", "detail"),
    [
        (b'{"format": {}}', "no duration"),
        (
            b'{"format": {"duration": "1"}, "streams": [{"codec_type": "video"}]}',
            "probe",
        ),
        (b"not json", "probe"),
        (b'{"format": {"duration": "n/a"}}', "probe"),
    ],
)
def test_unreadable_probe_output(
    monkeypatch: pytest.MonkeyPatch,
    ffmpeg_tool: FfmpegMediaTool,
    tmp_path: Path,
    output: bytes,
    detail: str,
) -> None:
    monkeypatch.setattr(
        FfmpegMediaTool, "_media", staticmethod(lambda *_, **__: output)
    )
    with pytest.raises(InputError, match=detail) as caught:
        ffmpeg_tool.probe(tmp_path / "x.mp4")
    assert caught.value.code == "corrupt_media"


@pytest.mark.parametrize("name", ["upload.m3u8", "upload.mp4"])
def test_a_playlist_cannot_reach_other_files(
    ffmpeg_tool: FfmpegMediaTool, fixtures_dir: Path, tmp_path: Path, name: str
) -> None:
    secret = tmp_path / "secret.m4a"
    secret.write_bytes((fixtures_dir / "tone.m4a").read_bytes())
    playlist = tmp_path / name
    playlist.write_text(
        "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2.0,\n"
        f"file:{secret}\n#EXT-X-ENDLIST\n",
        encoding="utf-8",
    )
    with pytest.raises(InputError) as caught:
        ffmpeg_tool.probe(playlist)
    assert caught.value.code == "corrupt_media"
    with (
        pytest.raises(InputError),
        ffmpeg_tool.audio_track([playlist], deadline=time.monotonic() + 60),
    ):
        pass
