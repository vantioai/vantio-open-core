"""One sliding window per process. Memory stays at max_queries timestamps."""

from __future__ import annotations

import threading
import time


class VolumeGate:
    def __init__(self, max_queries: int, window_seconds: int, workload_id: str) -> None:
        if not isinstance(workload_id, str) or not workload_id or len(workload_id) > 64:
            raise ValueError("workload id")
        if any(ord(ch) > 127 for ch in workload_id):
            raise ValueError("workload id")
        self.max_queries = max_queries
        self.window_ns = window_seconds * 1_000_000_000
        self.workload_id = workload_id
        self._times: list[int] = []
        self._lock = threading.Lock()
        self._broken = False

    def hit(self, workload_id: object, now_ns: int | None = None) -> str:
        """Return ok, over, or failure. failure does not record the attempt."""
        try:
            stamp = time.monotonic_ns() if now_ns is None else now_ns
            if isinstance(stamp, bool) or not isinstance(stamp, int):
                raise TypeError("clock")
        except (TypeError, OSError, OverflowError):
            self._mark_broken()
            return "failure"
        with self._lock:
            if self._broken:
                return "failure"
            if workload_id != self.workload_id:
                return "failure"
            try:
                cutoff = stamp - self.window_ns
                self._times = [item for item in self._times if item > cutoff]
                if len(self._times) >= self.max_queries:
                    self._times.pop(0)
                    self._times.append(stamp)
                    return "over"
                self._times.append(stamp)
                return "ok"
            except (TypeError, OverflowError, IndexError):
                self._broken = True
                self._times.clear()
                return "failure"

    def _mark_broken(self) -> None:
        with self._lock:
            self._broken = True
            self._times.clear()

    def stored(self) -> int:
        with self._lock:
            return len(self._times)
