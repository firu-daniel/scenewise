"""Probed media facts, frames and image tiles."""

from dataclasses import dataclass
from typing import Final

from scenewise.domain.time import Seconds

RGB24_BYTES_PER_PIXEL: Final = 3


def _check_positive(**values: int) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be positive, got {value}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaInfo:
    """What ffprobe found in one media file."""

    duration: Seconds
    has_audio: bool
    has_video: bool
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        """Reject a negative duration and half-known dimensions."""
        if self.duration < 0:
            msg = f"duration must not be negative, got {self.duration}"
            raise ValueError(msg)
        if (self.width is None) != (self.height is None):
            msg = "width and height are either both known or both unknown"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class Rect:
    """A rectangle in pixels; the origin is the top-left corner."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject negative origins and empty rectangles."""
        if self.x < 0 or self.y < 0:
            msg = f"origin must not be negative, got ({self.x}, {self.y})"
            raise ValueError(msg)
        _check_positive(width=self.width, height=self.height)


@dataclass(frozen=True, slots=True, kw_only=True)
class Tile:
    """One timed region of an image; ``rect=None`` is the whole image."""

    timestamp: Seconds
    rect: Rect | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Frame:
    """A decoded frame: packed RGB24, row-major, ``len(rgb) == width * height * 3``."""

    timestamp: Seconds
    width: int
    height: int
    rgb: bytes

    def __post_init__(self) -> None:
        """Reject a pixel buffer that does not match the dimensions."""
        _check_positive(width=self.width, height=self.height)
        expected = self.width * self.height * RGB24_BYTES_PER_PIXEL
        if len(self.rgb) != expected:
            msg = f"rgb has {len(self.rgb)} bytes, expected {expected}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FrameRef:
    """A still image at a URI, shown at ``timestamp``."""

    uri: str
    timestamp: Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class SpriteGrid:
    """The layout of a sprite sheet."""

    columns: int
    rows: int
    tile_width: int
    tile_height: int

    def __post_init__(self) -> None:
        """Reject empty grids."""
        _check_positive(
            columns=self.columns,
            rows=self.rows,
            tile_width=self.tile_width,
            tile_height=self.tile_height,
        )
