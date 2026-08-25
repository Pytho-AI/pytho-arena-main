"""Transport-neutral messages at the simulation/live-data boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=120)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    simulation_time: float | None = Field(default=None, ge=0.0)
    sequence: int | None = Field(default=None, ge=0)


class TrackUpdate(MessageBase):
    kind: Literal["track"] = "track"
    track_id: str = Field(min_length=1, max_length=120)
    position: tuple[float, ...] = Field(min_length=2, max_length=3)
    velocity: tuple[float, ...] | None = Field(default=None, min_length=2, max_length=3)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    covariance: list[list[float]] | None = None
    classification: str | None = Field(default=None, max_length=120)
    faction_hint: str | None = Field(default=None, max_length=64)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TrackBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updates: list[TrackUpdate] = Field(min_length=1, max_length=10_000)


class SensorMeasurement(MessageBase):
    kind: Literal["measurement"] = "measurement"
    sensor_id: str = Field(min_length=1, max_length=120)
    measurement_id: str = Field(min_length=1, max_length=120)
    values: tuple[float, ...]
    covariance: list[list[float]] | None = None
    track_id: str | None = None


class CommandEnvelope(MessageBase):
    kind: Literal["command"] = "command"
    binding_id: str = Field(min_length=1, max_length=120)
    command: list[list[float]] | list[float]
    mode: Literal["simulation", "shadow"] = "shadow"


class ClockUpdate(MessageBase):
    kind: Literal["clock"] = "clock"
    state: Literal["running", "paused", "stopped"] = "running"
    rate: float = Field(default=1.0, gt=0.0, le=1_000.0)
