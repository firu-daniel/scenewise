import pytest

from tests.contract.mediatool_contract import MediaToolContract
from tests.fakes import FIXTURE_INFOS, FakeMediaTool


class TestFakeMediaTool(MediaToolContract):
    @pytest.fixture
    def media(self) -> FakeMediaTool:
        return FakeMediaTool(infos=FIXTURE_INFOS)
