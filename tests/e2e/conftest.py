"""End-to-end fixtures: a copy of the media in a temporary input directory."""

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def inputs(
    tmp_path: Path, fixtures_dir: Path, ffmpeg_binaries: tuple[str, str]
) -> Path:
    """A directory holding the fixture media (needs ffmpeg, like every e2e test)."""
    del ffmpeg_binaries
    directory = tmp_path / "inputs"
    directory.mkdir()
    for name in ("clip.mp4", "silent.mp4", "tone.m4a"):
        shutil.copy(fixtures_dir / name, directory / name)
    (directory / "broken.mp4").write_bytes(b"\x00not media" * 50)
    return directory
