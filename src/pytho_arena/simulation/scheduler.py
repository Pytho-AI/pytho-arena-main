"""Deterministic multi-rate scheduling relative to the policy decision clock."""

from __future__ import annotations

from dataclasses import dataclass

from ..scenario.models import ScenarioSpec


@dataclass(frozen=True)
class MultiRateScheduler:
    decision_interval: float
    physics_interval: float
    sensor_every: int
    effects_every: int

    @classmethod
    def from_scenario(cls, scenario: ScenarioSpec) -> MultiRateScheduler:
        spec = scenario.simulation
        return cls(
            decision_interval=scenario.step_seconds,
            physics_interval=spec.physics_step_seconds or scenario.step_seconds,
            sensor_every=round(
                (spec.sensor_interval_seconds or scenario.step_seconds) / scenario.step_seconds
            ),
            effects_every=round(
                (spec.effects_interval_seconds or scenario.step_seconds) / scenario.step_seconds
            ),
        )

    @property
    def physics_substeps(self) -> int:
        return round(self.decision_interval / self.physics_interval)

    def sensing_due(self, step_index: int) -> bool:
        return step_index % self.sensor_every == 0

    def effects_due(self, step_index: int) -> bool:
        return step_index % self.effects_every == 0
