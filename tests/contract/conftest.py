"""Fixtures shared by the contract tests."""

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def image(tmp_path: Path) -> Path:
    """A 160x120 picture for the ``ImageReader`` contract."""
    path = tmp_path / "frame.png"
    Image.new("RGB", (160, 120), (200, 30, 30)).save(path)
    return path
