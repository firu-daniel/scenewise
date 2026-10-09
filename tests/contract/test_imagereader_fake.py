import pytest

from tests.contract.imagereader_contract import ImageReaderContract
from tests.fakes import FakeImageReader


class TestFakeImageReader(ImageReaderContract):
    @pytest.fixture
    def reader(self) -> FakeImageReader:
        return FakeImageReader(width=160, height=120)
