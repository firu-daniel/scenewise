"""``PillowImageReader``: still images and sprite tiles through Pillow (D3)."""

from collections.abc import Sequence
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from scenewise.domain.errors import InputError
from scenewise.domain.media import Frame, Tile


class PillowImageReader:
    """``ImageReader`` over Pillow."""

    def read(self, path: Path, tiles: Sequence[Tile], *, max_side: int) -> list[Frame]:
        """Cut each tile out of the image and downscale it to ``max_side``."""
        try:
            with Image.open(path) as image:
                rgb = image.convert("RGB")
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
            raise InputError(code="corrupt_media", detail="unreadable image") from e
        frames: list[Frame] = []
        for tile in tiles:
            part = rgb
            if tile.rect is not None:
                r = tile.rect
                if r.x + r.width > rgb.width or r.y + r.height > rgb.height:
                    raise InputError(
                        code="invalid_sprite_grid", detail="tile outside the image"
                    )
                part = rgb.crop((r.x, r.y, r.x + r.width, r.y + r.height))
            part = part.copy() if part is rgb else part
            part.thumbnail((max_side, max_side))
            frames.append(
                Frame(
                    timestamp=tile.timestamp,
                    width=part.width,
                    height=part.height,
                    rgb=part.tobytes(),
                )
            )
        return frames
