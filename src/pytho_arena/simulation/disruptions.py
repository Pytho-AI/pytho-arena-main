"""Run-level ability degradation contracts: sense, share, and act.

Disruptions are counterfactual experiment knobs, not scenario truth: they
live on the run (and training job), never in the scenario hash. Each kind
degrades one stage of the engagement chain:

- ``sensor`` degrades the ability to *see* — it modulates detection
  probability, range, and measurement noise, so analyst truth itself
  records less.
- ``communications`` degrades the ability to *share* — sensor truth is
  intact but reports are dropped before they reach the faction's fused
  picture (``delivered_detections``).
- ``effector`` degrades the ability to *act* — response effectiveness and
  launch reliability, leaving pictures untouched.

``faction_ids: None`` targets the defending network: the scenario's
evaluation faction, else every faction that declares an opponent or
protected relationship (the same fallback aggregate metrics use).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class _DisruptionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faction_ids: list[str] | None = Field(
        default=None,
        description=("Factions whose assets are degraded; omit to target the defending network."),
    )


class CommunicationsDisruption(_DisruptionBase):
    """Drop sensor reports on the network hop; truth stays recorded."""

    kind: Literal["communications"] = "communications"
    drop_probability: float = Field(ge=0.0, le=1.0)


class SensorDisruption(_DisruptionBase):
    """Degrade what sensors physically see; analyst truth itself dims."""

    kind: Literal["sensor"] = "sensor"
    detection_probability_multiplier: float = Field(default=1.0, ge=0.0, le=1.0)
    range_multiplier: float = Field(default=1.0, ge=0.0, le=1.0)
    noise_multiplier: float = Field(default=1.0, ge=1.0, le=16.0)


class EffectorDisruption(_DisruptionBase):
    """Degrade response outcomes: effectiveness and launch reliability."""

    kind: Literal["effector"] = "effector"
    effectiveness_multiplier: float = Field(default=1.0, ge=0.0, le=1.0)
    reliability: float = Field(default=1.0, ge=0.0, le=1.0)


DisruptionSpec = Annotated[
    CommunicationsDisruption | SensorDisruption | EffectorDisruption,
    Field(discriminator="kind"),
]

_DISRUPTION_LIST = TypeAdapter(list[DisruptionSpec])


def validate_disruptions(disruptions: Iterable[object] | None) -> list[DisruptionSpec]:
    """Normalize models or raw dicts into validated disruption specs."""
    return _DISRUPTION_LIST.validate_python(list(disruptions or []))
