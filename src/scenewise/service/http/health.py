"""The liveness watchdog: ``/healthz`` fails when a job outlives budget + grace.

The Cloud Run liveness probe then replaces the instance before the job's lease
expires (ARCHITECTURE.md §8). The registry lives on the app instance, not the module.
"""

import itertools
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager


class Watchdog:
    """Tracks when each admitted job started."""

    def __init__(self, *, limit_s: float) -> None:
        """Report a job as hung once it has run for ``limit_s`` seconds."""
        self._limit_s = limit_s
        self._lock = threading.Lock()
        self._keys = itertools.count()
        self._started: dict[int, tuple[str, float]] = {}

    @contextmanager
    def watch(self, job_id: str) -> Iterator[None]:
        """Register the job for the duration of the block."""
        with self._lock:
            key = next(self._keys)
            self._started[key] = (job_id, time.monotonic())
        try:
            yield
        finally:
            with self._lock:
                del self._started[key]

    def overdue(self, now: float) -> list[str]:
        """Ids of the jobs that have run longer than the limit at ``now``."""
        with self._lock:
            entries = list(self._started.values())
        return sorted(job for job, started in entries if now - started > self._limit_s)
