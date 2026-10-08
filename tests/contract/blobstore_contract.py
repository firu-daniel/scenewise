"""The ``BlobStore`` contract (ports.BlobStore docstring), shared by every store."""

import pytest

from scenewise.domain.errors import InputError
from scenewise.ports import BlobStore, WriteConflictError


class BlobStoreContract:
    """Subclass and provide the ``store``, ``base`` and ``outside`` fixtures."""

    def test_round_trip(self, store: BlobStore, base: str) -> None:
        generation = store.write(
            f"{base}/a.json", b"{}", content_type="application/json"
        )
        blob = store.read(f"{base}/a.json")
        assert blob is not None
        assert (blob.data, blob.generation) == (b"{}", generation)
        assert generation > 0

    def test_absent_is_none(self, store: BlobStore, base: str) -> None:
        assert store.read(f"{base}/missing") is None

    def test_create_if_absent(self, store: BlobStore, base: str) -> None:
        uri = f"{base}/status.json"
        store.write(uri, b"1", content_type="application/json", if_generation=0)
        with pytest.raises(WriteConflictError):
            store.write(uri, b"2", content_type="application/json", if_generation=0)

    def test_stale_generation_is_fenced(self, store: BlobStore, base: str) -> None:
        uri = f"{base}/status.json"
        g = store.write(uri, b"claim", content_type="application/json")
        newer = store.write(
            uri, b"winner", content_type="application/json", if_generation=g
        )
        assert newer > g
        with pytest.raises(WriteConflictError):
            store.write(
                uri, b"zombie", content_type="application/json", if_generation=g
            )
        blob = store.read(uri)
        assert blob is not None
        assert blob.data == b"winner"

    def test_unconditional_write_overwrites(self, store: BlobStore, base: str) -> None:
        uri = f"{base}/a1/result.json"
        store.write(uri, b"1", content_type="application/json")
        store.write(uri, b"2", content_type="application/json")
        blob = store.read(uri)
        assert blob is not None
        assert blob.data == b"2"

    def test_materialise(self, store: BlobStore, base: str) -> None:
        store.write(f"{base}/clip.mp4", b"media", content_type="video/mp4")
        with store.materialise(f"{base}/clip.mp4") as path:
            assert path.read_bytes() == b"media"

    def test_materialise_missing(self, store: BlobStore, base: str) -> None:
        with pytest.raises(InputError) as caught, store.materialise(f"{base}/nope"):
            pass
        assert caught.value.code == "input_unavailable"

    def test_outside_the_allow_list(self, store: BlobStore, outside: str) -> None:
        for call in (
            lambda: store.read(outside),
            lambda: store.write(outside, b"", content_type="text/plain"),
        ):
            with pytest.raises(InputError) as caught:
                call()
            assert caught.value.code == "uri_not_allowed"
