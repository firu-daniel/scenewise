"""``FfmpegMediaTool``: ffprobe and ffmpeg through ``subprocess`` (ARCHITECTURE.md §11).

Always an argv list, never a shell; always a timeout; inputs are local paths passed with
the ``file:`` protocol under ``-protocol_whitelist file,pipe``, so ffmpeg never fetches
anything itself. Exit codes and the stderr tail map to
``InputError(code="corrupt_media")``.
"""

import json
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

from scenewise.domain.errors import ConfigurationError, InputError, InternalError
from scenewise.domain.media import RGB24_BYTES_PER_PIXEL, Frame, MediaInfo
from scenewise.domain.time import Seconds
from scenewise.ports import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE

PROBE_TIMEOUT_S: Final = 60.0
_STDERR_TAIL: Final = 500
_FRAMES_PER_SEEK: Final = 1
_MIN_SIDE_PX: Final = 1
_VERSION: Final = re.compile(r"version n?(\d+)\.")
# Before every -i: ffmpeg may open only local files and pipes, and only through these
# demuxers. Without the format list, an input whose content is an HLS playlist makes
# the hls demuxer open other local files outside every store allow-list.
DEMUXERS: Final = "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mpegts,wav,mp3,aac,flac,ogg"
_PROTOCOLS: Final = ("-protocol_whitelist", "file,pipe", "-format_whitelist", DEMUXERS)
_INSTALL_HINT: Final = (
    "install ffmpeg (apt install ffmpeg, brew install ffmpeg) or set "
    "SCENEWISE_MEDIA__FFMPEG and SCENEWISE_MEDIA__FFPROBE"
)


def _file(path: Path) -> str:
    return f"file:{path.resolve()}"


def _run(argv: list[str], *, timeout: float) -> subprocess.CompletedProcess[bytes]:
    """The one place scenewise starts a process."""
    if timeout <= 0:
        raise InternalError(code="deadline_exceeded")
    try:
        return subprocess.run(  # noqa: S603  # why: argv list; binaries resolved by which()
            argv, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as e:
        detail = Path(argv[0]).name
        raise InternalError(code="deadline_exceeded", detail=detail) from e


def find_binaries(*, ffmpeg: str, ffprobe: str, min_major: int) -> tuple[str, str]:
    """Resolve both binaries and check ffmpeg's major version; start-up only.

    Returns the absolute paths. Raises ``ConfigurationError`` with an install hint.
    """
    found = (shutil.which(ffmpeg), shutil.which(ffprobe))
    if found[0] is None or found[1] is None:
        raise ConfigurationError(code="ffmpeg_unavailable", detail=_INSTALL_HINT)
    run = _run([found[0], "-hide_banner", "-version"], timeout=PROBE_TIMEOUT_S)
    match = _VERSION.search(run.stdout.decode(errors="replace"))
    if run.returncode != 0 or match is None:
        raise ConfigurationError(
            code="ffmpeg_unavailable", detail="cannot read ffmpeg's version"
        )
    if int(match.group(1)) < min_major:
        detail = f"ffmpeg {match.group(1)} is older than {min_major}; {_INSTALL_HINT}"
        raise ConfigurationError(code="ffmpeg_too_old", detail=detail)
    return found[0], found[1]


def scaled_size(width: int, height: int, max_side: int) -> tuple[int, int]:
    """Downscale so the longer side is at most ``max_side``; never upscale."""
    scale = min(1.0, max_side / max(width, height))
    return (
        max(_MIN_SIDE_PX, round(width * scale)),
        max(_MIN_SIDE_PX, round(height * scale)),
    )


def _media_info(doc: dict[str, Any]) -> MediaInfo:
    streams = doc.get("streams", [])
    video = [
        s
        for s in streams
        if s.get("codec_type") == "video"
        and not s.get("disposition", {}).get("attached_pic")
    ]
    if "duration" not in doc.get("format", {}):
        raise InputError(code="corrupt_media", detail="no duration")
    return MediaInfo(
        duration=Seconds(float(doc["format"]["duration"])),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        has_video=bool(video),
        width=int(video[0]["width"]) if video else None,
        height=int(video[0]["height"]) if video else None,
    )


class FfmpegMediaTool:
    """``MediaTool`` over the system ffmpeg and ffprobe."""

    def __init__(self, *, ffmpeg: str, ffprobe: str) -> None:
        """Use the binaries ``find_binaries`` resolved."""
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe

    @staticmethod
    def _media(argv: list[str], *, timeout: float) -> bytes:
        run = _run(argv, timeout=timeout)
        if run.returncode != 0:
            tail = run.stderr.decode(errors="replace")[-_STDERR_TAIL:].strip()
            raise InputError(code="corrupt_media", detail=tail)
        return run.stdout

    def probe(self, path: Path) -> MediaInfo:
        """Describe the media with ``ffprobe -show_format -show_streams``."""
        argv = [self._ffprobe, "-v", "error", *_PROTOCOLS, "-print_format", "json"]
        argv += ["-show_format", "-show_streams", _file(path)]
        out = self._media(argv, timeout=PROBE_TIMEOUT_S)
        try:
            return _media_info(json.loads(out))
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            raise InputError(code="corrupt_media", detail="unreadable probe") from e

    @contextmanager
    def audio_track(self, parts: Sequence[Path], *, deadline: float) -> Iterator[Path]:
        """Concatenate ``parts`` byte-wise and extract one 16 kHz mono s16 WAV."""
        with tempfile.TemporaryDirectory(prefix="scenewise-audio-") as tmp:
            source = parts[0]
            if len(parts) > 1:
                source = Path(tmp) / "joined"
                with source.open("wb") as joined:
                    for part in parts:
                        joined.write(part.read_bytes())
            track = Path(tmp) / "track.wav"
            argv = [self._ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
            argv += [*_PROTOCOLS, "-i", _file(source), "-map", "0:a:0", "-vn"]
            argv += ["-ac", str(AUDIO_CHANNELS), "-ar", str(AUDIO_SAMPLE_RATE)]
            argv += ["-c:a", "pcm_s16le"]
            argv += ["-map_metadata", "-1", "-fflags", "+bitexact", "-f", "wav"]
            argv += ["-y", _file(track)]
            self._media(argv, timeout=deadline - time.monotonic())
            yield track

    def video_frames(
        self,
        path: Path,
        times: Sequence[Seconds],
        *,
        max_side: int,
        deadline: float,
    ) -> Iterator[Frame]:
        """Decode one RGB24 frame per time, downscaled at decode."""
        info = self.probe(path)
        if info.width is None or info.height is None:
            raise InputError(code="corrupt_media", detail="no video stream")
        width, height = scaled_size(info.width, info.height, max_side)
        size = width * height * RGB24_BYTES_PER_PIXEL
        for t in times:
            argv = [self._ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
            argv += ["-ss", f"{t:.3f}", *_PROTOCOLS, "-i", _file(path)]
            argv += ["-frames:v", str(_FRAMES_PER_SEEK)]
            argv += ["-vf", f"scale={width}:{height}"]
            argv += ["-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
            rgb = self._media(argv, timeout=deadline - time.monotonic())
            if len(rgb) != size:
                raise InputError(code="corrupt_media", detail=f"no frame at {t:.3f} s")
            yield Frame(timestamp=t, width=width, height=height, rgb=rgb)
