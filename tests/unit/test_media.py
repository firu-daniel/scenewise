import pytest

from scenewise.domain.inputs import AudioSegments
from scenewise.domain.media import Frame, MediaInfo, Rect, SpriteGrid, Tile
from scenewise.domain.time import Seconds


def test_media_info_valid() -> None:
    info = MediaInfo(duration=Seconds(2), has_audio=True, has_video=False)
    assert info.width is None


@pytest.mark.parametrize(
    ("duration", "width", "height"), [(-1.0, None, None), (1.0, 10, None)]
)
def test_media_info_rejects(
    duration: float, width: int | None, height: int | None
) -> None:
    with pytest.raises(ValueError, match=r"duration|width"):
        MediaInfo(
            duration=Seconds(duration),
            has_audio=False,
            has_video=True,
            width=width,
            height=height,
        )


def test_rect_and_tile() -> None:
    tile = Tile(timestamp=Seconds(1), rect=Rect(x=0, y=0, width=2, height=3))
    assert tile.rect is not None
    assert tile.rect.height == 3


@pytest.mark.parametrize(("x", "width"), [(-1, 1), (0, 0)])
def test_rect_rejects(x: int, width: int) -> None:
    with pytest.raises(ValueError, match=r"origin|width"):
        Rect(x=x, y=0, width=width, height=1)


def test_frame_checks_buffer_size() -> None:
    assert Frame(timestamp=Seconds(0), width=2, height=1, rgb=bytes(6)).width == 2
    with pytest.raises(ValueError, match="expected 6"):
        Frame(timestamp=Seconds(0), width=2, height=1, rgb=bytes(5))


def test_sprite_grid_rejects_empty() -> None:
    assert SpriteGrid(columns=2, rows=2, tile_width=8, tile_height=8).rows == 2
    with pytest.raises(ValueError, match="rows"):
        SpriteGrid(columns=2, rows=0, tile_width=8, tile_height=8)


def test_audio_segments_need_exactly_one_list() -> None:
    ok = AudioSegments(
        container="fmp4", init_uri="i", segment_uris=("a",), list_uri=None
    )
    assert ok.segment_uris == ("a",)
    with pytest.raises(ValueError, match="exactly one"):
        AudioSegments(container="fmp4", init_uri=None, segment_uris=None, list_uri=None)
