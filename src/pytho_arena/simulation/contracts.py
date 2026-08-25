"""Stable hashes describing the policy/simulation boundary."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict

from ..scenario.models import ScenarioSpec
from .physics import physics_backend

OBSERVATION_SCHEMA_VERSION = "faction-belief-v1"
ACTION_SCHEMA_VERSION = "normalized-command-v2"


class EnvironmentContract(BaseModel):
    """Identity of the interfaces a policy was trained against."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_hash: str
    physics_backend: str
    spatial_dimensions: int
    observation_schema: str
    action_schema: str
    binding_actions: dict[str, dict[str, int | str]]

    def content_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"scenario_hash"})
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


def environment_contract(
    scenario: ScenarioSpec, *, scenario_hash: str | None = None
) -> EnvironmentContract:
    dimensions = physics_backend(scenario.simulation.physics_backend).spatial_dimensions
    groups = {group.id: group for group in scenario.actor_groups}
    bindings: dict[str, dict[str, int | str]] = {}
    for binding in scenario.policy_bindings:
        resource_count = (
            sum(groups[group_id].count for group_id in binding.actor_group_ids)
            if binding.role == "movement"
            else len(binding.sensor_ids)
        )
        bindings[binding.id] = {
            "role": binding.role,
            "resources": resource_count,
            "dimensions": dimensions if binding.role == "movement" else 1,
        }
    return EnvironmentContract(
        scenario_hash=scenario_hash or scenario.content_hash(),
        physics_backend=scenario.simulation.physics_backend,
        spatial_dimensions=dimensions,
        observation_schema=OBSERVATION_SCHEMA_VERSION,
        action_schema=ACTION_SCHEMA_VERSION,
        binding_actions=bindings,
    )
