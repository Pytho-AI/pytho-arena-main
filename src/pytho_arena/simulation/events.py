"""Canonical events used by replay, objectives, experiments, and live adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventKind(StrEnum):
    DETECTION = "detection"
    TRACK_FUSION = "track_fusion"
    TRACK_DROP = "track_drop"
    ROE_REQUEST = "roe_request"
    ROE_DECISION = "roe_decision"
    EFFECTOR_USE = "effector_use"
    EFFECT_OUTCOME = "effect_outcome"
    INTERCEPT = "intercept"
    ATTACK = "attack"
    TRANSIT_COMPLETION = "transit_completion"


class SimulationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: EventKind
    step: int = Field(ge=0)
    time_seconds: float = Field(ge=0.0)
    source_faction_id: str | None = None
    source_id: str | None = None
    target_faction_id: str | None = None
    target_id: str | None = None
    position: tuple[float, ...] | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
