"""Tensorized scripted baselines, one Policy object per binding.

Scripted policies emit normalized commands — unit-ball direction vectors for
movement, desired headings for sensing — and the engine's actuator stage
applies declared capabilities (speed, slew rate). Each policy uses global
entity or sensor indices for phase terms, so a scripted rollout through
``step(actions)`` is bit-for-bit identical to the pre-inversion engine
(guarded by the golden fixture test).
"""

from __future__ import annotations

import math

import torch


def _unit(vector: torch.Tensor) -> torch.Tensor:
    return vector / torch.linalg.vector_norm(vector, dim=-1, keepdim=True).clamp_min(1e-6)


class ScriptedMovementPolicy:
    """Scripted movement for one binding: transit, direct, probe, or coordinated."""

    def __init__(
        self,
        binding_id: str,
        faction_id: str,
        policy_id: str,
        *,
        own_slots: torch.Tensor,
        entity_phase: torch.Tensor,
        targets: torch.Tensor,
        transit_directions: torch.Tensor,
    ) -> None:
        self.binding_id = binding_id
        self.faction_id = faction_id
        self.policy_id = policy_id
        self.own_slots = own_slots
        self.entity_phase = entity_phase
        self.targets = targets
        self.transit_directions = transit_directions

    def act(self, observation: dict[str, torch.Tensor], step: int) -> torch.Tensor:
        if self.policy_id == "transit":
            return self.transit_directions
        positions = observation["own_positions"][:, self.own_slots, :]
        direct = _unit(self.targets - positions)
        if self.policy_id == "direct":
            return direct
        if self.policy_id == "probe":
            perpendicular = torch.zeros_like(direct)
            perpendicular[..., 0] = -direct[..., 1]
            perpendicular[..., 1] = direct[..., 0]
            weave = torch.sin(step * 0.16 + self.entity_phase * 0.71)
            return _unit(direct * 0.82 + perpendicular * weave * 0.58)
        phase = step * 0.055
        offset = torch.tensor(
            [math.cos(phase) * 5.0, math.sin(phase) * 5.0],
            dtype=positions.dtype,
            device=positions.device,
        )
        return _unit(self.targets + offset - positions)


class ScriptedSensingPolicy:
    """Scripted sensing for one binding: sweep, track, or coverage."""

    def __init__(
        self,
        binding_id: str,
        faction_id: str,
        policy_id: str,
        *,
        initial_headings: torch.Tensor,
        sensor_positions: torch.Tensor,
        coverage_spread: torch.Tensor,
    ) -> None:
        self.binding_id = binding_id
        self.faction_id = faction_id
        self.policy_id = policy_id
        self.initial_headings = initial_headings
        self.sensor_positions = sensor_positions
        self.coverage_spread = coverage_spread

    def act(self, observation: dict[str, torch.Tensor], step: int) -> torch.Tensor:
        sweep = self.initial_headings + step * math.radians(7.0)
        if self.policy_id == "sweep":
            return sweep
        if self.policy_id == "coverage":
            return self.initial_headings + self.coverage_spread
        centroid = observation["last_detection_centroid"]
        has_detection = observation["has_last_detection"]
        relative = centroid[:, None, :] - self.sensor_positions
        tracked = torch.atan2(relative[..., 1], relative[..., 0])
        return torch.where(has_detection[:, None], tracked, sweep)
