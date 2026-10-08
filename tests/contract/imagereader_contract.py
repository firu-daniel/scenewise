"""The ``ImageReader`` contract (ports.ImageReader docstring)."""

from pathlib import Path

import pytest

from scenewise.domain.errors import InputError
from scenewise.domain.media import Rect, Tile
from scenewise.domain.time import Seconds
from scenewise.ports import ImageReader


class ImageReaderContract:
    """Subclass and provide ``reader``; ``image`` is a 160x120 picture."""

    def test_one_frame_per_tile(self, reader: ImageReader, image: Path) -> None:
        tiles = [
            Tile(timestamp=Seconds(0)),
            Tile(timestamp=Seconds(1), rect=Rect(x=80, y=0, width=80, height=60)),
        ]
        frames = reader.read(image, tiles, max_side=1000)
        assert [f.timestamp for f in frames] == [Seconds(0), Seconds(1)]
        assert [(f.width, f.height) for f in frames] == [(160, 120), (80, 60)]

    def test_downscale(self, reader: ImageReader, image: Path) -> None:
        (frame,) = reader.read(image, [Tile(timestamp=Seconds(0))], max_side=40)
        assert (frame.width, frame.height) == (40, 30)

    def test_unreadable(self, reader: ImageReader, tmp_path: Path) -> None:
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(InputError):
            reader.read(bad, [Tile(timestamp=Seconds(0))], max_side=10)
