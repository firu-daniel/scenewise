import math
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scenewise.domain.time import Seconds, TimeSpan, vtt_timestamp

times = st.floats(min_value=0, max_value=360_000, allow_nan=False)
VTT = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d)\.(\d{3})$")


def test_span_duration() -> None:
    assert TimeSpan(start=Seconds(1.5), end=Seconds(4.0)).duration == 2.5


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1.0, 1.0), (2.0, 1.0), (0.0, math.inf), (math.nan, 1.0)],
)
def test_span_rejects_invalid(start: float, end: float) -> None:
    with pytest.raises(ValueError, match=r"span|seconds"):
        TimeSpan(start=Seconds(start), end=Seconds(end))


@pytest.mark.parametrize(
    ("t", "text"),
    [
        (0.0, "00:00:00.000"),
        (1.0005, "00:00:01.000"),  # 1000.4999... ms in binary floating point
        (61.25, "00:01:01.250"),
        (3723.4567, "01:02:03.457"),
        (359_999.9996, "100:00:00.000"),
    ],
)
def test_vtt_timestamp_examples(t: float, text: str) -> None:
    assert vtt_timestamp(Seconds(t)) == text


def test_vtt_timestamp_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        vtt_timestamp(Seconds(-0.1))


def _parse(text: str) -> float:
    match = VTT.match(text)
    assert match is not None
    h, m, s, ms = (int(g) for g in match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


@given(times)
def test_vtt_timestamp_round_trips_to_the_millisecond(t: float) -> None:
    assert abs(_parse(vtt_timestamp(Seconds(t))) - t) <= 0.0005 + 1e-9


@given(times, times)
def test_vtt_timestamp_is_monotonic(a: float, b: float) -> None:
    lo, hi = sorted((a, b))
    assert _parse(vtt_timestamp(Seconds(lo))) <= _parse(vtt_timestamp(Seconds(hi)))
