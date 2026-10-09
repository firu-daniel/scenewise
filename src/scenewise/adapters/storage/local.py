"""``LocalBlobStore``: ``file://`` objects with single-host compare-and-swap (D14).

Each object ``name`` has a sidecar ``.name.meta.json`` holding its generation and
content type. Reads and writes of one object hold an exclusive ``flock`` on
``.name.lock``, so concurrent writers on one host (threads or processes) serialise;
the data file is replaced atomically. Network file systems are not supported.
"""

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit
from urllib.request import url2pathname

from scenewise.domain.errors import InputError, RetryableError
from scenewise.ports import ABSENT_GENERATION, Blob, WriteConflictError

_HAND_PLACED_GENERATION: Final = 1  # a file placed by hand, with no sidecar


class LocalBlobStore:
    """Objects under a fixed set of root directories, addressed by ``file://`` URI."""

    def __init__(self, *, roots: Sequence[Path], excluded: Sequence[Path] = ()) -> None:
        """Allow access only below ``roots`` and never below ``excluded``.

        ``excluded`` keeps an input store out of the state and artifact directories
        even when an input root contains them.
        """
        self._roots = tuple(root.resolve() for root in roots)
        self._excluded = tuple(path.resolve() for path in excluded)

    def _path(self, uri: str) -> Path:
        parts = urlsplit(uri)
        if parts.scheme != "file" or parts.netloc not in {"", "localhost"}:
            raise InputError(
                code="uri_not_allowed", detail="only file:// URIs are local"
            )
        path = Path(url2pathname(parts.path)).resolve()
        allowed = any(path.is_relative_to(root) for root in self._roots)
        if not allowed or any(path.is_relative_to(x) for x in self._excluded):
            raise InputError(code="uri_not_allowed", detail="path is not allowed")
        return path

    @staticmethod
    def _meta(path: Path) -> Path:
        return path.with_name(f".{path.name}.meta.json")

    @contextmanager
    def _locked(self, path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_name(f".{path.name}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _generation(self, path: Path) -> int:
        if not path.exists():
            return ABSENT_GENERATION
        meta = self._meta(path)
        if not meta.exists():
            return _HAND_PLACED_GENERATION
        return int(json.loads(meta.read_text(encoding="utf-8"))["generation"])

    @contextmanager
    def materialise(self, uri: str) -> Iterator[Path]:
        """Yield the file itself; it is already local."""
        path = self._path(uri)
        if not path.is_file():
            raise InputError(code="input_unavailable", detail="no such file")
        yield path

    def read(self, uri: str) -> Blob | None:
        """Return the object and its generation, or ``None``."""
        path = self._path(uri)
        if not path.is_file():
            return None  # reads never create directories or lock files
        try:
            with self._locked(path):
                if not path.is_file():
                    return None
                return Blob(data=path.read_bytes(), generation=self._generation(path))
        except OSError as e:
            raise RetryableError(
                code="storage_unavailable", detail=type(e).__name__
            ) from e

    def write(
        self,
        uri: str,
        data: bytes,
        *,
        content_type: str,
        if_generation: int | None = None,
    ) -> int:
        """Replace the object atomically under the optional precondition."""
        path = self._path(uri)
        try:
            with self._locked(path):
                current = self._generation(path)
                if if_generation is not None and if_generation != current:
                    raise WriteConflictError(uri)
                generation = current + 1
                meta = {"generation": generation, "content_type": content_type}
                # Generation first: a crash in between leaves a stale token unusable.
                _replace(self._meta(path), json.dumps(meta).encode())
                _replace(path, data)
                return generation
        except OSError as e:
            raise RetryableError(
                code="storage_unavailable", detail=type(e).__name__
            ) from e


def _replace(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
