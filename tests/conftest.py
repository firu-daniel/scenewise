"""Shared fixtures and the hypothesis ``nightly`` profile."""

import shutil
from pathlib import Path

import pytest
from hypothesis import settings

settings.register_profile(
    "nightly",
    parent=settings.get_profile("default"),
    derandomize=False,
    max_examples=1000,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def ffmpeg_binaries() -> tuple[str, str]:
    """The ffmpeg and ffprobe on PATH; CI installs them, and a skip fails CI."""
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    return ffmpeg, ffprobe


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """The committed media made by ``tests/fixtures/generate.sh``."""
    return FIXTURES
