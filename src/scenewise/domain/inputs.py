"""Where a job's audio and frames come from; wire names stay in ``app/contract``."""

from dataclasses import dataclass
from typing import Literal

from scenewise.domain.media import FrameRef, SpriteGrid
from scenewise.domain.time import Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioFile:
    """One video or audio file; ffmpeg probes it and extracts the audio."""

    uri: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioSegments:
    """Init plus ordered media segments, stitched into one track (roadmap item 1)."""

    container: Literal["fmp4", "mpegts"]
    init_uri: str | None
    segment_uris: tuple[str, ...] | None
    list_uri: str | None

    def __post_init__(self) -> None:
        """Exactly one of ``segment_uris`` and ``list_uri`` is given."""
        if (self.segment_uris is None) == (self.list_uri is None):
            msg = "give exactly one of segment_uris and list_uri"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioManifest:
    """An HLS playlist whose audio segments are stitched (roadmap item 1; D10)."""

    uri: str
    rendition: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class NoAudio:
    """The caller knows there is no audio track."""


type AudioSource = AudioFile | AudioSegments | AudioManifest | NoAudio


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoFrames:
    """Frames sampled from a video file every ``interval`` seconds."""

    uri: str
    interval: Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class TimedFrames:
    """Still images with their timestamps."""

    frames: tuple[FrameRef, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class IntervalFrames:
    """Numbered stills from a URI template, one every ``interval`` seconds."""

    uri_template: str
    count: int
    interval: Seconds
    start_offset: Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class SpriteSheets:
    """Sprite sheets cut into timed tiles."""

    sheets: tuple[str, ...]
    grid: SpriteGrid
    interval: Seconds
    start_offset: Seconds
    count: int | None


type VisualSource = VideoFrames | TimedFrames | IntervalFrames | SpriteSheets
