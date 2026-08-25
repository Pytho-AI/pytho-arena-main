"""Adapters that exercise live contracts using deterministic replay evidence."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .messages import TrackUpdate


class ReplayTrackAdapter:
    """Translate analyst replay frames into the same messages future feeds use."""

    def __init__(self, frames: Iterable[dict], *, source: str = "arena-replay") -> None:
        self.frames = frames
        self.source = source

    def __iter__(self) -> Iterator[TrackUpdate]:
        sequence = 0
        for frame in self.frames:
            for entity in frame.get("truth", []):
                yield TrackUpdate(
                    source=self.source,
                    sequence=sequence,
                    simulation_time=float(frame.get("time", 0.0)),
                    track_id=entity["id"],
                    position=tuple(entity["position"]),
                    velocity=tuple(entity["velocity"]),
                    confidence=1.0,
                    faction_hint=entity.get("factionId"),
                    classification="analyst-truth",
                    attributes={"active": entity.get("active", True)},
                )
                sequence += 1
