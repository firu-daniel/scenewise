from pathlib import Path

import pytest

from scenewise.adapters.media.images import PillowImageReader
from scenewise.domain.errors import InputError
from scenewise.domain.media import Rect, Tile
from scenewise.domain.time import Seconds
from tests.contract.imagereader_contract import ImageReaderContract


class TestPillowImageReader(ImageReaderContract):
    @pytest.fixture
    def reader(self) -> PillowImageReader:
        return PillowImageReader()


def test_pillow_decodes_pixels(image: Path) -> None:
    (frame,) = PillowImageReader().read(image, [Tile(timestamp=Seconds(0))], max_side=4)
    assert frame.rgb[:3] == bytes((200, 30, 30))


def test_tile_outside_the_image(image: Path) -> None:
    tile = Tile(timestamp=Seconds(0), rect=Rect(x=100, y=0, width=100, height=10))
    with pytest.raises(InputError) as caught:
        PillowImageReader().read(image, [tile], max_side=10)
    assert caught.value.code == "invalid_sprite_grid"
