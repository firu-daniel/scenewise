"""Time on the presentation timeline of the output media, in float seconds."""

import math
from dataclasses import dataclass
from typing import Final, NewType

Seconds = NewType("Seconds", float)

MS_PER_SECOND: Final = 1_000
_MS_PER_MINUTE: Final = 60_000
_MS_PER_HOUR: Final = 3_600_000


def _check_time(t: float, name: str) -> None:
    if not (math.isfinite(t) and t >= 0):
        msg = f"{name} must be a finite, non-negative number of seconds, got {t!r}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeSpan:
    """A span ``[start, end]`` of the timeline, with ``0 <= start <= end``."""

    start: Seconds
    end: Seconds

    def __post_init__(self) -> None:
        """Reject negative, non-finite or reversed spans."""
        _check_time(self.start, "start")
        _check_time(self.end, "end")
        if self.start > self.end:
            msg = f"span starts after it ends: {self.start} > {self.end}"
            raise ValueError(msg)

    @property
    def duration(self) -> Seconds:
        """Length of the span."""
        return Seconds(self.end - self.start)


def vtt_timestamp(t: Seconds) -> str:
    """Format ``t`` as a WebVTT timestamp ``HH:MM:SS.mmm``.

    This is the one place where times are rounded to milliseconds.
    """
    _check_time(t, "timestamp")
    total = round(t * MS_PER_SECOND)
    hours, rest = divmod(total, _MS_PER_HOUR)
    minutes, rest = divmod(rest, _MS_PER_MINUTE)
    seconds, millis = divmod(rest, MS_PER_SECOND)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
