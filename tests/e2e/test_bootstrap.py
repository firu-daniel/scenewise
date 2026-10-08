from pathlib import Path

import pytest

from scenewise.domain.errors import ConfigurationError
from scenewise.domain.jobs import StageName
from scenewise.service.bootstrap import build_dependencies
from scenewise.service.config import ServiceSettings, Settings

pytestmark = pytest.mark.e2e


@pytest.mark.usefixtures("ffmpeg_binaries")
def test_builds_the_skeleton_dependencies(tmp_path: Path) -> None:
    settings = Settings(service=ServiceSettings(state_prefix=tmp_path.as_uri()))
    assert build_dependencies(settings).enabled_stages == {StageName.AUDIO}


@pytest.mark.usefixtures("ffmpeg_binaries")
@pytest.mark.parametrize(
    ("service", "code"),
    [
        (ServiceSettings(state_prefix="gs://bucket/state"), "store_unavailable"),
        (
            ServiceSettings(required_stages=frozenset({StageName.CAPTIONS})),
            "stage_unavailable",
        ),
    ],
)
def test_configuration_errors(service: ServiceSettings, code: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        build_dependencies(Settings(service=service))
    assert caught.value.code == code
