import pytest

from tests.contract.blobstore_contract import BlobStoreContract
from tests.fakes import InMemoryBlobStore


class TestInMemoryBlobStore(BlobStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryBlobStore:
        return InMemoryBlobStore()

    @pytest.fixture
    def base(self) -> str:
        return "mem://bucket/job"

    @pytest.fixture
    def outside(self) -> str:
        return "gs://elsewhere/x"
