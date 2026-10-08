import threading
from pathlib import Path

import pytest

from scenewise.adapters.storage.local import LocalBlobStore
from scenewise.domain.errors import InputError, RetryableError
from scenewise.ports import WriteConflictError
from tests.contract.blobstore_contract import BlobStoreContract


class TestLocalBlobStore(BlobStoreContract):
    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalBlobStore:
        return LocalBlobStore(roots=[tmp_path / "root"])

    @pytest.fixture
    def base(self, tmp_path: Path) -> str:
        return (tmp_path / "root" / "job").as_uri()

    @pytest.fixture
    def outside(self, tmp_path: Path) -> str:
        return (tmp_path / "elsewhere" / "x").as_uri()


@pytest.mark.parametrize(
    "uri", ["gs://bucket/x", "https://host/x", "file://otherhost/tmp/x", "relative/x"]
)
def test_only_local_file_uris(tmp_path: Path, uri: str) -> None:
    with pytest.raises(InputError) as caught:
        LocalBlobStore(roots=[tmp_path]).read(uri)
    assert caught.value.code == "uri_not_allowed"


def test_dot_dot_cannot_escape_a_root(tmp_path: Path) -> None:
    store = LocalBlobStore(roots=[tmp_path / "root"])
    escape = (tmp_path / "root").as_uri() + "/../secret"
    with pytest.raises(InputError):
        store.read(escape)


def test_a_file_placed_by_hand_is_generation_one(tmp_path: Path) -> None:
    (tmp_path / "in.bin").write_bytes(b"x")
    store = LocalBlobStore(roots=[tmp_path])
    blob = store.read((tmp_path / "in.bin").as_uri())
    assert blob is not None
    assert blob.generation == 1


def test_content_type_is_kept(tmp_path: Path) -> None:
    store = LocalBlobStore(roots=[tmp_path])
    store.write((tmp_path / "a.wav").as_uri(), b"x", content_type="audio/wav")
    meta = (tmp_path / ".a.wav.meta.json").read_text(encoding="utf-8")
    assert '"content_type": "audio/wav"' in meta


def test_storage_errors_are_retryable(tmp_path: Path) -> None:
    (tmp_path / "file").write_bytes(b"")
    store = LocalBlobStore(roots=[tmp_path])
    below_a_file = (tmp_path / "file" / "x").as_uri()
    with pytest.raises(RetryableError):
        store.write(below_a_file, b"", content_type="text/plain")
    assert store.read(below_a_file) is None


def test_reads_never_write(tmp_path: Path) -> None:
    store = LocalBlobStore(roots=[tmp_path])
    for n in range(3):
        assert store.read((tmp_path / f"job-{n}" / "status.json").as_uri()) is None
    assert list(tmp_path.iterdir()) == []


def test_excluded_paths_inside_a_root(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "x").write_bytes(b"x")
    (tmp_path / "in.mp4").write_bytes(b"x")
    store = LocalBlobStore(roots=[tmp_path], excluded=[tmp_path / "state"])
    assert store.read((tmp_path / "in.mp4").as_uri()) is not None
    with pytest.raises(InputError) as caught:
        store.read((tmp_path / "state" / "x").as_uri())
    assert caught.value.code == "uri_not_allowed"


def test_concurrent_claims_have_one_winner(tmp_path: Path) -> None:
    store = LocalBlobStore(roots=[tmp_path])
    uri = (tmp_path / "status.json").as_uri()
    wins: list[int] = []
    conflicts: list[int] = []

    def claim(n: int) -> None:
        try:
            store.write(uri, str(n).encode(), content_type="x", if_generation=0)
            wins.append(n)
        except WriteConflictError:
            conflicts.append(n)

    threads = [threading.Thread(target=claim, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(wins) == 1
    assert len(conflicts) == 7
