"""Bounded, thread-safe shadow-mode buffer for canonical track updates."""

from __future__ import annotations

import threading
from collections import deque

from .messages import TrackUpdate


class LiveDataBuffer:
    def __init__(self, capacity: int = 10_000) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._items: deque[TrackUpdate] = deque(maxlen=capacity)
        self._latest: dict[str, TrackUpdate] = {}
        self._lock = threading.Lock()

    def ingest(self, updates: list[TrackUpdate]) -> int:
        accepted = 0
        with self._lock:
            for update in updates:
                previous = self._latest.get(update.track_id)
                if (
                    previous is not None
                    and update.sequence is not None
                    and previous.sequence is not None
                    and update.sequence <= previous.sequence
                ):
                    continue
                self._items.append(update)
                self._latest[update.track_id] = update
                accepted += 1
            return accepted

    def latest(self) -> list[TrackUpdate]:
        with self._lock:
            return sorted(self._latest.values(), key=lambda item: item.track_id)

    def history(self, limit: int = 1_000) -> list[TrackUpdate]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._lock:
            return list(self._items)[-limit:]
