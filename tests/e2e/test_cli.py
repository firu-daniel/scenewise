import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _cli(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # why: this interpreter, fixed argv
        [sys.executable, "-m", "scenewise", *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
        timeout=60,
    )


def test_analyse_extracts_the_audio_track(inputs: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    run = _cli("analyse", str(inputs / "clip.mp4"), "--out", str(out))
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["status"] == "succeeded"
    assert result["stages"]["audio"]["status"] == "succeeded"
    assert result["stages"]["audio"]["uri"] == (out / "audio.wav").resolve().as_uri()
    with wave.open(str(out / "audio.wav")) as track:
        assert (track.getframerate(), track.getnchannels(), track.getsampwidth()) == (
            16_000,
            1,
            2,
        )
        assert track.getnframes() == pytest.approx(32_000, abs=1_600)


def test_analyse_video_without_audio(inputs: Path, tmp_path: Path) -> None:
    run = _cli("analyse", str(inputs / "silent.mp4"), "--out", str(tmp_path / "o"))
    assert run.returncode == 0, run.stderr
    audio = json.loads(run.stdout)["stages"]["audio"]
    assert (audio["status"], audio["reason"]) == ("skipped", "no_audio_stream")
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (["broken.mp4"], "corrupt_media"),
        (["clip.mp4", "--stage", "captions"], "stage_unavailable"),
    ],
)
def test_analyse_failures(
    inputs: Path, tmp_path: Path, args: list[str], code: str
) -> None:
    first, *rest = args
    run = _cli("analyse", str(inputs / first), "--out", str(tmp_path), *rest)
    assert run.returncode == 1
    assert f"scenewise: {code}" in run.stderr


def test_missing_ffmpeg_is_a_configuration_error(inputs: Path, tmp_path: Path) -> None:
    env = {"SCENEWISE_MEDIA__FFMPEG": "/nonexistent/ffmpeg"}
    run = _cli("analyse", str(inputs / "clip.mp4"), "--out", str(tmp_path), env=env)
    assert run.returncode == 2
    assert "ffmpeg_unavailable" in run.stderr


def test_invalid_settings_are_a_configuration_error(inputs: Path) -> None:
    env = {"SCENEWISE_SERVICE__ATTEMPT_BUDGET_S": "1790"}
    run = _cli("analyse", str(inputs / "clip.mp4"), "--out", "x", env=env)
    assert run.returncode == 2
    assert "invalid settings: service" in run.stderr


def test_version() -> None:
    run = _cli("--version")
    assert run.returncode == 0
    assert run.stdout.strip() == "0.1.0"
